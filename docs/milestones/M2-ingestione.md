# M2 — Ingestione

> I dati grezzi sono sul disco, scaricati una volta e riscaricabili — e le
> competizioni sono quelle che esistono davvero, non quelle che il piano
> presumeva.

**Periodo:** dal 2026-08-07 al \_\_ · **Issue chiuse:** \_\_ / 7 · **Commit:** \_\_

> Questo file viene compilato **mentre** la milestone procede, non alla fine.
> Le sezioni con `__` sono ancora aperte.

---

## 1. Cosa è stato costruito

<!-- Da completare a fine milestone. -->

Finora: il registro delle competizioni in `config.py`, verificato contro
StatsBomb, e lo script che ha permesso di verificarlo.

## 2. File creati e modificati

| File | Cosa fa |
| --- | --- |
| `src/football_analytics/config.py` | Tipo `Competizione`, enum `Gruppo` e `Copertura360`, le nove competizioni |
| `tests/test_competizioni.py` | 14 test offline sul registro + 18 di rete che lo confrontano con StatsBomb |
| `scripts/esplora_open_data.py` | Conta le partite di ogni stagione dell'Open Data e ne riporta i dati 360 |

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

| Cosa | Valore |
| --- | --- |
| Peso di `data/raw/` | \_\_ |
| Durata dello scaricamento completo | \_\_ |
| Partite con `has_360` vero (M2-T4) | \_\_ |

## 5. Problemi incontrati

Il racconto a caldo è in [`NOTES.md`](../../NOTES.md). In sintesi: il piano si
sbagliava su metà delle competizioni, e la prima versione dello script di
esplorazione dichiarava i dati 360 disponibili ovunque perché `bool(NaN)` in
Python vale `True`.

<!-- Il resto si aggiunge man mano. -->

## 6. Cosa resta aperto

- **Il peso dei Parquet è un rischio noto.** 1.517 partite di campionato sono
  circa il 40 % in più di quanto il piano prevedeva. `passes` e `touches`
  andranno aggregati a monte per stare sotto i limiti di M3-T7.
- **Le finali di Champions dichiarano `ASSENTE` per i 360.** Il piano diceva
  «parziale»; il valore attuale viene dal campo dichiarato da StatsBomb e lo
  verifica un test di rete. Se M2-T4 trovasse freeze frame in qualche finale
  recente, il valore va corretto.
- **I frammenti di club con i 360 restano inutilizzati**: 101 partite scartate
  per una ragione metodologica, non tecnica. Se un domani servisse più volume
  per il modello 360, sono la prima riserva.

## 7. Come verificarlo

```bash
uv run pytest -m "not rete"          # coerenza interna del registro
uv run pytest -m rete                # confronto con StatsBomb: conteggi e 360
uv run python scripts/esplora_open_data.py --tutte --min 30
```

I test di rete sono la verifica vera: confrontano ogni numero scritto in
`config.py` con quello che StatsBomb pubblica oggi. Se un giorno l'Open Data
cambia, sono loro ad accorgersene.
