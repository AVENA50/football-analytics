"""Verifiche della trasformazione degli eventi in `shots.parquet` (M3-T1).

Nessun test tocca la rete: gli eventi arrivano da `tests/fixtures/`, un
campione costruito a mano che contiene di proposito le trappole del conteggio
dei gol — i rigori finali e gli autogol.

Il campione descrive una partita che finisce **2 a 1**:

- Casalinga: un gol su azione (12'), piu' un autogol subito dall'Ospite (75');
- Ospite: un gol nei supplementari (118');
- piu' due tiri di rigore finali, uno segnato dalla Casalinga e uno sbagliato
  dall'Ospite, che **non** contano per il risultato.

Ogni modo plausibile di sbagliare produce un risultato diverso, e tutti e tre
sembrano ragionevoli finche' non li si confronta con il tabellino:

===========================================  =========
Come si conta                                Risultato
===========================================  =========
Corretto                                     2 a 1
Solo eventi ``Shot``, autogol ignorato       1 a 1
Rigori finali inclusi                        3 a 1
Autogol contato per entrambe le squadre      2 a 2
===========================================  =========

La fixture e' scritta a mano e non estratta da una partita vera proprio per
questo: una partita reale difficilmente conterrebbe tutte e tre le trappole
insieme.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from football_analytics import ingest, transform
from football_analytics.config import EURO_2020
from football_analytics.transform import QualitaError

FIXTURES = Path(__file__).parent / "fixtures"

META: dict[str, Any] = {
    "casa": "Casalinga",
    "ospite": "Ospite",
    "casa_id": 1,
    "ospite_id": 2,
    "gol_casa": 2,
    "gol_ospite": 1,
    "ha_360": True,
}


@pytest.fixture
def eventi() -> list[dict[str, Any]]:
    """Gli eventi del campione.

    Returns:
        La lista di eventi letta dalla fixture.
    """
    testo = (FIXTURES / "eventi_campione.json").read_text(encoding="utf-8")
    dati: list[dict[str, Any]] = json.loads(testo)
    return dati


# ---------------------------------------------------------------------------
# Il conteggio dei gol: il criterio di M3-T1
# ---------------------------------------------------------------------------


def test_il_risultato_calcolato_e_quello_ufficiale(eventi: list[dict[str, Any]]) -> None:
    assert transform.gol_per_squadra(eventi, META) == {"Casalinga": 2, "Ospite": 1}


def test_ignorare_l_autogol_darebbe_uno_a_uno(eventi: list[dict[str, Any]]) -> None:
    solo_tiri = [e for e in eventi if e["type"]["name"] == "Shot"]
    assert transform.gol_per_squadra(solo_tiri, META) == {"Casalinga": 1, "Ospite": 1}


def test_i_rigori_finali_non_contano(eventi: list[dict[str, Any]]) -> None:
    # Senza l'esclusione del periodo 5, la Casalinga risulterebbe a 3.
    senza_rigori = [e for e in eventi if e["period"] != transform.PERIODO_RIGORI]
    assert transform.gol_per_squadra(senza_rigori, META) == transform.gol_per_squadra(eventi, META)


def test_l_autogol_conta_una_volta_sola(eventi: list[dict[str, Any]]) -> None:
    # L'autogol compare due volte negli eventi, una per squadra. Contarle
    # entrambe darebbe 2 a 2 invece di 2 a 1.
    tipi = [e["type"]["name"] for e in eventi]
    assert tipi.count("Own Goal For") == 1
    assert tipi.count("Own Goal Against") == 1
    assert transform.gol_per_squadra(eventi, META)["Casalinga"] == 2


def test_l_autogol_va_alla_squadra_che_ne_beneficia(eventi: list[dict[str, Any]]) -> None:
    solo_autogol = [e for e in eventi if "Own Goal" in e["type"]["name"]]
    assert transform.gol_per_squadra(solo_autogol, META) == {"Casalinga": 1}


def test_verifica_risultato_passa_quando_torna(eventi: list[dict[str, Any]]) -> None:
    transform.verifica_risultato(1, transform.gol_per_squadra(eventi, META), META)


def test_verifica_risultato_si_ferma_quando_non_torna() -> None:
    with pytest.raises(QualitaError, match="non tornano con il risultato"):
        transform.verifica_risultato(1, {"Casalinga": 1, "Ospite": 2}, META)


def test_una_squadra_senza_gol_non_e_un_errore() -> None:
    meta = {**META, "gol_casa": 0, "gol_ospite": 1}
    transform.verifica_risultato(1, {"Ospite": 1}, meta)


# ---------------------------------------------------------------------------
# Le righe della tabella
# ---------------------------------------------------------------------------


def righe(eventi: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Costruisce le righe di tiro dal campione.

    Args:
        eventi: Gli eventi grezzi.

    Returns:
        Una riga per evento di tipo Shot.
    """
    tiri = [e for e in eventi if e["type"]["name"] == "Shot"]
    return [transform.riga_tiro(e, EURO_2020, 999, META) for e in tiri]


