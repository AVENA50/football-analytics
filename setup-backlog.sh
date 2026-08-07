#!/usr/bin/env bash
# Crea etichette, milestone e issue del progetto Football Analytics.
# Da eseguire DENTRO il repository, dopo `gh auth login`.
set -euo pipefail

# --- etichette ---------------------------------------------------------
gh label create setup         --color 0F6E56 --description "Impalcatura, strumenti, CI" --force
gh label create dati          --color 1D9E75 --description "Ingestione e trasformazione" --force
gh label create modello       --color 5DCAA5 --description "Feature, addestramento, valutazione" --force
gh label create dashboard     --color 143C8C --description "Viste Streamlit" --force
gh label create design        --color 2A62C9 --description "Tema, componenti, grafici" --force
gh label create test          --color B45309 --description "Test automatici" --force
gh label create docs          --color 6B7280 --description "README, note, metodologia" --force
gh label create milestone-doc --color 374151 --description "Documentazione di chiusura milestone" --force
gh label create deploy        --color 7C3AED --description "Pubblicazione" --force
gh label create portfolio     --color DB2777 --description "Case study nel portfolio" --force
gh label create bloccante     --color DC2626 --description "Blocca altre issue" --force

# --- milestone ---------------------------------------------------------
for m in \
  "M1 - Fondamenta|Repository, ambiente, strumenti di qualita e CI" \
  "M2 - Ingestione|Scaricamento incrementale dei dati grezzi" \
  "M3 - Trasformazione|Dai JSON ai Parquet, con i controlli di qualita" \
  "M4 - Esplorazione|Capire i dati prima di modellarli" \
  "M5 - Modello xG|Due modelli, validati onestamente" \
  "M6 - Dashboard|Nove viste e il tema che cambia" \
  "M7 - Pubblicazione|Deploy su Streamlit Community Cloud" \
  "M8 - Portfolio|Il case study nel sito"
do
  titolo="${m%%|*}"; desc="${m##*|}"
  gh api "repos/{owner}/{repo}/milestones" -f title="$titolo" -f description="$desc" >/dev/null 2>&1 \
    || echo "milestone gia presente: $titolo"
done

# --- issue -------------------------------------------------------------
crea() {  # crea <milestone> <etichette> <titolo> <corpo>
  gh issue create --milestone "$1" --label "$2" --title "$3" --body "$4"
}

# ---- M1 ---------------------------------------------------------------
crea "M1 - Fondamenta" "setup,docs" "M1-T1 Creare il repository pubblico" \
  "Repository pubblico (richiesto da Streamlit Community Cloud). README con attribuzione a StatsBomb.

