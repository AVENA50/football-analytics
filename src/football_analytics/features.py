"""Strato 3, prima parte: le variabili del modello xG.

Qui si trasforma una riga di ``shots.parquet`` in numeri che un modello puo'
usare. La separazione da ``transform.py`` non e' formale: il magazzino conserva
``x`` e ``y`` grezze proprio perche' la definizione di «angolo di tiro» e' una
scelta con piu' convenzioni possibili, e cambiarla non deve costare la
ricostruzione di sei milioni di eventi.

**Cosa resta fuori, e perche'.** I rigori non entrano nel modello. La ragione
ovvia e' che hanno xG praticamente fisso e non dipendono da dove sono i
difensori. La seconda l'ha trovata M4 ed e' piu' insidiosa: su 480 rigori solo
54 hanno il fotogramma, e quei 54 convertono all'11 % contro l'82 % degli
altri, perche' StatsBomb allega il fotogramma quasi solo quando il rigore
sbaglia. La presenza del dato dipende dall'esito. Un modello che vedesse quei
rigori imparerebbe una regola sul modo in cui i dati sono raccolti, non sul
calcio.
"""

from __future__ import annotations

from typing import Final

import numpy as np
import numpy.typing as npt
import pandas as pd

#: Il centro della porta nel sistema di coordinate di StatsBomb.
PORTA_X: Final[float] = 120.0
PORTA_Y: Final[float] = 40.0

#: I due pali. La porta e' larga otto unita', da 36 a 44.
PALO_SINISTRO_Y: Final[float] = 36.0
PALO_DESTRO_Y: Final[float] = 44.0
LARGHEZZA_PORTA: Final[float] = PALO_DESTRO_Y - PALO_SINISTRO_Y

#: I tipi di tiro che il modello **non** vede.
TIPI_ESCLUSI: Final[frozenset[str]] = frozenset({"Penalty"})

#: Le variabili base, nell'ordine in cui compaiono nella tabella.
VARIABILI_BASE: Final[tuple[str, ...]] = (
    "distanza",
    "angolo",
    "parte_corpo",
    "tipo",
    "schema",
    "sotto_pressione",
)

#: Quali fra le variabili base sono numeriche e quali categoriche. Serve al
#: preprocessore di M5-T4, che deve trattarle in modo diverso.
VARIABILI_NUMERICHE: Final[tuple[str, ...]] = ("distanza", "angolo")
VARIABILI_CATEGORICHE: Final[tuple[str, ...]] = ("parte_corpo", "tipo", "schema")
VARIABILI_BOOLEANE: Final[tuple[str, ...]] = ("sotto_pressione",)


def distanza(x: npt.ArrayLike, y: npt.ArrayLike) -> npt.NDArray[np.float64]:
    """Distanza euclidea dal centro della porta.

    Args:
        x: Coordinata lungo la lunghezza del campo, da 0 a 120.
        y: Coordinata lungo la larghezza, da 0 a 80.

    Returns:
        La distanza nelle stesse unita' del campo.
    """
    ax = np.asarray(x, dtype=np.float64)
    ay = np.asarray(y, dtype=np.float64)
    return np.hypot(PORTA_X - ax, PORTA_Y - ay)


def angolo_porta(x: npt.ArrayLike, y: npt.ArrayLike) -> npt.NDArray[np.float64]:
    """Angolo sotto cui la porta e' vista dal punto del tiro, in radianti.

    Calcolato con il teorema del coseno sul triangolo che ha per vertici il
    punto del tiro e i due pali. E' la definizione geometricamente esatta, e ha
    il pregio di rendere i casi noti verificabili a mente:

    - dalla bandierina del corner, sulla linea di porta, vale **zero**: i due
      pali sono allineati con chi tira;
    - da un punto sulla linea di porta fra i due pali vale **pi greco**: la
      porta occupa tutto il campo visivo;
    - dal dischetto vale circa **0,64 rad**, cioe' 36,9 gradi.

    Args:
        x: Coordinata lungo la lunghezza del campo.
        y: Coordinata lungo la larghezza.

    Returns:
        L'angolo in radianti, fra 0 e pi greco.
    """
    ax = np.asarray(x, dtype=np.float64)
    ay = np.asarray(y, dtype=np.float64)

    al_palo_sinistro = np.hypot(PORTA_X - ax, PALO_SINISTRO_Y - ay)
    al_palo_destro = np.hypot(PORTA_X - ax, PALO_DESTRO_Y - ay)
    prodotto = 2 * al_palo_sinistro * al_palo_destro

    # Un tiro esattamente su un palo annulla il prodotto: li' l'angolo non e'
    # definito e vale zero per continuita'.
    with np.errstate(divide="ignore", invalid="ignore"):
        coseno = np.where(
            prodotto > 0,
            (al_palo_sinistro**2 + al_palo_destro**2 - LARGHEZZA_PORTA**2) / prodotto,
            1.0,
        )

    # Il coseno puo' uscire di un'inezia dall'intervallo per errore numerico,
    # e arccos restituirebbe NaN: e' il tipo di difetto che compare su un tiro
    # ogni centomila e fa fallire un addestramento senza spiegare perche'.
    angolo: npt.NDArray[np.float64] = np.arccos(np.clip(coseno, -1.0, 1.0))
    return angolo


def tiri_modellabili(tiri: pd.DataFrame) -> pd.DataFrame:
    """Tiene solo i tiri che il modello xG deve vedere.

    Args:
        tiri: La tabella ``shots.parquet``.

    Returns:
        I tiri di gioco, senza rigori ne' tiri della serie finale.
    """
    return tiri[~tiri["rigori_finali"] & ~tiri["tipo"].isin(TIPI_ESCLUSI)].copy()


def variabili_base(tiri: pd.DataFrame) -> pd.DataFrame:
    """Costruisce le variabili base a partire dai tiri.

    Args:
        tiri: I tiri gia' filtrati da :func:`tiri_modellabili`.

    Returns:
        Una tabella con le colonne di :data:`VARIABILI_BASE`, piu' ``gol`` come
        variabile da prevedere e ``match_id`` per la divisione per partita.
    """
    fuori = pd.DataFrame(index=tiri.index)
    fuori["distanza"] = distanza(tiri["x"], tiri["y"]).astype("float32")
    fuori["angolo"] = angolo_porta(tiri["x"], tiri["y"]).astype("float32")
    for colonna in (*VARIABILI_CATEGORICHE, *VARIABILI_BOOLEANE):
        fuori[colonna] = tiri[colonna]
    fuori["gol"] = tiri["gol"]
    fuori["match_id"] = tiri["match_id"]
    return fuori
