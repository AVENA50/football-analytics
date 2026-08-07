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
from typing import TYPE_CHECKING, Any, Final, NamedTuple

import pandas as pd

from football_analytics import ingest
from football_analytics.config import SOGLIA_MINUTI, Competizione, percorso_tabella

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path

#: Il periodo dei tiri di rigore a fine partita. Non contano per il risultato.
PERIODO_RIGORI: Final[int] = 5

#: Nome dell'esito che identifica un gol.
ESITO_GOL: Final[str] = "Goal"

#: I tipi di evento che assegnano un gol senza essere un tiro.
AUTOGOL_A_FAVORE: Final[str] = "Own Goal For"

#: L'evento che chiude un periodo di gioco.
FINE_PERIODO: Final[str] = "Half End"

#: Ultimo periodo che conta come gioco. Il 5 sono i rigori finali: includerlo
#: nel calcolo della durata darebbe giocatori in campo 129 minuti.
ULTIMO_PERIODO_DI_GIOCO: Final[int] = 4

#: Dimensioni del campo nel sistema di coordinate di StatsBomb.
LUNGHEZZA_CAMPO: Final[float] = 120.0
LARGHEZZA_CAMPO: Final[float] = 80.0

#: Quanto una coordinata puo' sporgere dal campo senza essere un errore.
#:
#: Su 44.000 tiri ce ne sono due a ``x = 120,1`` e ``120,2`` con ``y`` vicino a
#: 1: calciati dalla linea di fondo all'altezza della bandierina, dove il centro
#: del pallone puo' trovarsi qualche centimetro oltre la linea. Entrambi hanno
#: l'xG minimo, il che conferma la lettura. E' rumore di misura, non un dato
#: sbagliato: un controllo che pretende una precisione che il tracciamento non
#: ha e' un controllo che verra' disattivato al primo falso allarme.
TOLLERANZA_CAMPO: Final[float] = 1.0

#: Durata plausibile di una partita, in minuti. Sotto gli 80 significa che
#: manca un tempo, sopra i 135 che si sta contando qualcosa che non e' gioco.
DURATA_MINIMA: Final[int] = 80
DURATA_MASSIMA: Final[int] = 135

#: Griglia della heatmap: celle da 5x5 metri su un campo 120x80.
#:
#: Non e' una scelta di compressione ma di senso: una heatmap **e'** una
#: densita' su griglia. Salvare sei milioni di tocchi per poi contarli in celle
#: a ogni caricamento significa far fare a Streamlit, dentro un gigabyte di
#: RAM, un lavoro che va fatto una volta sola qui.
CELLE_X: Final[int] = 24
CELLE_Y: Final[int] = 16

#: Gli eventi in cui un giocatore tocca il pallone.
#:
#: `Pressure` resta fuori di proposito: e' un'azione **senza** palla, registrata
#: alla posizione di chi pressa. Includerla gonfierebbe la heatmap di un
#: centrocampista difensivo con posizioni in cui non ha mai avuto il pallone.
TIPI_TOCCO: Final[frozenset[str]] = frozenset(
    {
        "Pass",
        "Ball Receipt*",
        "Carry",
        "Shot",
        "Dribble",
        "Clearance",
        "Interception",
        "Ball Recovery",
        "Duel",
        "Block",
        "Miscontrol",
        "Dispossessed",
        "Goal Keeper",
        "Shield",
        "50/50",
    }
)

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

#: Tipo di dato di ogni colonna di ``matches.parquet``.
TIPI_PARTITE: Final[dict[str, str]] = {
    "match_id": "int32",
    "competizione": "category",
    "gruppo": "category",
    "stagione": "category",
    "data": "string",
    "giornata": "int16",
    "fase": "category",
    "casa": "category",
    "ospite": "category",
    "gol_casa": "int8",
    "gol_ospite": "int8",
    "gol_casa_da_tiro": "int8",
    "gol_ospite_da_tiro": "int8",
    "autogol_casa": "int8",
    "autogol_ospite": "int8",
    "xg_casa": "float32",
    "xg_ospite": "float32",
    "tiri_casa": "int16",
    "tiri_ospite": "int16",
    "durata_minuti": "int16",
    "ai_rigori": "bool",
    "ha_360": "bool",
}

#: Tipo di dato di ogni colonna di ``player_stats.parquet``.
TIPI_GIOCATORI: Final[dict[str, str]] = {
    "competizione": "category",
    "gruppo": "category",
    "stagione": "category",
    "giocatore_id": "int32",
    "giocatore": "string",
    "squadra": "category",
    "ruolo": "category",
    "partite": "int16",
    "minuti": "int32",
    "tiri": "int16",
    "gol": "int16",
    "xg": "float32",
    "gol_meno_xg": "float32",
    "tiri_90": "float32",
    "gol_90": "float32",
    "xg_90": "float32",
    "x_media": "float32",
    "y_media": "float32",
    "sopra_soglia": "bool",
}

#: Il nome del ruolo che identifica il portiere nei fotogrammi.
RUOLO_PORTIERE: Final[str] = "Goalkeeper"