**Fatto quando:** \`git clone\` funziona e il README cita StatsBomb."

crea "M1 - Fondamenta" "setup" "M1-T2 Ambiente Python isolato" \
  "uv, Python 3.12. .gitignore che esclude data/raw/, .venv/, __pycache__/.

**Fatto quando:** \`uv sync --all-extras\` installa il pacchetto e \`import football_analytics\` funziona."

crea "M1 - Fondamenta" "setup" "M1-T3 pyproject.toml con dipendenze bloccate" \
  "statsbombpy, pandas, pyarrow, numpy, scikit-learn, plotly, streamlit. Versioni fissate a valore esatto, piu uv.lock committato.

**Fatto quando:** l'installazione da zero produce le stesse versioni."

crea "M1 - Fondamenta" "setup,test" "M1-T4 Strumenti di qualita" \
  "ruff, mypy, pytest configurati in pyproject.toml.

**Fatto quando:** i tre comandi passano su un repository vuoto."

crea "M1 - Fondamenta" "setup,test" "M1-T5 CI su GitHub Actions" \
  "Lint, tipi e test a ogni push e PR, in due job separati, con cache di uv.

**Fatto quando:** il badge verde e sul README."

crea "M1 - Fondamenta" "setup,docs" "M1-T6 Struttura delle cartelle" \
  "src/, scripts/, tests/, app/, data/, models/, notebooks/, docs/milestones/ con _template.md.

**Fatto quando:** corrisponde alla struttura del piano e il modello di documentazione esiste."

crea "M1 - Fondamenta" "milestone-doc" "M1-T7 Documentazione della milestone M1" \
  "Compilare docs/milestones/M1-fondamenta.md seguendo il modello.

Decisioni da motivare: ruff invece di black + flake8, versioni fissate invece di intervalli, pyproject.toml invece di setup.py, due job separati in CI.

**Fatto quando:** il file ha tutte e sette le sezioni ed e linkato da docs/milestones/README.md."

# ---- M2 ---------------------------------------------------------------
crea "M2 - Ingestione" "dati" "M2-T1 Competizioni in config.py" \
  "Ligue 1 (7,108), Bundesliga (9,281), Serie A (12,27), Champions comp 16.

**Fatto quando:** i conteggi reali sono 380, 306, 380 e 18."

crea "M2 - Ingestione" "dati,bloccante" "M2-T2 ingest.py incrementale e ripartibile" \
  "Non riscarica cio che esiste. Se si interrompe, riprende.

**Fatto quando:** la seconda esecuzione non scarica nulla."

crea "M2 - Ingestione" "dati" "M2-T3 Registro dello scaricamento" \
  "data/raw/manifest.json con competizione, stagione, data, numero di partite.

**Fatto quando:** e aggiornato dall'ingestione, non a mano."

crea "M2 - Ingestione" "dati,bloccante" "M2-T4 Verificare la disponibilita dei dati 360" \
  "Per ogni competizione, quante partite hanno i freeze frame.

**Fatto quando:** il numero e nel manifest e nel README. E il fatto da cui nasce la scelta dei due modelli."

crea "M2 - Ingestione" "dati" "M2-T5 Scaricare la Ligue 1 2021/22" \
  "Prima competizione, quella su cui si dimostra la pipeline.

**Fatto quando:** 380 partite in data/raw/, tutte con eventi."

crea "M2 - Ingestione" "dati" "M2-T6 Scaricare Bundesliga, Serie A e finali" \
  "Solo dopo che M3 funziona sulla Ligue 1.

**Fatto quando:** 306 + 380 + 18 partite scaricate."

crea "M2 - Ingestione" "milestone-doc" "M2-T7 Documentazione della milestone M2" \
  "Compilare docs/milestones/M2-ingestione.md.

Da documentare: durata dello scaricamento completo e peso di data/raw/, quante partite hanno i dati 360 per competizione, come e stata resa ripartibile l'ingestione, sorprese nei dati di partenza.

**Fatto quando:** il file contiene i numeri reali dello scaricamento."

# ---- M3 ---------------------------------------------------------------
crea "M3 - Trasformazione" "dati,bloccante" "M3-T1 shots.parquet" \
  "Una riga per tiro, colonne tipizzate, colonna has_360, xG di StatsBomb incluso.

**Fatto quando:** tiri e gol coincidono con i risultati ufficiali."

crea "M3 - Trasformazione" "dati" "M3-T2 matches.parquet e player_stats.parquet" \
  "Aggregati per partita e per giocatore, con i valori per 90 minuti.

**Fatto quando:** la somma dei gol per giocatore coincide con quella per partita."

crea "M3 - Trasformazione" "dati" "M3-T3 passes.parquet e touches.parquet" \
  "Solo le colonne che le viste usano davvero.

**Fatto quando:** insieme pesano meno di 40 MB."

crea "M3 - Trasformazione" "dati,test" "M3-T4 Controlli di qualita" \
  "Nessun NaN inatteso, coordinate nei limiti, gol coerenti, nessun duplicato.

**Fatto quando:** i controlli interrompono build_dataset.py in caso di anomalia."

crea "M3 - Trasformazione" "dati" "M3-T5 scripts/build_dataset.py" \
  "Un comando dall'inizio alla fine.

**Fatto quando:** due esecuzioni danno conteggi identici."

crea "M3 - Trasformazione" "test" "M3-T6 Test di transform.py su campione ridotto" \
  "Campione di eventi in tests/fixtures/.

**Fatto quando:** pytest e verde senza connessione."

crea "M3 - Trasformazione" "dati" "M3-T7 Verificare il peso dei Parquet" \
  "GitHub avverte a 50 MB e rifiuta a 100 MB.

**Fatto quando:** ogni file sotto i 50 MB, somma sotto i 100 MB. Mai Git LFS."

crea "M3 - Trasformazione" "milestone-doc" "M3-T8 Documentazione della milestone M3" \
  "Compilare docs/milestones/M3-trasformazione.md.

La milestone con piu decisioni da spiegare: colonne tenute e scartate, trattamento dei valori mancanti, perche has_360 non viene mai riempito con zeri, quali controlli hanno trovato anomalie reali. Conteggi finali: tiri, gol, righe per Parquet, peso in MB.

**Fatto quando:** chiunque, leggendolo, potrebbe ricostruire la trasformazione da zero."

# ---- M4 ---------------------------------------------------------------
crea "M4 - Esplorazione" "dati,docs" "M4-T1 Notebook di esplorazione" \
  "Distribuzioni, valori anomali, correlazioni. Fuori dal pacchetto.

**Fatto quando:** gira dall'inizio alla fine e ogni grafico ha un commento."

crea "M4 - Esplorazione" "docs" "M4-T2 Le tre domande della dashboard" \
  "Scegliere le tre domande a cui il progetto risponde.

**Fatto quando:** sono nel README, non in testa."

crea "M4 - Esplorazione" "milestone-doc" "M4-T3 Documentazione della milestone M4" \
  "Compilare docs/milestones/M4-esplorazione.md.

Qui va il contenuto dell'esplorazione, non il processo: cosa hai scoperto guardando i dati. Le tre domande scelte e perche hai scartato le altre.

**Fatto quando:** contiene almeno tre osservazioni concrete che non erano ovvie prima di guardare i dati."

# ---- M5 ---------------------------------------------------------------
crea "M5 - Modello xG" "modello,test" "M5-T1 Variabili base" \
  "Distanza, angolo, parte del corpo, tipo di azione, sotto pressione.

**Fatto quando:** ogni variabile ha un test su casi noti."

crea "M5 - Modello xG" "modello,bloccante" "M5-T2 Variabili 360" \
  "Difensori nel cono, distanza del portiere, compagni in area.

**Fatto quando:** calcolate solo dove has_360 e vero. Mai riempite con zeri."

crea "M5 - Modello xG" "modello,test,bloccante" "M5-T3 Divisione train/test per partita" \
  "Nessun tiro della stessa partita da entrambe le parti.

**Fatto quando:** un test verifica che l'intersezione degli id di partita sia vuota."

crea "M5 - Modello xG" "modello" "M5-T4 Modello base, regressione logistica" \
  "**Fatto quando:** salvato in models/xg_base.pkl e riproducibile con un seed fisso."

crea "M5 - Modello xG" "modello" "M5-T5 Modello migliore, gradient boosting" \
  "**Fatto quando:** confrontato con la regressione logistica sullo stesso insieme di verifica."

crea "M5 - Modello xG" "modello" "M5-T6 Base contro 360" \
  "Le due varianti sulle stesse partite, stesso insieme di verifica.

**Fatto quando:** la differenza fra i punteggi e nel README. E il risultato piu raccontabile del progetto."

crea "M5 - Modello xG" "modello" "M5-T7 Valutazione" \
  "Log loss, Brier score, AUC, curva di calibrazione. **Non l'accuratezza.**

**Fatto quando:** i quattro numeri sono nel README."

crea "M5 - Modello xG" "modello" "M5-T8 Confronto con l'xG di StatsBomb" \
  "Scarto medio e correlazione sugli stessi tiri.

**Fatto quando:** dichiarati. Se il modello e peggiore va scritto."

crea "M5 - Modello xG" "modello" "M5-T9 Modello base su Serie A e finali" \
  "**Fatto quando:** ogni tiro di quelle competizioni ha un xG calcolato."

crea "M5 - Modello xG" "modello,dashboard" "M5-T10 Spiegabilita" \
  "Quali variabili contano di piu e in che direzione.

**Fatto quando:** il grafico e nella vista Modello xG."

crea "M5 - Modello xG" "modello" "M5-T11 scripts/train_model.py" \
  "**Fatto quando:** rilanciarlo con lo stesso seed produce gli stessi numeri."

crea "M5 - Modello xG" "milestone-doc" "M5-T12 Documentazione della milestone M5" \
  "Compilare docs/milestones/M5-modello-xg.md.

La milestone piu importante da documentare: formula di ogni variabile, tabella completa delle metriche per entrambi i modelli, curva di calibrazione, confronto con StatsBomb, perche l'accuratezza e la metrica sbagliata, perche la divisione va fatta per partita. Anche cio che non ha funzionato.

**Fatto quando:** contiene tutte le metriche misurate e un lettore tecnico potrebbe replicare l'addestramento."

# ---- M6 ---------------------------------------------------------------
crea "M6 - Dashboard" "design,test,bloccante" "M6-T1 Tema e cambio dinamico" \
  "theme.py, .streamlit/config.toml, variabili --st-* iniettate a ogni rerun.

**Fatto quando:** le finali di Champions rendono l'app blu, e un test verifica che viz.py non contenga colori letterali."

crea "M6 - Dashboard" "design,dashboard" "M6-T2 Il campo in Plotly" \
  "Erba a strisce, linee bianche, proporzioni regolamentari.

**Fatto quando:** shot map, rete dei passaggi e heatmap usano la stessa funzione."

crea "M6 - Dashboard" "dashboard" "M6-T3 Vista Panoramica" \
  "KPI, xG per squadra, shot map, andamento, top giocatori, insight.

**Fatto quando:** i numeri coincidono con quelli calcolati a mano su dieci partite."

crea "M6 - Dashboard" "dashboard" "M6-T4 Vista Squadre" \
  "Scheda squadra, rete dei passaggi, shot map, confronto, gol contro xG.

**Fatto quando:** si sceglie la squadra e si confronta con un'altra."

crea "M6 - Dashboard" "dashboard" "M6-T5 Vista Giocatori con tabella cliccabile" \
  "st.dataframe con on_select=rerun e selection_mode=single-row.

**Fatto quando:** il clic apre la scheda, e la soglia dei 500 minuti esclude dalle graduatorie senza togliere dalla tabella."

crea "M6 - Dashboard" "dashboard" "M6-T6 Scheda del giocatore" \
  "KPI, radar, shot map, heatmap, cumulata, dettaglio dei tiri.

**Fatto quando:** il radar confronta con la media del ruolo, non con l'intero campionato."

crea "M6 - Dashboard" "dashboard" "M6-T7 Vista Partite" \
  "Elenco con xG casa/trasferta, dettaglio, xG cumulato minuto per minuto.

**Fatto quando:** ci si arriva anche dalla scheda di una squadra."

crea "M6 - Dashboard" "dashboard" "M6-T8 Vista Confronto leghe" \
  "Tre schede, distribuzione dell'xG per tiro, gol contro xG per lega.

**Fatto quando:** include l'avvertenza sul fatto che i tre numeri non sono direttamente confrontabili."

crea "M6 - Dashboard" "dashboard,modello" "M6-T9 Viste Modello xG e Base contro 360" \
  "Calibrazione, importanza delle variabili, le due varianti a confronto.

**Fatto quando:** un tecnico capisce il modello senza leggere il codice."

crea "M6 - Dashboard" "dashboard,design" "M6-T10 Vista Finali di Champions, in blu" \
  "18 finali, shot map, xG cumulato.

**Fatto quando:** il tema passa al blu e la nota spiega che il modello non ha mai visto queste partite."

crea "M6 - Dashboard" "dashboard,docs" "M6-T11 Vista Metodologia" \
  "Catena del dato, cosa e stato verificato, limiti dichiarati, attribuzione.

**Fatto quando:** esiste prima del deploy, non dopo."

crea "M6 - Dashboard" "dashboard" "M6-T12 insights.py, le frasi calcolate" \
  "**Fatto quando:** cambiando competizione la frase cambia da sola con i numeri giusti."

crea "M6 - Dashboard" "dashboard" "M6-T13 Cache dei dati" \
  "@st.cache_data sul caricamento dei Parquet.

**Fatto quando:** cambiare un filtro non rilegge i file da disco."

crea "M6 - Dashboard" "milestone-doc" "M6-T14 Documentazione della milestone M6" \
  "Compilare docs/milestones/M6-dashboard.md.

Struttura delle viste e perche quell'ordine, funzionamento del cambio tema con il codice, Plotly invece di mplsoccer, la soglia dei 500 minuti, una schermata per vista. Anche cio che non sei riuscito a ottenere con Streamlit e come hai deciso di conviverci.

**Fatto quando:** contiene una schermata per vista e la spiegazione del cambio tema."

# ---- M7 ---------------------------------------------------------------
crea "M7 - Pubblicazione" "deploy" "M7-T1 Parquet nel repository" \
  "**Fatto quando:** un clone pulito contiene i Parquet e l'app parte senza scaricare niente."

crea "M7 - Pubblicazione" "deploy" "M7-T2 requirements.txt per Streamlit Cloud" \
  "Streamlit Cloud non legge pyproject.toml. Generarlo con uv export.

**Fatto quando:** il file rispecchia le versioni di uv.lock."

crea "M7 - Pubblicazione" "deploy" "M7-T3 Deploy su Streamlit Community Cloud" \
  "**Fatto quando:** l'indirizzo pubblico si apre da telefono e tutte le viste funzionano."

crea "M7 - Pubblicazione" "docs" "M7-T4 README completo" \
  "Cosa fa, come si esegue, i numeri del modello, le schermate, l'attribuzione, i limiti.

**Fatto quando:** chi arriva dal portfolio capisce il progetto in trenta secondi."

crea "M7 - Pubblicazione" "deploy" "M7-T5 Verifica della memoria" \
  "**Fatto quando:** con tutte le viste aperte l'app resta sotto il gigabyte."

crea "M7 - Pubblicazione" "docs" "M7-T6 NOTES.md, il diario degli inciampi" \
  "Creato in M1 e aggiornato lungo tutto il progetto: qui si verifica che sia completo.

**Fatto quando:** contiene almeno un'annotazione per milestone."

crea "M7 - Pubblicazione" "milestone-doc" "M7-T7 Documentazione della milestone M7" \
  "Compilare docs/milestones/M7-pubblicazione.md.

Procedura di deploy passo per passo, consumo di memoria misurato, tempi di risveglio dopo l'inattivita, e ogni sorpresa emersa fra ambiente locale e Streamlit Cloud.

**Fatto quando:** un'altra persona potrebbe ripetere il deploy seguendo solo questo file."

# ---- M8 ---------------------------------------------------------------
crea "M8 - Portfolio" "portfolio" "M8-T1 Schermate in .webp" \
  "**Fatto quando:** ogni immagine sta sotto i 200 KB."

crea "M8 - Portfolio" "portfolio" "M8-T2 Copertina e video dimostrativo" \
  "Copertina 16:9, video muto in loop sotto i 30 secondi con poster.

**Fatto quando:** il video pesa meno di 5 MB."

crea "M8 - Portfolio" "portfolio" "M8-T3 MDX italiano" \
  "Frontmatter compilato. Solo numeri misurati, presi dai file di milestone.

**Fatto quando:** npm run build non segnala errori di validazione."

crea "M8 - Portfolio" "portfolio" "M8-T4 MDX inglese" \
  "**Fatto quando:** il test del portfolio conferma che i campi condivisi coincidono."

crea "M8 - Portfolio" "portfolio,test" "M8-T5 Verifica finale del portfolio" \
  "**Fatto quando:** npm run check e npm run build sono verdi e la pagina si apre in entrambe le lingue."

crea "M8 - Portfolio" "milestone-doc,portfolio" "M8-T6 Documentazione finale e indice" \
  "Compilare docs/milestones/M8-portfolio.md e completare docs/milestones/README.md con l'indice di tutte le milestone, le date e i numeri chiave.

**Fatto quando:** tutti e otto i file esistono, l'indice li elenca, e i numeri nel MDX coincidono con quelli documentati."

echo "Fatto: 8 milestone, 11 etichette, 64 issue."
