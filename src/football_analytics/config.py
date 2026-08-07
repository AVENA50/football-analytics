"""Percorsi, costanti e competizioni scelte, condivisi da tutti gli strati.

Questo modulo e' l'unica fonte dei percorsi: nessun altro file costruisce a mano
una stringa come ``"data/processed/shots.parquet"``. Il motivo e' pratico —
l'app Streamlit puo' essere avviata da una directory di lavoro qualsiasi, e i
percorsi relativi si romperebbero senza dare un errore leggibile.

Vale lo stesso per le competizioni: gli identificativi di StatsBomb stanno qui
e da nessun'altra parte.

**Le competizioni non sono quelle del piano iniziale.** Il piano assumeva 380
partite di Ligue 1 2021/22 e 306 di Bundesliga 2023/24; ce ne sono 26 e 34,
perche' StatsBomb a volte pubblica solo il sottoinsieme legato a un tema — le
partite di un giocatore, la stagione di una squadra. La verifica di M2-T1 lo ha
scoperto e le fonti sono state riscelte sui dati reali. Il racconto completo e'
in ``docs/milestones/M2-ingestione.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

# ---------------------------------------------------------------------------
# Percorsi
# ---------------------------------------------------------------------------

#: Radice del repository, calcolata risalendo da ``src/football_analytics/``.
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

#: JSON scaricati da StatsBomb. Esclusa da git: si riscarica con un comando.
DATA_RAW: Final[Path] = PROJECT_ROOT / "data" / "raw"

#: Parquet compatti letti dalla dashboard. Versionata in git.
DATA_PROCESSED: Final[Path] = PROJECT_ROOT / "data" / "processed"

#: Modelli xG addestrati e serializzati.
MODELS_DIR: Final[Path] = PROJECT_ROOT / "models"

#: Registro dello scaricamento, scritto dall'ingestione (M2-T3).
MANIFEST_PATH: Final[Path] = DATA_RAW / "manifest.json"

# ---------------------------------------------------------------------------
# Competizioni
# ---------------------------------------------------------------------------


class Copertura360(StrEnum):
    """Quanto una competizione dispone dei file ``three-sixty`` di StatsBomb.

    **Attenzione a non confonderli con i freeze frame dei tiri.** StatsBomb
    pubblica due cose diverse:

    - ``shot.freeze_frame``, dentro l'evento di tiro, con posizione, identita'
      e ruolo di ogni giocatore inquadrato al momento del tiro. E' presente nel
      97 % circa dei tiri di **tutte** le competizioni, campionati del 2015/16
      compresi, ed e' cio' che il modello xG usa;
    - i file ``three-sixty/``, che coprono tutti gli eventi della partita e
      aggiungono l'area inquadrata, ma non riportano nomi ne' ruoli.

    Questo enum descrive **i secondi**, ed e' quindi un fatto sulla ricchezza
    dei dati di contesto, non sulla possibilita' di addestrare il modello con
    le variabili spaziali. La colonna corrispondente in ``shots.parquet`` si
    chiama ``ha_fotogramma`` e riguarda il primo tipo.

    **Il valore va letto partita per partita, non dall'indice.** Il campo
    ``match_available_360`` dell'indice competizioni diventa non nullo anche se
    una sola partita ha i file: la Coppa d'Africa 2023 risulta cosi' coperta,
    e invece su 52 partite ne ha **una**. Il dato affidabile e'
    ``match_status_360`` nel file delle partite, che vale ``available``,
    ``scheduled``, ``processing`` o ``unscheduled``: solo il primo significa
    che il file esiste davvero.

    Attributes:
        COMPLETA: Tutte le partite hanno i file 360.
        ASSENTE: Nessuna li ha.
        PARZIALE: Alcune si', altre no.
    """

    COMPLETA = "completa"
    ASSENTE = "assente"
    PARZIALE = "parziale"


class Gruppo(StrEnum):
    """A cosa serve una competizione dentro il progetto.

    La separazione serve alle viste, non al modello. Un confronto fra leghe ha
    senso solo fra campionati completi della stessa stagione; un torneo a
    eliminazione diretta non ha giornate ne' classifica e va raccontato in un
    altro modo.

    **Non e' piu' una separazione fra «con e senza freeze frame».** All'inizio
    lo era, perche' il piano assumeva che solo alcune competizioni li avessero.
    La verifica di M3-T1 ha mostrato che ``shot.freeze_frame`` e' presente nel
    97 % dei tiri ovunque, campionati del 2015/16 compresi: il modello con le
    variabili spaziali puo' girare su tutte e 1.753 le partite.

    Attributes:
        CAMPIONATO: Stagioni complete di lega, stessa annata. Alimentano le
            viste esplorative e il confronto fra campionati.
        TORNEO: Tornei per nazionali, con in piu' i file 360 per il contesto.
        FINALI: Le finali di Champions League, su cui il modello viene
            **applicato** a dati che non ha mai visto.
    """

    CAMPIONATO = "campionato"
    TORNEO = "torneo"
    FINALI = "finali"


@dataclass(frozen=True, slots=True)
class Competizione:
    """Una competizione-stagione fra quelle su cui lavora il progetto.

    Attributes:
        chiave: Nome breve e stabile, usato nei percorsi e nei filtri.
        nome: Nome leggibile della competizione.
        stagione: Stagione in forma leggibile, oppure l'intervallo di anni.
        competition_id: Identificativo StatsBomb della competizione.
        season_id: Identificativo StatsBomb della stagione. Vale ``None``
            quando servono **tutte** le stagioni disponibili: e' il caso delle
            finali di Champions, dove l'Open Data contiene una sola partita per
            stagione e l'insieme interessante e' l'intera competizione.
        gruppo: A quale scopo serve la competizione.
        copertura_360: Disponibilita' dei freeze frame dichiarata da StatsBomb.
        partite_attese: Quante partite ci si aspetta di trovare. Questi numeri
            sono **misurati**, non stimati: vengono dall'esecuzione di
            ``scripts/esplora_open_data.py`` del 2026-08-07.
    """

    chiave: str
    nome: str
    stagione: str
    competition_id: int
    season_id: int | None
    gruppo: Gruppo
    copertura_360: Copertura360
    partite_attese: int

    @property
    def etichetta(self) -> str:
        """Nome e stagione in una stringa sola, per menu e titoli.

        Returns:
            Una stringa come ``"Serie A 2015/2016"``.
        """
        return f"{self.nome} {self.stagione}"

    @property
    def tutte_le_stagioni(self) -> bool:
        """Indica se la competizione va scaricata per intero.

        Returns:
            ``True`` quando ``season_id`` e' ``None``.
        """
        return self.season_id is None


# --- I quattro campionati 2015/16 ------------------------------------------
#
# Stessa stagione per tutti e quattro, e non e' un dettaglio: confrontare
# leghe di annate diverse non permette di distinguere la differenza fra i
# campionati da quella fra le epoche. Il piano iniziale prendeva tre leghe da
# tre stagioni distanti fino a otto anni; questo insieme toglie l'ambiguita'.
# Nessuno di questi ha i dati 360.

LA_LIGA_2015_16: Final[Competizione] = Competizione(
    chiave="la_liga_2015_16",
    nome="La Liga",
    stagione="2015/2016",
    competition_id=11,
    season_id=27,
    gruppo=Gruppo.CAMPIONATO,
    copertura_360=Copertura360.ASSENTE,
    partite_attese=380,
)

PREMIER_2015_16: Final[Competizione] = Competizione(
    chiave="premier_2015_16",
    nome="Premier League",
    stagione="2015/2016",
    competition_id=2,
    season_id=27,
    gruppo=Gruppo.CAMPIONATO,
    copertura_360=Copertura360.ASSENTE,
    partite_attese=380,
)

SERIE_A_2015_16: Final[Competizione] = Competizione(
    chiave="serie_a_2015_16",
    nome="Serie A",
    stagione="2015/2016",
    competition_id=12,
    season_id=27,
    gruppo=Gruppo.CAMPIONATO,
    copertura_360=Copertura360.ASSENTE,
    partite_attese=380,
)

# 377 e non 380: tre partite mancano nell'Open Data. Il numero e' quello
# misurato, non quello che ci si aspetterebbe da un campionato a venti squadre.
LIGUE_1_2015_16: Final[Competizione] = Competizione(
    chiave="ligue1_2015_16",
    nome="Ligue 1",
    stagione="2015/2016",
    competition_id=7,
    season_id=27,
    gruppo=Gruppo.CAMPIONATO,
    copertura_360=Copertura360.ASSENTE,
    partite_attese=377,
)

# --- I tornei per nazionali ------------------------------------------------
#
# Restano fuori i frammenti di club (La Liga 2020/21, Bundesliga 2023/24,
# Ligue 1 2021/22 e 2022/23): riguardano una squadra sola, quindi il campione
# non e' rappresentativo del campionato da cui viene.
#
# Tre di questi quattro hanno anche i file 360 su tutte le partite. La Coppa
# d'Africa no — ne ha una su 52 — ma resta nel gruppo: i tornei stanno insieme
# per **tipo di competizione**, e cio' che serve al modello xG e'
# ``shot.freeze_frame``, presente nel 95 % dei suoi tiri.

MONDIALI_2022: Final[Competizione] = Competizione(
    chiave="mondiali_2022",
    nome="Coppa del Mondo",
    stagione="2022",
    competition_id=43,
    season_id=106,
    gruppo=Gruppo.TORNEO,
    copertura_360=Copertura360.COMPLETA,
    partite_attese=64,
)

COPPA_AFRICA_2023: Final[Competizione] = Competizione(
    chiave="coppa_africa_2023",
    nome="Coppa d'Africa",
    stagione="2023",
    competition_id=1267,
    season_id=107,
    gruppo=Gruppo.TORNEO,
    # Una partita su 52. L'indice competizioni la dichiarava coperta.
    copertura_360=Copertura360.PARZIALE,
    partite_attese=52,
)

EURO_2024: Final[Competizione] = Competizione(
    chiave="euro_2024",
    nome="Campionato Europeo",
    stagione="2024",
    competition_id=55,
    season_id=282,
    gruppo=Gruppo.TORNEO,
    copertura_360=Copertura360.COMPLETA,
    partite_attese=51,
)

EURO_2020: Final[Competizione] = Competizione(
    chiave="euro_2020",
    nome="Campionato Europeo",
    stagione="2020",
    competition_id=55,
    season_id=43,
    gruppo=Gruppo.TORNEO,
    copertura_360=Copertura360.COMPLETA,
    partite_attese=51,
)

# --- Le finali di Champions ------------------------------------------------

CHAMPIONS_FINALI: Final[Competizione] = Competizione(
    chiave="champions_finali",
    nome="Finali di Champions League",
    stagione="1971-2019",
    competition_id=16,
    season_id=None,
    gruppo=Gruppo.FINALI,
    copertura_360=Copertura360.ASSENTE,
    partite_attese=18,
)

#: I quattro campionati completi: viste esplorative e modello base.
CAMPIONATI: Final[tuple[Competizione, ...]] = (
    LA_LIGA_2015_16,
    PREMIER_2015_16,
    SERIE_A_2015_16,
    LIGUE_1_2015_16,
)

#: I tornei per nazionali.
TORNEI: Final[tuple[Competizione, ...]] = (
    MONDIALI_2022,
    COPPA_AFRICA_2023,
    EURO_2024,
    EURO_2020,
)

#: Tutte le competizioni del progetto.
COMPETIZIONI: Final[tuple[Competizione, ...]] = (
    *CAMPIONATI,
    *TORNEI,
    CHAMPIONS_FINALI,
)

#: La competizione da cui parte lo scaricamento (M2-T5).
#:
#: Euro 2020 e' la piu' piccola fra quelle complete e ha i dati 360, quindi
#: esercita anche il percorso dei freeze frame. Se ``transform.py`` ha un
#: difetto lo si scopre su 51 partite invece che su 380.
PRIMA_COMPETIZIONE: Final[Competizione] = EURO_2020

# ---------------------------------------------------------------------------
# Tabelle del "magazzino"
# ---------------------------------------------------------------------------

#: Nomi logici delle tabelle Parquet prodotte dallo strato di trasformazione.
TABELLE: Final[tuple[str, ...]] = (
    "shots",
    "matches",
    "player_stats",
    "passes",
    "touches",
)

#: Limite oltre il quale GitHub emette un avviso su un singolo file, in byte.
LIMITE_FILE_BYTE: Final[int] = 50 * 1024 * 1024

#: Limite complessivo che ci siamo dati per ``data/processed/``, in byte.
LIMITE_TOTALE_BYTE: Final[int] = 100 * 1024 * 1024

#: Minuti sotto i quali un giocatore resta in tabella ma esce dalle graduatorie.
SOGLIA_MINUTI: Final[int] = 500

#: Seed unico per ogni operazione con una componente casuale (M5).
SEED: Final[int] = 42

#: Attribuzione richiesta dalle condizioni d'uso di StatsBomb Open Data.
ATTRIBUZIONE: Final[str] = (
    "Dati forniti da StatsBomb Open Data — https://github.com/statsbomb/open-data"
)


def competizione(chiave: str) -> Competizione:
    """Restituisce una competizione a partire dalla sua chiave.

    Args:
        chiave: La chiave breve, per esempio ``"serie_a_2015_16"``.

    Returns:
        La competizione corrispondente.

    Raises:
        ValueError: Se la chiave non esiste. Meglio fallire qui che ritrovarsi
            un ``None`` propagato per tre livelli di chiamate.
    """
    for voce in COMPETIZIONI:
        if voce.chiave == chiave:
            return voce
    attese = ", ".join(c.chiave for c in COMPETIZIONI)
    msg = f"Competizione sconosciuta: {chiave!r}. Attese: {attese}."
    raise ValueError(msg)


def del_gruppo(gruppo: Gruppo) -> tuple[Competizione, ...]:
    """Restituisce le competizioni di un gruppo.

    Args:
        gruppo: Il gruppo da filtrare.

    Returns:
        Le competizioni che vi appartengono, nell'ordine di dichiarazione.
    """
    return tuple(c for c in COMPETIZIONI if c.gruppo is gruppo)


def percorso_tabella(nome: str) -> Path:
    """Restituisce il percorso del Parquet di una tabella del magazzino.

    Args:
        nome: Nome logico della tabella, fra quelli elencati in :data:`TABELLE`.

    Returns:
        Il percorso assoluto del file ``.parquet`` corrispondente.

    Raises:
        ValueError: Se il nome non e' fra le tabelle previste. Meglio fallire
            qui che leggere un file inesistente con un errore poco chiaro.
    """
    if nome not in TABELLE:
        attese = ", ".join(TABELLE)
        msg = f"Tabella sconosciuta: {nome!r}. Attese: {attese}."
        raise ValueError(msg)
    return DATA_PROCESSED / f"{nome}.parquet"


def assicura_cartelle() -> None:
    """Crea le cartelle dei dati e dei modelli se non esistono gia'.

    Serve al primo avvio su una macchina pulita, dove git non ha materializzato
    le cartelle vuote.
    """
    for cartella in (DATA_RAW, DATA_PROCESSED, MODELS_DIR):
        cartella.mkdir(parents=True, exist_ok=True)
