"""Verifiche sulle competizioni scelte (M2-T1).

I test sono divisi in due gruppi. Quelli **offline** controllano la coerenza
interna del registro e girano ovunque, CI compresa. Quelli marcati ``rete``
interrogano davvero StatsBomb e verificano il criterio di completamento di
M2-T1: i conteggi dichiarati devono coincidere con quelli reali. In CI vengono
esclusi con ``-m "not rete"``, perche' una suite che dipende da un servizio
esterno diventa rossa per motivi che non hanno niente a che vedere con il
codice.

Per lanciare anche quelli::

    uv run pytest -m rete
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
import pytest
from statsbombpy import sb

from football_analytics import config
from football_analytics.config import CAMPIONATI, COMPETIZIONI, TORNEI_360, Copertura360, Gruppo

if TYPE_CHECKING:
    from football_analytics.config import Competizione


# ---------------------------------------------------------------------------
# Offline: coerenza del registro
# ---------------------------------------------------------------------------


def test_ci_sono_nove_competizioni() -> None:
    assert len(COMPETIZIONI) == 9


def test_le_chiavi_sono_uniche() -> None:
    chiavi = [c.chiave for c in COMPETIZIONI]
    assert len(set(chiavi)) == len(chiavi)


def test_gli_identificativi_sono_unici() -> None:
    coppie = [(c.competition_id, c.season_id) for c in COMPETIZIONI]
    assert len(set(coppie)) == len(coppie)


@pytest.mark.parametrize("comp", COMPETIZIONI, ids=lambda c: c.chiave)
def test_ogni_competizione_e_descritta(comp: Competizione) -> None:
    assert comp.nome
    assert comp.stagione
    assert comp.competition_id > 0
    assert comp.partite_attese > 0
    assert comp.season_id is None or comp.season_id > 0


def test_i_gruppi_partizionano_le_competizioni() -> None:
    per_gruppo = [config.del_gruppo(g) for g in Gruppo]
    assert sum(len(g) for g in per_gruppo) == len(COMPETIZIONI)


def test_i_campionati_sono_tutti_della_stessa_stagione() -> None:
    # E' la ragione per cui il confronto fra leghe ha senso: stagioni diverse
    # renderebbero impossibile distinguere la differenza fra i campionati da
    # quella fra le epoche.
    stagioni = {c.stagione for c in CAMPIONATI}
    assert stagioni == {"2015/2016"}


def test_nessun_campionato_ha_i_dati_360() -> None:
    assert all(c.copertura_360 is Copertura360.ASSENTE for c in CAMPIONATI)


def test_tutti_i_tornei_hanno_i_dati_360() -> None:
    # Il confronto base contro 360 si regge su questo: se un torneo entrasse
    # senza freeze frame, i due modelli non sarebbero addestrati sulle stesse
    # partite e il confronto perderebbe significato.
    assert all(c.copertura_360 is Copertura360.COMPLETA for c in TORNEI_360)


def test_solo_le_finali_richiedono_tutte_le_stagioni() -> None:
    senza_stagione = [c.chiave for c in COMPETIZIONI if c.tutte_le_stagioni]
    assert senza_stagione == ["champions_finali"]


def test_i_totali_attesi_di_partite() -> None:
    assert sum(c.partite_attese for c in CAMPIONATI) == 1517
    assert sum(c.partite_attese for c in TORNEI_360) == 218
    assert config.CHAMPIONS_FINALI.partite_attese == 18
    assert sum(c.partite_attese for c in COMPETIZIONI) == 1753


def test_si_parte_dalla_competizione_piu_piccola_con_i_360() -> None:
    prima = config.PRIMA_COMPETIZIONE
    assert prima.copertura_360 is Copertura360.COMPLETA
    assert prima.partite_attese == min(c.partite_attese for c in TORNEI_360)


def test_etichetta_unisce_nome_e_stagione() -> None:
    assert config.SERIE_A_2015_16.etichetta == "Serie A 2015/2016"
    assert config.CHAMPIONS_FINALI.etichetta == "Finali di Champions League 1971-2019"


def test_competizione_trova_per_chiave() -> None:
    assert config.competizione("serie_a_2015_16") is config.SERIE_A_2015_16


def test_competizione_rifiuta_una_chiave_inventata() -> None:
    with pytest.raises(ValueError, match="Competizione sconosciuta"):
        config.competizione("bundesliga_2023_24")


def test_del_gruppo_restituisce_i_campionati() -> None:
    assert config.del_gruppo(Gruppo.CAMPIONATO) == CAMPIONATI


# ---------------------------------------------------------------------------
# Rete: il criterio di completamento di M2-T1
# ---------------------------------------------------------------------------


def stagioni_di(comp: Competizione) -> list[int]:
    """Elenca le stagioni da considerare per una competizione.

    Args:
        comp: La competizione da espandere.

    Returns:
        La singola stagione dichiarata, oppure tutte quelle disponibili quando
        ``season_id`` e' ``None``.
    """
    if comp.season_id is not None:
        return [comp.season_id]
    elenco = sb.competitions()
    righe = elenco.loc[elenco["competition_id"] == comp.competition_id, "season_id"]
    return [int(s) for s in righe.unique()]


def conta_partite(comp: Competizione) -> int:
    """Conta le partite realmente disponibili su StatsBomb Open Data.

    Args:
        comp: La competizione da interrogare.

    Returns:
        Il numero di partite trovate, sommato su tutte le stagioni pertinenti.
    """
    return sum(len(sb.matches(comp.competition_id, s)) for s in stagioni_di(comp))


def copertura_reale(comp: Competizione) -> Copertura360:
    """Legge da StatsBomb la disponibilita' dichiarata dei freeze frame.

    Args:
        comp: La competizione da interrogare.

    Returns:
        La copertura ricavata dal campo ``match_available_360`` del file delle
        competizioni, aggregata su tutte le stagioni pertinenti.
    """
    elenco = sb.competitions()
    pertinenti = elenco[
        (elenco["competition_id"] == comp.competition_id)
        & (elenco["season_id"].isin(stagioni_di(comp)))
    ]
    # Attenzione: il campo assente arriva come NaN, e `bool(NaN)` vale True
    # perche' NaN e' un float diverso da zero. Serve un controllo esplicito.
    disponibili = [bool(pd.notna(v)) for v in pertinenti["match_available_360"]]
    if all(disponibili):
        return Copertura360.COMPLETA
    if any(disponibili):
        return Copertura360.PARZIALE
    return Copertura360.ASSENTE


@pytest.mark.rete
@pytest.mark.parametrize("comp", COMPETIZIONI, ids=lambda c: c.chiave)
def test_il_conteggio_reale_coincide_con_l_atteso(comp: Competizione) -> None:
    reale = conta_partite(comp)
    assert reale == comp.partite_attese, (
        f"{comp.etichetta}: attese {comp.partite_attese} partite, trovate {reale}. "
        "StatsBomb non pubblica sempre stagioni intere: verificare con "
        "scripts/esplora_open_data.py prima di scaricare."
    )


@pytest.mark.rete
@pytest.mark.parametrize("comp", COMPETIZIONI, ids=lambda c: c.chiave)
def test_la_copertura_360_coincide_con_l_atteso(comp: Competizione) -> None:
    reale = copertura_reale(comp)
    assert reale is comp.copertura_360, (
        f"{comp.etichetta}: dichiarata copertura 360 {comp.copertura_360}, "
        f"StatsBomb ne dichiara {reale}."
    )
