"""Elenca cosa contiene davvero StatsBomb Open Data, con conteggi e dati 360.

Nasce da una sorpresa di M2-T1: il piano dava per scontate 380 partite di
Ligue 1 2021/22 e 306 di Bundesliga 2023/24, e ce ne sono rispettivamente 26 e
34. StatsBomb non pubblica sempre stagioni intere — a volte rilascia il
sottoinsieme legato a un tema, per esempio le partite di un singolo giocatore o
di una singola squadra.

Questo script non assume niente: legge l'elenco delle competizioni, conta le
partite di ciascuna e riporta la disponibilita' dei freeze frame. E' il
materiale su cui si sceglie quali competizioni useranno davvero il progetto.

Uso::

    uv run python scripts/esplora_open_data.py            # solo con dati 360
    uv run python scripts/esplora_open_data.py --tutte    # tutto l'Open Data
    uv run python scripts/esplora_open_data.py --min 100  # almeno 100 partite
"""

from __future__ import annotations

import argparse
import warnings
from typing import NamedTuple

import pandas as pd
from statsbombpy import sb
from statsbombpy.api_client import NoAuthWarning

# statsbombpy avvisa a ogni chiamata che non sono state fornite credenziali.
# E' corretto e voluto — usiamo l'Open Data — ma ripetuto ottanta volte rende
# illeggibile l'output.
warnings.filterwarnings("ignore", category=NoAuthWarning)

LARGHEZZA: int = 92


class Riga(NamedTuple):
    """Una competizione-stagione con i suoi numeri reali.

    Attributes:
        paese: Nazione o confederazione.
        competizione: Nome della competizione.
        stagione: Nome della stagione.
        competition_id: Identificativo StatsBomb della competizione.
        season_id: Identificativo StatsBomb della stagione.
        partite: Numero di partite realmente presenti.
        ha_360: Se la stagione dichiara la disponibilita' dei freeze frame.
    """

    paese: str
    competizione: str
    stagione: str
    competition_id: int
    season_id: int
    partite: int
    ha_360: bool


def raccogli(solo_360: bool, minimo: int) -> list[Riga]:
    """Interroga StatsBomb e costruisce l'elenco delle stagioni disponibili.

    Args:
        solo_360: Se vero, tiene solo le stagioni con i freeze frame.
        minimo: Numero minimo di partite perche' una stagione venga inclusa.

    Returns:
        Le righe che superano i filtri, ordinate per numero di partite.
    """
    elenco = sb.competitions()
    righe: list[Riga] = []

    for _, voce in elenco.iterrows():
        # Attenzione: quando il campo manca, pandas restituisce NaN, e
        # `bool(NaN)` vale True perche' NaN e' un float diverso da zero.
        # Un controllo di verita' diretto direbbe "si" per tutte le stagioni.
        ha_360 = bool(pd.notna(voce.get("match_available_360")))
        if solo_360 and not ha_360:
            continue

        cid = int(voce["competition_id"])
        sid = int(voce["season_id"])
        try:
            partite = len(sb.matches(cid, sid))
        except Exception as errore:
            print(f"  ! {voce['competition_name']} {voce['season_name']}: {errore}")
            continue

        if partite < minimo:
            continue

        righe.append(
            Riga(
                paese=str(voce["country_name"]),
                competizione=str(voce["competition_name"]),
                stagione=str(voce["season_name"]),
                competition_id=cid,
                season_id=sid,
                partite=partite,
                ha_360=ha_360,
            )
        )

    righe.sort(key=lambda r: r.partite, reverse=True)
    return righe


def stampa(righe: list[Riga]) -> None:
    """Mostra le righe in tabella, con i totali in fondo.

    Args:
        righe: Le stagioni da mostrare.
    """
    intestazione = f"{'Competizione':<38}{'Stagione':<12}{'id':>10}{'partite':>9}{'360':>6}"
    print(f"\n{intestazione}")
    print("-" * LARGHEZZA)
    for r in righe:
        nome = f"{r.competizione} ({r.paese})"[:37]
        ids = f"{r.competition_id},{r.season_id}"
        print(f"{nome:<38}{r.stagione:<12}{ids:>10}{r.partite:>9}{'si' if r.ha_360 else '-':>6}")

    print("-" * LARGHEZZA)
    con_360 = [r for r in righe if r.ha_360]
    partite_360 = sum(r.partite for r in con_360)
    print(f"Stagioni elencate: {len(righe)}   partite totali: {sum(r.partite for r in righe)}")
    print(f"Di cui con dati 360: {len(con_360)} stagioni, {partite_360} partite")


def main() -> int:
    """Punto di ingresso da riga di comando.

    Returns:
        0 al termine.
    """
    analizzatore = argparse.ArgumentParser(description=__doc__)
    analizzatore.add_argument(
        "--tutte", action="store_true", help="include anche le stagioni senza dati 360"
    )
    analizzatore.add_argument(
        "--min", type=int, default=0, dest="minimo", help="numero minimo di partite"
    )
    argomenti = analizzatore.parse_args()

    print("Interrogazione di StatsBomb Open Data in corso.")
    print("La prima esecuzione richiede qualche minuto; poi la cache la rende immediata.")
    stampa(raccogli(solo_360=not argomenti.tutte, minimo=argomenti.minimo))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
