"""Strato 1: scarica i dati grezzi di StatsBomb e li salva senza toccarli.

Qui non avviene nessuna trasformazione. Il JSON che StatsBomb pubblica finisce
su disco byte per byte, nella stessa struttura di cartelle del repository di
origine, cosi' un file scaricato e' confrontabile con l'originale.

**Perche' HTTP diretto e non `statsbombpy`.** La libreria restituisce DataFrame
gia' appiattiti, mentre i freeze frame dei dati 360 sono profondamente
annidati: contengono la posizione di ogni giocatore in campo al momento
dell'evento. Appiattirli qui per poi ricostruirli in M5 significa perdere
informazione e scrivere due volte lo stesso codice. Lo strato 1 salva il
grezzo; chi vuole i DataFrame se li costruisce nello strato 2.

**Come funziona la ripartenza.** Due meccanismi, e il secondo e' quello che
conta. Il primo: se il file esiste gia', si salta. Il secondo: ogni file viene
scritto in un temporaneo e poi rinominato, operazione atomica sia su Windows
sia su Unix. Se il processo muore a meta' scaricamento non resta un file
troncato che la volta dopo verrebbe scambiato per completo — resta un
temporaneo che nessuno guarda. Senza la scrittura atomica, «il file esiste»
sarebbe un'affermazione inaffidabile.
"""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, NamedTuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from football_analytics.config import DATA_RAW, MANIFEST_PATH, Competizione

if TYPE_CHECKING:
    from collections.abc import Iterable

#: Radice dell'Open Data di StatsBomb.
BASE_URL: Final[str] = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"

#: Secondi oltre i quali una singola richiesta viene considerata persa.
TIMEOUT: Final[float] = 30.0

#: Quante richieste in parallelo. Otto e' educato verso raw.githubusercontent
#: e riduce lo scaricamento completo da ore a decine di minuti.
LAVORATORI: Final[int] = 8

#: Valore di ``match_status_360`` che indica freeze frame disponibili.
STATO_360_DISPONIBILE: Final[str] = "available"

#: Le cartelle di risorse legate alle partite, nell'ordine di scaricamento.
CARTELLE: Final[tuple[str, ...]] = ("events", "lineups", "three-sixty")

_blocco = threading.Lock()


class Stato(StrEnum):
    """Come si e' conclusa la richiesta di una singola risorsa.

    Attributes:
        SCARICATA: Non c'era e ora c'e'.
        SALTATA: C'era gia'. E' il caso normale dalla seconda esecuzione.
        ASSENTE: StatsBomb non la pubblica (404). Non e' un errore.
    """

    SCARICATA = "scaricata"
    SALTATA = "saltata"
    ASSENTE = "assente"


class Partita(NamedTuple):
    """Il minimo che serve sapere di una partita per scaricarla.

    Attributes:
        match_id: Identificativo StatsBomb della partita.
        ha_360: Se il file delle partite dichiara i freeze frame disponibili.
    """

    match_id: int
    ha_360: bool


@dataclass(slots=True)
class Esito:
    """Il riepilogo di una sessione di scaricamento.

    Attributes:
        scaricate: Risorse effettivamente prelevate dalla rete.
        saltate: Risorse gia' presenti su disco.
        assenti: Risorse che StatsBomb non pubblica.
    """

    scaricate: int = 0
    saltate: int = 0
    assenti: int = 0

    def registra(self, stato: Stato) -> None:
        """Incrementa il contatore corrispondente a uno stato.

        Args:
            stato: L'esito della singola risorsa.
        """
        if stato is Stato.SCARICATA:
            self.scaricate += 1
        elif stato is Stato.SALTATA:
            self.saltate += 1
        else:
            self.assenti += 1

    @property
    def totale(self) -> int:
        """Quante risorse sono state considerate in tutto.

        Returns:
            La somma dei tre contatori.
        """
        return self.scaricate + self.saltate + self.assenti


# ---------------------------------------------------------------------------
# Percorsi e indirizzi
# ---------------------------------------------------------------------------


def percorso_competizioni() -> Path:
    """Percorso locale dell'indice delle competizioni.

    Returns:
        Il percorso di ``data/raw/competitions.json``.
    """
    return DATA_RAW / "competitions.json"


