"""Verifiche dei controlli di qualita' e del salvataggio (M3-T4 e M3-T5).

Un controllo che non e' mai stato visto fallire non e' un controllo: e' una
riga di codice che nessuno ha mai eseguito davvero. Per ogni anomalia che
`controlla` sa intercettare c'e' quindi un test che la introduce di proposito e
verifica che venga segnalata.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd
import pytest

from football_analytics import config, ingest, transform
from football_analytics.config import EURO_2020
from football_analytics.transform import QualitaError

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@pytest.fixture
def tabelle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prepara: Callable[..., None]
) -> dict[str, pd.DataFrame]:
    """Le tre tabelle costruite dalla fixture, tutte coerenti.

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


# ---------------------------------------------------------------------------
# Il percorso sano
# ---------------------------------------------------------------------------


def test_le_tabelle_coerenti_passano_i_controlli(tabelle: dict[str, pd.DataFrame]) -> None:
    transform.controlla(tabelle)


def test_costruisci_tabelle_restituisce_tutte_le_tabelle_dichiarate(
    tabelle: dict[str, pd.DataFrame],
) -> None:
    # Legato a config.TABELLE invece che a un elenco scritto qui: cosi'
    # aggiungere una tabella al magazzino non lascia indietro un test che
    # afferma il numero vecchio, come e' successo due volte.
    assert set(tabelle) == set(config.TABELLE)
    assert len(tabelle["shots"]) == 5
    assert len(tabelle["matches"]) == 1
    assert len(tabelle["player_stats"]) == 6


def test_una_lettura_sola_da_lo_stesso_risultato_di_due(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prepara: Callable[..., None]
) -> None:
    # `costruisci_tabelle` legge gli eventi una volta sola; le funzioni
    # separate li rileggono. Devono dire la stessa cosa.
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    prepara(tmp_path)

    insieme = transform.costruisci_tabelle([EURO_2020])
    tiri = transform.costruisci_tiri([EURO_2020])
    partite, _ = transform.costruisci_partite_e_presenze([EURO_2020])

    assert len(insieme["shots"]) == len(tiri)
    assert insieme["matches"]["gol_casa"].tolist() == partite["gol_casa"].tolist()


# ---------------------------------------------------------------------------
# Ogni anomalia viene segnalata
# ---------------------------------------------------------------------------


def guasta(tabelle: dict[str, pd.DataFrame], tabella: str, colonna: str, valore: Any) -> None:
    """Introduce un'anomalia nella prima riga di una tabella.

    Args:
        tabelle: Le tabelle da guastare.
        tabella: Quale tabella toccare.
        colonna: Quale colonna.
        valore: Il valore anomalo da scrivere.
    """
    tabelle[tabella] = tabelle[tabella].copy()
    tabelle[tabella][colonna] = tabelle[tabella][colonna].astype("object")
    tabelle[tabella].loc[0, colonna] = valore


def test_un_tiro_fuori_dal_campo_viene_segnalato(tabelle: dict[str, pd.DataFrame]) -> None:
    guasta(tabelle, "shots", "x", 999.0)
    with pytest.raises(QualitaError, match="fuori dal campo"):
        transform.controlla(tabelle)


def test_un_tiro_appena_oltre_la_linea_e_tollerato(tabelle: dict[str, pd.DataFrame]) -> None:
    # Su 44.000 tiri ce ne sono due a x = 120,1 e 120,2, calciati dalla linea
    # di fondo: il centro del pallone sporge di qualche centimetro. E' rumore
    # di misura, e un controllo che lo segnala verrebbe disattivato al primo
    # falso allarme.
    guasta(tabelle, "shots", "x", transform.LUNGHEZZA_CAMPO + 0.2)
    transform.controlla(tabelle)


def test_un_xg_impossibile_viene_segnalato(tabelle: dict[str, pd.DataFrame]) -> None:
    guasta(tabelle, "shots", "xg_statsbomb", 1.5)
    with pytest.raises(QualitaError, match="xG fuori dall'intervallo"):
        transform.controlla(tabelle)


def test_un_tiro_duplicato_viene_segnalato(tabelle: dict[str, pd.DataFrame]) -> None:
    tabelle["shots"] = pd.concat([tabelle["shots"], tabelle["shots"].head(1)])
    with pytest.raises(QualitaError, match="identificativi duplicati"):
        transform.controlla(tabelle)


