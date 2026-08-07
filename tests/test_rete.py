"""Verifiche di `passes.parquet` e `touches.parquet` (M3-T3).

Le due tabelle non contengono passaggi e tocchi: contengono la **rete** e la
**densita'**. E' una scelta di senso prima che di dimensione — la rete dei
passaggi mostra quante volte due giocatori si sono scambiati il pallone in
stagione, non chi ha passato a chi al 34'; la heatmap e' per definizione un
conteggio su griglia.

Che poi siano anche 28 e 11 volte piu' piccole e' una conseguenza, non
l'obiettivo: 1,68 milioni di passaggi diventano ~58.000 archi, 6,1 milioni di
tocchi diventano ~580.000 celle.
"""

from __future__ import annotations

import collections
from typing import TYPE_CHECKING, Any

import pandas as pd
import pytest

from football_analytics import ingest, transform
from football_analytics.config import EURO_2020
from football_analytics.transform import CELLE_X, CELLE_Y, QualitaError

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@pytest.fixture
def tabelle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prepara: Callable[..., None]
) -> dict[str, pd.DataFrame]:
    """Le cinque tabelle costruite dalla partita di prova.

    Args:
        tmp_path: La cartella temporanea che fa da ``data/raw``.
        monkeypatch: Per dirottare i percorsi.
        prepara: La funzione che materializza la partita di prova.

    Returns:
        Le tabelle del magazzino.
    """
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    prepara(tmp_path)
    return transform.costruisci_tabelle([EURO_2020])


# ---------------------------------------------------------------------------
# La griglia
# ---------------------------------------------------------------------------


def test_la_cella_di_un_angolo() -> None:
    assert transform.cella(0.0, 0.0) == (0, 0)


def test_la_cella_della_linea_di_porta() -> None:
    # x vale esattamente 120 sulla linea: senza il limite finirebbe fuori
    # griglia, e sarebbe la cella 24 su una griglia che arriva alla 23.
    assert transform.cella(120.0, 80.0) == (CELLE_X - 1, CELLE_Y - 1)


