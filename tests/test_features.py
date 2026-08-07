"""Verifiche delle variabili del modello xG (M5-T1).

Il criterio di M5-T1 chiede che ogni variabile sia verificata **su casi noti**.
Per la geometria i casi noti esistono davvero, e si calcolano a mano:

=============================  ==========  ==========
Da dove                        Distanza    Angolo
=============================  ==========  ==========
Bandierina del corner          40,0        0 gradi
Dischetto del rigore           12,0        36,87 gradi
Centrocampo                    60,0        7,63 gradi
Sulla linea, fra i due pali     0,0        180 gradi
=============================  ==========  ==========

I due estremi sono i piu' utili: un tiro dalla bandierina vede i pali allineati
e quindi un angolo nullo; un tiro sulla linea fra i pali ha la porta che occupa
tutto il campo visivo. Qualunque errore di segno, di unita' o di scambio fra i
pali rompe almeno uno dei due.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
import pytest

from football_analytics import features, ingest, transform
from football_analytics.config import EURO_2020
from football_analytics.features import PALO_DESTRO_Y, PORTA_X, PORTA_Y

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def gradi(radianti: float) -> float:
    """Converte in gradi, per rendere leggibili le asserzioni.

    Args:
        radianti: L'angolo in radianti.

    Returns:
        L'angolo in gradi.
    """
    return float(np.degrees(radianti))


# ---------------------------------------------------------------------------
# La distanza
# ---------------------------------------------------------------------------


def test_distanza_dal_dischetto() -> None:
    # Il dischetto e' a 12 unita' dalla linea, sull'asse della porta.
    assert float(features.distanza(108.0, 40.0)) == pytest.approx(12.0)


def test_distanza_dalla_bandierina() -> None:
    # Sulla linea di fondo, all'angolo: mezza larghezza del campo.
    assert float(features.distanza(120.0, 0.0)) == pytest.approx(40.0)


def test_distanza_dal_centrocampo() -> None:
    assert float(features.distanza(60.0, 40.0)) == pytest.approx(60.0)


def test_distanza_sulla_linea_in_mezzo_ai_pali() -> None:
    assert float(features.distanza(PORTA_X, PORTA_Y)) == pytest.approx(0.0)


def test_la_distanza_e_simmetrica_rispetto_all_asse() -> None:
    sopra = float(features.distanza(100.0, 30.0))
    sotto = float(features.distanza(100.0, 50.0))
    assert sopra == pytest.approx(sotto)


# ---------------------------------------------------------------------------
# L'angolo — dove i casi noti valgono davvero
# ---------------------------------------------------------------------------


def test_angolo_dalla_bandierina_e_nullo() -> None:
    # Sulla linea di porta all'altezza della bandierina i due pali sono
    # allineati con chi tira: la porta si vede di taglio, angolo zero.
    assert gradi(float(features.angolo_porta(120.0, 0.0))) == pytest.approx(0.0, abs=1e-6)


def test_angolo_sulla_linea_fra_i_pali_e_piatto() -> None:
    # Da li' la porta occupa tutto il campo visivo: 180 gradi.
    assert gradi(float(features.angolo_porta(PORTA_X, PORTA_Y))) == pytest.approx(180.0)


def test_angolo_dal_dischetto() -> None:
    # Triangolo isoscele: lati sqrt(12^2 + 4^2), base 8.
    # cos = (160 + 160 - 64) / (2 * 160) = 0,8  →  36,87 gradi.
    assert gradi(float(features.angolo_porta(108.0, 40.0))) == pytest.approx(36.87, abs=0.01)


def test_angolo_dal_centrocampo() -> None:
    assert gradi(float(features.angolo_porta(60.0, 40.0))) == pytest.approx(7.63, abs=0.01)


def test_angolo_su_un_palo_non_e_nan() -> None:
    # Il prodotto delle distanze si annulla: senza il caso esplicito uscirebbe
    # una divisione per zero e poi NaN.
    valore = float(features.angolo_porta(PORTA_X, PALO_DESTRO_Y))
    assert not math.isnan(valore)


def test_l_angolo_e_simmetrico_rispetto_all_asse() -> None:
    sopra = float(features.angolo_porta(100.0, 30.0))
    sotto = float(features.angolo_porta(100.0, 50.0))
    assert sopra == pytest.approx(sotto)


def test_l_angolo_si_restringe_allontanandosi() -> None:
    posizioni = [110.0, 100.0, 90.0, 60.0, 30.0]
    angoli = [float(features.angolo_porta(x, PORTA_Y)) for x in posizioni]
    assert angoli == sorted(angoli, reverse=True)


def test_l_angolo_si_restringe_spostandosi_di_lato() -> None:
    laterali = [40.0, 30.0, 20.0, 10.0, 0.0]
    angoli = [float(features.angolo_porta(100.0, y)) for y in laterali]
    assert angoli == sorted(angoli, reverse=True)


@pytest.mark.parametrize(
    ("x", "y"),
    [(0.0, 0.0), (60.0, 40.0), (119.9, 79.9), (120.0, 80.0), (120.2, 1.0), (35.0, 12.0)],
)
def test_l_angolo_resta_fra_zero_e_pi(x: float, y: float) -> None:
    valore = float(features.angolo_porta(x, y))
    assert 0.0 <= valore <= math.pi
    assert not math.isnan(valore)


def test_le_formule_funzionano_su_interi_vettori() -> None:
    xs = np.array([108.0, 120.0, 60.0])
    ys = np.array([40.0, 0.0, 40.0])
    assert features.distanza(xs, ys) == pytest.approx([12.0, 40.0, 60.0])
    assert np.degrees(features.angolo_porta(xs, ys)) == pytest.approx([36.87, 0.0, 7.63], abs=0.01)


# ---------------------------------------------------------------------------
# Il cono di tiro (M5-T2)
# ---------------------------------------------------------------------------


def dentro(gx: float, gy: float, tx: float, ty: float) -> bool:
    """Dice se un giocatore cade nel cono di un tiro.

    Args:
        gx: Ascissa del giocatore.
        gy: Ordinata del giocatore.
        tx: Ascissa del tiro.
        ty: Ordinata del tiro.

    Returns:
        Vero se il giocatore e' nel triangolo fra il tiro e i due pali.
    """
    return bool(
        features.nel_cono(np.array([gx]), np.array([gy]), np.array([tx]), np.array([ty]))[0]
    )


def test_un_difensore_davanti_al_pallone_e_nel_cono() -> None:
    assert dentro(114.0, 40.0, 108.0, 40.0)


def test_un_difensore_alle_spalle_di_chi_tira_non_lo_e() -> None:
    # Sta dietro al pallone: non puo' intercettare niente.
    assert not dentro(100.0, 40.0, 108.0, 40.0)


def test_un_difensore_dietro_la_porta_non_lo_e() -> None:
    assert not dentro(125.0, 40.0, 108.0, 40.0)


def test_un_difensore_di_lato_non_lo_e() -> None:
    assert not dentro(114.0, 55.0, 108.0, 40.0)


def test_un_difensore_sul_palo_e_dentro() -> None:
    # Il bordo conta: e' esattamente la posizione da cui si salva sulla linea.
    assert dentro(PORTA_X, 36.0, 108.0, 40.0)


def test_il_cono_si_restringe_avvicinandosi_alla_porta() -> None:
    # Da (110, 40) il triangolo a x = 112 va da y = 39,2 a y = 40,8: un
    # difensore a 38 e' di fianco, non davanti. E' controintuitivo a occhio,
    # ed e' il motivo per cui questo test esiste.
    assert dentro(112.0, 40.0, 110.0, 40.0)
    assert not dentro(112.0, 38.0, 110.0, 40.0)


def test_il_cono_di_un_tiro_laterale_e_obliquo() -> None:
    assert dentro(110.0, 30.0, 100.0, 20.0)
    assert not dentro(110.0, 60.0, 100.0, 20.0)


# ---------------------------------------------------------------------------
# Le variabili spaziali
# ---------------------------------------------------------------------------


def fotogramma_di_prova() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Un tiro con tre giocatori inquadrati, in posizioni scelte a mano.

    Returns:
        La tabella dei tiri e quella dei fotogrammi.
    """
    tiri = pd.DataFrame([{"shot_id": "s1", "x": 110.0, "y": 40.0}])
    fotogrammi = pd.DataFrame(
        [
            # portiere avversario, otto metri davanti, due fuori dalla linea
            {"shot_id": "s1", "x": 118.0, "y": 40.0, "compagno": False, "portiere": True},
            # difensore addosso a chi tira ma di fianco: fuori dal cono
            {"shot_id": "s1", "x": 112.0, "y": 38.0, "compagno": False, "portiere": False},
            # compagno in area
            {"shot_id": "s1", "x": 108.0, "y": 44.0, "compagno": True, "portiere": False},
        ]
    )
    return tiri, fotogrammi


