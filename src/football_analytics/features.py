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


#: Le variabili ricavate dal fotogramma del tiro.
VARIABILI_SPAZIALI: Final[tuple[str, ...]] = (
    "difensori_nel_cono",
    "distanza_portiere",
    "portiere_avanzato",
    "avversari_vicini",
    "compagni_in_area",
)

#: Limiti dell'area di rigore nel sistema di coordinate di StatsBomb.
AREA_X: Final[float] = 102.0
AREA_Y_MIN: Final[float] = 18.0
AREA_Y_MAX: Final[float] = 62.0

#: Entro quanti metri un avversario si considera addosso a chi tira.
RAGGIO_VICINANZA: Final[float] = 3.0


def nel_cono(
    x: npt.ArrayLike,
    y: npt.ArrayLike,
    tiro_x: npt.ArrayLike,
    tiro_y: npt.ArrayLike,
) -> npt.NDArray[np.bool_]:
    """Dice se un punto cade nel triangolo fra il tiro e i due pali.

    E' la definizione operativa di «difensore fra il pallone e la porta»: il
    triangolo che ha per vertici il punto del tiro e i due pali e' esattamente
    lo spazio che un difensore puo' occupare per intercettare.

    Il calcolo confronta da che parte il punto sta rispetto ai tre lati: se sta
    sempre dalla stessa parte, e' dentro. E' il metodo dei segni — nessuna
    divisione, quindi nessun caso degenere da gestire.

    Args:
        x: Ascissa dei giocatori da collocare.
        y: Ordinata dei giocatori.
        tiro_x: Ascissa del tiro, una per giocatore.
        tiro_y: Ordinata del tiro.

    Returns:
        Vero per i giocatori dentro il triangolo, bordo compreso.
    """
    px = np.asarray(x, dtype=np.float64)
    py = np.asarray(y, dtype=np.float64)
    tx = np.asarray(tiro_x, dtype=np.float64)
    ty = np.asarray(tiro_y, dtype=np.float64)

    # Prodotto vettoriale rispetto a ciascuno dei tre lati del triangolo
    # (tiro, palo sinistro, palo destro).
    lato_sinistro = (px - PORTA_X) * (ty - PALO_SINISTRO_Y) - (tx - PORTA_X) * (
        py - PALO_SINISTRO_Y
    )
    # Il lato fra i due pali sta tutto sulla linea di porta, quindi il termine
    # orizzontale si annulla e resta la sola distanza dalla linea: e' positivo
    # per chiunque sia davanti alla porta.
    linea_di_porta = (PORTA_X - px) * LARGHEZZA_PORTA
    lato_destro = (px - tx) * (PALO_DESTRO_Y - ty) - (PORTA_X - tx) * (py - ty)

    negativo = (lato_sinistro < 0) | (linea_di_porta < 0) | (lato_destro < 0)
    positivo = (lato_sinistro > 0) | (linea_di_porta > 0) | (lato_destro > 0)
    dentro: npt.NDArray[np.bool_] = ~(negativo & positivo)
    return dentro


def variabili_spaziali(tiri: pd.DataFrame, fotogrammi: pd.DataFrame) -> pd.DataFrame:
    """Ricava dal fotogramma le variabili che descrivono lo spazio.

    **Nessuna variabile viene riempita con zeri dove il fotogramma manca.** Uno
    zero in ``difensori_nel_cono`` significherebbe «nessun difensore davanti»,
    che e' l'opposto di «non lo sappiamo», e insegnerebbe al modello una cosa
    falsa. Dove il fotogramma non c'e', le variabili restano mancanti e il tiro
    esce dall'insieme su cui il modello spaziale viene addestrato.

    Args:
        tiri: I tiri, gia' filtrati da :func:`tiri_modellabili`.
        fotogrammi: La tabella ``freeze_frames.parquet``.

    Returns:
        Una tabella con le colonne di :data:`VARIABILI_SPAZIALI`, allineata
        all'indice dei tiri.
    """
    vuoto = pd.DataFrame(
        {colonna: np.full(len(tiri), np.nan, dtype="float32") for colonna in VARIABILI_SPAZIALI},
        index=tiri.index,
    )
    if fotogrammi.empty or tiri.empty:
        return vuoto

    unito = fotogrammi.merge(
        tiri[["shot_id", "x", "y"]].rename(columns={"x": "tiro_x", "y": "tiro_y"}),
        on="shot_id",
        how="inner",
    )
    if unito.empty:
        return vuoto

    unito["dentro"] = nel_cono(unito["x"], unito["y"], unito["tiro_x"], unito["tiro_y"])
    unito["distanza_dal_tiro"] = np.hypot(
        unito["x"].to_numpy() - unito["tiro_x"].to_numpy(),
        unito["y"].to_numpy() - unito["tiro_y"].to_numpy(),
    )
    avversari = unito[~unito["compagno"]]

    per_tiro = pd.DataFrame(index=pd.Index(fotogrammi["shot_id"].unique(), name="shot_id"))
    per_tiro["difensori_nel_cono"] = (
        avversari[avversari["dentro"] & ~avversari["portiere"]].groupby("shot_id").size()
    )
    per_tiro["avversari_vicini"] = (
        avversari[avversari["distanza_dal_tiro"] <= RAGGIO_VICINANZA].groupby("shot_id").size()
    )
    compagni = unito[unito["compagno"]]
    in_area = compagni[
        (compagni["x"] >= AREA_X) & (compagni["y"] >= AREA_Y_MIN) & (compagni["y"] <= AREA_Y_MAX)
    ]
    per_tiro["compagni_in_area"] = in_area.groupby("shot_id").size()

    # I conteggi mancano solo perche' il gruppo era vuoto: li' lo zero e' un
    # fatto, non un'ipotesi — il fotogramma c'era e non conteneva nessuno.
    for colonna in ("difensori_nel_cono", "avversari_vicini", "compagni_in_area"):
        per_tiro[colonna] = per_tiro[colonna].fillna(0)

    portieri = avversari[avversari["portiere"]].drop_duplicates(subset="shot_id")
    portieri = portieri.set_index("shot_id")
    per_tiro["distanza_portiere"] = portieri["distanza_dal_tiro"]
    # Quanto il portiere e' uscito dalla linea di porta.
    per_tiro["portiere_avanzato"] = PORTA_X - portieri["x"]

    allineato = per_tiro.reindex(tiri["shot_id"])
    allineato.index = tiri.index
    return allineato[list(VARIABILI_SPAZIALI)].astype("float32")


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
