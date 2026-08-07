"""Verifiche minime di M1: il pacchetto si importa e i percorsi sono coerenti.

Questi test non toccano la rete ne' i dati. Servono a dare a `pytest` qualcosa
da eseguire fin dal primo giorno: senza almeno un test, `pytest` esce con
codice 5 e la CI risulterebbe rossa su un repository perfettamente sano.
"""

from __future__ import annotations

import pytest

import football_analytics
from football_analytics import config


def test_il_pacchetto_si_importa() -> None:
    assert football_analytics.__version__ == "0.1.0"


def test_i_percorsi_sono_assoluti() -> None:
    for percorso in (
        config.PROJECT_ROOT,
        config.DATA_RAW,
        config.DATA_PROCESSED,
        config.MODELS_DIR,
    ):
        assert percorso.is_absolute()


def test_la_radice_contiene_pyproject() -> None:
    assert (config.PROJECT_ROOT / "pyproject.toml").is_file()


def test_percorso_tabella_costruisce_il_nome_giusto() -> None:
    atteso = config.DATA_PROCESSED / "shots.parquet"
    assert config.percorso_tabella("shots") == atteso


def test_percorso_tabella_rifiuta_una_tabella_inventata() -> None:
    with pytest.raises(ValueError, match="Tabella sconosciuta"):
        config.percorso_tabella("corner")


def test_assicura_cartelle_e_idempotente() -> None:
    config.assicura_cartelle()
    config.assicura_cartelle()
    assert config.DATA_RAW.is_dir()
    assert config.DATA_PROCESSED.is_dir()
    assert config.MODELS_DIR.is_dir()