def test_si_estraggono_solo_i_tiri(eventi: list[dict[str, Any]]) -> None:
    # Otto eventi, di cui cinque tiri: passaggio e autogol restano fuori.
    assert len(righe(eventi)) == 5


def test_i_rigori_finali_restano_in_tabella_ma_marcati(eventi: list[dict[str, Any]]) -> None:
    # Escluderli perderebbe i gol dei rigori, che la vista Partite mostra;
    # non distinguerli falserebbe ogni risultato. Una colonna risolve entrambi.
    marcati = [r for r in righe(eventi) if r["rigori_finali"]]
    assert len(marcati) == 2
    assert all(r["periodo"] == 5 for r in marcati)


def test_il_gol_e_derivato_dall_esito(eventi: list[dict[str, Any]]) -> None:
    for riga in righe(eventi):
        assert riga["gol"] == (riga["esito"] == "Goal")


def test_le_colonne_del_fotogramma(eventi: list[dict[str, Any]]) -> None:
    primo, secondo = righe(eventi)[0], righe(eventi)[1]
    assert primo["ha_fotogramma"] is True
    assert primo["giocatori_fotogramma"] == 3
    assert primo["avversari_fotogramma"] == 2
    assert secondo["ha_fotogramma"] is False
    assert secondo["giocatori_fotogramma"] == 0


def test_i_campi_opzionali_assenti_diventano_falsi(eventi: list[dict[str, Any]]) -> None:
    # `under_pressure`, `first_time` e simili compaiono solo quando sono veri.
    # Un `if evento.get(...)` sbagliato qui produrrebbe silenziosamente
    # colonne tutte vere.
    secondo = righe(eventi)[1]
    assert secondo["sotto_pressione"] is False
    assert secondo["primo_tocco"] is False
    assert secondo["duello_aereo"] is False
    assert righe(eventi)[0]["sotto_pressione"] is True
    assert righe(eventi)[2]["duello_aereo"] is True


def test_casa_e_trasferta_sono_dedotte_dai_metadati(eventi: list[dict[str, Any]]) -> None:
    prima = righe(eventi)[0]
    assert prima["squadra"] == "Casalinga"
    assert prima["in_casa"] is True
    assert prima["avversario"] == "Ospite"

    seconda = righe(eventi)[1]
    assert seconda["in_casa"] is False
    assert seconda["avversario"] == "Casalinga"


# ---------------------------------------------------------------------------
# Tipi e dimensione
# ---------------------------------------------------------------------------


def test_la_tabella_ha_i_tipi_dichiarati(eventi: list[dict[str, Any]]) -> None:
    df = transform.applica_tipi(righe(eventi))
    assert list(df.columns) == list(transform.TIPI_TIRI)
    for colonna, tipo in transform.TIPI_TIRI.items():
        assert str(df[colonna].dtype) == tipo, colonna


