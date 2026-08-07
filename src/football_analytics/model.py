"""Strato 3, seconda parte: addestramento e valutazione del modello xG.

**La divisione train/test si fa per partita, non per tiro.** E' la regola che
decide se i numeri di questo progetto valgono qualcosa, e il modo piu' comune
di sbagliare senza accorgersene.

I tiri della stessa partita si somigliano: stesso campo, stesse due squadre,
stesso arbitro, stessa serata, spesso le stesse azioni ripetute. Se meta'
finiscono in addestramento e meta' in verifica, il modello ha gia' visto
qualcosa di quella partita quando la valuta, e il punteggio che ottiene e'
migliore di quello che otterrebbe su una partita mai vista. Il modello sembra
buono e non lo e'.

Il difetto e' invisibile: nessun errore, nessun avviso, solo metriche
lusinghiere. Si scopre quando il modello incontra dati veri — o quando in un
colloquio qualcuno chiede «come hai diviso i dati?».
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import numpy as np

from football_analytics.config import SEED

if TYPE_CHECKING:
    import pandas as pd

#: Quota di partite che finisce nell'insieme di verifica.
QUOTA_TEST: Final[float] = 0.2

#: La colonna che identifica il gruppo da non spezzare.
COLONNA_GRUPPO: Final[str] = "match_id"


def partite_di_verifica(
    dati: pd.DataFrame, quota_test: float = QUOTA_TEST, seed: int = SEED
) -> set[int]:
    """Sceglie quali partite finiscono nell'insieme di verifica.

    L'elenco delle partite viene **ordinato** prima di essere mescolato: senza,
    il risultato dipenderebbe dall'ordine in cui pandas restituisce i valori
    unici, e due esecuzioni sugli stessi dati potrebbero dare divisioni diverse.

    Args:
        dati: Le righe da dividere, con la colonna ``match_id``.
        quota_test: Frazione delle partite da destinare alla verifica.
        seed: Radice del generatore, per rendere la divisione riproducibile.

    Returns:
        Gli identificativi delle partite di verifica.
    """
    partite = np.array(sorted(dati[COLONNA_GRUPPO].unique()))
    generatore = np.random.default_rng(seed)
    generatore.shuffle(partite)
    quante = round(len(partite) * quota_test)
    return {int(p) for p in partite[:quante]}


def dividi_per_partita(
    dati: pd.DataFrame, quota_test: float = QUOTA_TEST, seed: int = SEED
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Divide i tiri in addestramento e verifica **senza spezzare le partite**.

    Args:
        dati: Le righe da dividere, con la colonna ``match_id``.
        quota_test: Frazione delle partite da destinare alla verifica.
        seed: Radice del generatore.

    Returns:
        Addestramento e verifica, nell'ordine. Nessuna partita compare in
        entrambi.
    """
    verifica = partite_di_verifica(dati, quota_test, seed)
    in_verifica = dati[COLONNA_GRUPPO].isin(verifica)
    return dati[~in_verifica].copy(), dati[in_verifica].copy()


def riepilogo_divisione(train: pd.DataFrame, test: pd.DataFrame) -> dict[str, float]:
    """Descrive una divisione, per poterla dichiarare invece che assumerla.

    Args:
        train: L'insieme di addestramento.
        test: L'insieme di verifica.

    Returns:
        Conteggi e frequenza dei gol nei due insiemi. La frequenza serve a
        controllare che la divisione non abbia sbilanciato la classe positiva:
        con un gol ogni dieci tiri, una divisione sfortunata puo' produrre due
        insiemi che non si somigliano.
    """
    return {
        "tiri_train": float(len(train)),
        "tiri_test": float(len(test)),
        "partite_train": float(train[COLONNA_GRUPPO].nunique()),
        "partite_test": float(test[COLONNA_GRUPPO].nunique()),
        "quota_test": float(len(test) / (len(train) + len(test)))
        if len(train) + len(test)
        else 0.0,
        "gol_train": float(train["gol"].mean()) if len(train) else 0.0,
        "gol_test": float(test["gol"].mean()) if len(test) else 0.0,
    }
