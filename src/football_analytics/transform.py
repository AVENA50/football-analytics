"""Strato 2: dagli eventi grezzi alle tabelle compatte del magazzino.

Qui si decide **cosa non entra**. Una partita contiene circa 3.400 eventi e per
1.753 partite fanno sei milioni di righe: salvarle tutte significherebbe un
Parquet che Streamlit Cloud non riesce a caricare dentro un gigabyte di RAM. Da
ogni tipo di evento si estraggono solo le colonne che una vista usa davvero.

**Sui due tipi di freeze frame.** StatsBomb ne pubblica due, e vanno distinti:

- ``shot.freeze_frame``, dentro l'evento di tiro, contiene posizione, identita'
  e ruolo di ogni giocatore inquadrato al momento del tiro. E' presente nel
  97 % circa dei tiri di **tutte** le competizioni, campionati del 2015/16
  compresi;
- i file ``three-sixty/`` coprono tutti gli eventi della partita e aggiungono
  l'area inquadrata, ma non riportano nomi ne' ruoli, e esistono solo per
  alcune competizioni.

Per il modello xG serve il primo. La colonna si chiama percio' ``ha_fotogramma``
e non ``has_360``: descrive quello che contiene davvero.
"""

from __future__ import annotations

import collections
from typing import TYPE_CHECKING, Any, Final

import pandas as pd

from football_analytics import ingest
from football_analytics.config import Competizione

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

#: Il periodo dei tiri di rigore a fine partita. Non contano per il risultato.
PERIODO_RIGORI: Final[int] = 5

#: Nome dell'esito che identifica un gol.
ESITO_GOL: Final[str] = "Goal"

#: I tipi di evento che assegnano un gol senza essere un tiro.
AUTOGOL_A_FAVORE: Final[str] = "Own Goal For"

#: Tipo di dato di ogni colonna di ``shots.parquet``.
#:
#: Dichiararli qui invece di lasciarli dedurre a pandas non e' pignoleria: un
#: `object` al posto di una `category` su 44.000 righe e' la differenza fra due
#: e venti megabyte, e su Streamlit Cloud quei megabyte sono RAM.
TIPI_TIRI: Final[dict[str, str]] = {
    "shot_id": "string",
    "match_id": "int32",
    "competizione": "category",
    "gruppo": "category",
    "stagione": "category",
    "squadra": "category",
    "avversario": "category",
    "in_casa": "bool",
    "giocatore": "category",
    "giocatore_id": "int32",
    "ruolo": "category",
    "periodo": "int8",
    "minuto": "int16",
    "secondo": "int8",
    "x": "float32",
    "y": "float32",
    "esito": "category",
    "gol": "bool",
    "rigori_finali": "bool",
    "tipo": "category",
    "parte_corpo": "category",
    "tecnica": "category",
    "schema": "category",
    "sotto_pressione": "bool",
    "primo_tocco": "bool",
    "una_contro_uno": "bool",
    "porta_vuota": "bool",
    "deviato": "bool",
    "duello_aereo": "bool",
    "xg_statsbomb": "float32",
    "ha_fotogramma": "bool",
    "giocatori_fotogramma": "int8",
    "avversari_fotogramma": "int8",
    "ha_360": "bool",
}


class QualitaError(Exception):
    """I dati trasformati non superano un controllo di coerenza.

    Interrompe la costruzione del magazzino invece di lasciar passare numeri
    sbagliati: scoprirlo qui costa un'ora, scoprirlo nella dashboard costa la
    credibilita' di tutto il progetto.
    """


def _nome(blocco: Any, chiave: str = "name") -> str:
    """Estrae il nome da un blocco annidato di StatsBomb.

    Args:
        blocco: Il dizionario, che puo' mancare del tutto.
        chiave: La chiave da leggere.

    Returns:
        Il valore, oppure stringa vuota se il blocco non c'e'.
    """
    if isinstance(blocco, dict):
        return str(blocco.get(chiave, ""))
    return ""


