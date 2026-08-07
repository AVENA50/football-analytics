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

from typing import TYPE_CHECKING, Any

import pandas as pd
import pytest

from football_analytics import ingest, transform
from football_analytics.config import EURO_2020
from football_analytics.transform import QualitaError

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


# ---------------------------------------------------------------------------
# La durata della partita
# ---------------------------------------------------------------------------


def test_la_durata_esclude_i_rigori_finali(eventi: list[dict[str, Any]], durata: int) -> None:
    # Il quinto periodo chiude al 128'. Includerlo darebbe giocatori in campo
    # per 128 minuti: e' successo davvero su quattro partite di Euro 2020.
    assert transform.durata_partita(eventi) == durata


def test_senza_fine_periodo_la_durata_e_zero() -> None:
    assert transform.durata_partita([]) == 0


# ---------------------------------------------------------------------------
# I minuti giocati
# ---------------------------------------------------------------------------


def minuti_per_nome(meta: dict[str, Any], durata: int) -> dict[str, int]:
    """Calcola i minuti di ogni giocatore della partita di prova.

    Args:
        meta: I metadati della partita.
        durata: La durata effettiva in secondi.

    Returns:
        Mappa dal nome del giocatore ai minuti giocati.
    """
    righe = transform.presenze_di_partita(999, EURO_2020, meta, durata)
    return {r["giocatore"]: r["minuti"] for r in righe}


def test_i_minuti_di_ogni_giocatore(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    prepara: Callable[..., None],
    meta: dict[str, Any],
    durata: int,
) -> None:
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    prepara(tmp_path)

    assert minuti_per_nome(meta, durata) == {
        "Attaccante Uno": 121,
        "Regista": 60,
        "Rigorista Uno": 61,
        "Ospite Uno": 121,
        "Ospite Due": 16,
        "Rigorista Due": 121,
    }


def test_gli_spezzoni_invertiti_non_producono_minuti_negativi(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    prepara: Callable[..., None],
    meta: dict[str, Any],
    durata: int,
) -> None:
    # Sommare le durate degli spezzoni di Rigorista Uno darebbe 31 minuti:
    # -30 dal primo, che ha `to` precedente a `from`, piu' 61 dal secondo.
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    prepara(tmp_path)

    assert minuti_per_nome(meta, durata)["Rigorista Uno"] == 61


def test_chi_non_entra_non_compare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    prepara: Callable[..., None],
    meta: dict[str, Any],
    durata: int,
) -> None:
    # Una riga di soli zeri non aggiunge informazione e moltiplicherebbe la
    # tabella: su Euro 2020 sono 849 giocatori mai entrati.
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    prepara(tmp_path)

    assert "Panchinaro" not in minuti_per_nome(meta, durata)


def test_i_minuti_non_sono_mai_negativi(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    prepara: Callable[..., None],
    meta: dict[str, Any],
    durata: int,
) -> None:
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    prepara(tmp_path)
    righe = transform.presenze_di_partita(999, EURO_2020, meta, durata)

    assert all(r["minuti"] >= 0 for r in righe)


def test_senza_file_formazioni_non_si_rompe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, meta: dict[str, Any]
) -> None:
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)

    assert transform.presenze_di_partita(999, EURO_2020, meta, 5400) == []


# ---------------------------------------------------------------------------
# matches.parquet
# ---------------------------------------------------------------------------


@pytest.fixture
def partite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prepara: Callable[..., None]
) -> pd.DataFrame:
    """La tabella delle partite costruita dalla fixture.

    Args:
        tmp_path: La cartella temporanea che fa da ``data/raw``.
        monkeypatch: Per dirottare i percorsi.
        prepara: La funzione che materializza la partita di prova.

    Returns:
        La tabella con la sola partita di prova.
    """
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    prepara(tmp_path)
    tabella, _ = transform.costruisci_partite_e_presenze([EURO_2020])
    return tabella


def test_la_riga_partita_separa_gol_da_tiro_e_autogol(partite: pd.DataFrame) -> None:
    riga = partite.iloc[0]

    # Ufficiale 2-1. Da tiro: 1-1. L'autogol porta la Casalinga a 2.
    assert (riga["gol_casa"], riga["gol_ospite"]) == (2, 1)
    assert (riga["gol_casa_da_tiro"], riga["gol_ospite_da_tiro"]) == (1, 1)
    assert (riga["autogol_casa"], riga["autogol_ospite"]) == (1, 0)


def test_i_gol_da_tiro_piu_gli_autogol_danno_il_risultato(partite: pd.DataFrame) -> None:
    riga = partite.iloc[0]

    assert riga["gol_casa_da_tiro"] + riga["autogol_casa"] == riga["gol_casa"]
    assert riga["gol_ospite_da_tiro"] + riga["autogol_ospite"] == riga["gol_ospite"]


def test_gli_aggregati_escludono_i_rigori_finali(partite: pd.DataFrame) -> None:
    riga = partite.iloc[0]

    # Cinque tiri in tutto, due dei quali dal dischetto a fine partita.
    assert riga["tiri_casa"] + riga["tiri_ospite"] == 3
    assert bool(riga["ai_rigori"]) is True


def test_la_partita_registra_la_durata(partite: pd.DataFrame) -> None:
    assert partite.iloc[0]["durata_minuti"] == 121


def test_la_tabella_partite_ha_i_tipi_dichiarati(partite: pd.DataFrame) -> None:
    assert list(partite.columns) == list(transform.TIPI_PARTITE)
    for colonna, tipo in transform.TIPI_PARTITE.items():
        assert str(partite[colonna].dtype) == tipo, colonna


# ---------------------------------------------------------------------------
# player_stats.parquet e il criterio di M3-T2
# ---------------------------------------------------------------------------


