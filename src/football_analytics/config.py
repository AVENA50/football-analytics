"""Percorsi e costanti condivise da tutti gli strati del progetto.

Questo modulo e' l'unica fonte dei percorsi: nessun altro file costruisce a mano
una stringa come ``"data/processed/shots.parquet"``. Il motivo e' pratico —
l'app Streamlit puo' essere avviata da una directory di lavoro qualsiasi, e i
percorsi relativi si romperebbero senza dare un errore leggibile.

Gli identificativi delle competizioni arrivano in M2-T1: qui restano solo le
costanti che M1 puo' verificare.
"""

from __future__ import annotations

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