def metadati_partite(comp: Competizione) -> dict[int, dict[str, Any]]:
    """Legge i dati di contesto delle partite di una competizione.

    Args:
        comp: La competizione.

    Returns:
        Mappa da ``match_id`` a squadra di casa, ospite, risultato ufficiale e
        disponibilita' dei file 360.
    """
    metadati: dict[int, dict[str, Any]] = {}
    for stagione in _stagioni_su_disco(comp):
        percorso = ingest.percorso_partite(comp.competition_id, stagione)
        if not percorso.exists():
            continue
        for voce in ingest.leggi_json(percorso):
            metadati[int(voce["match_id"])] = {
                "casa": _nome(voce.get("home_team"), "home_team_name"),
                "ospite": _nome(voce.get("away_team"), "away_team_name"),
                "gol_casa": int(voce["home_score"]),
                "gol_ospite": int(voce["away_score"]),
                "ha_360": voce.get("match_status_360") == ingest.STATO_360_DISPONIBILE,
            }
    return metadati


def _stagioni_su_disco(comp: Competizione) -> list[int]:
    """Elenca le stagioni gia' scaricate di una competizione.

    Args:
        comp: La competizione.

    Returns:
        Gli identificativi di stagione presenti in ``data/raw/matches/``.
    """
    if comp.season_id is not None:
        return [comp.season_id]
    cartella = ingest.cartella_partite(comp.competition_id)
    if not cartella.exists():
        return []
    return sorted(int(f.stem) for f in cartella.glob("*.json"))


def riga_tiro(
    evento: dict[str, Any],
    comp: Competizione,
    match_id: int,
    meta: dict[str, Any],
) -> dict[str, Any]:
    """Appiattisce un evento di tiro in una riga di tabella.

    Args:
        evento: L'evento grezzo di StatsBomb.
        comp: La competizione a cui appartiene.
        match_id: La partita.
        meta: I metadati della partita.

    Returns:
        Una riga con tutte le colonne di :data:`TIPI_TIRI`.
    """
    tiro = evento.get("shot", {})
    posizione = evento.get("location") or [float("nan"), float("nan")]
    fotogramma = tiro.get("freeze_frame")
    squadra = _nome(evento.get("team"))
    in_casa = squadra == meta["casa"]

    return {
        "shot_id": str(evento["id"]),
        "match_id": match_id,
        "competizione": comp.chiave,
        "gruppo": str(comp.gruppo),
        "stagione": comp.stagione,
        "squadra": squadra,
        "avversario": meta["ospite"] if in_casa else meta["casa"],
        "in_casa": in_casa,
        "giocatore": _nome(evento.get("player")),
        "giocatore_id": int(_id(evento.get("player"))),
        "ruolo": _nome(evento.get("position")),
        "periodo": int(evento["period"]),
        "minuto": int(evento["minute"]),
        "secondo": int(evento["second"]),
        "x": float(posizione[0]),
        "y": float(posizione[1]),
        "esito": _nome(tiro.get("outcome")),
        "gol": _nome(tiro.get("outcome")) == ESITO_GOL,
        "rigori_finali": int(evento["period"]) == PERIODO_RIGORI,
        "tipo": _nome(tiro.get("type")),
        "parte_corpo": _nome(tiro.get("body_part")),
        "tecnica": _nome(tiro.get("technique")),
        "schema": _nome(evento.get("play_pattern")),
        "sotto_pressione": bool(evento.get("under_pressure", False)),
        "primo_tocco": bool(tiro.get("first_time", False)),
        "una_contro_uno": bool(tiro.get("one_on_one", False)),
        "porta_vuota": bool(tiro.get("open_goal", False)),
        "deviato": bool(tiro.get("deflected", False)),
        "duello_aereo": bool(tiro.get("aerial_won", False)),
        "xg_statsbomb": float(tiro.get("statsbomb_xg", float("nan"))),
        "ha_fotogramma": fotogramma is not None,
        "giocatori_fotogramma": len(fotogramma) if fotogramma else 0,
        "avversari_fotogramma": (
            sum(1 for g in fotogramma if not g.get("teammate", False)) if fotogramma else 0
        ),
        "ha_360": bool(meta["ha_360"]),
    }


def _id(blocco: Any) -> int:
    """Estrae un identificativo numerico da un blocco annidato.

    Args:
        blocco: Il dizionario, che puo' mancare.

    Returns:
        L'identificativo, oppure 0 se assente.
    """
    if isinstance(blocco, dict):
        return int(blocco.get("id", 0))
    return 0


