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

### 2026-08-07 · M2-T2 · una stima sbagliata del 50 %, e il modo di accorgersene

**Cosa:** avevo stimato circa 4,5 GB per lo scaricamento completo. Misurando i
file veri di Euro 2020 — 516,9 MB per 51 partite — l'estrapolazione dice **7 GB**.

**Come si e' capito:** guardando il disco invece dei propri calcoli. La stima
veniva da un'ipotesi sulla dimensione media di un file di eventi; il numero
reale e' 3,1 MB per gli eventi e 7,1 MB per i freeze frame.

**Cosa insegna:** la stima non era irragionevole, era solo non misurata — e
nessuno l'avrebbe controllata, perche' «circa 4,5 GB» non ha l'aria di un
numero da verificare. E' lo stesso meccanismo che aveva reso invisibile
l'errore del piano sulle 380 partite di Ligue 1. Un numero plausibile e non
misurato e' il posto dove gli errori si nascondono meglio.

---

## M3 — Trasformazione

### 2026-08-07 · M3-T1 · i freeze frame erano ovunque, e non me n'ero accorto

**Cosa:** aprendo un evento di tiro per capire come costruire `shots.parquet`,
`shot.freeze_frame` era li' dentro — posizione, nome e ruolo di ogni giocatore
al momento del tiro. Non nei file `three-sixty/`: **dentro l'evento**.

**Come si e' capito:** contando. Un campione di tre partite di Serie A 2015/16
e tre finali di Champions, competizioni che il piano dava per prive di dati
spaziali:

| Competizione | Tiri | Con `shot.freeze_frame` |
| --- | ---: | ---: |
| Serie A 2015/16 | 66 | 64 (97 %) |
| Euro 2020 | 1.289 | 1.247 (97 %) |
| Finali Champions 2017-2019 | 85 | 84 (99 %) |

**Perche' e' la scoperta piu' grossa finora:** l'intera architettura si reggeva
sull'idea che solo alcune competizioni permettessero il modello con le
variabili spaziali. Era falso. La domanda centrale del progetto — quanto vale
sapere dove sono i difensori — passa da ~5.500 tiri a ~44.000, e con quel
volume la differenza fra i due modelli diventa misurabile invece che
indicativa.

**I due freeze frame, per non confonderli mai piu':**

| | `shot.freeze_frame` | file `three-sixty/` |
| --- | --- | --- |
| Dove | dentro l'evento di tiro | file separato, 6,5 MB a partita |
| Quando | solo al momento del tiro | tutti i 3.400 eventi |
| Contiene | posizione, **nome**, **ruolo**, compagno si/no | posizione, compagno, portiere, attore |
| In piu' | — | area inquadrata dalla telecamera |
| Disponibile | ~97 % dei tiri, ovunque | solo alcune competizioni |

Per il modello xG serve il primo, ed e' anche il piu' ricco: sapere che il
difensore piu' vicino e' un centrale invece di un terzino e' informazione che
i file 360 non hanno.

**Cosa insegna:** avevo verificato *quali competizioni hanno i file 360* e mi
ero fermato li', perche' la risposta confermava il piano. Non avevo verificato
*cosa serve davvero al modello*. Confermare l'ipotesi che si aveva in testa e'
il momento in cui si smette di guardare — ed e' esattamente quando bisognerebbe
guardare meglio.

### 2026-08-07 · M3-T1 · la fixture sbagliata, smascherata dal suo stesso test

**Cosa:** avevo scritto una fixture dichiarando che la partita finiva 2 a 2. Il
test e' fallito: gli eventi dicevano 2 a 1.

**Chi aveva ragione:** il codice. Contando a mano — un gol su azione della
Casalinga, un autogol a suo favore, un gol dell'Ospite nei supplementari, due
rigori finali che non contano — fa 2 a 1. Il numero nei metadati era mio, e
sbagliato.

