# Football Analytics

[![CI](https://github.com/AVENA50/football-analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/AVENA50/football-analytics/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Una pipeline che legge i dati evento per evento di StatsBomb su tre campionati,
li riduce a tabelle compatte, addestra un modello che stima la probabilita' di
gol di ogni tiro, e li mette in una dashboard dove si possono esplorare
squadre, partite e giocatori.

> **Stato:** M1 — Fondamenta. Il repository esiste, il codice si installa, i
> controlli girano. Le milestone successive sono elencate in
> [`docs/milestones/README.md`](docs/milestones/README.md).

---

## Attribuzione dei dati

Questo progetto usa **[StatsBomb Open Data](https://github.com/statsbomb/open-data)**,
resi disponibili gratuitamente da StatsBomb. La citazione della fonte e' una
**condizione d'uso**, non una cortesia: compare qui, nel piede di ogni pagina
della dashboard e nella pagina Metodologia.

I dati sono soggetti alla licenza pubblicata nel repository di StatsBomb.
Nessuno stemma di club e nessuna fotografia di agenzia e' usato in questo
progetto.

---

## Cosa contiene

| Strato | Cartella | Cosa fa |
| --- | --- | --- |
| 1. Ingestione | `src/football_analytics/ingest.py` | Scarica i JSON in `data/raw/`, in modo incrementale e ripartibile |
| 2. Trasformazione | `src/football_analytics/transform.py` | Riduce gli eventi a Parquet compatti in `data/processed/` |
| 3. Modello | `src/football_analytics/model.py` | Due modelli xG: base e con dati 360 |
| 4. Dashboard | `app/` | Nove viste Streamlit, tema che cambia con la competizione |

**La regola che governa l'architettura:** l'app non legge mai i dati grezzi,
legge solo tabelle gia' preparate. Streamlit Community Cloud da' 1 GB di RAM, e
caricare i JSON a ogni visita significherebbe un'app che muore al primo utente.

---

## Installazione

Serve **Python 3.12** e **[uv](https://docs.astral.sh/uv/)**.

```bash
git clone https://github.com/AVENA50/football-analytics.git
cd football-analytics

uv sync --all-extras      # crea .venv e installa le versioni bloccate da uv.lock
```

Il file `uv.lock` blocca l'intero albero delle dipendenze, non solo quelle
dirette: e' cio' che rende l'installazione identica su una macchina diversa.

Verifica che tutto sia a posto:

```bash
uv run python -c "import football_analytics; print(football_analytics.__version__)"
```

## Controlli di qualita'

```bash
uv run ruff format .        # formatta
uv run ruff check --fix .   # lint, con le correzioni automatiche
uv run mypy                 # tipi, in modalita' strict
uv run pytest               # test con misura della copertura
```

Gli stessi comandi girano in CI a ogni push e a ogni pull request, in due job
separati: **Lint e tipi** e **Test**.

---

## Struttura

```
football-analytics/
├── src/football_analytics/   il pacchetto: config, ingest, transform, model, viz
├── scripts/                  build_dataset.py e train_model.py
├── app/                      la dashboard Streamlit
├── tests/                    test automatici, senza rete
├── notebooks/                esplorazione (M4), fuori dal pacchetto
├── data/raw/                 JSON scaricati — fuori da git
├── data/processed/           Parquet — versionati, sono cio' che l'app legge
├── models/                   xg_base.pkl e xg_360.pkl
└── docs/milestones/          una relazione per ogni milestone conclusa
```

---

## Le competizioni

Nove competizioni, 1.753 partite, divise per scopo. I conteggi sono **misurati**
con `scripts/esplora_open_data.py`, non stimati: il piano iniziale ne assumeva
altri e si e' rivelato sbagliato su meta' delle fonti — il racconto e' in
[`docs/milestones/M2-ingestione.md`](docs/milestones/M2-ingestione.md).

**Campionati 2015/16** — viste esplorative e modello base. Stessa stagione per
tutti e quattro, cosi' il confronto fra leghe non confonde la differenza fra i
campionati con quella fra le epoche.

| Competizione | id | Partite | Dati 360 |
| --- | --- | ---: | --- |
| La Liga 2015/16 | 11, 27 | 380 | no |
| Premier League 2015/16 | 2, 27 | 380 | no |
| Serie A 2015/16 | 12, 27 | 380 | no |
| Ligue 1 2015/16 | 7, 27 | 377 | no |

**Tornei per nazionali** — competizioni complete, con in piu' i file 360 di
contesto su quasi tutte le partite.

| Competizione | id | Partite | File 360 |
| --- | --- | ---: | ---: |
| Coppa del Mondo 2022 | 43, 106 | 64 | 64 |
| Coppa d'Africa 2023 | 1267, 107 | 52 | 1 |
| Campionato Europeo 2024 | 55, 282 | 51 | 51 |
| Campionato Europeo 2020 | 55, 43 | 51 | 51 |

**Finali di Champions League** — 18 finali dal 1971 al 2019, `competition_id`
16, senza freeze frame. Il modello base vi viene **applicato**, non addestrato:
un modello si valuta su dati che non ha mai visto.

### La domanda che regge il progetto

> **Quanto vale, davvero, sapere dove sono i difensori?**

Si addestrano **due modelli** sulle stesse identiche partite: uno con le
variabili ricavate dal fotogramma del tiro — difensori nel cono, distanza del
portiere — e uno senza. La differenza fra i loro punteggi, misurata sullo
stesso insieme di verifica, e' la risposta.

Il piano prevedeva di poterlo fare su poche centinaia di partite. Si e' poi
scoperto che `shot.freeze_frame` — la posizione di ogni giocatore al momento
del tiro, **dentro l'evento** — e' presente nel 95-99 % dei tiri di tutte le
competizioni, campionati del 2015/16 compresi. Il confronto gira quindi su
circa 44.000 tiri invece di 5.500.

E' una cosa diversa dai file `three-sixty/`, che coprono tutti gli eventi della
partita ma non riportano nomi ne' ruoli. Il dettaglio e' in
[`docs/milestones/M3-trasformazione.md`](docs/milestones/M3-trasformazione.md).

## Stato dello scaricamento

Generato da `data/raw/manifest.json`, che l'ingestione aggiorna da sola.
Rigenerabile con `uv run python scripts/scarica_dati.py --riepilogo`.

| Competizione | Gruppo | Partite | File 360 | Peso |
| --- | --- | ---: | ---: | ---: |
| La Liga 2015/2016 | campionato | 380 | 0 | 1.076 MB |
| Premier League 2015/2016 | campionato | 380 | 0 | 1.083 MB |
| Serie A 2015/2016 | campionato | 380 | 0 | 1.111 MB |
| Ligue 1 2015/2016 | campionato | 377 | 0 | 1.115 MB |
| Coppa del Mondo 2022 | torneo | 64 | 64 | 630 MB |
| Coppa d'Africa 2023 | torneo | 52 | 1 | 134 MB |
| Campionato Europeo 2024 | torneo | 51 | 51 | 535 MB |
| Campionato Europeo 2020 | torneo | 51 | 51 | 517 MB |
| Finali di Champions League | finali | 18 | 0 | 54 MB |
| **Totale** | | **1.753** | **167** | **6.255 MB** |

Lo scaricamento e' incrementale e ripartibile: rilanciarlo su dati gia' presenti
non produce nessuna richiesta di contenuto e termina in meno di un secondo.
Da zero richiede circa dieci minuti e **6,25 GB** di spazio libero.

```bash
uv run python scripts/scarica_dati.py --tutte           # tutto
uv run python scripts/scarica_dati.py --gruppo torneo   # solo un gruppo
uv run python scripts/scarica_dati.py --riepilogo       # rigenera questa tabella
```

Poi il magazzino:

```bash
uv run python scripts/build_dataset.py
```

I numeri del modello (log loss, Brier score, AUC, scarto dall'xG di StatsBomb)
compariranno qui quando M5 sara' conclusa. Non prima: in questo repository non
si scrivono numeri che non siano stati misurati.

---

## Licenza

Codice sotto licenza MIT. I dati appartengono a StatsBomb e sono soggetti alle
loro condizioni d'uso.