#: Tipo di dato di ogni colonna di ``freeze_frames.parquet``.
#:
#: Una riga per **giocatore inquadrato** al momento di un tiro: circa
#: quattordici righe per tiro. E' la tabella piu' lunga del magazzino e resta
#: comunque piccola, perche' ha sette colonne di cui cinque numeriche corte e
#: uno ``shot_id`` che si ripete quattordici volte e quindi si comprime bene.
TIPI_FOTOGRAMMI: Final[dict[str, str]] = {
    "shot_id": "string",
    "match_id": "int32",
    "giocatore_id": "int32",
    "x": "float32",
    "y": "float32",
    "compagno": "bool",
    "portiere": "bool",
    "ruolo": "category",
}

#: L'ordine delle componenti della chiave di ``passes.parquet``.
CHIAVE_PASSAGGI: Final[tuple[str, ...]] = (
    "competizione",
    "gruppo",
    "stagione",
    "squadra",
    "passatore_id",
    "ricevitore_id",
)

#: L'ordine delle componenti della chiave di ``touches.parquet``.
CHIAVE_TOCCHI: Final[tuple[str, ...]] = (
    "competizione",
    "gruppo",
    "stagione",
    "giocatore_id",
    "squadra",
    "cella_x",
    "cella_y",
)

#: Tipo di dato di ogni colonna di ``passes.parquet``.
#:
#: Sono gli **archi** della rete dei passaggi, non i passaggi. I nodi — le
#: posizioni medie dei giocatori — stanno in ``player_stats.parquet``, che ha
#: gia' la grana giusta.
TIPI_PASSAGGI: Final[dict[str, str]] = {
    "competizione": "category",
    "gruppo": "category",
    "stagione": "category",
    "squadra": "category",
    "passatore_id": "int32",
    "ricevitore_id": "int32",
    "passaggi": "int32",
}