def gol_per_squadra(eventi: Sequence[dict[str, Any]]) -> dict[str, int]:
    """Conta i gol di una partita a partire dagli eventi.

    Due trappole, ed e' il motivo per cui questa funzione esiste separata:

    1. i rigori finali sono eventi ``Shot`` con ``period = 5`` e **non**
       contano per il risultato;
    2. gli autogol non sono eventi ``Shot``: compaiono come ``Own Goal For``
       per la squadra che ne beneficia e ``Own Goal Against`` per quella che lo
       subisce. Contarli entrambi raddoppierebbe il totale.

    Args:
        eventi: Gli eventi grezzi della partita.

    Returns:
        Quanti gol ha segnato ciascuna squadra.
    """
    conteggio: collections.Counter[str] = collections.Counter()
    for evento in eventi:
        tipo = _nome(evento.get("type"))
        squadra = _nome(evento.get("team"))
        if tipo == "Shot":
            e_gol = _nome(evento.get("shot", {}).get("outcome")) == ESITO_GOL
            if e_gol and int(evento["period"]) != PERIODO_RIGORI:
                conteggio[squadra] += 1
        elif tipo == AUTOGOL_A_FAVORE:
            conteggio[squadra] += 1
    return dict(conteggio)


def verifica_risultato(match_id: int, calcolati: dict[str, int], meta: dict[str, Any]) -> None:
    """Confronta i gol calcolati con il risultato ufficiale della partita.

    E' il criterio di completamento di M3-T1. Se non torna, la costruzione del
    magazzino si interrompe.

    Args:
        match_id: La partita in esame.
        calcolati: I gol contati dagli eventi.
        meta: I metadati con il risultato ufficiale.

    Raises:
        QualitaError: Se il risultato calcolato non coincide con quello
            ufficiale.
    """
    atteso = {meta["casa"]: meta["gol_casa"], meta["ospite"]: meta["gol_ospite"]}
    ottenuto = {squadra: calcolati.get(squadra, 0) for squadra in atteso}
    if ottenuto != atteso:
        msg = (
            f"Partita {match_id}: risultato calcolato {ottenuto}, "
            f"ufficiale {atteso}. Gli eventi non tornano con il risultato."
        )
        raise QualitaError(msg)


def tiri_di_partita(
    match_id: int, comp: Competizione, meta: dict[str, Any], verifica: bool = True
) -> list[dict[str, Any]]:
    """Estrae le righe di tiro di una singola partita.

    Args:
        match_id: La partita.
        comp: La competizione a cui appartiene.
        meta: I metadati della partita.
        verifica: Se vero, controlla che i gol coincidano con il risultato.

    Returns:
        Una riga per tiro, rigori finali compresi e marcati.
    """
    percorso = ingest.percorso_risorsa("events", match_id)
    eventi: list[dict[str, Any]] = ingest.leggi_json(percorso)

    if verifica:
        verifica_risultato(match_id, gol_per_squadra(eventi), meta)

    return [riga_tiro(e, comp, match_id, meta) for e in eventi if _nome(e.get("type")) == "Shot"]


def costruisci_tiri(competizioni: Iterable[Competizione], verifica: bool = True) -> pd.DataFrame:
    """Costruisce la tabella dei tiri per le competizioni gia' scaricate.

    Args:
        competizioni: Le competizioni da includere.
        verifica: Se vero, ogni partita viene confrontata con il suo risultato
            ufficiale e un'incoerenza interrompe la costruzione.

    Returns:
        La tabella dei tiri, con i tipi di :data:`TIPI_TIRI` gia' applicati.
    """
    righe: list[dict[str, Any]] = []
    for comp in competizioni:
        metadati = metadati_partite(comp)
        for match_id, meta in metadati.items():
            if not ingest.percorso_risorsa("events", match_id).exists():
                continue
            righe.extend(tiri_di_partita(match_id, comp, meta, verifica))
    return applica_tipi(righe)


def applica_tipi(righe: list[dict[str, Any]]) -> pd.DataFrame:
    """Costruisce il DataFrame con i tipi dichiarati.

    Args:
        righe: Le righe grezze.

    Returns:
        La tabella tipizzata, vuota ma con le colonne giuste se non ci sono
        righe — cosi' chi la riceve non deve gestire il caso a parte.
    """
    df = pd.DataFrame(righe, columns=list(TIPI_TIRI))
    return df.astype(TIPI_TIRI)