def test_un_gol_incoerente_con_l_esito_viene_segnalato(
    tabelle: dict[str, pd.DataFrame],
) -> None:
    # La prima riga e' il gol del 12': ha gia' `gol` vero. Scriverci True
    # non guasterebbe niente — e infatti la prima versione di questo test
    # passava senza che il controllo scattasse mai.
    assert bool(tabelle["shots"].loc[0, "gol"]) is True

    guasta(tabelle, "shots", "gol", False)
    with pytest.raises(QualitaError, match="incoerente con l'esito"):
        transform.controlla(tabelle)


def test_un_risultato_che_non_torna_viene_segnalato(tabelle: dict[str, pd.DataFrame]) -> None:
    # E' l'identita' fra gol ufficiali, gol da tiro e autogol.
    guasta(tabelle, "matches", "autogol_casa", 7)
    with pytest.raises(QualitaError, match="gol casa non tornano"):
        transform.controlla(tabelle)


def test_una_durata_assurda_viene_segnalata(tabelle: dict[str, pd.DataFrame]) -> None:
    guasta(tabelle, "matches", "durata_minuti", 300)
    with pytest.raises(QualitaError, match="durate fuori dall'intervallo"):
        transform.controlla(tabelle)


def test_piu_gol_che_tiri_viene_segnalato(tabelle: dict[str, pd.DataFrame]) -> None:
    guasta(tabelle, "player_stats", "gol", 99)
    with pytest.raises(QualitaError, match="piu' gol che tiri"):
        transform.controlla(tabelle)


def test_un_tiro_senza_la_sua_partita_viene_segnalato(
    tabelle: dict[str, pd.DataFrame],
) -> None:
    guasta(tabelle, "shots", "match_id", 12345)
    with pytest.raises(QualitaError, match="non in matches"):
        transform.controlla(tabelle)


def test_i_problemi_vengono_riportati_tutti_insieme(
    tabelle: dict[str, pd.DataFrame],
) -> None:
    # Quando una trasformazione si rompe, di solito si rompe in piu' punti.
    # Scoprirli uno alla volta costa un'esecuzione completa per ognuno.
    guasta(tabelle, "shots", "x", 999.0)
    guasta(tabelle, "matches", "durata_minuti", 300)

    with pytest.raises(QualitaError) as errore:
        transform.controlla(tabelle)

    messaggio = str(errore.value)
    assert "fuori dal campo" in messaggio
    assert "durate fuori dall'intervallo" in messaggio


def test_tabelle_vuote_non_sono_un_errore() -> None:
    vuote = {
        "shots": transform.applica_tipi([]),
        "matches": transform.applica_tipi([], transform.TIPI_PARTITE),
        "player_stats": transform.applica_tipi([], transform.TIPI_GIOCATORI),
    }
    transform.controlla(vuote)


# ---------------------------------------------------------------------------
# Il salvataggio
# ---------------------------------------------------------------------------


def test_salva_scrive_il_parquet_e_rilegge_uguale(
    tabelle: dict[str, pd.DataFrame], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "DATA_PROCESSED", tmp_path / "processed")
    monkeypatch.setattr(transform, "percorso_tabella", lambda n: tmp_path / f"{n}.parquet")

    percorso = transform.salva("shots", tabelle["shots"])
    riletta = pd.read_parquet(percorso)

    assert percorso.exists()
    assert len(riletta) == len(tabelle["shots"])
    assert list(riletta.columns) == list(transform.TIPI_TIRI)


def test_due_esecuzioni_danno_lo_stesso_file(
    tabelle: dict[str, pd.DataFrame], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # E' il criterio di completamento di M3-T5: due esecuzioni sugli stessi
    # dati grezzi devono dare conteggi identici.
    monkeypatch.setattr(transform, "percorso_tabella", lambda n: tmp_path / f"{n}.parquet")

    primo = pd.read_parquet(transform.salva("shots", tabelle["shots"]))
    secondo = pd.read_parquet(transform.salva("shots", tabelle["shots"]))

    pd.testing.assert_frame_equal(primo, secondo)