#: Tipo di dato di ogni colonna di ``touches.parquet``.
TIPI_TOCCHI: Final[dict[str, str]] = {
    "competizione": "category",
    "gruppo": "category",
    "stagione": "category",
    "giocatore_id": "int32",
    "squadra": "category",
    "cella_x": "int8",
    "cella_y": "int8",
    "tocchi": "int32",
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


def _valore(blocco: Any, chiave: str, predefinito: int = 0) -> int:
    """Estrae un numero da un blocco annidato di StatsBomb.

    Args:
        blocco: Il dizionario, che puo' mancare.
        chiave: La chiave da leggere.
        predefinito: Valore da usare se la chiave non c'e'.

    Returns:
        Il numero, oppure il predefinito.
    """
    if isinstance(blocco, dict):
        return int(blocco.get(chiave, predefinito))
    return predefinito


def nome_squadra(meta: dict[str, Any], squadra_id: int) -> str:
    """Restituisce il nome canonico di una squadra della partita.

    Il nome viene dal file delle partite, non dall'evento: e' l'unico modo per
    avere una grafia sola in tutto il magazzino. Due squadre di Ligue 1 —
    Marsiglia e Caen — compaiono negli eventi con due nomi diversi, e senza
    questa normalizzazione le tabelle avrebbero due righe per la stessa
    squadra e i join della dashboard perderebbero meta' dei dati.

    Args:
        meta: I metadati della partita.
        squadra_id: L'identificativo della squadra nell'evento.

    Returns:
        Il nome canonico, oppure stringa vuota se l'identificativo non
        appartiene a nessuna delle due squadre della partita.
    """
    if squadra_id and squadra_id == meta.get("casa_id"):
        return str(meta["casa"])
    if squadra_id and squadra_id == meta.get("ospite_id"):
        return str(meta["ospite"])
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
                # L'identita' di una squadra e' il suo identificativo. Negli
                # eventi il Marsiglia compare a volte come «Marseille» e a
                # volte come «Olympique de Marseille», e il Caen lo stesso:
                # confrontare per nome fa risultare a zero i loro gol.
                "casa_id": int(_valore(voce.get("home_team"), "home_team_id")),
                "ospite_id": int(_valore(voce.get("away_team"), "away_team_id")),
                "gol_casa": int(voce["home_score"]),
                "gol_ospite": int(voce["away_score"]),
                "ha_360": voce.get("match_status_360") == ingest.STATO_360_DISPONIBILE,
                "data": str(voce.get("match_date", "")),
                # I tornei a eliminazione diretta non hanno giornate: zero
                # significa «non applicabile», non «prima giornata».
                "giornata": int(voce.get("match_week") or 0),
                "fase": _nome(voce.get("competition_stage")),
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
    in_casa = _id(evento.get("team")) == meta["casa_id"]
    squadra = meta["casa"] if in_casa else meta["ospite"]

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


def gol_per_squadra(eventi: Sequence[dict[str, Any]], meta: dict[str, Any]) -> dict[str, int]:
    """Conta i gol di una partita a partire dagli eventi.

    Due trappole, ed e' il motivo per cui questa funzione esiste separata:

    1. i rigori finali sono eventi ``Shot`` con ``period = 5`` e **non**
       contano per il risultato;
    2. gli autogol non sono eventi ``Shot``: compaiono come ``Own Goal For``
       per la squadra che ne beneficia e ``Own Goal Against`` per quella che lo
       subisce. Contarli entrambi raddoppierebbe il totale.

    Args:
        eventi: Gli eventi grezzi della partita.
        meta: I metadati, da cui si ricava il nome canonico delle squadre.

    Returns:
        Quanti gol ha segnato ciascuna squadra, con i nomi del file partite.
    """
    conteggio: collections.Counter[str] = collections.Counter()
    for evento in eventi:
        tipo = _nome(evento.get("type"))
        squadra = nome_squadra(meta, _id(evento.get("team")))
        if not squadra:
            continue
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
        verifica_risultato(match_id, gol_per_squadra(eventi, meta), meta)

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


def applica_tipi(righe: list[dict[str, Any]], tipi: dict[str, str] | None = None) -> pd.DataFrame:
    """Costruisce il DataFrame con i tipi dichiarati.

    Args:
        righe: Le righe grezze.
        tipi: Lo schema da applicare. Se assente, quello dei tiri.

    Returns:
        La tabella tipizzata, vuota ma con le colonne giuste se non ci sono
        righe — cosi' chi la riceve non deve gestire il caso a parte.
    """
    schema = TIPI_TIRI if tipi is None else tipi
    df = pd.DataFrame(righe, columns=list(schema))
    return df.astype(schema)


# ---------------------------------------------------------------------------
# matches.parquet e i minuti giocati (M3-T2)
# ---------------------------------------------------------------------------


def durata_partita(eventi: Sequence[dict[str, Any]]) -> int:
    """Calcola la durata effettiva della partita, in secondi.

    Esclude il periodo dei rigori finali. Includerlo darebbe giocatori in campo
    per 129 minuti: e' successo, ed e' il motivo per cui questa funzione esiste
    invece di un ``max()`` scritto sul posto.

    Args:
        eventi: Gli eventi grezzi della partita.

    Returns:
        Il secondo dell'ultimo fischio di un periodo di gioco. Zero se la
        partita non contiene eventi di fine periodo.
    """
    fini = [
        int(e["minute"]) * 60 + int(e["second"])
        for e in eventi
        if _nome(e.get("type")) == FINE_PERIODO and int(e["period"]) <= ULTIMO_PERIODO_DI_GIOCO
    ]
    return max(fini) if fini else 0


def _secondi(orario: str | None) -> int | None:
    """Converte un orario ``"MM:SS"`` in secondi dall'inizio della partita.

    Args:
        orario: L'orario nel formato di StatsBomb, oppure ``None``.

    Returns:
        I secondi, oppure ``None`` se l'orario e' assente.
    """
    if orario is None:
        return None
    minuti, secondi = orario.split(":")
    return int(minuti) * 60 + int(secondi)


def presenze_di_partita(
    match_id: int, comp: Competizione, meta: dict[str, Any], durata: int
) -> list[dict[str, Any]]:
    """Calcola i minuti giocati da ogni giocatore di una partita.

    **Non somma gli spezzoni**, e la ragione e' un difetto dei dati: nell'1,3 %
    dei casi StatsBomb pubblica uno spezzone con ``to`` precedente a ``from``,
    e sommarli produrrebbe minuti negativi. Un giocatore entra in campo una
    volta sola ed esce una volta sola — gli spezzoni intermedi esistono solo
    per registrare i cambi di posizione — quindi il tempo in campo e' la
    distanza fra il primo ingresso e l'ultima uscita.

    Args:
        match_id: La partita.
        comp: La competizione a cui appartiene.
        meta: I metadati della partita.
        durata: La durata effettiva in secondi, da :func:`durata_partita`.

    Returns:
        Una riga per giocatore **sceso in campo**. Chi resta in panchina non
        ha spezzoni e non compare: una riga di soli zeri non aggiunge nulla e
        moltiplicherebbe la tabella per tre.
    """
    percorso = ingest.percorso_risorsa("lineups", match_id)
    if not percorso.exists():
        return []

    righe: list[dict[str, Any]] = []
    for squadra in ingest.leggi_json(percorso):
        squadra_id = int(squadra.get("team_id", 0))
        nome = nome_squadra(meta, squadra_id) or str(squadra.get("team_name", ""))
        in_casa = squadra_id == meta.get("casa_id")
        for giocatore in squadra.get("lineup", []):
            spezzoni = giocatore.get("positions") or []
            if not spezzoni:
                continue

            inizio = min(_secondi(p["from"]) or 0 for p in spezzoni)
            if any(p["to"] is None for p in spezzoni):
                uscita = durata
            else:
                uscita = max(_secondi(p["to"]) or 0 for p in spezzoni)

            minuti = max(0, round((uscita - inizio) / 60))
            righe.append(
                {
                    "match_id": match_id,
                    "competizione": comp.chiave,
                    "gruppo": str(comp.gruppo),
                    "stagione": comp.stagione,
                    "giocatore_id": int(giocatore["player_id"]),
                    "giocatore": str(giocatore["player_name"]),
                    "squadra": nome,
                    "in_casa": in_casa,
                    "ruolo": str(spezzoni[0].get("position", "")),
                    "minuti": minuti,
                }
            )
    return righe


def _riga_partita(
    match_id: int,
    comp: Competizione,
    meta: dict[str, Any],
    eventi: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Costruisce la riga di una partita, con aggregati e controlli.

    Args:
        match_id: La partita.
        comp: La competizione.
        meta: I metadati, con il risultato ufficiale.
        eventi: Gli eventi grezzi.

    Returns:
        Una riga con tutte le colonne di :data:`TIPI_PARTITE`.
    """
    aggregati: dict[str, dict[str, float]] = {
        meta["casa"]: {"gol": 0, "xg": 0.0, "tiri": 0, "autogol": 0},
        meta["ospite"]: {"gol": 0, "xg": 0.0, "tiri": 0, "autogol": 0},
    }
    ai_rigori = False

    for evento in eventi:
        tipo = _nome(evento.get("type"))
        squadra = nome_squadra(meta, _id(evento.get("team")))
        if squadra not in aggregati:
            continue

        if tipo == "Shot":
            if int(evento["period"]) == PERIODO_RIGORI:
                ai_rigori = True
                continue
            tiro = evento.get("shot", {})
            aggregati[squadra]["tiri"] += 1
            aggregati[squadra]["xg"] += float(tiro.get("statsbomb_xg", 0.0))
            if _nome(tiro.get("outcome")) == ESITO_GOL:
                aggregati[squadra]["gol"] += 1
        elif tipo == AUTOGOL_A_FAVORE:
            aggregati[squadra]["autogol"] += 1

    casa, ospite = aggregati[meta["casa"]], aggregati[meta["ospite"]]
    return {
        "match_id": match_id,
        "competizione": comp.chiave,
        "gruppo": str(comp.gruppo),
        "stagione": comp.stagione,
        "data": str(meta.get("data", "")),
        "giornata": int(meta.get("giornata", 0)),
        "fase": str(meta.get("fase", "")),
        "casa": meta["casa"],
        "ospite": meta["ospite"],
        "gol_casa": meta["gol_casa"],
        "gol_ospite": meta["gol_ospite"],
        "gol_casa_da_tiro": int(casa["gol"]),
        "gol_ospite_da_tiro": int(ospite["gol"]),
        "autogol_casa": int(casa["autogol"]),
        "autogol_ospite": int(ospite["autogol"]),
        "xg_casa": float(casa["xg"]),
        "xg_ospite": float(ospite["xg"]),
        "tiri_casa": int(casa["tiri"]),
        "tiri_ospite": int(ospite["tiri"]),
        "durata_minuti": round(durata_partita(eventi) / 60),
        "ai_rigori": ai_rigori,
        "ha_360": bool(meta["ha_360"]),
    }


def costruisci_partite_e_presenze(
    competizioni: Iterable[Competizione], verifica: bool = True
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Costruisce ``matches.parquet`` e la tabella intermedia delle presenze.

    Le due cose insieme perche' condividono la lettura degli eventi: separarle
    significherebbe analizzare due volte cinque gigabyte di JSON.

    Args:
        competizioni: Le competizioni da includere.
        verifica: Se vero, ogni partita viene confrontata con il risultato
            ufficiale.

    Returns:
        La tabella delle partite e quella delle presenze, una riga per
        giocatore sceso in campo in ogni partita.
    """
    righe_partite: list[dict[str, Any]] = []
    righe_presenze: list[dict[str, Any]] = []

    for comp in competizioni:
        for match_id, meta in metadati_partite(comp).items():
            percorso = ingest.percorso_risorsa("events", match_id)
            if not percorso.exists():
                continue
            eventi: list[dict[str, Any]] = ingest.leggi_json(percorso)
            if verifica:
                verifica_risultato(match_id, gol_per_squadra(eventi, meta), meta)
            righe_partite.append(_riga_partita(match_id, comp, meta, eventi))
            righe_presenze.extend(presenze_di_partita(match_id, comp, meta, durata_partita(eventi)))

    presenze = pd.DataFrame(righe_presenze)
    return applica_tipi(righe_partite, TIPI_PARTITE), presenze


def _prevalente(presenze: pd.DataFrame, chiave: list[str], attributo: str) -> pd.DataFrame:
    """Sceglie il valore di un attributo che copre piu' minuti giocati.

    Serve per nome e ruolo, che possono cambiare fra una partita e l'altra: il
    ruolo perche' un giocatore cambia posizione, il nome perche' StatsBomb a
    volte lo scrive in due modi — «Danny Ward» e «Daniel Ward» sono la stessa
    persona.

    A parita' di minuti sceglie l'ordine alfabetico, non il primo incontrato:
    senza un criterio deterministico due esecuzioni potrebbero dare risultati
    diversi, e M3-T5 chiede esattamente il contrario.

    Args:
        presenze: La tabella delle presenze.
        chiave: Le colonne che identificano un giocatore.
        attributo: La colonna di cui scegliere il valore prevalente.

    Returns:
        Una riga per chiave, con il valore scelto.
    """
    conteggi = presenze.groupby([*chiave, attributo], observed=True)["minuti"].sum().reset_index()
    ordinati = conteggi.sort_values(
        [*chiave, "minuti", attributo],
        ascending=[True] * len(chiave) + [False, True],
    )
    return ordinati.drop_duplicates(subset=chiave)[[*chiave, attributo]]


def costruisci_giocatori(
    tiri: pd.DataFrame,
    presenze: pd.DataFrame,
    posizioni: dict[tuple[str, int, str], list[float]] | None = None,
) -> pd.DataFrame:
    """Aggrega minuti e tiri in ``player_stats.parquet``.

    La chiave e' competizione + **identificativo** + squadra. Il nome resta
    fuori di proposito: e' un attributo, non un'identita'. StatsBomb scrive
    tre giocatori su Euro 2020 con due grafie diverse — «Danny Ward» e «Daniel
    Ward», «N'Golo Kante» con l'apostrofo raddoppiato — e metterlo nella
    chiave produrrebbe due righe per la stessa persona.

    La squadra invece **e'** parte della chiave: in un campionato un giocatore
    puo' cambiare maglia a gennaio, e sommare le due meta' della sua stagione
    sotto un'unica squadra darebbe una riga che non corrisponde a nessuna
    realta'.

    Args:
        tiri: La tabella dei tiri.
        presenze: La tabella delle presenze.
        posizioni: Somme delle coordinate e numero di tocchi per giocatore, da
            cui si ricavano ``x_media`` e ``y_media``. Se assente, le posizioni
            medie restano a zero.

    Returns:
        Una riga per giocatore, con i valori per 90 minuti gia' calcolati.
    """
    if presenze.empty:
        return applica_tipi([], TIPI_GIOCATORI)

    chiave = ["competizione", "gruppo", "stagione", "giocatore_id", "squadra"]
    base = (
        presenze.groupby(chiave, observed=True)
        .agg(partite=("match_id", "nunique"), minuti=("minuti", "sum"))
        .reset_index()
    )
    for attributo in ("giocatore", "ruolo"):
        base = base.merge(_prevalente(presenze, chiave, attributo), on=chiave, how="left")

    # I rigori finali non sono tiri della partita: non entrano nelle
    # statistiche del giocatore, altrimenti chi calcia dal dischetto a fine
    # supplementari risulterebbe con un xG per 90 minuti fuori scala.
    da_gioco = tiri[~tiri["rigori_finali"]]
    per_giocatore = (
        da_gioco.groupby(["competizione", "giocatore_id", "squadra"], observed=True)
        .agg(tiri=("gol", "size"), gol=("gol", "sum"), xg=("xg_statsbomb", "sum"))
        .reset_index()
    )

    unito = base.merge(per_giocatore, on=["competizione", "giocatore_id", "squadra"], how="left")
    for colonna in ("tiri", "gol", "xg"):
        unito[colonna] = unito[colonna].fillna(0)

    # La posizione media e' il nodo della rete dei passaggi: la calcoliamo qui
    # perche' questa tabella ha gia' la grana giusta, una riga per giocatore,
    # competizione e squadra. Una tabella a parte direbbe la stessa cosa.
    somme = posizioni or {}
    medie = [
        somme.get((c, int(g), s), [0.0, 0.0, 0.0])
        for c, g, s in zip(
            unito["competizione"], unito["giocatore_id"], unito["squadra"], strict=True
        )
    ]
    unito["x_media"] = [m[0] / m[2] if m[2] else 0.0 for m in medie]
    unito["y_media"] = [m[1] / m[2] if m[2] else 0.0 for m in medie]

    novanta = unito["minuti"].clip(lower=1) / 90.0
    unito["gol_meno_xg"] = unito["gol"] - unito["xg"]
    unito["tiri_90"] = unito["tiri"] / novanta
    unito["gol_90"] = unito["gol"] / novanta
    unito["xg_90"] = unito["xg"] / novanta
    unito["sopra_soglia"] = unito["minuti"] >= SOGLIA_MINUTI

    righe = [{str(k): v for k, v in riga.items()} for riga in unito.to_dict("records")]
    return applica_tipi(righe, TIPI_GIOCATORI)


def righe_fotogramma(evento: dict[str, Any], match_id: int) -> list[dict[str, Any]]:
    """Appiattisce il fotogramma di un tiro in una riga per giocatore.

    Args:
        evento: L'evento di tiro grezzo.
        match_id: La partita a cui appartiene.

    Returns:
        Una riga per giocatore inquadrato. Lista vuota se il tiro non ha il
        fotogramma — cosa che nell'Open Data succede quasi solo ai rigori.
    """
    fotogramma = evento.get("shot", {}).get("freeze_frame")
    if not fotogramma:
        return []

    shot_id = str(evento["id"])
    righe: list[dict[str, Any]] = []
    for giocatore in fotogramma:
        posizione = giocatore.get("location") or [float("nan"), float("nan")]
        ruolo = _nome(giocatore.get("position"))
        righe.append(
            {
                "shot_id": shot_id,
                "match_id": match_id,
                "giocatore_id": _id(giocatore.get("player")),
                "x": float(posizione[0]),
                "y": float(posizione[1]),
                "compagno": bool(giocatore.get("teammate", False)),
                "portiere": ruolo == RUOLO_PORTIERE,
                "ruolo": ruolo,
            }
        )
    return righe


def cella(x: float, y: float) -> tuple[int, int]:
    """Converte una posizione in campo nelle coordinate della griglia.

    Args:
        x: Posizione lungo la lunghezza del campo, da 0 a 120.
        y: Posizione lungo la larghezza, da 0 a 80.

    Returns:
        Gli indici di cella, gia' limitati ai bordi: un tiro sulla linea di
        porta ha x esattamente 120 e finirebbe fuori griglia.
    """
    cx = min(int(x / LUNGHEZZA_CAMPO * CELLE_X), CELLE_X - 1)
    cy = min(int(y / LARGHEZZA_CAMPO * CELLE_Y), CELLE_Y - 1)
    return max(cx, 0), max(cy, 0)


class Accumulatori(NamedTuple):
    """Le strutture in cui si sommano gli aggregati durante la lettura.

    Attributes:
        passaggi: Conteggio per arco della rete dei passaggi.
        tocchi: Conteggio per cella della griglia.
        posizioni: Somma delle coordinate e numero di tocchi per giocatore,
            da cui si ricava la posizione media esatta — non approssimata
            dalla griglia.
    """

    passaggi: collections.Counter[tuple[str, str, str, str, int, int]]
    tocchi: collections.Counter[tuple[str, str, str, int, str, int, int]]
    posizioni: dict[tuple[str, int, str], list[float]]


def accumula(
    eventi: Iterable[dict[str, Any]],
    comp: Competizione,
    acc: Accumulatori,
    meta: dict[str, Any],
) -> None:
    """Somma passaggi, tocchi e posizioni di una partita negli accumulatori.

    Args:
        eventi: Gli eventi grezzi della partita.
        comp: La competizione a cui appartiene.
        acc: Le strutture da aggiornare.
        meta: I metadati, da cui si ricava il nome canonico delle squadre.
    """
    contesto = (comp.chiave, str(comp.gruppo), comp.stagione)

    for evento in eventi:
        tipo = _nome(evento.get("type"))
        giocatore = evento.get("player")
        posizione = evento.get("location")
        squadra = nome_squadra(meta, _id(evento.get("team")))
        if not isinstance(giocatore, dict) or not posizione or not squadra:
            continue

        gid = int(giocatore.get("id", 0))

        if tipo in TIPI_TOCCO:
            cx, cy = cella(float(posizione[0]), float(posizione[1]))
            acc.tocchi[(*contesto, gid, squadra, cx, cy)] += 1
            somma = acc.posizioni.setdefault((comp.chiave, gid, squadra), [0.0, 0.0, 0.0])
            somma[0] += float(posizione[0])
            somma[1] += float(posizione[1])
            somma[2] += 1

        if tipo == "Pass":
            passaggio = evento.get("pass", {})
            ricevitore = passaggio.get("recipient")
            # Solo i passaggi riusciti: l'esito assente significa completato.
            # Per un passaggio sbagliato il ricevitore non e' un compagno, e un
            # arco della rete verso un avversario non vuol dire niente.
            if "outcome" not in passaggio and isinstance(ricevitore, dict):
                acc.passaggi[(*contesto, squadra, gid, int(ricevitore.get("id", 0)))] += 1


def costruisci_tabelle(
    competizioni: Iterable[Competizione], verifica: bool = True
) -> dict[str, pd.DataFrame]:
    """Costruisce le cinque tabelle leggendo gli eventi **una volta sola**.

    Le funzioni `costruisci_tiri` e `costruisci_partite_e_presenze` esistono
    ancora e restano utili per lavorare su una tabella alla volta, ma ognuna
    rilegge i JSON: usarle in sequenza significherebbe analizzare cinque
    gigabyte due volte.

    Args:
        competizioni: Le competizioni da includere.
        verifica: Se vero, ogni partita viene confrontata con il risultato
            ufficiale e un'incoerenza interrompe la costruzione.

    Returns:
        Le cinque tabelle del magazzino, con i nomi che corrispondono ai file
        Parquet.
    """
    righe_tiri: list[dict[str, Any]] = []
    righe_partite: list[dict[str, Any]] = []
    righe_presenze: list[dict[str, Any]] = []
    righe_fotogrammi: list[dict[str, Any]] = []
    acc = Accumulatori(collections.Counter(), collections.Counter(), {})

    for comp in competizioni:
        for match_id, meta in metadati_partite(comp).items():
            percorso = ingest.percorso_risorsa("events", match_id)
            if not percorso.exists():
                continue
            eventi: list[dict[str, Any]] = ingest.leggi_json(percorso)
            if verifica:
                verifica_risultato(match_id, gol_per_squadra(eventi, meta), meta)

            tiri_partita = [e for e in eventi if _nome(e.get("type")) == "Shot"]
            righe_tiri.extend(riga_tiro(e, comp, match_id, meta) for e in tiri_partita)
            for e in tiri_partita:
                righe_fotogrammi.extend(righe_fotogramma(e, match_id))
            righe_partite.append(_riga_partita(match_id, comp, meta, eventi))
            righe_presenze.extend(presenze_di_partita(match_id, comp, meta, durata_partita(eventi)))
            accumula(eventi, comp, acc, meta)

    tiri = applica_tipi(righe_tiri)
    return {
        "shots": tiri,
        "matches": applica_tipi(righe_partite, TIPI_PARTITE),
        "player_stats": costruisci_giocatori(tiri, pd.DataFrame(righe_presenze), acc.posizioni),
        "passes": tabella_da_conteggi(acc.passaggi, CHIAVE_PASSAGGI, "passaggi", TIPI_PASSAGGI),
        "touches": tabella_da_conteggi(acc.tocchi, CHIAVE_TOCCHI, "tocchi", TIPI_TOCCHI),
        "freeze_frames": applica_tipi(righe_fotogrammi, TIPI_FOTOGRAMMI),
    }


def tabella_da_conteggi(
    conteggi: collections.Counter[Any],
    colonne: tuple[str, ...],
    misura: str,
    tipi: dict[str, str],
) -> pd.DataFrame:
    """Trasforma un contatore con chiavi a tupla in una tabella tipizzata.

    Args:
        conteggi: Il contatore accumulato durante la lettura.
        colonne: I nomi delle componenti della chiave, nell'ordine.
        misura: Il nome della colonna che contiene il conteggio.
        tipi: Lo schema da applicare.

    Returns:
        La tabella, con le righe ordinate per chiave cosi' che due esecuzioni
        producano file identici byte per byte.
    """
    righe = [
        {**dict(zip(colonne, chiave, strict=True)), misura: valore}
        for chiave, valore in sorted(conteggi.items())
    ]
    return applica_tipi(righe, tipi)


# ---------------------------------------------------------------------------
# Controlli di qualita' (M3-T4)
# ---------------------------------------------------------------------------


def _problemi_tiri(tiri: pd.DataFrame) -> list[str]:
    """Cerca incoerenze nella tabella dei tiri.

    Args:
        tiri: La tabella da controllare.

    Returns:
        Le anomalie trovate, in chiaro. Lista vuota se e' tutto a posto.
    """
    problemi: list[str] = []
    if tiri.empty:
        return problemi

    duplicati = int(tiri["shot_id"].duplicated().sum())
    if duplicati:
        problemi.append(f"tiri: {duplicati} identificativi duplicati")

    limite_x = LUNGHEZZA_CAMPO + TOLLERANZA_CAMPO
    limite_y = LARGHEZZA_CAMPO + TOLLERANZA_CAMPO
    fuori_x = int(((tiri["x"] < -TOLLERANZA_CAMPO) | (tiri["x"] > limite_x)).sum())
    fuori_y = int(((tiri["y"] < -TOLLERANZA_CAMPO) | (tiri["y"] > limite_y)).sum())
    if fuori_x or fuori_y:
        problemi.append(f"tiri: {fuori_x} coordinate x e {fuori_y} y fuori dal campo")

    mancanti = int(tiri[["x", "y", "xg_statsbomb"]].isna().to_numpy().sum())
    if mancanti:
        problemi.append(f"tiri: {mancanti} valori mancanti fra coordinate e xG")

    xg_assurdi = int(((tiri["xg_statsbomb"] < 0) | (tiri["xg_statsbomb"] > 1)).sum())
    if xg_assurdi:
        problemi.append(f"tiri: {xg_assurdi} valori di xG fuori dall'intervallo 0-1")

    incoerenti = int((tiri["gol"] != (tiri["esito"] == ESITO_GOL)).sum())
    if incoerenti:
        problemi.append(f"tiri: {incoerenti} righe con 'gol' incoerente con l'esito")

    return problemi


def _problemi_partite(partite: pd.DataFrame) -> list[str]:
    """Cerca incoerenze nella tabella delle partite.

    Args:
        partite: La tabella da controllare.

    Returns:
        Le anomalie trovate, in chiaro.
    """
    problemi: list[str] = []
    if partite.empty:
        return problemi

    duplicati = int(partite["match_id"].duplicated().sum())
    if duplicati:
        problemi.append(f"partite: {duplicati} identificativi duplicati")

    # E' l'identita' che tiene insieme le due letture del risultato: i gol
    # ufficiali sono quelli da tiro piu' gli autogol subiti dall'avversario.
    for lato in ("casa", "ospite"):
        scarto = int(
            (
                partite[f"gol_{lato}_da_tiro"] + partite[f"autogol_{lato}"]
                != partite[f"gol_{lato}"]
            ).sum()
        )
        if scarto:
            problemi.append(f"partite: {scarto} righe in cui i gol {lato} non tornano")

    durate = partite["durata_minuti"]
    strane = int(((durate < DURATA_MINIMA) | (durate > DURATA_MASSIMA)).sum())
    if strane:
        problemi.append(
            f"partite: {strane} durate fuori dall'intervallo "
            f"{DURATA_MINIMA}-{DURATA_MASSIMA} minuti"
        )

    return problemi


def _problemi_giocatori(giocatori: pd.DataFrame) -> list[str]:
    """Cerca incoerenze nella tabella dei giocatori.

    Args:
        giocatori: La tabella da controllare.

    Returns:
        Le anomalie trovate, in chiaro.
    """
    problemi: list[str] = []
    if giocatori.empty:
        return problemi

    chiave = ["competizione", "giocatore_id", "squadra"]
    duplicati = int(giocatori.duplicated(subset=chiave).sum())
    if duplicati:
        problemi.append(f"giocatori: {duplicati} righe duplicate per {'+'.join(chiave)}")

    piu_gol_che_tiri = int((giocatori["gol"] > giocatori["tiri"]).sum())
    if piu_gol_che_tiri:
        problemi.append(f"giocatori: {piu_gol_che_tiri} con piu' gol che tiri")

    minuti_assurdi = int((giocatori["minuti"] <= 0).sum())
    if minuti_assurdi:
        problemi.append(f"giocatori: {minuti_assurdi} con minuti non positivi")

    mancanti = int(giocatori[["gol_90", "xg_90", "tiri_90"]].isna().to_numpy().sum())
    if mancanti:
        problemi.append(f"giocatori: {mancanti} valori per 90 minuti mancanti")

    return problemi


def _problemi_rete(passaggi: pd.DataFrame | None, tocchi: pd.DataFrame | None) -> list[str]:
    """Cerca incoerenze nella rete dei passaggi e nella griglia dei tocchi.

    Args:
        passaggi: La tabella degli archi, se presente.
        tocchi: La tabella della densita', se presente.

    Returns:
        Le anomalie trovate, in chiaro.
    """
    problemi: list[str] = []

    if passaggi is not None and not passaggi.empty:
        auto = int((passaggi["passatore_id"] == passaggi["ricevitore_id"]).sum())
        if auto:
            problemi.append(f"passaggi: {auto} archi da un giocatore a se stesso")
        vuoti = int((passaggi["passaggi"] <= 0).sum())
        if vuoti:
            problemi.append(f"passaggi: {vuoti} archi con conteggio non positivo")
        duplicati = int(passaggi.duplicated(subset=list(CHIAVE_PASSAGGI)).sum())
        if duplicati:
            problemi.append(f"passaggi: {duplicati} archi duplicati")

    if tocchi is not None and not tocchi.empty:
        fuori = int(
            (
                (tocchi["cella_x"] < 0)
                | (tocchi["cella_x"] >= CELLE_X)
                | (tocchi["cella_y"] < 0)
                | (tocchi["cella_y"] >= CELLE_Y)
            ).sum()
        )
        if fuori:
            problemi.append(f"tocchi: {fuori} celle fuori dalla griglia")
        vuote = int((tocchi["tocchi"] <= 0).sum())
        if vuote:
            problemi.append(f"tocchi: {vuote} celle con conteggio non positivo")
        duplicate = int(tocchi.duplicated(subset=list(CHIAVE_TOCCHI)).sum())
        if duplicate:
            problemi.append(f"tocchi: {duplicate} celle duplicate")

    return problemi


def controlla(tabelle: dict[str, pd.DataFrame]) -> None:
    """Esegue tutti i controlli di qualita' e interrompe se qualcosa non torna.

    Riporta **tutti** i problemi insieme invece di fermarsi al primo: quando
    una trasformazione si rompe, di solito si rompe in piu' punti, e scoprirli
    uno alla volta costa un'esecuzione completa per ognuno.

    Args:
        tabelle: Le tabelle da controllare, come le restituisce
            :func:`costruisci_tabelle`.

    Raises:
        QualitaError: Se anche un solo controllo trova un'anomalia.
    """
    problemi = [
        *_problemi_tiri(tabelle["shots"]),
        *_problemi_partite(tabelle["matches"]),
        *_problemi_giocatori(tabelle["player_stats"]),
        *_problemi_rete(tabelle.get("passes"), tabelle.get("touches")),
    ]

    partite_note = set(tabelle["matches"]["match_id"])
    orfani = set(tabelle["shots"]["match_id"]) - partite_note
    if orfani:
        problemi.append(f"tiri: {len(orfani)} partite presenti nei tiri ma non in matches")

    try:
        verifica_gol_giocatori(tabelle["player_stats"], tabelle["matches"])
    except QualitaError as errore:
        problemi.append(str(errore))

    if problemi:
        elenco = "\n  - ".join(problemi)
        msg = f"Controlli di qualita' falliti:\n  - {elenco}"
        raise QualitaError(msg)


def salva(nome: str, tabella: pd.DataFrame) -> Path:
    """Scrive una tabella nel magazzino, in Parquet compresso.

    Args:
        nome: Il nome logico della tabella, fra quelli di ``config.TABELLE``.
        tabella: I dati da scrivere.

    Returns:
        Il percorso del file scritto.
    """
    percorso = percorso_tabella(nome)
    percorso.parent.mkdir(parents=True, exist_ok=True)
    # zstd comprime meglio di snappy a parita' di velocita' di lettura, e qui
    # ogni megabyte conta: il limite di GitHub e' 50 MB per file.
    tabella.to_parquet(percorso, index=False, compression="zstd")
    return percorso


def verifica_gol_giocatori(giocatori: pd.DataFrame, partite: pd.DataFrame) -> None:
    """Confronta i gol attribuiti ai giocatori con quelli delle partite.

    E' il criterio di completamento di M3-T2. Il confronto e' sui gol **da
    tiro**: gli autogol non si attribuiscono a chi li subisce, quindi stanno
    nelle partite ma non nei giocatori.

    Args:
        giocatori: La tabella dei giocatori.
        partite: La tabella delle partite.

    Raises:
        QualitaError: Se i due totali non coincidono.
    """
    da_giocatori = int(giocatori["gol"].sum())
    da_partite = int(partite["gol_casa_da_tiro"].sum() + partite["gol_ospite_da_tiro"].sum())
    if da_giocatori != da_partite:
        msg = (
            f"Gol per giocatore: {da_giocatori}, gol da tiro per partita: "
            f"{da_partite}. L'attribuzione ai giocatori perde o duplica dei gol."
        )
        raise QualitaError(msg)
