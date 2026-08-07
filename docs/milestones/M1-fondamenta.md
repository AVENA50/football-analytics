# M1 — Fondamenta

> Il repository esiste, il codice si installa con un comando, e lint, tipi e
> test girano da soli a ogni push.

**Periodo:** dal 2026-08-07 al \_\_ · **Issue chiuse:** \_\_ / 7 · **Commit:** \_\_

---

## 1. Cosa è stato costruito

<!-- Da completare a fine milestone. Traccia: prima di M1 non esisteva niente;
adesso esiste un pacchetto Python installabile, con una struttura a quattro
strati già predisposta, dipendenze bloccate a versione esatta, e una CI che
impedisce a codice non formattato o non tipizzato di entrare in main. -->

## 2. File creati e modificati

| File | Cosa fa |
| --- | --- |
| `pyproject.toml` | Metadati, dipendenze bloccate, configurazione di ruff, mypy, pytest e coverage |
| `uv.lock` | L'albero completo delle dipendenze risolto: è ciò che rende l'installazione identica altrove |
| `.python-version` | Fissa Python 3.12 per uv e per `actions/setup-python` |
| `.gitignore` | Esclude `data/raw/`, gli ambienti e le cache; **non** esclude `data/processed/` |
| `.github/workflows/ci.yml` | Due job: «Lint e tipi» e «Test» |
| `.streamlit/config.toml` | Tema di partenza, tavolozza verde |
| `src/football_analytics/__init__.py` | Versione del pacchetto e attribuzione |
| `src/football_analytics/config.py` | Unica fonte dei percorsi e delle costanti condivise |
| `src/football_analytics/py.typed` | Dichiara il pacchetto tipizzato (PEP 561) |
| `tests/test_impalcatura.py` | Sei test: import, percorsi assoluti, `percorso_tabella`, idempotenza |
| `docs/milestones/_template.md` | Le sette sezioni da compilare a ogni milestone |
| `docs/milestones/README.md` | Indice e stato di avanzamento |
| `README.md` | Descrizione, installazione, **attribuzione a StatsBomb** |
| `NOTES.md` | Il diario degli inciampi |
| `setup-backlog.sh` | Crea su GitHub 11 etichette, 8 milestone e 64 issue |

## 3. Decisioni tecniche

### Scelta: `ruff` al posto di `black` + `flake8` + `isort`

**Alternativa scartata:** la triade classica, con `black` per il formato,
`flake8` (più i suoi plugin) per il lint e `isort` per gli import.

**Perché:** sono tre strumenti, tre file di configurazione e tre occasioni di
disaccordo — il caso tipico è `black` che formatta una riga e `flake8` che poi
la segnala come troppo lunga. `ruff` fa i tre lavori con una configurazione
sola dentro `pyproject.toml`, e in Rust: su questo repository gira in
millisecondi, il che significa che si può lanciare a ogni salvataggio invece
che solo prima del commit. Lo strumento che si usa davvero vale più di quello
teoricamente più completo.

### Scelta: versioni bloccate a valore esatto (`==`), non a intervallo

**Alternativa scartata:** `pandas>=3.0` e simili, cioè lasciare che
l'installazione prenda l'ultima versione compatibile.

**Perché:** il criterio di M1-T3 è che un'installazione da zero su una macchina
pulita produca le stesse versioni. Con un intervallo aperto non è vero: fra sei
mesi una minor release potrebbe cambiare un default di `pandas` e la pipeline
darebbe numeri diversi senza che una sola riga del repository sia cambiata. In
un progetto il cui punto è che i numeri siano verificabili, sarebbe un difetto
grave. Il costo — aggiornare le versioni a mano — è reale ma esplicito.

`uv.lock` estende il blocco anche alle dipendenze indirette, che `pyproject.toml`
da solo non copre.

### Scelta: `pyproject.toml` e non `setup.py`

**Alternativa scartata:** `setup.py` più `requirements.txt`.

**Perché:** `setup.py` è codice Python eseguito all'installazione, quindi i
metadati si conoscono solo dopo averlo eseguito. `pyproject.toml` è dichiarativo
e standardizzato (PEP 517/518/621): gli strumenti lo leggono senza eseguire
nulla. In più raccoglie in un file unico ciò che prima stava sparso fra
`setup.cfg`, `.flake8`, `mypy.ini` e `pytest.ini`. `requirements.txt` resterà
comunque necessario, ma per un motivo diverso: Streamlit Cloud non legge
`pyproject.toml` (M7-T2).

### Scelta: due job separati in CI invece di uno solo

**Alternativa scartata:** un unico job che esegue in sequenza `ruff`, `mypy` e
`pytest`.