def test_una_tabella_vuota_ha_comunque_le_colonne() -> None:
    df = transform.applica_tipi([])
    assert len(df) == 0
    assert list(df.columns) == list(transform.TIPI_TIRI)


# ---------------------------------------------------------------------------
# Il percorso completo, con i file su disco
# ---------------------------------------------------------------------------


def prepara_partita(radice: Path, match_id: int, gol_casa: int, gol_ospite: int) -> None:
    """Materializza su disco una partita finta, eventi e metadati.

    Args:
        radice: La cartella che fa da ``data/raw``.
        match_id: L'identificativo della partita.
        gol_casa: Il risultato ufficiale della squadra di casa.
        gol_ospite: Quello della squadra ospite.
    """
    eventi = (FIXTURES / "eventi_campione.json").read_text(encoding="utf-8")
    percorso = radice / "events" / f"{match_id}.json"
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(eventi, encoding="utf-8")

    partite = [
        {
            "match_id": match_id,
            "home_team": {"home_team_id": 1, "home_team_name": "Casalinga"},
            "away_team": {"away_team_id": 2, "away_team_name": "Ospite"},
            "home_score": gol_casa,
            "away_score": gol_ospite,
            "match_status_360": "available",
        }
    ]
    elenco = radice / "matches" / str(EURO_2020.competition_id) / f"{EURO_2020.season_id}.json"
    elenco.parent.mkdir(parents=True, exist_ok=True)
    elenco.write_text(json.dumps(partite), encoding="utf-8")


def test_costruisci_tiri_legge_i_file_e_verifica(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    prepara_partita(tmp_path, 999, gol_casa=2, gol_ospite=1)

    df = transform.costruisci_tiri([EURO_2020])

    assert len(df) == 5
    assert df["match_id"].unique().tolist() == [999]
    assert df["competizione"].unique().tolist() == ["euro_2020"]
    assert int(df["gol"].sum()) == 3  # due su azione piu' il rigore finale


def test_costruisci_tiri_si_ferma_su_un_risultato_sbagliato(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # E' il comportamento che protegge il progetto: meglio fermarsi qui che
    # pubblicare una dashboard con numeri che non tornano.
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    prepara_partita(tmp_path, 999, gol_casa=5, gol_ospite=0)

    with pytest.raises(QualitaError, match="Partita 999"):
        transform.costruisci_tiri([EURO_2020])


def test_la_verifica_si_puo_disattivare(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    prepara_partita(tmp_path, 999, gol_casa=5, gol_ospite=0)

    assert len(transform.costruisci_tiri([EURO_2020], verifica=False)) == 5


def test_le_partite_non_scaricate_vengono_saltate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Il magazzino si costruisce anche a scaricamento parziale: e' cosi' che
    # si prova la trasformazione su una competizione prima di prenderle tutte.
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    prepara_partita(tmp_path, 999, gol_casa=2, gol_ospite=1)
    (tmp_path / "events" / "999.json").unlink()

    assert len(transform.costruisci_tiri([EURO_2020])) == 0


def test_metadati_partite_legge_il_risultato_ufficiale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    prepara_partita(tmp_path, 999, gol_casa=2, gol_ospite=1)

    meta = transform.metadati_partite(EURO_2020)[999]

    assert meta["casa"] == "Casalinga"
    assert (meta["gol_casa"], meta["gol_ospite"]) == (2, 1)
    assert meta["ha_360"] is True


def test_le_categorie_pesano_meno_delle_stringhe(eventi: list[dict[str, Any]]) -> None:
    # Su 44.000 righe la differenza fra `object` e `category` sono megabyte di
    # RAM, e Streamlit Cloud ne ha uno solo.
    df = transform.applica_tipi(righe(eventi) * 200)
    tipizzata = df["squadra"].memory_usage(deep=True)
    grezza = df["squadra"].astype("object").memory_usage(deep=True)
    assert tipizzata < grezza