**Cosa insegna:** e' esattamente il meccanismo che dovra' proteggere il
progetto quando i dati saranno 1.753 partite invece di una inventata. Se un
test scritto apposta per verificare i risultati smaschera chi l'ha scritto,
funziona. E la fixture corretta e' finita per essere migliore: i modi
plausibili di sbagliare quel conteggio sono **tre** — ignorare l'autogol
(1 a 1), includere i rigori finali (3 a 1), contare l'autogol per entrambe le
squadre (2 a 2) — e ora c'e' un test per ciascuno.

### 2026-08-07 · M3-T2 · i minuti non si sommano

**Cosa:** calcolando i minuti giocati come somma delle durate degli spezzoni di
`positions`, alcuni giocatori risultavano con valori negativi.

**Come si e' capito:** guardando uno spezzone di Federico Chiesa in
Italia-Austria:

```
da 108:54 (p4) a  83:34 (p2)   inizio "Tactical Shift"    fine "Substitution - On"
da  83:34 (p2) a  None         inizio "Substitution - On" fine "Final Whistle"
```

Il primo ha `to` **precedente** a `from`. Non e' un caso isolato: succede
nell'1,3 % degli spezzoni, 30 volte su 2.320 nelle sole 57 partite scaricate.

**Risolto:** non sommando. Un giocatore entra in campo una volta ed esce una
volta; gli spezzoni intermedi esistono solo per registrare i cambi di
posizione. Il tempo in campo e' quindi `max(to) - min(from)`, e con quella
formula l'anomalia diventa innocua — nel caso di Chiesa da' i 61 minuti
corretti invece dei 31 che darebbe la somma.

