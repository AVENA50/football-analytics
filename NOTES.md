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

## M2 — Ingestione

### 2026-08-07 · M2-T1 · il piano si sbagliava su meta' delle competizioni

**Cosa:** il test di rete di M2-T1 e' fallito su due competizioni su quattro.
Ligue 1 2021/22: attese 380 partite, trovate **26**. Bundesliga 2023/24:
attese 306, trovate **34**. Serie A 2015/16 e finali di Champions tornavano.

**Come si e' capito:** 26 e 34 non sono numeri casuali. 34 e' una stagione
intera di Bundesliga **per una squadra sola**; 26 sono le presenze di un
giocatore in un campionato. StatsBomb non pubblica sempre stagioni complete:
a volte rilascia il sottoinsieme legato a un tema — la biografia di Messi, la
stagione imbattuta del Leverkusen.

**Perche' era grave:** quelle due erano le uniche fonti di dati 360 del piano.
Insieme dovevano dare 686 partite e ne danno 60. L'intero confronto fra
modello base e modello 360 — la parte piu' raccontabile del progetto — si
sarebbe addestrato su un decimo dei dati previsti, e i 27.000 tiri stimati
sarebbero stati circa 1.500.

**Risolto:** scritto `scripts/esplora_open_data.py`, che conta le partite di
ogni stagione dell'Open Data e ne riporta la disponibilita' dei freeze frame.
Da li' e' emerso il quadro reale e le fonti sono state riscelte.

**Cosa insegna:** il piano si basava su numeri plausibili — 380 partite sono
un campionato a venti squadre, 306 uno a diciotto — ma nessuno li aveva
verificati. Un numero che *sembra* giusto e' il tipo peggiore di errore,
perche' non attira controlli. Il task che li ha verificati esisteva apposta, ed
e' l'unico motivo per cui il problema e' emerso al secondo task di M2 invece
che a M5.

### 2026-08-07 · M2-T1 · `bool(NaN)` vale True

**Cosa:** la prima versione di `esplora_open_data.py` dichiarava i dati 360
disponibili per tutte e quaranta le stagioni, comprese quelle che il piano
sapeva non averli.

**Come si e' capito:** il risultato era troppo bello. Se *tutto* ha i 360, la
domanda centrale del progetto non ha senso — e un controllo che risponde
sempre si' non e' un controllo.

**La causa:**

```python
ha_360 = bool(voce.get("match_available_360"))  # sbagliato
```

Quando il campo manca, pandas restituisce `NaN`. E `bool(NaN)` in Python vale
`True`, perche' NaN e' un float diverso da zero. La correzione e'
`bool(pd.notna(...))`.

**Cosa insegna:** con pandas, il valore mancante non e' `None` e non e' falso.
Ogni controllo di verita' su una cella che puo' essere vuota va scritto con
`pd.notna` o `pd.isna`, mai con `if valore:`. Vale per tutto M3, dove i campi
opzionali degli eventi StatsBomb sono la norma.

---

<!--
Le milestone successive aggiungono qui la loro sezione.
Almeno un'annotazione per milestone: e' il criterio di M7-T6.
-->