def test_le_variabili_spaziali_sulla_configurazione_nota() -> None:
    tiri, fotogrammi = fotogramma_di_prova()
    v = features.variabili_spaziali(tiri, fotogrammi).iloc[0]

    assert v["distanza_portiere"] == pytest.approx(8.0)
    assert v["portiere_avanzato"] == pytest.approx(2.0)
    assert v["avversari_vicini"] == 1  # il difensore, a 2,83 metri
    assert v["compagni_in_area"] == 1


def test_il_portiere_non_conta_fra_i_difensori_nel_cono() -> None:
    # Il portiere e' dentro il cono, ma ha variabili proprie: contarlo anche
    # li' significherebbe misurare due volte la stessa cosa.
    tiri, fotogrammi = fotogramma_di_prova()
    assert float(features.variabili_spaziali(tiri, fotogrammi).iloc[0]["difensori_nel_cono"]) == 0.0


def test_un_difensore_nel_cono_viene_contato() -> None:
    tiri, fotogrammi = fotogramma_di_prova()
    aggiunto = pd.concat(
        [
            fotogrammi,
            pd.DataFrame(
                [{"shot_id": "s1", "x": 115.0, "y": 40.0, "compagno": False, "portiere": False}]
            ),
        ]
    )
    assert float(features.variabili_spaziali(tiri, aggiunto).iloc[0]["difensori_nel_cono"]) == 1.0


