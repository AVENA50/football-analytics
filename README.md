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

| Competizione | Stagione | Partite | Dati 360 |
| --- | --- | --- | --- |
| Ligue 1 | 2021/22 | 380 | si' |
| Bundesliga | 2023/24 | 306 | si' |
| Serie A | 2015/16 | 380 | **no** |
| Finali di Champions League | 1971–2019 | 18 | parziale |

La Serie A non ha i freeze frame, e da questo vincolo nasce la domanda piu'
interessante del progetto: **quanto vale, davvero, sapere dove sono i
difensori?** Si addestrano due modelli — uno con le variabili 360, uno senza —
e la differenza fra i loro punteggi e' la risposta misurata.

I numeri del modello (log loss, Brier score, AUC, scarto dall'xG di StatsBomb)
compariranno qui quando M5 sara' conclusa. Non prima: in questo repository non
si scrivono numeri che non siano stati misurati.

---

## Licenza

Codice sotto licenza MIT. I dati appartengono a StatsBomb e sono soggetti alle
loro condizioni d'uso.