**Cosa insegna:** quando un dato ha una struttura ridondante — spezzoni che
insieme ricostruiscono un intervallo — conviene calcolare sull'**invariante**
(l'intervallo complessivo) invece che sui pezzi. I pezzi possono essere
incoerenti fra loro; l'invariante no.

### 2026-08-07 · M3-T2 · 129 minuti in campo

**Cosa:** cinque giocatori francesi risultavano aver giocato 129 minuti.

**Come si e' capito:** il massimo teorico e' 120, supplementari compresi. La
partita era Francia-Svizzera, finita ai rigori: prendendo `max(Half End)` su
tutti i periodi si prendeva anche la fine del **quinto**, cioe' dei rigori, che
cade al 128'.

**Risolto:** la durata della partita considera solo i periodi fino al quarto.
Quattro partite di Euro 2020 ne erano affette.

**Cosa insegna:** e' la terza volta che il periodo 5 si intrufola dove non
dovrebbe — prima nei gol, poi nei tiri delle statistiche giocatore, ora nella
durata. I rigori finali sono eventi a tutti gli effetti ma non sono gioco, e
ogni aggregazione va scritta chiedendosi se li vuole dentro. Ora c'e' una
costante, `ULTIMO_PERIODO_DI_GIOCO`, invece di un `5` sparso nel codice.

### 2026-08-07 · M3-T2 · la prima verifica contro il mondo esterno

**Cosa:** la classifica marcatori calcolata da `player_stats.parquet` su Euro
2020 e' Ronaldo 5, Schick 5, poi Lukaku, Forsberg, Kane e Benzema a 4.

**Perche' conta:** e' la classifica ufficiale del torneo — Ronaldo e Schick
vinsero la Scarpa d'Oro a pari merito. Tutte le verifiche fino a qui erano
**interne**: i gol tornano con i risultati scritti nello stesso file. Questa e'
la prima che si confronta con un fatto pubblico, verificabile da chiunque.

Una pipeline puo' essere internamente coerente e sbagliata: basta un errore
sistematico che si propaga ovunque. Il confronto con l'esterno e' l'unico che
lo smaschera, e vale la pena cercarne uno per ogni tabella prodotta.

### 2026-08-07 · M3-T4 · un test che guastava la tabella con lo stesso valore

**Cosa:** `test_un_gol_incoerente_con_l_esito_viene_segnalato` falliva con
`DID NOT RAISE`.

**Come si e' capito:** il test scriveva `gol = True` sulla prima riga di
`shots` per creare un'incoerenza. Ma la prima riga e' il gol del 12': aveva
gia' `gol` vero. Il controllo non scattava perche' non c'era niente da trovare.

**Risolto:** `gol = False`, piu' un'asserzione che verifica il valore di
partenza prima di guastarlo — cosi' l'errore non puo' ripetersi in silenzio.

**Cosa insegna:** e' esattamente cio' contro cui metteva in guardia la
docstring del file, «un controllo mai visto fallire non e' un controllo». Vale
anche per il test stesso: un test negativo che passa perche' non ha davvero
introdotto l'anomalia e' peggio di nessun test, perche' da' fiducia
ingiustificata. Quando si scrive un test che si aspetta un fallimento, va
verificato **anche** che la condizione di partenza fosse sana.

### 2026-08-07 · M2-T4 · l'indice competizioni mente per omissione

**Cosa:** avevo dichiarato la Coppa d'Africa 2023 coperta dai dati 360.
Scaricandola, il manifest ha riportato **1 partita su 52**.

**Come si e' capito:** dal peso. 134 MB contro i ~530 delle altre competizioni
con i 360. Un numero che non torna con gli altri numeri.

**La causa:** il campo `match_available_360` dell'indice competizioni e'
**a livello di competizione**, e diventa non nullo anche se una sola partita ha
i file. Il dato affidabile e' `match_status_360` nel file delle partite, che ha
quattro valori:

| valore | significato |
| --- | --- |
| `available` | il file esiste |
| `processing` | StatsBomb lo sta producendo |
| `scheduled` | ha in programma di produrlo |
| `unscheduled` | non e' previsto |

Solo il primo e' un file. Gli altri sono promesse — e la Premier League 2015/16
ne ha 200 in `processing` e 180 in `scheduled`, cioe' zero file e 380 promesse.

**Risolto:** Coppa d'Africa portata a `PARZIALE`, e il test di rete riscritto
per contare gli stati partita per partita invece di leggere l'indice.
Rinominato anche `TORNEI_360` in `TORNEI`: il nome vecchio affermava una cosa
falsa.

**Il modello non ne risente:** nella Coppa d'Africa `shot.freeze_frame` c'e'
nel 95 % dei tiri. E' la conferma pratica di quanto contasse distinguere i due
tipi di fotogramma.

**Cosa insegna, ed e' il filo di tutta M2:** ogni volta che mi sono sbagliato,
la fonte sbagliata era **quella piu' comoda da leggere**. Un numero scritto nel
piano invece di contare le partite. Un campo aggregato invece di scorrere le
righe. Una cella che sembra falsa invece di chiedere a `pd.notna`. La fonte
giusta costava sempre un passo in piu', e quel passo e' esattamente il lavoro.

### 2026-08-07 · M3-T3 · lo stesso errore due volte, con un'altra maschera

**Cosa:** la costruzione del magazzino su 1.753 partite si e' fermata su
Lorient-Marsiglia: risultato calcolato 1-0, ufficiale 1-1.

**Come si e' capito:** guardando gli eventi. Il gol c'era, al 45' del secondo
tempo. Ma:

```
evento:    team = "Marseille"
metadati:  ospite = "Olympique de Marseille"
```

Lo stesso club con due nomi. Contavo i gol per **nome squadra**, e il nome
negli eventi non e' quello nel file delle partite: il Marsiglia risultava a
zero. Succede a due squadre su 152, Marsiglia e Caen, entrambe di Ligue 1.

**Risolto:** confronto per identificativo, e i nomi presi sempre dal file
partite cosi' che il magazzino ne abbia una grafia sola. Aggiunta
`nome_squadra(meta, id)`, che e' l'unico punto in cui un identificativo diventa
un nome.

**Cosa insegna, e questa e' la parte che conta:** e' **lo stesso errore** dei
giocatori sdoppiati di poche ore prima — «Danny Ward» e «Daniel Ward» — con
un'altra maschera. Li' avevo scritto nel commit *«l'identita' e'
l'identificativo, il nome e' un attributo»*, l'avevo applicato ai giocatori, e
non mi era venuto in mente di applicarlo alle squadre.

Imparare una lezione su un caso non basta: va cercato **dove altro vale lo
stesso principio**. Ogni volta che una chiave e' una stringa leggibile invece
di un identificativo, il difetto e' gia' li' e aspetta solo il dato giusto per
manifestarsi. Nel magazzino restano da controllare le competizioni, che pero'
usano una chiave scelta da noi e non da StatsBomb.

**Nota di merito al controllo:** questo non l'ha trovato una lettura del
codice. L'ha trovato `verifica_risultato`, su una partita fra 1.753, mesi prima
che qualcuno guardasse una dashboard.

### 2026-08-07 · M3-T4 · due tiri fuori dal campo, e non era un errore

**Cosa:** sul dataset completo il controllo delle coordinate ha segnalato due
tiri con `x` oltre la linea di porta: 120,2 e 120,1 su un campo lungo 120.

**Come si e' capito:** guardandoli. Entrambi hanno `y` vicino a 1, cioe' sono
calciati dalla linea di fondo all'altezza della bandierina, ed entrambi hanno
l'xG **minimo** possibile, 0,00018. Un pallone calciato sulla linea puo' avere
il centro qualche centimetro oltre: e' rumore di misura del tracciamento, non
un dato sbagliato.

**Risolto:** una tolleranza esplicita di un metro, con il perche' scritto
accanto alla costante.

**Cosa insegna:** il primo istinto e' stato «il controllo ha trovato qualcosa,
quindi i dati sono sbagliati». Ma un controllo puo' essere **troppo severo**, e
quello e' un difetto peggiore di uno troppo permissivo: un controllo che
segnala falsi allarmi viene disattivato, e da quel momento non trova piu'
nemmeno i problemi veri. Due tiri su 44.000 non giustificano di bloccare la
pipeline; una tolleranza documentata si'.

La differenza fra questo caso e quello del Marsiglia e' tutta qui: li' il
controllo aveva ragione e ho corretto il codice, qui aveva torto e ho corretto
il controllo. Distinguere i due casi e' il lavoro — allentare sempre e'
comodo, irrigidire sempre e' inutile.

### 2026-08-07 · M3 · la verifica esterna che vale piu' di tutte le altre

**Cosa:** le classifiche marcatori calcolate dal magazzino, confrontate con i
fatti pubblici:

| Giocatore | Competizione | Calcolati | Ufficiali |
| --- | --- | ---: | ---: |
| Luis Suarez | La Liga 2015/16 | 40 | 40 (Pichichi) |
| Gonzalo Higuain | Serie A 2015/16 | 36 | 36 (record) |
| Cristiano Ronaldo | La Liga 2015/16 | 35 | 35 |
| Lionel Messi | La Liga 2015/16 | 26 | 26 |
| Zlatan Ibrahimovic | Ligue 1 2015/16 | 36 | **38** |

**Lo scarto e' la parte interessante.** Non e' un difetto della pipeline: alla
Ligue 1 2015/16 mancano 3 partite su 380 — le giornate 14, 23 e 36 ne hanno
nove invece di dieci — e il PSG e' fra le sei squadre a cui ne manca una.

**Cosa insegna:** sapere **quale** partita manca e' cio' che separa un dato
incompleto da un dato sbagliato. Un totale che non torna, da solo, e' inutile;
un totale che non torna **e di cui si conosce la ragione esatta** e' una
dichiarazione onesta che si puo' mettere in una pagina Metodologia.

Ed e' la ragione per cui vale la pena cercare una verifica esterna per ogni
tabella prodotta: quella interna dice che i numeri sono coerenti fra loro, non
che sono veri.

---

<!--
Le milestone successive aggiungono qui la loro sezione.
Almeno un'annotazione per milestone: e' il criterio di M7-T6.
-->
