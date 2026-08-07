"""Verifiche dello strato di ingestione (M2-T2), tutte senza rete.

Il criterio di M2-T2 e' che la seconda esecuzione non scarichi nulla. Qui viene
verificato **contando le richieste**: una funzione finta sostituisce
`ingest.preleva` e tiene il conto di quante volte viene chiamata. Se la logica
incrementale si rompesse, il contatore lo direbbe subito.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from football_analytics import ingest
from football_analytics.config import EURO_2020, SERIE_A_2015_16
from football_analytics.ingest import Esito, Partita, Stato

if TYPE_CHECKING:
    from pathlib import Path

    import requests


class Finta:
    """Sostituto di :func:`ingest.preleva` che non tocca la rete.

    Attributes:
        chiamate: Gli indirizzi richiesti, nell'ordine.
        assenti: Indirizzi per cui simulare un 404.
    """

    def __init__(self, assenti: set[str] | None = None) -> None:
        """Prepara il sostituto.

        Args:
            assenti: Indirizzi da trattare come non pubblicati.
        """
        self.chiamate: list[str] = []
        self.assenti: set[str] = assenti or set()

    def __call__(self, sessione: requests.Session, url: str) -> bytes | None:
        """Finge di scaricare, registrando la richiesta.

        Args:
            sessione: Ignorata, presente per rispettare la firma.
            url: L'indirizzo richiesto.

        Returns:
            Un contenuto JSON minimo, oppure ``None`` per i 404 simulati.
        """
        del sessione
        self.chiamate.append(url)
        if url in self.assenti:
            return None
        return b'{"finto": true}'


# ---------------------------------------------------------------------------
# Indirizzi e percorsi
# ---------------------------------------------------------------------------


def test_indirizzo_punta_all_open_data() -> None:
    atteso = "https://raw.githubusercontent.com/statsbomb/open-data/master/data/events/1.json"
    assert ingest.indirizzo("events/1.json") == atteso


def test_i_percorsi_rispecchiano_la_struttura_di_statsbomb() -> None:
    assert ingest.percorso_partite(55, 43).parts[-3:] == ("matches", "55", "43.json")
    assert ingest.percorso_risorsa("events", 7).name == "7.json"
    assert ingest.percorso_risorsa("three-sixty", 7).parent.name == "three-sixty"


# ---------------------------------------------------------------------------
# Scrittura atomica
# ---------------------------------------------------------------------------


def test_salva_atomico_crea_le_cartelle(tmp_path: Path) -> None:
    destinazione = tmp_path / "a" / "b" / "c.json"
    ingest.salva_atomico(b"contenuto", destinazione)
    assert destinazione.read_bytes() == b"contenuto"


def test_salva_atomico_non_lascia_file_temporanei(tmp_path: Path) -> None:
    destinazione = tmp_path / "c.json"
    ingest.salva_atomico(b"contenuto", destinazione)
    assert list(tmp_path.iterdir()) == [destinazione]


def test_salva_atomico_sovrascrive(tmp_path: Path) -> None:
    destinazione = tmp_path / "c.json"
    ingest.salva_atomico(b"vecchio", destinazione)
    ingest.salva_atomico(b"nuovo", destinazione)
    assert destinazione.read_bytes() == b"nuovo"


# ---------------------------------------------------------------------------
# Logica incrementale: il criterio di M2-T2
# ---------------------------------------------------------------------------


def test_assicura_scarica_quando_manca(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    finta = Finta()
    monkeypatch.setattr(ingest, "preleva", finta)
    destinazione = tmp_path / "x.json"

    stato = ingest.assicura(None, "https://esempio/x.json", destinazione)  # type: ignore[arg-type]

    assert stato is Stato.SCARICATA
    assert len(finta.chiamate) == 1
    assert destinazione.exists()


def test_assicura_non_richiede_cio_che_esiste(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    finta = Finta()
    monkeypatch.setattr(ingest, "preleva", finta)
    destinazione = tmp_path / "x.json"
    destinazione.write_bytes(b"gia' qui")

    stato = ingest.assicura(None, "https://esempio/x.json", destinazione)  # type: ignore[arg-type]

    assert stato is Stato.SALTATA
    assert finta.chiamate == []
    assert destinazione.read_bytes() == b"gia' qui"


def test_la_seconda_esecuzione_non_scarica_nulla(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # E' il criterio di completamento di M2-T2, verificato contando le
    # richieste invece che fidandosi del tempo di esecuzione.
    finta = Finta()
    monkeypatch.setattr(ingest, "preleva", finta)
    risorse = [(f"https://esempio/{i}.json", tmp_path / f"{i}.json") for i in range(10)]

    primo = ingest.scarica_molte(None, risorse, lavoratori=4, silenzioso=True)  # type: ignore[arg-type]
    richieste_dopo_il_primo = len(finta.chiamate)
    secondo = ingest.scarica_molte(None, risorse, lavoratori=4, silenzioso=True)  # type: ignore[arg-type]

    assert primo.scaricate == 10
    assert richieste_dopo_il_primo == 10
    assert secondo.scaricate == 0
    assert secondo.saltate == 10
    assert len(finta.chiamate) == 10


def test_un_404_e_assente_non_un_errore(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    url = "https://esempio/mancante.json"
    monkeypatch.setattr(ingest, "preleva", Finta(assenti={url}))
    destinazione = tmp_path / "mancante.json"

    stato = ingest.assicura(None, url, destinazione)  # type: ignore[arg-type]

    assert stato is Stato.ASSENTE
    assert not destinazione.exists()


# ---------------------------------------------------------------------------
# Selezione delle risorse
# ---------------------------------------------------------------------------


def test_i_360_si_chiedono_solo_dove_esistono() -> None:
    partite = [Partita(match_id=1, ha_360=True), Partita(match_id=2, ha_360=False)]
    cartelle = [dest.parent.name for _, dest in ingest.risorse_di(partite)]
    assert cartelle.count("three-sixty") == 1
    assert cartelle.count("events") == 2
    assert cartelle.count("lineups") == 2


def test_senza_360_si_scaricano_due_file_per_partita() -> None:
    partite = [Partita(match_id=i, ha_360=False) for i in range(5)]
    assert len(ingest.risorse_di(partite)) == 10


def test_elenca_partite_legge_lo_stato_360(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    contenuto = [
        {"match_id": 11, "match_status_360": "available"},
        {"match_id": 22, "match_status_360": "unscheduled"},
        {"match_id": 33},
    ]
    destinazione = tmp_path / "matches" / "55" / "43.json"
    destinazione.parent.mkdir(parents=True)
    destinazione.write_text(json.dumps(contenuto), encoding="utf-8")

    partite = ingest.elenca_partite(None, EURO_2020)  # type: ignore[arg-type]

    assert partite == [
        Partita(11, ha_360=True),
        Partita(22, ha_360=False),
        Partita(33, ha_360=False),
    ]


# ---------------------------------------------------------------------------
# Registro dello scaricamento (M2-T3) e conteggio dei 360 (M2-T4)
# ---------------------------------------------------------------------------


def prepara_finti_file(radice: Path, partite: list[Partita]) -> None:
    """Crea file finti sul disco come se fossero stati scaricati.

    Args:
        radice: La cartella che fa da ``data/raw``.
        partite: Le partite da materializzare.
    """
    for partita in partite:
        for cartella in ("events", "lineups"):
            percorso = radice / cartella / f"{partita.match_id}.json"
            percorso.parent.mkdir(parents=True, exist_ok=True)
            percorso.write_bytes(b"x" * 1024)
        if partita.ha_360:
            percorso = radice / "three-sixty" / f"{partita.match_id}.json"
            percorso.parent.mkdir(parents=True, exist_ok=True)
            percorso.write_bytes(b"y" * 2048)


def test_file_presenti_guarda_il_disco(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    partite = [Partita(1, ha_360=True), Partita(2, ha_360=False)]
    prepara_finti_file(tmp_path, partite)

    assert ingest.file_presenti(partite) == {"events": 2, "lineups": 2, "three-sixty": 1}


def test_file_presenti_si_accorge_di_una_cancellazione(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    partite = [Partita(1, ha_360=False), Partita(2, ha_360=False)]
    prepara_finti_file(tmp_path, partite)
    (tmp_path / "events" / "1.json").unlink()

    assert ingest.file_presenti(partite)["events"] == 1


def test_il_manifest_registra_il_conteggio_dei_360(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # E' il criterio di M2-T4: il numero deve stare nel registro, ed e' il
    # fatto su cui si regge la scelta dei due modelli.
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    monkeypatch.setattr(ingest, "MANIFEST_PATH", tmp_path / "manifest.json")
    partite = [Partita(i, ha_360=i < 3) for i in range(5)]
    prepara_finti_file(tmp_path, partite)

    manifest = ingest.aggiorna_manifest(EURO_2020, partite)

    voce = manifest["competizioni"]["euro_2020"]
    assert voce["partite"] == 5
    assert voce["partite_con_360"] == 3
    assert voce["file"] == {"events": 5, "lineups": 5, "three-sixty": 3}
    assert manifest["totali"]["partite_con_360"] == 3


def test_il_manifest_e_scritto_su_disco(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    percorso = tmp_path / "manifest.json"
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    monkeypatch.setattr(ingest, "MANIFEST_PATH", percorso)
    partite = [Partita(1, ha_360=True)]
    prepara_finti_file(tmp_path, partite)

    ingest.aggiorna_manifest(EURO_2020, partite)

    assert json.loads(percorso.read_text(encoding="utf-8"))["competizioni"]["euro_2020"]


def test_il_manifest_non_cancella_le_altre_competizioni(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    monkeypatch.setattr(ingest, "MANIFEST_PATH", tmp_path / "manifest.json")
    partite = [Partita(1, ha_360=True)]
    prepara_finti_file(tmp_path, partite)

    ingest.aggiorna_manifest(EURO_2020, partite)
    manifest = ingest.aggiorna_manifest(SERIE_A_2015_16, [Partita(2, ha_360=False)])

    assert set(manifest["competizioni"]) == {"euro_2020", "serie_a_2015_16"}
    assert manifest["totali"]["competizioni"] == 2


def test_riepilogo_senza_dati_lo_dice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest, "MANIFEST_PATH", tmp_path / "assente.json")
    assert "Nessuna competizione" in ingest.riepilogo_markdown()


def test_riepilogo_produce_una_tabella(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest, "DATA_RAW", tmp_path)
    monkeypatch.setattr(ingest, "MANIFEST_PATH", tmp_path / "manifest.json")
    partite = [Partita(1, ha_360=True)]
    prepara_finti_file(tmp_path, partite)
    ingest.aggiorna_manifest(EURO_2020, partite)

    tabella = ingest.riepilogo_markdown()

    assert tabella.startswith("| Competizione |")
    assert "Campionato Europeo 2020" in tabella
    assert "**Totale**" in tabella


# ---------------------------------------------------------------------------
# Riepilogo degli esiti
# ---------------------------------------------------------------------------


def test_esito_conta_per_categoria() -> None:
    esito = Esito()
    for stato in (Stato.SCARICATA, Stato.SCARICATA, Stato.SALTATA, Stato.ASSENTE):
        esito.registra(stato)
    assert (esito.scaricate, esito.saltate, esito.assenti) == (2, 1, 1)
    assert esito.totale == 4


def test_scaricare_un_elenco_vuoto_non_fa_niente() -> None:
    assert ingest.scarica_molte(None, [], silenzioso=True).totale == 0  # type: ignore[arg-type]
