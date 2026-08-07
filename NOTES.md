# NOTES — il diario degli inciampi

Ogni volta che qualcosa si rompe, una riga qui. Non e' un changelog: e' il
posto dove finisce cio' che non funzionava e perche'.

Questo file diventa la sezione `learnings` del case study nel portfolio, ed e'
la parte che distingue un case study da una brochure. Scritto a caldo vale;
ricostruito alla fine, no.

**Formato:** data, milestone-task, cosa si e' rotto, come si e' capito, come si
e' risolto.

---

## M1 — Fondamenta

### 2026-08-07 · M1-T3 · streamlit 1.61 e pyarrow 25 non stanno insieme

**Cosa:** risolvendo le dipendenze, chiedere sia `streamlit` sia `pyarrow`
all'ultima versione dava `streamlit==1.59.1` invece di `1.61.1`.

**Come si e' capito:** `uv pip compile` con `streamlit==1.61.1` fissato ha
mostrato che la 1.61.1 vincola `pyarrow<25`, quindi il risolutore stava
retrocedendo streamlit per tenere pyarrow 25.

**Risolto:** scelto `streamlit==1.61.1` + `pyarrow==24.0.0`. Fra le due,
streamlit e' la dipendenza che decide cosa la dashboard puo' fare
(`st.navigation`, `on_select` sulle tabelle); pyarrow 24 legge e scrive Parquet
esattamente come la 25.

### 2026-08-07 · M1-T2 · Windows blocca il Python scaricato da uv

**Cosa:** `uv python install 3.12` va a buon fine, ma il primo `uv sync` muore
mentre costruisce il pacchetto, con
`ImportError: DLL load failed while importing _socket: Un criterio di controllo
dell'applicazione ha bloccato il file`.

**Come si e' capito:** il percorso nella traccia dell'errore
(`AppData\Roaming\uv\python\cpython-3.12-...`) dice che il file bloccato non e'
del progetto, ma dell'interprete stesso. Il messaggio «criterio di controllo
dell'applicazione» e' Smart App Control / WDAC: impedisce l'esecuzione di
binari non firmati che compaiono nelle cartelle utente, e le distribuzioni
python-build-standalone usate da uv non sono firmate da Microsoft.

**Risolto:** installato il Python 3.12 ufficiale
(`winget install --id Python.Python.3.12 -e`), che e' firmato, poi
`uv python uninstall 3.12` per togliere di mezzo quello bloccato. Senza un
interprete gestito da usare, uv ripiega su quello di sistema. Il `.venv`
risultante gira su CPython 3.12.10.

**Perche' non si e' disattivato Smart App Control:** su Windows 11 e' una
scelta irreversibile — una volta spento non si riaccende senza reinstallare il
sistema. Cambiare interprete costa due comandi.

**Da ricordare per M7:** questo vincolo e' locale alla macchina di sviluppo.
Streamlit Community Cloud e i runner di GitHub Actions girano su Linux e non
hanno il problema; il `ci.yml` continua a usare il Python gestito da uv.

### 2026-08-07 · M1-T4 · lo stesso blocco colpisce mypy e coverage

**Cosa:** risolto il problema dell'interprete, `uv run mypy` falliva con
`ImportError: DLL load failed while importing internal`, e `pytest` emetteva
`CoverageWarning: Couldn't import C tracer`.

**Come si e' capito:** stesso criterio di controllo di prima, applicato pero'
ai binari delle librerie invece che a quelli di Python. `mypy` viene
distribuito compilato con mypyc e `coverage` include un tracciatore in C:
entrambi sono file `.pyd` non firmati, quindi entrambi bloccati. `ruff` invece
passa, perche' e' un singolo eseguibile Rust senza DLL da caricare.

**Il falso allarme:** il primo sospetto era che fossero bloccate anche pandas,
numpy e pyarrow — nel qual caso il progetto non sarebbe girato affatto su
questa macchina. Un `import` esplicito di tutte e sei le librerie pesanti ha
risposto `TUTTO OK`. Il comando sembrava bloccato ma era solo lento: `streamlit`
e `sklearn` al primo import impiegano diversi secondi, e l'antivirus che
ispeziona ogni DLL peggiora l'attesa. **Lezione: prima di dichiarare un blocco,
verificare che non sia solo lentezza.**

**Risolto:** `mypy` installato da sorgente, in versione pura Python, tramite la
variabile d'ambiente utente `UV_NO_BINARY_PACKAGE=mypy` piu'
`uv sync --reinstall-package mypy`. Costruzione in 18.9s, poi
`Success: no issues found in 3 source files`. Per `coverage` e' bastato
`disable_warnings = ["no-ctracer"]`: la libreria ripiega gia' da sola sul
tracciatore Python e i numeri sono identici.

**Perche' una variabile d'ambiente e non una riga in `pyproject.toml`:** il
blocco e' un fatto di questa macchina, non del progetto. Su Linux — dove girano
sia GitHub Actions sia Streamlit Cloud — mypy compilato funziona, e rallentare
la CI per un vincolo locale sarebbe la scelta sbagliata. Il repository resta
pulito; il rimedio vive sul computer che ha il problema.

---

<!--
Le milestone successive aggiungono qui la loro sezione.
Almeno un'annotazione per milestone: e' il criterio di M7-T6.
-->