def test_senza_fotogramma_le_variabili_restano_mancanti() -> None:
    # E' la regola del piano: mai riempire con zeri. Uno zero significherebbe
    # «nessun difensore davanti», che e' l'opposto di «non lo sappiamo».
    tiri, _ = fotogramma_di_prova()
    vuoti = pd.DataFrame(columns=["shot_id", "x", "y", "compagno", "portiere"])

    v = features.variabili_spaziali(tiri, vuoti)

    assert v.isna().all(axis=None)


def test_uno_zero_e_un_fatto_quando_il_fotogramma_c_e() -> None:
    # Distinzione che regge tutto: se il fotogramma esiste e non contiene
    # difensori nel cono, lo zero e' una misura. Se il fotogramma manca, e'
    # un'ignoranza. I due casi non devono avere lo stesso valore.
    tiri, fotogrammi = fotogramma_di_prova()
    solo_portiere = fotogrammi[fotogrammi["portiere"]]

    v = features.variabili_spaziali(tiri, solo_portiere).iloc[0]

    assert float(v["difensori_nel_cono"]) == 0.0
    assert float(v["compagni_in_area"]) == 0.0
    assert not math.isnan(float(v["distanza_portiere"]))


def test_un_tiro_senza_il_suo_fotogramma_resta_mancante() -> None:
    tiri = pd.DataFrame(
        [{"shot_id": "s1", "x": 110.0, "y": 40.0}, {"shot_id": "s2", "x": 100.0, "y": 30.0}]
    )
    _, fotogrammi = fotogramma_di_prova()

    v = features.variabili_spaziali(tiri, fotogrammi)

    assert not v.iloc[0].isna().any()
    assert v.iloc[1].isna().all()


