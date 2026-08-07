"""Verifiche di `matches.parquet` e `player_stats.parquet` (M3-T2).

Le fixture descrivono la stessa partita di `test_transform.py` — finita 2 a 1
dopo i supplementari e i rigori — con l'aggiunta delle formazioni. La durata
effettiva e' **121 minuti**: il fischio finale del quarto periodo. Il quinto
periodo chiude al 128', ma sono i rigori, e nessuno e' in campo a giocarli nel
senso in cui lo si intende per i minuti giocati.

I minuti attesi, calcolati a mano dalla fixture:

===================  =======  ====================================
Giocatore            Minuti   Perche'
===================  =======  ====================================
Attaccante Uno           121  dall'inizio al fischio finale
Regista                   60  esce al 60'
Rigorista Uno             61  entra al 60', spezzoni **invertiti**
Ospite Uno               121  dall'inizio al fischio finale
Ospite Due                16  entra al 105'
Rigorista Due            121  dall'inizio al fischio finale
Panchinaro                 —  non entra, non compare in tabella
===================  =======  ====================================

Rigorista Uno e' il caso importante. I suoi due spezzoni sono::

    da 90:00 (p4) a 60:00 (p2)   inizio "Tactical Shift"
    da 60:00 (p2) a None         inizio "Substitution - On"

Il primo ha ``to`` **precedente** a ``from``: e' un difetto reale dei dati di
StatsBomb, presente nell'1,3 % degli spezzoni. Sommare le durate darebbe
-30 + 61 = 31 minuti. Prendendo il primo ingresso e l'ultima uscita si
ottengono i 61 corretti.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from football_analytics import ingest, transform
from football_analytics.config import EURO_2020
from football_analytics.transform import QualitaError

FIXTURES = Path(__file__).parent / "fixtures"

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

DURATA_ATTESA_SECONDI = 121 * 60


@pytest.fixture
def eventi() -> list[dict[str, Any]]:
    """Gli eventi del campione.

    Returns:
        La lista di eventi letta dalla fixture.
    """
    dati: list[dict[str, Any]] = json.loads(
        (FIXTURES / "eventi_campione.json").read_text(encoding="utf-8")
    )
    return dati


def prepara(radice: Path, match_id: int = 999) -> None:
    """Materializza eventi, formazioni ed elenco partite su disco.

    Args:
        radice: La cartella che fa da ``data/raw``.
        match_id: L'identificativo della partita.
    """
    for nome, cartella in (("eventi_campione", "events"), ("formazioni_campione", "lineups")):
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
            "home_score": META["gol_casa"],
            "away_score": META["gol_ospite"],
            "match_status_360": "available",
        }
    ]
    elenco = radice / "matches" / str(EURO_2020.competition_id) / f"{EURO_2020.season_id}.json"
    elenco.parent.mkdir(parents=True, exist_ok=True)
    elenco.write_text(json.dumps(partite), encoding="utf-8")


# ---------------------------------------------------------------------------
# La durata della partita
# ---------------------------------------------------------------------------


def test_la_durata_esclude_i_rigori_finali(eventi: list[dict[str, Any]]) -> None:
    # Il quinto periodo chiude al 128'. Includerlo darebbe giocatori in campo
    # per 128 minuti: e' successo davvero su quattro partite di Euro 2020.
    assert transform.durata_partita(eventi) == DURATA_ATTESA_SECONDI


def test_senza_fine_periodo_la_durata_e_zero() -> None:
    assert transform.durata_partita([]) == 0


# ---------------------------------------------------------------------------
# I minuti giocati
# ---------------------------------------------------------------------------


def minuti_per_nome() -> dict[str, int]:
    """Calcola i minuti di ogni giocatore della fixture.

    Returns:
        Mappa dal nome del giocatore ai minuti giocati.
    """
    righe = transform.presenze_di_partita(999, EURO_2020, META, DURATA_ATTESA_SECONDI)
    return {r["giocatore"]: r["minuti"] for r in righe}


def test_i_minuti_di_ogni_giocatore(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    prepara(tmp_path)

    assert minuti_per_nome() == {
        "Attaccante Uno": 121,
        "Regista": 60,
        "Rigorista Uno": 61,
        "Ospite Uno": 121,
        "Ospite Due": 16,
        "Rigorista Due": 121,
    }


def test_gli_spezzoni_invertiti_non_producono_minuti_negativi(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Sommare le durate degli spezzoni di Rigorista Uno darebbe 31 minuti:
    # -30 dal primo, che ha `to` precedente a `from`, piu' 61 dal secondo.
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    prepara(tmp_path)

    assert minuti_per_nome()["Rigorista Uno"] == 61


def test_chi_non_entra_non_compare(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Una riga di soli zeri non aggiunge informazione e moltiplicherebbe la
    # tabella: su Euro 2020 sono 849 giocatori mai entrati.
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    prepara(tmp_path)

    assert "Panchinaro" not in minuti_per_nome()


def test_i_minuti_non_sono_mai_negativi(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    prepara(tmp_path)
    righe = transform.presenze_di_partita(999, EURO_2020, META, DURATA_ATTESA_SECONDI)

    assert all(r["minuti"] >= 0 for r in righe)


def test_senza_file_formazioni_non_si_rompe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)

    assert transform.presenze_di_partita(999, EURO_2020, META, 5400) == []


# ---------------------------------------------------------------------------
# matches.parquet
# ---------------------------------------------------------------------------


def test_la_riga_partita_separa_gol_da_tiro_e_autogol(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    prepara(tmp_path)
    partite, _ = transform.costruisci_partite_e_presenze([EURO_2020])
    riga = partite.iloc[0]

    # Ufficiale 2-1. Da tiro: 1-1. L'autogol porta la Casalinga a 2.
    assert (riga["gol_casa"], riga["gol_ospite"]) == (2, 1)
    assert (riga["gol_casa_da_tiro"], riga["gol_ospite_da_tiro"]) == (1, 1)
    assert (riga["autogol_casa"], riga["autogol_ospite"]) == (1, 0)


def test_i_gol_da_tiro_piu_gli_autogol_danno_il_risultato(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    prepara(tmp_path)
    partite, _ = transform.costruisci_partite_e_presenze([EURO_2020])
    riga = partite.iloc[0]

    assert riga["gol_casa_da_tiro"] + riga["autogol_casa"] == riga["gol_casa"]
    assert riga["gol_ospite_da_tiro"] + riga["autogol_ospite"] == riga["gol_ospite"]


def test_gli_aggregati_escludono_i_rigori_finali(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    prepara(tmp_path)
    partite, _ = transform.costruisci_partite_e_presenze([EURO_2020])
    riga = partite.iloc[0]

    # Cinque tiri in tutto, due dei quali dal dischetto a fine partita.
    assert riga["tiri_casa"] + riga["tiri_ospite"] == 3
    assert bool(riga["ai_rigori"]) is True


def test_la_partita_registra_la_durata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    prepara(tmp_path)
    partite, _ = transform.costruisci_partite_e_presenze([EURO_2020])

    assert partite.iloc[0]["durata_minuti"] == 121


def test_la_tabella_partite_ha_i_tipi_dichiarati(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    prepara(tmp_path)
    partite, _ = transform.costruisci_partite_e_presenze([EURO_2020])

    assert list(partite.columns) == list(transform.TIPI_PARTITE)
    for colonna, tipo in transform.TIPI_PARTITE.items():
        assert str(partite[colonna].dtype) == tipo, colonna


# ---------------------------------------------------------------------------
# player_stats.parquet e il criterio di M3-T2
# ---------------------------------------------------------------------------


def costruisci_tutto(tmp_path: Path) -> tuple[Any, Any, Any]:
    """Costruisce le tre tabelle dalla fixture.

    Args:
        tmp_path: La cartella temporanea che fa da ``data/raw``.

    Returns:
        Tiri, partite e giocatori.
    """
    prepara(tmp_path)
    tiri = transform.costruisci_tiri([EURO_2020])
    partite, presenze = transform.costruisci_partite_e_presenze([EURO_2020])
    return tiri, partite, transform.costruisci_giocatori(tiri, presenze)


def test_la_somma_dei_gol_per_giocatore_torna(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # E' il criterio di completamento di M3-T2.
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    _, partite, giocatori = costruisci_tutto(tmp_path)

    transform.verifica_gol_giocatori(giocatori, partite)
    assert int(giocatori["gol"].sum()) == 2


def test_la_verifica_dei_gol_si_ferma_se_non_torna(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    _, partite, giocatori = costruisci_tutto(tmp_path)
    giocatori.loc[0, "gol"] = 99

    with pytest.raises(QualitaError, match="perde o duplica"):
        transform.verifica_gol_giocatori(giocatori, partite)


def test_i_rigori_finali_non_entrano_nelle_statistiche(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Rigorista Uno segna dal dischetto a fine supplementari. Contarlo
    # gli darebbe un gol e un xG per 90 minuti fuori scala.
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    _, _, giocatori = costruisci_tutto(tmp_path)
    riga = giocatori[giocatori["giocatore"] == "Rigorista Uno"].iloc[0]

    assert riga["gol"] == 0
    assert riga["tiri"] == 0


def test_i_valori_per_novanta_minuti(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    _, _, giocatori = costruisci_tutto(tmp_path)
    riga = giocatori[giocatori["giocatore"] == "Attaccante Uno"].iloc[0]

    assert riga["minuti"] == 121
    assert riga["gol"] == 1
    assert riga["gol_90"] == pytest.approx(1 / (121 / 90), rel=1e-4)


def test_la_soglia_dei_cinquecento_minuti(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Nessuno arriva a 500 minuti in una partita sola: la colonna esiste per
    # escludere dalle graduatorie senza togliere dalla tabella.
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    _, _, giocatori = costruisci_tutto(tmp_path)

    assert not giocatori["sopra_soglia"].any()
    assert len(giocatori) == 6


def test_la_tabella_giocatori_ha_i_tipi_dichiarati(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    _, _, giocatori = costruisci_tutto(tmp_path)

    assert list(giocatori.columns) == list(transform.TIPI_GIOCATORI)
    for colonna, tipo in transform.TIPI_GIOCATORI.items():
        assert str(giocatori[colonna].dtype) == tipo, colonna


def test_senza_presenze_la_tabella_e_vuota_ma_valida() -> None:
    vuota = transform.costruisci_giocatori(transform.applica_tipi([]), pd.DataFrame())
    assert len(vuota) == 0
    assert list(vuota.columns) == list(transform.TIPI_GIOCATORI)
