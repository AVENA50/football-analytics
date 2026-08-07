# M2 — Ingestione

> I dati grezzi sono sul disco, scaricati una volta e riscaricabili — e le
> competizioni sono quelle che esistono davvero, non quelle che il piano
> presumeva.

**Periodo:** 2026-08-07, in giornata · **Issue chiuse:** 7 / 7 · **Commit:** 4

---

## 1. Cosa è stato costruito

Prima di M2 il progetto sapeva trasformare dati che non aveva. Adesso ha
**1.753 partite** su disco — 6,25 GB di JSON grezzo — scaricate da un comando
che si può interrompere e rilanciare senza perdere niente.

Il pezzo che rende possibile tutto il resto è la ripartenza. Non è una comodità:
migliaia di richieste separate a GitHub significano che *qualcosa* andrà storto,
e senza ripartenza ogni interruzione ricomincia da zero. Rilanciare
l'ingestione su dati già presenti termina in meno di un secondo con zero
richieste di contenuto, e lo si verifica contando le chiamate, non
cronometrando.

Ma la cosa che questa milestone ha davvero prodotto non è il download: è la
**correzione del piano**. Le competizioni scelte all'inizio avevano un decimo
delle partite previste, e nessuno lo sapeva perché i numeri sembravano giusti.
Il progetto che esce da M2 lavora su fonti verificate una per una, e ogni
numero in `config.py` è confrontato con StatsBomb da un test.

## 2. File creati e modificati

| File | Cosa fa |
| --- | --- |
| `src/football_analytics/config.py` | Tipo `Competizione`, enum `Gruppo` e `Copertura360`, le nove competizioni |
| `src/football_analytics/ingest.py` | Lo strato 1: scaricamento incrementale, atomico, in parallelo, più il registro |
| `tests/test_competizioni.py` | 14 test offline sul registro + 18 di rete che lo confrontano con StatsBomb |
| `tests/test_ingest.py` | 21 test sull'ingestione, nessuno tocca la rete |
| `scripts/esplora_open_data.py` | Conta le partite di ogni stagione dell'Open Data e ne riporta i dati 360 |
| `scripts/scarica_dati.py` | La riga di comando dell'ingestione, con `--riepilogo` per il README |

## 3. Decisioni tecniche

### Scelta: le competizioni del piano sono state sostituite

**Alternativa scartata:** tenere Ligue 1 2021/22 e Bundesliga 2023/24 così com'erano, correggendo i numeri attesi da 380 e 306 a 26 e 34.

**Perché:** avrebbe fatto passare il test senza risolvere il problema. Quelle due erano le uniche fonti di dati 360 del progetto: 60 partite in tutto, circa 1.500 tiri, da dividere fra addestramento e verifica per **due** modelli da confrontare fra loro. Un confronto su quei numeri non avrebbe potuto distinguere una differenza reale dal rumore, e il risultato più raccontabile del progetto sarebbe stato il meno difendibile.

### Scelta: separare i campionati dai tornei

**Alternativa scartata:** un insieme unico di competizioni, come nel piano, dove le stesse leghe servivano sia all'esplorazione sia al confronto fra modelli.

**Perché:** i dati non lo permettono. Nell'Open Data **nessun campionato completo ha i freeze frame, e nessuna competizione con i freeze frame è un campionato completo**. Il piano legava le due cose — tre leghe, due con i 360 e una senza — e quel legame semplicemente non esiste. Tenerli separati permette di avere sia il volume (1.517 partite di campionato) sia la ricchezza (218 partite con i 360), invece di dover scegliere.

L'enum `Gruppo` rende la separazione esplicita nel codice, così una vista non può per sbaglio mescolare i due insiemi.

### Scelta: quattro campionati della stessa stagione

**Alternativa scartata:** tre leghe da tre stagioni diverse, come nel piano — Ligue 1 21/22, Bundesliga 23/24, Serie A 15/16.

**Perché:** è un miglioramento arrivato per caso. Cercando sostituti è emerso che La Liga, Premier League, Serie A e Ligue 1 hanno tutte la stagione 2015/16 completa nell'Open Data. Confrontare leghe di annate diverse ha un difetto che il piano non aveva notato: se una mostra meno gol dell'altra, non si può dire se dipenda dal campionato o dagli otto anni che le separano. Con la stessa stagione l'ambiguità sparisce, e la vista *Confronto leghe* smette di aver bisogno di un asterisco.