# ---------------------------------------------------------------------------
# La selezione dei tiri
# ---------------------------------------------------------------------------


@pytest.fixture
def tiri(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prepara: Callable[..., None]
) -> pd.DataFrame:
    """I tiri della partita di prova.

    Args:
        tmp_path: La cartella temporanea che fa da ``data/raw``.
        monkeypatch: Per dirottare i percorsi.
        prepara: La funzione che materializza la partita di prova.

    Returns:
        La tabella dei tiri.
    """
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    prepara(tmp_path)
    return transform.costruisci_tabelle([EURO_2020])["shots"]


def test_i_rigori_finali_restano_fuori(tiri: pd.DataFrame) -> None:
    assert not features.tiri_modellabili(tiri)["rigori_finali"].any()


def test_i_rigori_restano_fuori(tiri: pd.DataFrame) -> None:
    # Non solo per l'xG fisso: su 480 rigori solo 54 hanno il fotogramma, e
    # quei 54 convertono all'11 % contro l'82 % degli altri. La presenza del
    # dato dipende dall'esito, ed e' esattamente cio' che un modello impara
    # volentieri e non dovrebbe.
    assert "Penalty" not in set(features.tiri_modellabili(tiri)["tipo"])


def test_restano_i_tiri_di_gioco(tiri: pd.DataFrame) -> None:
    # Cinque tiri nella fixture: uno su azione, uno da corner, uno di testa
    # nei supplementari, due rigori della serie finale.
    assert len(features.tiri_modellabili(tiri)) == 3


# ---------------------------------------------------------------------------
# La tabella delle variabili
# ---------------------------------------------------------------------------


def test_la_tabella_ha_le_colonne_dichiarate(tiri: pd.DataFrame) -> None:
    v = features.variabili_base(features.tiri_modellabili(tiri))
    attese = [*features.VARIABILI_BASE, "gol", "match_id"]
    assert set(v.columns) == set(attese)


def test_le_variabili_non_hanno_valori_mancanti(tiri: pd.DataFrame) -> None:
    v = features.variabili_base(features.tiri_modellabili(tiri))
    assert not v[list(features.VARIABILI_NUMERICHE)].isna().to_numpy().any()


def test_match_id_serve_alla_divisione_per_partita(tiri: pd.DataFrame) -> None:
    # M5-T3 dividera' train e test **per partita**: senza questa colonna
    # sarebbe impossibile, e tiri della stessa partita finirebbero da
    # entrambe le parti.
    v = features.variabili_base(features.tiri_modellabili(tiri))
    assert set(v["match_id"]) == {999}


def test_la_distanza_calcolata_coincide_con_la_formula(tiri: pd.DataFrame) -> None:
    modellabili = features.tiri_modellabili(tiri)
    v = features.variabili_base(modellabili)
    attesa = np.hypot(PORTA_X - modellabili["x"].to_numpy(), PORTA_Y - modellabili["y"].to_numpy())
    assert v["distanza"].to_numpy() == pytest.approx(attesa, abs=1e-4)


def test_le_categoriche_e_le_numeriche_coprono_le_variabili_base() -> None:
    dichiarate = {
        *features.VARIABILI_NUMERICHE,
        *features.VARIABILI_CATEGORICHE,
        *features.VARIABILI_BOOLEANE,
    }
    assert dichiarate == set(features.VARIABILI_BASE)


def test_una_tabella_vuota_non_rompe_niente() -> None:
    vuota: pd.DataFrame = pd.DataFrame(
        {
            "x": pd.Series(dtype="float32"),
            "y": pd.Series(dtype="float32"),
            "parte_corpo": pd.Series(dtype="category"),
            "tipo": pd.Series(dtype="category"),
            "schema": pd.Series(dtype="category"),
            "sotto_pressione": pd.Series(dtype="bool"),
            "gol": pd.Series(dtype="bool"),
            "match_id": pd.Series(dtype="int32"),
        }
    )
    risultato: Any = features.variabili_base(vuota)
    assert len(risultato) == 0
