"""Fixture condivise dai test.

La partita di prova vive qui invece che dentro un singolo file di test: due
moduli la usano, e importare una funzione da un altro modulo di test funziona
con pytest ma confonde mypy, che vede lo stesso sorgente sotto due nomi.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from football_analytics.config import EURO_2020

if TYPE_CHECKING:
    from collections.abc import Callable

FIXTURES = Path(__file__).parent / "fixtures"

#: I metadati della partita di prova, coerenti con le fixture.
META: dict[str, Any] = {
    "casa": "Casalinga",
    "ospite": "Ospite",
    "gol_casa": 2,
    "gol_ospite": 1,
    "ha_360": True,
    "data": "2026-08-07",
    "giornata": 0,
    "fase": "Final",
}

#: La durata effettiva della partita di prova: il fischio del quarto periodo.
DURATA_SECONDI: int = 121 * 60


@pytest.fixture
def eventi() -> list[dict[str, Any]]:
    """Gli eventi della partita di prova.

    Returns:
        La lista di eventi letta dalla fixture.
    """
    dati: list[dict[str, Any]] = json.loads(
        (FIXTURES / "eventi_campione.json").read_text(encoding="utf-8")
    )
    return dati


@pytest.fixture
def meta() -> dict[str, Any]:
    """I metadati della partita di prova.

    Returns:
        Una copia, cosi' un test che la modifica non contagia gli altri.
    """
    return dict(META)


@pytest.fixture
def durata() -> int:
    """La durata effettiva della partita di prova, in secondi.

    Returns:
        I secondi del fischio finale del quarto periodo.
    """
    return DURATA_SECONDI


@pytest.fixture
def prepara() -> Callable[..., None]:
    """Restituisce la funzione che materializza la partita di prova su disco.

    Returns:
        Una funzione che accetta la radice di ``data/raw`` e, opzionalmente,
        l'identificativo della partita e il risultato ufficiale.
    """

    def _prepara(
        radice: Path,
        match_id: int = 999,
        gol_casa: int | None = None,
        gol_ospite: int | None = None,
    ) -> None:
        for nome, cartella in (
            ("eventi_campione", "events"),
            ("formazioni_campione", "lineups"),
        ):
            destinazione = radice / cartella / f"{match_id}.json"
            destinazione.parent.mkdir(parents=True, exist_ok=True)
            destinazione.write_text(
                (FIXTURES / f"{nome}.json").read_text(encoding="utf-8"), encoding="utf-8"
            )

        partite = [
            {
                "match_id": match_id,
                "match_date": META["data"],
                "match_week": 0,
                "competition_stage": {"id": 26, "name": META["fase"]},
                "home_team": {"home_team_name": META["casa"]},
                "away_team": {"away_team_name": META["ospite"]},
                "home_score": META["gol_casa"] if gol_casa is None else gol_casa,
                "away_score": META["gol_ospite"] if gol_ospite is None else gol_ospite,
                "match_status_360": "available",
            }
        ]
        elenco = radice / "matches" / str(EURO_2020.competition_id) / f"{EURO_2020.season_id}.json"
        elenco.parent.mkdir(parents=True, exist_ok=True)
        elenco.write_text(json.dumps(partite), encoding="utf-8")

    return _prepara