Costo accettato: 1.517 partite invece di 1.066 significa più tempo di scaricamento e più pressione sul limite dei 50 MB per Parquet. `passes` e `touches` andranno pre-aggregati a monte — posizioni medie invece di ogni passaggio, griglia di densità invece di ogni tocco.

### Scelta: solo tornei maschili per il confronto fra modelli

**Alternativa scartata:** aggiungere Mondiali femminili 2023 ed Europei femminili 2022 e 2025, che avrebbero portato l'insieme da 218 a 344 partite.

**Perché:** un modello xG addestrato su calcio maschile e femminile insieme mescola due distribuzioni di tiro diverse. Non è un ostacolo insormontabile — sarebbe anzi un'analisi interessante — ma richiederebbe di dimostrare che la cosa non distorce il confronto fra base e 360, che è la domanda a cui il progetto vuole rispondere. Due domande in un progetto solo ne indeboliscono entrambe.

Scartati per lo stesso motivo i frammenti di club con i 360 (La Liga 2020/21, Bundesliga 2023/24, Ligue 1 2021/22 e 2022/23): riguardano una squadra sola, quindi il campione non rappresenta il campionato da cui viene.

### Scelta: si parte da Euro 2020, non da un campionato

**Alternativa scartata:** cominciare dal campionato più grande, come suggeriva il piano con la Ligue 1.

**Perché:** Euro 2020 ha 51 partite ed è la più piccola fra le competizioni complete scelte, ma ha i dati 360, quindi esercita anche il percorso dei freeze frame. Un difetto in `transform.py` si scopre dopo tre minuti invece che dopo venti, e si scopre su entrambi i rami del codice invece che su uno solo.

### Scelta: HTTP diretto invece di `statsbombpy` per gli eventi

**Alternativa scartata:** usare `statsbombpy` per tutto, come indicava il piano.

**Perché:** la libreria restituisce DataFrame già appiattiti, e i freeze frame dei dati 360 sono profondamente annidati — contengono la posizione di ogni giocatore in campo al momento dell'evento. Appiattirli nello strato 1 per poi ricostruirli in M5 significa perdere informazione e scrivere due volte lo stesso codice. Lo strato 1 salva il JSON byte per byte, che è letteralmente cosa vuol dire «grezzo»; chi vuole i DataFrame se li costruisce nello strato 2.

`statsbombpy` resta in uso per l'indice delle competizioni, dove la comodità del DataFrame non costa niente.

### Scelta: scrittura atomica, non semplice «il file esiste»

**Alternativa scartata:** scaricare direttamente sul percorso finale e saltare i file già presenti.

**Perché:** sarebbe stato sufficiente finché nulla va storto. Se il processo muore a metà scaricamento — rete che cade, `Ctrl+C`, batteria scarica — sul disco resta un file **troncato**, che alla ripartenza verrebbe scambiato per completo. Il difetto non si manifesta subito: emerge in M3, quando `transform.py` trova un JSON malformato, e a quel punto nessuno collega la cosa all'ingestione.

Ogni file viene quindi scritto in un temporaneo e poi rinominato, operazione atomica sia su Windows sia su Unix. Un file al percorso finale è per costruzione un file completo.

### Scelta: i freeze frame si chiedono solo dove esistono

**Alternativa scartata:** chiederli per tutte le partite e trattare il 404 come «assente».

**Perché:** avrebbe funzionato, ma 1.535 partite su 1.753 non hanno i 360, e ogni esecuzione avrebbe prodotto 1.535 richieste destinate a fallire. La seconda esecuzione non sarebbe più finita «in pochi secondi» come richiede il criterio di M2-T2. Il file delle partite dichiara `match_status_360` per ognuna: si legge quello.

### Scelta: il criterio di M2-T2 è verificato contando le richieste

**Alternativa scartata:** un test che misura il tempo della seconda esecuzione.

**Perché:** un test cronometrico passa o fallisce a seconda di quanto è carico il computer, e prima o poi diventa quel test che «ogni tanto fallisce» e che si finisce per ignorare. Il test sostituisce `preleva` con una funzione che conta le chiamate, e verifica che dopo la prima esecuzione il contatore non si muova più. Dice la verità sempre.

## 4. Numeri misurati

Tutti da `scripts/esplora_open_data.py --tutte --min 30`, eseguito il 2026-08-07.

