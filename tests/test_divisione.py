"""Verifiche della divisione train/test per partita (M5-T3).

Il criterio del backlog e' uno solo e non ammette sfumature: **l'intersezione
degli identificativi di partita fra addestramento e verifica dev'essere
vuota**. Il primo test di questo file e' quello.

Gli altri servono a proteggere le proprieta' che rendono la divisione
utilizzabile: riproducibilita' a parita' di seed, nessun tiro perso per strada,
proporzioni rispettate, classe positiva non sbilanciata.

C'e' anche un test che **dimostra il difetto**: divide gli stessi dati per tiro
invece che per partita e verifica che le partite finiscano da entrambe le
parti. Serve a lasciare per iscritto perche' la funzione esiste — fra sei mesi,
`dividi_per_partita` senza quel test sembrera' una complicazione inutile.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from football_analytics import model
from football_analytics.config import SEED


def campione(partite: int = 50, tiri_per_partita: int = 25, seed: int = 0) -> pd.DataFrame:
    """Costruisce un insieme di tiri finto ma realistico.

    Args:
        partite: Quante partite generare.
        tiri_per_partita: Quanti tiri per partita.
        seed: Radice del generatore.

    Returns:
        Una tabella con ``match_id`` e ``gol``, un gol ogni dieci tiri circa.
    """
    generatore = np.random.default_rng(seed)
    righe = partite * tiri_per_partita
    return pd.DataFrame(
        {
            "match_id": np.repeat(np.arange(1000, 1000 + partite), tiri_per_partita),
            "gol": generatore.random(righe) < 0.1,
            "distanza": generatore.uniform(5, 35, righe),
        }
    )


# ---------------------------------------------------------------------------
# Il criterio di M5-T3
# ---------------------------------------------------------------------------


def test_nessuna_partita_sta_da_entrambe_le_parti() -> None:
    train, test = model.dividi_per_partita(campione())

    assert set(train["match_id"]) & set(test["match_id"]) == set()


@pytest.mark.parametrize("seed", [0, 1, 42, 12345])
def test_l_intersezione_e_vuota_con_qualunque_seed(seed: int) -> None:
    train, test = model.dividi_per_partita(campione(), seed=seed)

    assert set(train["match_id"]).isdisjoint(set(test["match_id"]))


def test_dividere_per_tiro_invece_che_per_partita_perde_la_separazione() -> None:
    # Il difetto che `dividi_per_partita` esiste per evitare, messo per
    # iscritto: una divisione casuale a livello di tiro mette quasi tutte le
    # partite da entrambe le parti, e il modello valuta partite che ha gia'
    # visto in addestramento.
    dati = campione()
    generatore = np.random.default_rng(SEED)
    in_test = generatore.random(len(dati)) < 0.2

    ingenuo_train = dati[~in_test]
    ingenuo_test = dati[in_test]
    condivise = set(ingenuo_train["match_id"]) & set(ingenuo_test["match_id"])

    assert len(condivise) == dati["match_id"].nunique()


# ---------------------------------------------------------------------------
# Riproducibilita'
# ---------------------------------------------------------------------------


def test_lo_stesso_seed_da_la_stessa_divisione() -> None:
    prima = model.partite_di_verifica(campione(), seed=SEED)
    dopo = model.partite_di_verifica(campione(), seed=SEED)

    assert prima == dopo


def test_seed_diversi_danno_divisioni_diverse() -> None:
    assert model.partite_di_verifica(campione(), seed=1) != model.partite_di_verifica(
        campione(), seed=2
    )


def test_l_ordine_delle_righe_non_cambia_la_divisione() -> None:
    # Le partite vengono ordinate prima di essere mescolate. Senza, il
    # risultato dipenderebbe dall'ordine in cui pandas restituisce i valori
    # unici, e due esecuzioni sugli stessi dati potrebbero divergere.
    dati = campione()
    mescolati = dati.sample(frac=1.0, random_state=7)

    assert model.partite_di_verifica(dati) == model.partite_di_verifica(mescolati)


# ---------------------------------------------------------------------------
# Proprieta' della divisione
# ---------------------------------------------------------------------------


def test_nessun_tiro_va_perso() -> None:
    dati = campione()
    train, test = model.dividi_per_partita(dati)

    assert len(train) + len(test) == len(dati)


def test_le_partite_si_ritrovano_tutte() -> None:
    dati = campione()
    train, test = model.dividi_per_partita(dati)

    assert set(train["match_id"]) | set(test["match_id"]) == set(dati["match_id"])


@pytest.mark.parametrize("quota", [0.1, 0.2, 0.3, 0.5])
def test_la_quota_richiesta_viene_rispettata(quota: float) -> None:
    dati = campione(partite=200)
    _, test = model.dividi_per_partita(dati, quota_test=quota)

    assert test["match_id"].nunique() == pytest.approx(200 * quota, abs=1)


def test_la_frequenza_dei_gol_resta_simile() -> None:
    # La soglia e' espressa in **deviazioni standard**, non in punti
    # percentuali. Una soglia fissa sarebbe tarata sulla dimensione del
    # campione con cui e' stata scritta: su 12.500 tiri sintetici lo scarto
    # atteso e' tre volte quello dei 43.179 tiri veri, e un test che passa
    # sui secondi fallirebbe sui primi senza che nulla sia rotto.
    train, test = model.dividi_per_partita(campione(partite=500))
    r = model.riepilogo_divisione(train, test)

    frequenza = (train["gol"].sum() + test["gol"].sum()) / (len(train) + len(test))
    errore_standard = math.sqrt(frequenza * (1 - frequenza) * (1 / len(train) + 1 / len(test)))

    assert abs(r["gol_train"] - r["gol_test"]) < 4 * errore_standard


def test_il_riepilogo_conta_tutto() -> None:
    dati = campione(partite=100)
    train, test = model.dividi_per_partita(dati)
    r = model.riepilogo_divisione(train, test)

    assert r["partite_train"] + r["partite_test"] == 100
    assert r["tiri_train"] + r["tiri_test"] == len(dati)
    assert r["quota_test"] == pytest.approx(0.2, abs=0.05)


def test_una_sola_partita_finisce_tutta_da_una_parte() -> None:
    # Caso limite: con una partita sola la divisione non puo' che essere
    # sbilanciata, ma non deve rompersi ne' spezzare la partita.
    train, test = model.dividi_per_partita(campione(partite=1))

    assert (len(train) == 0) != (len(test) == 0)


def test_una_tabella_vuota_non_rompe_niente() -> None:
    vuota = campione(partite=0)
    train, test = model.dividi_per_partita(vuota)

    assert len(train) == 0
    assert len(test) == 0
    assert model.riepilogo_divisione(train, test)["quota_test"] == 0.0