def percorso_partite(competition_id: int, season_id: int) -> Path:
    """Percorso locale dell'elenco partite di una competizione-stagione.

    Args:
        competition_id: Identificativo della competizione.
        season_id: Identificativo della stagione.

    Returns:
        Il percorso del file JSON corrispondente.
    """
    return DATA_RAW / "matches" / str(competition_id) / f"{season_id}.json"


def percorso_risorsa(cartella: str, match_id: int) -> Path:
    """Percorso locale di una risorsa legata a una partita.

    Args:
        cartella: ``events``, ``lineups`` o ``three-sixty``.
        match_id: Identificativo della partita.

    Returns:
        Il percorso del file JSON corrispondente.
    """
    return DATA_RAW / cartella / f"{match_id}.json"


def indirizzo(percorso_relativo: str) -> str:
    """Costruisce l'indirizzo remoto di una risorsa dell'Open Data.

    Args:
        percorso_relativo: Percorso dentro ``data/``, per esempio
            ``"events/3795506.json"``.

    Returns:
        L'indirizzo completo su raw.githubusercontent.com.
    """
    return f"{BASE_URL}/{percorso_relativo}"


# ---------------------------------------------------------------------------
# Rete
# ---------------------------------------------------------------------------


def crea_sessione(tentativi: int = 3) -> requests.Session:
    """Prepara una sessione HTTP con nuovi tentativi automatici.

    Su migliaia di richieste, qualche errore temporaneo e' certo. Senza
    tentativi automatici basterebbe un singolo 503 per interrompere uno
    scaricamento da mezz'ora.

    Args:
        tentativi: Quante volte riprovare prima di arrendersi.

    Returns:
        La sessione, gia' configurata per HTTPS.
    """
    sessione = requests.Session()
    politica = Retry(
        total=tentativi,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    sessione.mount("https://", HTTPAdapter(max_retries=politica, pool_maxsize=LAVORATORI * 2))
    return sessione


def preleva(sessione: requests.Session, url: str) -> bytes | None:
    """Scarica una risorsa.

    Args:
        sessione: La sessione HTTP da usare.
        url: L'indirizzo della risorsa.

    Returns:
        Il contenuto grezzo, oppure ``None`` se StatsBomb non pubblica quella
        risorsa. Un 404 qui non e' un errore: i file ``three-sixty`` esistono
        solo per le partite che hanno i freeze frame.

    Raises:
        requests.HTTPError: Per qualsiasi altro codice di errore, cosi' un
            problema vero non passa inosservato.
    """
    risposta = sessione.get(url, timeout=TIMEOUT)
    if risposta.status_code == requests.codes.not_found:
        return None
    risposta.raise_for_status()
    return risposta.content


def salva_atomico(dati: bytes, destinazione: Path) -> None:
    """Scrive un file in modo che non possa mai esistere a meta'.

    Args:
        dati: Il contenuto da scrivere.
        destinazione: Il percorso finale.
    """
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    temporaneo = destinazione.with_suffix(destinazione.suffix + ".parziale")
    temporaneo.write_bytes(dati)
    temporaneo.replace(destinazione)


def assicura(sessione: requests.Session, url: str, destinazione: Path) -> Stato:
    """Garantisce che una risorsa sia su disco, scaricandola se manca.

    Args:
        sessione: La sessione HTTP da usare.
        url: L'indirizzo remoto.
        destinazione: Dove salvare.

    Returns:
        Lo stato della risorsa dopo la chiamata.
    """
    if destinazione.exists():
        return Stato.SALTATA
    dati = preleva(sessione, url)
    if dati is None:
        return Stato.ASSENTE
    salva_atomico(dati, destinazione)
    return Stato.SCARICATA


# ---------------------------------------------------------------------------
# Ingestione
# ---------------------------------------------------------------------------


def leggi_json(percorso: Path) -> Any:
    """Legge un file JSON gia' scaricato.

    Args:
        percorso: Il file da leggere.

    Returns:
        La struttura contenuta nel file.
    """
    return json.loads(percorso.read_bytes())


def stagioni_di(sessione: requests.Session, comp: Competizione) -> list[int]:
    """Elenca le stagioni da scaricare per una competizione.

    Args:
        sessione: La sessione HTTP da usare.
        comp: La competizione.

    Returns:
        La singola stagione dichiarata, oppure tutte quelle che l'Open Data
        pubblica per quella competizione quando ``season_id`` e' ``None``.
    """
    if comp.season_id is not None:
        return [comp.season_id]

    assicura(sessione, indirizzo("competitions.json"), percorso_competizioni())
    elenco = leggi_json(percorso_competizioni())
    return sorted(
        {int(v["season_id"]) for v in elenco if int(v["competition_id"]) == comp.competition_id}
    )


def elenca_partite(sessione: requests.Session, comp: Competizione) -> list[Partita]:
    """Scarica gli elenchi partite di una competizione e li legge.

    Args:
        sessione: La sessione HTTP da usare.
        comp: La competizione.

    Returns:
        Tutte le sue partite, con l'indicazione dei freeze frame disponibili.
    """
    partite: list[Partita] = []
    for stagione in stagioni_di(sessione, comp):
        destinazione = percorso_partite(comp.competition_id, stagione)
        assicura(
            sessione,
            indirizzo(f"matches/{comp.competition_id}/{stagione}.json"),
            destinazione,
        )
        for voce in leggi_json(destinazione):
            stato_360 = voce.get("match_status_360")
            partite.append(
                Partita(
                    match_id=int(voce["match_id"]),
                    ha_360=stato_360 == STATO_360_DISPONIBILE,
                )
            )
    return partite


def risorse_di(partite: Iterable[Partita]) -> list[tuple[str, Path]]:
    """Costruisce l'elenco di tutto cio' che va scaricato per delle partite.

    I freeze frame vengono chiesti **solo** dove il file delle partite li
    dichiara disponibili. Chiederli ovunque significherebbe migliaia di 404 a
    ogni esecuzione, e la seconda esecuzione non finirebbe piu' in pochi
    secondi come richiede il criterio di M2-T2.

    Args:
        partite: Le partite da coprire.

    Returns:
        Coppie indirizzo-destinazione, pronte per lo scaricamento.
    """
    elenco: list[tuple[str, Path]] = []
    for partita in partite:
        for cartella in ("events", "lineups"):
            elenco.append(
                (
                    indirizzo(f"{cartella}/{partita.match_id}.json"),
                    percorso_risorsa(cartella, partita.match_id),
                )
            )
        if partita.ha_360:
            elenco.append(
                (
                    indirizzo(f"three-sixty/{partita.match_id}.json"),
                    percorso_risorsa("three-sixty", partita.match_id),
                )
            )
    return elenco


def scarica_molte(
    sessione: requests.Session,
    risorse: list[tuple[str, Path]],
    lavoratori: int = LAVORATORI,
    silenzioso: bool = False,
) -> Esito:
    """Scarica in parallelo un elenco di risorse.

    Args:
        sessione: La sessione HTTP da usare.
        risorse: Coppie indirizzo-destinazione.
        lavoratori: Quante richieste tenere in volo contemporaneamente.
        silenzioso: Se vero, non stampa l'avanzamento.

    Returns:
        Il riepilogo dei tre esiti possibili.
    """
    esito = Esito()
    totale = len(risorse)
    if totale == 0:
        return esito

    with ThreadPoolExecutor(max_workers=lavoratori) as pozzo:
        futuri = {pozzo.submit(assicura, sessione, url, dest): url for url, dest in risorse}
        for fatto in as_completed(futuri):
            stato = fatto.result()
            with _blocco:
                esito.registra(stato)
                fatte = esito.totale
            if not silenzioso and (fatte % 50 == 0 or fatte == totale):
                print(
                    f"  {fatte:>5}/{totale}  nuove {esito.scaricate}, gia' presenti {esito.saltate}"
                )
    return esito


def ingerisci(
    comp: Competizione,
    lavoratori: int = LAVORATORI,
    silenzioso: bool = False,
) -> Esito:
    """Porta su disco tutti i dati grezzi di una competizione.

    Rilanciarla su una competizione gia' scaricata non produce nessuna
    richiesta di contenuto: e' il criterio di completamento di M2-T2.

    Args:
        comp: La competizione da scaricare.
        lavoratori: Quante richieste in parallelo.
        silenzioso: Se vero, non stampa l'avanzamento.

    Returns:
        Il riepilogo dello scaricamento.
    """
    sessione = crea_sessione()
    try:
        partite = elenca_partite(sessione, comp)
        if not silenzioso:
            con_360 = sum(1 for p in partite if p.ha_360)
            print(f"{comp.etichetta}: {len(partite)} partite, {con_360} con dati 360")
        esito = scarica_molte(sessione, risorse_di(partite), lavoratori, silenzioso)
    finally:
        sessione.close()

    aggiorna_manifest(comp, partite)
    return esito


# ---------------------------------------------------------------------------
# Registro dello scaricamento (M2-T3) e disponibilita' dei 360 (M2-T4)
# ---------------------------------------------------------------------------


def file_presenti(partite: Iterable[Partita]) -> dict[str, int]:
    """Conta quanti file di ogni tipo sono effettivamente su disco.

    Non si fida di quanto e' stato appena scaricato: guarda il disco. Se
    qualcuno cancella una cartella a mano, il registro se ne accorge.

    Args:
        partite: Le partite della competizione.

    Returns:
        Quanti file esistono per ciascuna cartella di risorse.
    """
    conteggi = dict.fromkeys(CARTELLE, 0)
    for partita in partite:
        for cartella in CARTELLE:
            if percorso_risorsa(cartella, partita.match_id).exists():
                conteggi[cartella] += 1
    return conteggi


def peso_byte(partite: Iterable[Partita]) -> int:
    """Somma la dimensione su disco dei file di una competizione.

    Args:
        partite: Le partite della competizione.

    Returns:
        Il peso complessivo in byte.
    """
    totale = 0
    for partita in partite:
        for cartella in CARTELLE:
            percorso = percorso_risorsa(cartella, partita.match_id)
            if percorso.exists():
                totale += percorso.stat().st_size
    return totale


def leggi_manifest() -> dict[str, Any]:
    """Legge il registro dello scaricamento, o ne restituisce uno vuoto.

    Returns:
        Il contenuto del manifest.
    """
    if not MANIFEST_PATH.exists():
        return {"competizioni": {}}
    dati: dict[str, Any] = leggi_json(MANIFEST_PATH)
    return dati


def aggiorna_manifest(comp: Competizione, partite: list[Partita]) -> dict[str, Any]:
    """Aggiorna la voce di una competizione nel registro dello scaricamento.

    Il registro e' scritto **dall'ingestione**, mai a mano: e' il criterio di
    M2-T3. La riga ``partite_con_360`` e' il criterio di M2-T4, ed e' il fatto
    su cui si regge la scelta dei due modelli.

    Args:
        comp: La competizione appena trattata.
        partite: Le sue partite, con lo stato dei freeze frame.

    Returns:
        Il manifest aggiornato.
    """
    manifest = leggi_manifest()
    conteggi = file_presenti(partite)
    manifest["competizioni"][comp.chiave] = {
        "nome": comp.etichetta,
        "gruppo": str(comp.gruppo),
        "competition_id": comp.competition_id,
        "season_id": comp.season_id,
        "partite": len(partite),
        "partite_attese": comp.partite_attese,
        "partite_con_360": sum(1 for p in partite if p.ha_360),
        "file": conteggi,
        "peso_mb": round(peso_byte(partite) / 1024 / 1024, 1),
        "aggiornata": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    voci = manifest["competizioni"].values()
    manifest["totali"] = {
        "competizioni": len(voci),
        "partite": sum(int(v["partite"]) for v in voci),
        "partite_con_360": sum(int(v["partite_con_360"]) for v in voci),
        "peso_mb": round(sum(float(v["peso_mb"]) for v in voci), 1),
    }
    manifest["generato"] = datetime.now(UTC).isoformat(timespec="seconds")

    testo = json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=False)
    salva_atomico(testo.encode("utf-8"), MANIFEST_PATH)
    return manifest


def riepilogo_markdown() -> str:
    """Costruisce la tabella del registro, pronta da incollare nel README.

    Returns:
        Una tabella Markdown con una riga per competizione scaricata.
    """
    manifest = leggi_manifest()
    voci = manifest.get("competizioni", {})
    if not voci:
        return "_Nessuna competizione ancora scaricata._"

    righe = [
        "| Competizione | Gruppo | Partite | Con dati 360 | Peso |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for voce in voci.values():
        righe.append(
            f"| {voce['nome']} | {voce['gruppo']} | {voce['partite']} "
            f"| {voce['partite_con_360']} | {voce['peso_mb']} MB |"
        )
    totali = manifest.get("totali", {})
    righe.append(
        f"| **Totale** | | **{totali.get('partite', 0)}** "
        f"| **{totali.get('partite_con_360', 0)}** | **{totali.get('peso_mb', 0)} MB** |"
    )
    return "\n".join(righe)