| Gruppo | Competizioni | Partite | Dati 360 |
| --- | --- | --- | --- |
| Campionati 2015/16 | La Liga, Premier, Serie A, Ligue 1 | 1.517 | no |
| Tornei per nazionali | Mondiali 2022, Coppa d'Africa 2023, Euro 2024, Euro 2020 | 218 | sì |
| Finali di Champions | 18 stagioni, una finale ciascuna | 18 | no |
| **Totale** | **9** | **1.753** | |

Il dettaglio per competizione:

| Competizione | id | Partite |
| --- | --- | --- |
| La Liga 2015/16 | 11, 27 | 380 |
| Premier League 2015/16 | 2, 27 | 380 |
| Serie A 2015/16 | 12, 27 | 380 |
| Ligue 1 2015/16 | 7, 27 | 377 |
| Coppa del Mondo 2022 | 43, 106 | 64 |
| Coppa d'Africa 2023 | 1267, 107 | 52 |
| Campionato Europeo 2024 | 55, 282 | 51 |
| Campionato Europeo 2020 | 55, 43 | 51 |
| Finali di Champions | 16 | 18 |

Ligue 1 2015/16 ha **377** partite e non 380: tre mancano nell'Open Data. Il
numero riportato è quello misurato, non quello che ci si aspetterebbe da un
campionato a venti squadre — ed è esattamente il tipo di scarto che questa
milestone esiste per intercettare.

Nell'Open Data ci sono in tutto **445 partite con i dati 360**, distribuite su
10 stagioni; il progetto ne usa 218.

### Lo scaricamento, misurato su Euro 2020

| Cosa | Valore | Come |
| --- | --- | --- |
| File scaricati | 153 | 51 partite × eventi + formazioni + freeze frame |
| Durata, prima esecuzione | 10,1 s | 8 richieste in parallelo, ~15 file al secondo |
| Durata, seconda esecuzione | 0,0 s | 0 file scaricati, 153 già presenti |
| Peso su disco | 516,9 MB | `data/raw/manifest.json` |
| Partite con dati 360 | 51 su 51 | `match_status_360` nel file delle partite |
| File `.parziale` rimasti | 0 | la scrittura atomica non lascia residui |

La seconda esecuzione a **0,0 secondi con zero file scaricati** è il criterio di
completamento di M2-T2, verificato sul campo oltre che nei test.

### Peso per partita, ed estrapolazione

| | Per partita | Su 1.753 partite |
| --- | ---: | ---: |
| Eventi | 3,1 MB | ~5,4 GB |
| Formazioni | 24 KB | ~42 MB |
| Freeze frame (solo 218 partite) | 7,1 MB | ~1,5 GB |
| **Totale stimato** | | **~7 GB** |

La stima iniziale era di 4,5 GB ed era sbagliata del 50 %: veniva da un'ipotesi
sulla dimensione dei file, non da una misura. Ora viene da 51 partite reali.

### Lo scaricamento completo

| Competizione | Gruppo | Partite | Attese | Con file 360 | Peso |
| --- | --- | ---: | ---: | ---: | ---: |
| La Liga 2015/16 | campionato | 380 | 380 | 0 | 1.076 MB |
| Premier League 2015/16 | campionato | 380 | 380 | 0 | 1.083 MB |
| Serie A 2015/16 | campionato | 380 | 380 | 0 | 1.111 MB |
| Ligue 1 2015/16 | campionato | 377 | 377 | 0 | 1.115 MB |
| Coppa del Mondo 2022 | torneo | 64 | 64 | 64 | 630 MB |
| Coppa d'Africa 2023 | torneo | 52 | 52 | **1** | 134 MB |
| Campionato Europeo 2024 | torneo | 51 | 51 | 51 | 535 MB |
| Campionato Europeo 2020 | torneo | 51 | 51 | 51 | 517 MB |
| Finali di Champions | finali | 18 | 18 | 0 | 54 MB |
| **Totale** | | **1.753** | **1.753** | **167** | **6.255 MB** |

**Tutti i conteggi coincidono con gli attesi.** Sono gli stessi numeri
verificati in M2-T1 contro l'indice di StatsBomb, ritrovati contando i file su
disco.

| Cosa | Valore | Come |
| --- | --- | --- |
| File scaricati | 3.699 | 1.753 eventi + 1.753 formazioni + 167 freeze frame + 26 elenchi |
| Peso di `data/raw/` | 6,25 GB | eventi 5,0 GB · 360 1,2 GB · formazioni 37 MB |
| Peso medio, partita senza 360 | 2,92 MB | Serie A 2015/16 |
| Peso medio, partita con 360 | 10,1 MB | Euro 2020 |
| Velocità | ~22 file al secondo | 760 file di Serie A in 34,1 s |
| Seconda esecuzione | 0 file, 0,0 s | il criterio di M2-T2 |
| File `.parziale` rimasti | 0 | la scrittura atomica non lascia residui |