**Perché:** in sequenza, il primo comando che fallisce nasconde tutti quelli
dopo di lui — una virgola fuori posto impedisce di sapere se i test passano.
Due job girano in parallelo (quindi la CI è anche più veloce) e il nome del job
rosso dice subito se il problema è di forma o di sostanza. Il costo è
un'installazione delle dipendenze in più, che la cache di `uv` rende
trascurabile.

### Scelta: layout `src/` invece del pacchetto nella radice

**Alternativa scartata:** `football_analytics/` direttamente nella radice del
repository.

**Perché:** con il pacchetto nella radice, `import football_analytics` funziona
anche se il pacchetto non è installato, perché Python trova la cartella nella
directory corrente. Il risultato è che i test passano in locale e falliscono in
CI. Il layout `src/` rende impossibile quell'errore: se l'import funziona, è
perché l'installazione funziona.

### Scelta: azioni GitHub bloccate al commit SHA

**Alternativa scartata:** `uses: actions/checkout@v7`.

**Perché:** un tag mobile può essere ripuntato. Da `setup-uv` v8 in poi le
release sono immutabili e i tag mobili `@v8`/`@v9` non esistono più, quindi il
blocco allo SHA non è nemmeno una scelta: è l'unico modo. Tanto vale essere
coerenti su tutte le azioni.

## 4. Numeri misurati

| Cosa | Valore | Come è stato ottenuto |
| --- | --- | --- |
| Dipendenze dirette | 7 runtime + 6 dev | `pyproject.toml` |
| Pacchetti risolti in totale | 68 | `uv lock` → `Resolved 68 packages` |
| Test automatici | 6 | `uv run pytest` |
| Copertura di `src/` | 100 % | `uv run pytest`, 26 statements, 4 branch, 0 miss |
| Tempo di `uv sync` da zero | ~5 s | `Prepared 1 in 1.48s` + `Installed 68 in 3.66s` |
| Costruzione di mypy da sorgente | 18.9 s | `uv sync --reinstall-package mypy` |
| Durata della CI | \_\_ s | Pagina Actions, prima esecuzione con cache calda |

**Verifica incrociata di M1-T3.** Le versioni risolte su Linux/Python 3.12 in
fase di stesura del `pyproject.toml` e quelle installate su Windows/Python
3.12.10 coincidono una per una: `pandas==3.0.5`, `numpy==2.5.1`,
`pyarrow==24.0.0`, `plotly==6.9.0`, `scikit-learn==1.9.0`,
`streamlit==1.61.1`, `statsbombpy==1.22.0`. Due sistemi operativi diversi,
stesso risultato — che è esattamente ciò che il criterio chiedeva di
dimostrare.

## 5. Problemi incontrati

<!-- Le annotazioni si aggiungono in NOTES.md mentre si lavora e si riportano
qui in forma discorsiva a fine milestone. -->

Vedi [`NOTES.md`](../../NOTES.md) — al momento: il conflitto fra
`streamlit==1.61.1` e `pyarrow==25`, risolto scegliendo `pyarrow==24.0.0`.

## 6. Cosa resta aperto

- **Nessuna soglia minima di copertura.** `--cov-fail-under` non è impostato:
  con un solo modulo fatto di costanti, una soglia sarebbe un numero senza
  significato. Si introduce quando `transform.py` e `features.py` esistono.
- **`app/` e `scripts/` sono vuoti**, con i soli `.gitkeep`. La struttura
  corrisponde al piano, ma il codice arriva in M3 e M6: un `main.py`
  segnaposto sarebbe codice morto da mantenere per due mesi.
- **`config.py` non contiene ancora gli identificativi delle competizioni.**
  Arrivano in M2-T1, dove esiste anche il modo di verificarli contro i
  conteggi reali (380, 306, 380, 18).
- **`mypy` esclude `scripts/` e `app/`** finché sono vuoti.
- **La macchina di sviluppo richiede `UV_NO_BINARY_PACKAGE=mypy`.** È una
  variabile d'ambiente utente, deliberatamente fuori dal repository: chi clona
  il progetto su un sistema senza Smart App Control non ne ha bisogno, e la CI
  usa i binari compilati. Il prezzo è che la configurazione dell'ambiente non è
  interamente descritta dai file versionati — un compromesso accettato per non
  imporre a tutti un vincolo di uno solo. È documentato in `NOTES.md`.

## 7. Come verificarlo

```bash
git clone https://github.com/AVENA50/football-analytics.git
cd football-analytics

uv sync --all-extras

uv run python -c "import football_analytics as f; print(f.__version__)"  # 0.1.0
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
```

Tutti e cinque i comandi devono terminare con codice 0. Sulla pagina Actions del
repository, entrambi i job dell'ultima esecuzione devono essere verdi, e il
badge in cima al README lo riflette.