@pytest.fixture
def tabelle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prepara: Callable[..., None]
) -> dict[str, pd.DataFrame]:
    """Le tre tabelle costruite dalla fixture.

    Args:
        tmp_path: La cartella temporanea che fa da ``data/raw``.
        monkeypatch: Per dirottare i percorsi.
        prepara: La funzione che materializza la partita di prova.

    Returns:
        Le tabelle ``shots``, ``matches`` e ``player_stats``.
    """
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    prepara(tmp_path)
    return transform.costruisci_tabelle([EURO_2020])


def test_la_somma_dei_gol_per_giocatore_torna(tabelle: dict[str, pd.DataFrame]) -> None:
    # E' il criterio di completamento di M3-T2.
    transform.verifica_gol_giocatori(tabelle["player_stats"], tabelle["matches"])
    assert int(tabelle["player_stats"]["gol"].sum()) == 2


def test_la_verifica_dei_gol_si_ferma_se_non_torna(
    tabelle: dict[str, pd.DataFrame],
) -> None:
    giocatori = tabelle["player_stats"].copy()
    giocatori.loc[0, "gol"] = 99

    with pytest.raises(QualitaError, match="perde o duplica"):
        transform.verifica_gol_giocatori(giocatori, tabelle["matches"])


def test_i_rigori_finali_non_entrano_nelle_statistiche(
    tabelle: dict[str, pd.DataFrame],
) -> None:
    # Rigorista Uno segna dal dischetto a fine supplementari. Contarlo gli
    # darebbe un gol e un xG per 90 minuti fuori scala.
    giocatori = tabelle["player_stats"]
    riga = giocatori[giocatori["giocatore"] == "Rigorista Uno"].iloc[0]

    assert riga["gol"] == 0
    assert riga["tiri"] == 0


def test_i_valori_per_novanta_minuti(tabelle: dict[str, pd.DataFrame]) -> None:
    giocatori = tabelle["player_stats"]
    riga = giocatori[giocatori["giocatore"] == "Attaccante Uno"].iloc[0]

    assert riga["minuti"] == 121
    assert riga["gol"] == 1
    assert riga["gol_90"] == pytest.approx(1 / (121 / 90), rel=1e-4)


def test_la_soglia_dei_cinquecento_minuti(tabelle: dict[str, pd.DataFrame]) -> None:
    # Nessuno arriva a 500 minuti in una partita sola: la colonna esiste per
    # escludere dalle graduatorie senza togliere dalla tabella.
    giocatori = tabelle["player_stats"]

    assert not giocatori["sopra_soglia"].any()
    assert len(giocatori) == 6


def test_la_tabella_giocatori_ha_i_tipi_dichiarati(
    tabelle: dict[str, pd.DataFrame],
) -> None:
    giocatori = tabelle["player_stats"]

    assert list(giocatori.columns) == list(transform.TIPI_GIOCATORI)
    for colonna, tipo in transform.TIPI_GIOCATORI.items():
        assert str(giocatori[colonna].dtype) == tipo, colonna


def test_due_grafie_dello_stesso_nome_danno_una_riga_sola() -> None:
    # Su Euro 2020 succede a tre giocatori: «Danny Ward» e «Daniel Ward»,
    # «Mykola Matvienko» e «Mykola Matviyenko», e Kante con l'apostrofo
    # raddoppiato. L'identita' e' l'identificativo, il nome e' un attributo.
    presenze = pd.DataFrame(
        [
            {
                "match_id": 1,
                "competizione": "euro_2020",
                "gruppo": "torneo",
                "stagione": "2020",
                "giocatore_id": 9914,
                "giocatore": "Danny Ward",
                "squadra": "Wales",
                "ruolo": "Goalkeeper",
                "minuti": 90,
            },
            {
                "match_id": 2,
                "competizione": "euro_2020",
                "gruppo": "torneo",
                "stagione": "2020",
                "giocatore_id": 9914,
                "giocatore": "Daniel Ward",
                "squadra": "Wales",
                "ruolo": "Goalkeeper",
                "minuti": 45,
            },
        ]
    )

    giocatori = transform.costruisci_giocatori(transform.applica_tipi([]), presenze)

    assert len(giocatori) == 1
    assert giocatori.iloc[0]["minuti"] == 135
    assert giocatori.iloc[0]["partite"] == 2
    # A parita' non c'e': 90 minuti battono 45, quindi vince «Danny Ward».
    assert giocatori.iloc[0]["giocatore"] == "Danny Ward"


def test_a_parita_di_minuti_il_nome_e_deterministico() -> None:
    # Senza un criterio esplicito, due esecuzioni potrebbero scegliere grafie
    # diverse. M3-T5 chiede l'opposto: stessi dati, stessi risultati.
    righe = [
        {
            "match_id": i,
            "competizione": "euro_2020",
            "gruppo": "torneo",
            "stagione": "2020",
            "giocatore_id": 1,
            "giocatore": nome,
            "squadra": "Wales",
            "ruolo": "Goalkeeper",
            "minuti": 90,
        }
        for i, nome in enumerate(("Zeta", "Alfa"))
    ]

    prima = transform.costruisci_giocatori(transform.applica_tipi([]), pd.DataFrame(righe))
    dopo = transform.costruisci_giocatori(
        transform.applica_tipi([]), pd.DataFrame(list(reversed(righe)))
    )

    assert prima.iloc[0]["giocatore"] == "Alfa"
    assert dopo.iloc[0]["giocatore"] == "Alfa"


def test_senza_presenze_la_tabella_e_vuota_ma_valida() -> None:
    vuota = transform.costruisci_giocatori(transform.applica_tipi([]), pd.DataFrame())

    assert len(vuota) == 0
    assert list(vuota.columns) == list(transform.TIPI_GIOCATORI)
