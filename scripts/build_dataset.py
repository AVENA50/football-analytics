"""Ricostruisce il magazzino ``data/processed/`` con un comando solo.

Legge i dati grezzi gia' scaricati, li trasforma nelle tabelle del magazzino,
esegue i controlli di qualita' e scrive i Parquet. Se un controllo trova
un'anomalia **non scrive niente**: meglio un magazzino vecchio che uno
sbagliato, perche' un Parquet incoerente non ha nulla di visibilmente rotto e
nessuno lo controlla piu'.

E' rieseguibile: due esecuzioni sugli stessi dati grezzi producono conteggi
identici.

Uso::

    uv run python scripts/build_dataset.py                  # trasforma cio' che c'e'
    uv run python scripts/build_dataset.py --scarica        # scarica prima
    uv run python scripts/build_dataset.py --gruppo torneo  # solo un gruppo
    uv run python scripts/build_dataset.py --no-verifica    # salta i controlli
"""

from __future__ import annotations

import argparse
import time
from typing import TYPE_CHECKING

from football_analytics import config, ingest, transform
from football_analytics.config import Competizione, Gruppo
from football_analytics.transform import QualitaError

if TYPE_CHECKING:
    import pandas as pd

LARGHEZZA: int = 64


def scegli(argomenti: argparse.Namespace) -> tuple[Competizione, ...]:
    """Determina su quali competizioni lavorare.

    Args:
        argomenti: Gli argomenti della riga di comando.

    Returns:
        Le competizioni selezionate.
    """
    if argomenti.gruppo is not None:
        return config.del_gruppo(Gruppo(argomenti.gruppo))
    if argomenti.competizione is not None:
        return (config.competizione(argomenti.competizione),)
    return config.COMPETIZIONI


def riepiloga(tabelle: dict[str, pd.DataFrame]) -> None:
    """Stampa righe, colonne e peso su disco di ogni tabella scritta.

    Args:
        tabelle: Le tabelle appena salvate.
    """
    print(f"\n{'Tabella':<16}{'righe':>10}{'colonne':>9}{'peso':>12}")
    print("-" * LARGHEZZA)
    totale = 0
    for nome, tabella in tabelle.items():
        percorso = config.percorso_tabella(nome)
        peso = percorso.stat().st_size if percorso.exists() else 0
        totale += peso
        print(f"{nome:<16}{len(tabella):>10}{len(tabella.columns):>9}{peso / 1024 / 1024:>9.1f} MB")
    print("-" * LARGHEZZA)
    print(f"{'Totale':<16}{'':>19}{totale / 1024 / 1024:>9.1f} MB")

    # M3-T7 chiede di stare sotto i 50 MB per file e sotto i 100 in tutto:
    # GitHub avverte alla prima soglia e rifiuta alla seconda.
    if totale > config.LIMITE_TOTALE_BYTE:
        print("\nATTENZIONE: il magazzino supera i 100 MB complessivi.")


def main() -> int:
    """Punto di ingresso da riga di comando.

    Returns:
        0 se il magazzino e' stato ricostruito, 1 se un controllo ha fallito.
    """
    analizzatore = argparse.ArgumentParser(description=__doc__)
    scelta = analizzatore.add_mutually_exclusive_group()
    scelta.add_argument("--gruppo", choices=[g.value for g in Gruppo], help="un gruppo")
    scelta.add_argument("--competizione", help="la chiave di una competizione")
    analizzatore.add_argument(
        "--scarica", action="store_true", help="scarica i dati grezzi mancanti prima di trasformare"
    )
    analizzatore.add_argument(
        "--no-verifica",
        action="store_false",
        dest="verifica",
        help="salta il confronto con i risultati ufficiali e i controlli di qualita'",
    )
    argomenti = analizzatore.parse_args()

    config.assicura_cartelle()
    competizioni = scegli(argomenti)
    inizio = time.perf_counter()

    if argomenti.scarica:
        print(f"Scaricamento di {len(competizioni)} competizioni\n")
        for comp in competizioni:
            ingest.ingerisci(comp)
            print()

    print(f"Trasformazione di {len(competizioni)} competizioni...")
    tabelle = transform.costruisci_tabelle(competizioni, verifica=argomenti.verifica)

    if argomenti.verifica:
        try:
            transform.controlla(tabelle)
        except QualitaError as errore:
            print(f"\n{errore}")
            print("\nNiente e' stato scritto: il magazzino precedente resta intatto.")
            return 1
        print("Controlli di qualita': superati")

    for nome, tabella in tabelle.items():
        transform.salva(nome, tabella)

    riepiloga(tabelle)
    print(f"\nDurata: {time.perf_counter() - inizio:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