### La disponibilità dei dati 360 (M2-T4)

Il campo `match_status_360` ha **quattro** valori, non due, e solo il primo
significa che il file esiste:

| Competizione | `available` | `processing` | `scheduled` | `unscheduled` |
| --- | ---: | ---: | ---: | ---: |
| Euro 2020 | 51 | | | |
| Euro 2024 | 51 | | | |
| Coppa del Mondo 2022 | 64 | | | |
| **Coppa d'Africa 2023** | **1** | | | 51 |
| Premier League 2015/16 | | 200 | 180 | |
| La Liga 2015/16 | | | 33 | 347 |
| Serie A 2015/16 | | | | 380 |
| Ligue 1 2015/16 | | | | 377 |
| Finali di Champions | | | 16 | 2 |

`scheduled` e `processing` dicono che StatsBomb **ha in programma** di produrre
quei dati. Sono promesse, non file — e trattarle come disponibili avrebbe
prodotto un progetto che si aspetta 380 partite di Premier League con i freeze
frame e ne trova zero.

## 5. Problemi incontrati

Il racconto a caldo è in [`NOTES.md`](../../NOTES.md). Tre episodi, con un
filo comune.

**Il piano si sbagliava su metà delle competizioni.** Ligue 1 2021/22 doveva
avere 380 partite e ne ha 26; Bundesliga 2023/24 doveva averne 306 e ne ha 34.
StatsBomb pubblica anche sottoinsiemi tematici — le partite di Messi, la
stagione del Leverkusen — e i numeri del piano erano plausibili ma mai
verificati.

**`bool(NaN)` vale `True`.** La prima versione dello script di esplorazione
dichiarava i dati 360 disponibili per tutte e quaranta le stagioni, comprese
quelle che sicuramente non li avevano. Con pandas il valore mancante non è
falso, e ogni controllo di verità su una cella che può essere vuota va scritto
con `pd.notna`.

**L'indice competizioni mente per omissione.** Avevo dichiarato la Coppa
d'Africa 2023 coperta dai dati 360 fidandomi del campo `match_available_360`,
che è a livello di competizione e diventa non nullo anche se **una sola**
partita ha i file. Su 52 ne ha una. Il dato affidabile è `match_status_360`,
partita per partita. Il test di rete ora legge quello.

Il filo comune: **ogni volta la fonte sbagliata era quella più comoda da
leggere.** Un numero nel piano, un campo aggregato, una cella che sembra falsa.
La fonte giusta costava sempre un passo in più.

## 6. Cosa resta aperto

- **I file 360 sono scaricati ma quasi inutili.** M3-T1 ha scoperto che al
  modello xG serve `shot.freeze_frame`, che sta dentro gli eventi ed è presente
  nel 95-99 % dei tiri di **tutte** le competizioni. Gli 1,2 GB di
  `three-sixty/` coprono anche gli eventi diversi dai tiri, cosa che nessuna
  delle nove viste usa. Sono stati tenuti per scelta esplicita, come riserva
  per analisi spaziali future.
- **`data/raw/` pesa 6,25 GB** e non è versionato, giustamente. Chi clona il
  repository deve rieseguire lo scaricamento: dieci minuti, documentati nel
  README.
- **La Coppa d'Africa 2023 resta nel gruppo dei tornei** pur avendo un file 360
  su 52. La scelta è consapevole: i gruppi separano per **tipo di
  competizione**, non per ricchezza dei dati, e ciò che serve al modello lì c'è.
- **I frammenti di club con i 360 restano inutilizzati**: 101 partite scartate
  per una ragione metodologica, non tecnica. Riguardano una squadra sola.

## 7. Come verificarlo

```bash
uv run pytest -m "not rete"          # coerenza interna del registro
uv run pytest -m rete                # confronto con StatsBomb: conteggi e 360
uv run python scripts/esplora_open_data.py --tutte --min 30
```

I test di rete sono la verifica vera: confrontano ogni numero scritto in
`config.py` con quello che StatsBomb pubblica oggi. Se un giorno l'Open Data
cambia, sono loro ad accorgersene.
