"""Scarica i dati grezzi di StatsBomb per una o piu' competizioni.

E' ripartibile: se si interrompe, basta rilanciarlo e riprende da dove era.
Rilanciarlo su dati gia' completi non produce nessuna richiesta di contenuto e
termina in pochi secondi.

Uso::

    uv run python scripts/scarica_dati.py                      # solo la prima
    uv run python scripts/scarica_dati.py --gruppo torneo      # tutti i tornei
    uv run python scripts/scarica_dati.py --competizione serie_a_2015_16
    uv run python scripts/scarica_dati.py --tutte              # 1.753 partite
"""

from __future__ import annotations

import argparse
import time

from football_analytics import config, ingest
from football_analytics.config import Competizione, Gruppo


def scegli(argomenti: argparse.Namespace) -> tuple[Competizione, ...]:
    """Determina quali competizioni scaricare dagli argomenti ricevuti.

    Args:
        argomenti: Gli argomenti della riga di comando.

    Returns:
        Le competizioni selezionate, nell'ordine di scaricamento.
    """
    if argomenti.tutte:
        return config.COMPETIZIONI
    if argomenti.gruppo is not None:
        return config.del_gruppo(Gruppo(argomenti.gruppo))
    if argomenti.competizione is not None:
        return (config.competizione(argomenti.competizione),)
    return (config.PRIMA_COMPETIZIONE,)


def main() -> int:
    """Punto di ingresso da riga di comando.

    Returns:
        0 al termine.
    """
    analizzatore = argparse.ArgumentParser(description=__doc__)
    gruppo = analizzatore.add_mutually_exclusive_group()
    gruppo.add_argument("--tutte", action="store_true", help="tutte le competizioni")
    gruppo.add_argument(
        "--gruppo", choices=[g.value for g in Gruppo], help="un intero gruppo di competizioni"
    )
    gruppo.add_argument("--competizione", help="la chiave di una competizione")
    analizzatore.add_argument(
        "--lavoratori",
        type=int,
        default=ingest.LAVORATORI,
        help=f"richieste in parallelo (predefinito: {ingest.LAVORATORI})",
    )
    analizzatore.add_argument(
        "--campione",
        type=int,
        default=None,
        metavar="N",
        help="scarica solo le prime N partite, per ispezionare la forma dei dati",
    )
    analizzatore.add_argument(
        "--riepilogo",
        action="store_true",
        help="stampa il registro in Markdown e termina, senza scaricare niente",
    )
    argomenti = analizzatore.parse_args()

    if argomenti.riepilogo:
        print(ingest.riepilogo_markdown())
        return 0

    config.assicura_cartelle()
    scelte = scegli(argomenti)
    print(f"Competizioni da scaricare: {len(scelte)}\n")

    inizio = time.perf_counter()
    totali = ingest.Esito()
    for comp in scelte:
        esito = ingest.ingerisci(comp, argomenti.lavoratori, campione=argomenti.campione)
        totali.scaricate += esito.scaricate
        totali.saltate += esito.saltate
        totali.assenti += esito.assenti
        print()

    durata = time.perf_counter() - inizio
    print("-" * 60)
    print(f"File scaricati:  {totali.scaricate}")
    print(f"Gia' presenti:   {totali.saltate}")
    print(f"Non pubblicati:  {totali.assenti}")
    print(f"Durata:          {durata:.1f}s")
    if argomenti.campione is not None:
        print("\nCampione: il registro non e' stato aggiornato.")
        return 0

    print(f"\nRegistro aggiornato: {config.MANIFEST_PATH}\n")
    print(ingest.riepilogo_markdown())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