def test_la_cella_del_centrocampo() -> None:
    assert transform.cella(60.0, 40.0) == (CELLE_X // 2, CELLE_Y // 2)


@pytest.mark.parametrize(
    ("x", "y"),
    [(0.0, 0.0), (60.0, 40.0), (119.9, 79.9), (120.0, 80.0), (-1.0, -1.0), (999.0, 999.0)],
)
def test_ogni_cella_resta_nella_griglia(x: float, y: float) -> None:
    cx, cy = transform.cella(x, y)
    assert 0 <= cx < CELLE_X
    assert 0 <= cy < CELLE_Y


# ---------------------------------------------------------------------------
# La rete dei passaggi
# ---------------------------------------------------------------------------


def rete(righe: list[dict[str, Any]]) -> pd.DataFrame:
    """Costruisce la tabella dei passaggi da eventi grezzi.

    Args:
        righe: Gli eventi da accumulare.

    Returns:
        La tabella degli archi.
    """
    acc = transform.Accumulatori(collections.Counter(), collections.Counter(), {})
    transform.accumula(
        righe,
        EURO_2020,
        acc,
        {"casa": "Casalinga", "casa_id": 1, "ospite": "Ospite", "ospite_id": 2},
    )
    return transform.tabella_da_conteggi(
        acc.passaggi, transform.CHIAVE_PASSAGGI, "passaggi", transform.TIPI_PASSAGGI
    )


def passaggio(passatore: int, ricevitore: int | None, riuscito: bool = True) -> dict[str, Any]:
    """Costruisce un evento di passaggio minimo.

    Args:
        passatore: Identificativo di chi passa.
        ricevitore: Identificativo di chi riceve, oppure ``None``.
        riuscito: Se falso, aggiunge un esito che lo marca come sbagliato.

    Returns:
        L'evento, nella forma di StatsBomb.
    """
    blocco: dict[str, Any] = {}
    if ricevitore is not None:
        blocco["recipient"] = {"id": ricevitore, "name": f"G{ricevitore}"}
    if not riuscito:
        blocco["outcome"] = {"id": 9, "name": "Incomplete"}
    return {
        "type": {"id": 30, "name": "Pass"},
        "team": {"id": 1, "name": "Casalinga"},
        "player": {"id": passatore, "name": f"G{passatore}"},
        "location": [60.0, 40.0],
        "pass": blocco,
    }


def test_gli_archi_si_sommano() -> None:
    archi = rete([passaggio(1, 2), passaggio(1, 2), passaggio(1, 3)])

    assert len(archi) == 2
    coppia = archi[(archi["passatore_id"] == 1) & (archi["ricevitore_id"] == 2)]
    assert int(coppia.iloc[0]["passaggi"]) == 2


def test_i_passaggi_sbagliati_non_fanno_arco() -> None:
    # Il ricevitore di un passaggio sbagliato non e' un compagno, e un arco
    # della rete verso un avversario non vuol dire niente.
    assert len(rete([passaggio(1, 2, riuscito=False)])) == 0


def test_un_passaggio_senza_ricevitore_non_fa_arco() -> None:
    assert len(rete([passaggio(1, None)])) == 0


def test_la_tabella_passaggi_ha_i_tipi_dichiarati(
    tabelle: dict[str, pd.DataFrame],
) -> None:
    assert list(tabelle["passes"].columns) == list(transform.TIPI_PASSAGGI)
    for colonna, tipo in transform.TIPI_PASSAGGI.items():
        assert str(tabelle["passes"][colonna].dtype) == tipo, colonna


# ---------------------------------------------------------------------------
# La densita' dei tocchi
# ---------------------------------------------------------------------------


def test_i_tocchi_della_partita_di_prova(tabelle: dict[str, pd.DataFrame]) -> None:
    tocchi = tabelle["touches"]
    # Cinque tiri piu' un passaggio: sei eventi con posizione e giocatore,
    # l'autogol e i suoi gemelli non sono tocchi.
    assert int(tocchi["tocchi"].sum()) == 6


def test_la_pressione_non_e_un_tocco() -> None:
    # Un'azione senza palla, registrata alla posizione di chi pressa.
    assert "Pressure" not in transform.TIPI_TOCCO
    assert "Pass" in transform.TIPI_TOCCO


def test_la_tabella_tocchi_ha_i_tipi_dichiarati(tabelle: dict[str, pd.DataFrame]) -> None:
    assert list(tabelle["touches"].columns) == list(transform.TIPI_TOCCHI)
    for colonna, tipo in transform.TIPI_TOCCHI.items():
        assert str(tabelle["touches"][colonna].dtype) == tipo, colonna


# ---------------------------------------------------------------------------
# Le posizioni medie, che sono i nodi della rete
# ---------------------------------------------------------------------------


def test_la_posizione_media_e_esatta_non_approssimata(
    tabelle: dict[str, pd.DataFrame],
) -> None:
    # E' la media delle coordinate vere, non del centro delle celle: la
    # griglia serve alla heatmap, non ai nodi della rete.
    giocatori = tabelle["player_stats"]
    riga = giocatori[giocatori["giocatore"] == "Attaccante Uno"].iloc[0]

    assert riga["x_media"] == pytest.approx(110.0)
    assert riga["y_media"] == pytest.approx(40.0)


def test_chi_non_tocca_mai_ha_posizione_zero(tabelle: dict[str, pd.DataFrame]) -> None:
    # Rigorista Due calcia solo dal dischetto a fine partita, che e' un tiro
    # e quindi un tocco: ha una posizione. Il portiere mai entrato no.
    giocatori = tabelle["player_stats"]
    assert (giocatori["x_media"] >= 0).all()


# ---------------------------------------------------------------------------
# I controlli di qualita' sulle due tabelle
# ---------------------------------------------------------------------------


def test_un_arco_verso_se_stessi_viene_segnalato(
    tabelle: dict[str, pd.DataFrame],
) -> None:
    tabelle["passes"] = pd.DataFrame(
        [
            {
                "competizione": "euro_2020",
                "gruppo": "torneo",
                "stagione": "2020",
                "squadra": "Casalinga",
                "passatore_id": 7,
                "ricevitore_id": 7,
                "passaggi": 3,
            }
        ]
    )
    with pytest.raises(QualitaError, match="a se stesso"):
        transform.controlla(tabelle)


def test_una_cella_fuori_griglia_viene_segnalata(
    tabelle: dict[str, pd.DataFrame],
) -> None:
    tabelle["touches"] = pd.DataFrame(
        [
            {
                "competizione": "euro_2020",
                "gruppo": "torneo",
                "stagione": "2020",
                "giocatore_id": 7,
                "squadra": "Casalinga",
                "cella_x": 99,
                "cella_y": 0,
                "tocchi": 1,
            }
        ]
    )
    with pytest.raises(QualitaError, match="fuori dalla griglia"):
        transform.controlla(tabelle)


def test_le_cinque_tabelle_coerenti_passano(tabelle: dict[str, pd.DataFrame]) -> None:
    assert set(tabelle) == {"shots", "matches", "player_stats", "passes", "touches"}
    transform.controlla(tabelle)


def test_le_righe_sono_ordinate_e_riproducibili(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prepara: Callable[..., None]
) -> None:
    # M3-T5 chiede che due esecuzioni diano conteggi identici. I contatori
    # Python non garantiscono un ordine stabile fra processi diversi: senza
    # l'ordinamento esplicito i Parquet differirebbero byte per byte.
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    prepara(tmp_path)

    prima = transform.costruisci_tabelle([EURO_2020])
    dopo = transform.costruisci_tabelle([EURO_2020])

    for nome in ("passes", "touches"):
        pd.testing.assert_frame_equal(prima[nome], dopo[nome])
