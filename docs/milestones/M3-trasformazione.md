# M3 — Trasformazione

> I Parquet esistono, sono corretti e sono piccoli. E i tiri portano con sé
> una colonna che il piano non sapeva di poter avere.

**Periodo:** dal 2026-08-07 al \_\_ · **Issue chiuse:** \_\_ / 8 · **Commit:** \_\_

> Questo file viene compilato **mentre** la milestone procede. Le sezioni con
> `__` sono ancora aperte.

---

## 1. Cosa è stato costruito

<!-- Da completare a fine milestone. -->

Finora: `shots.parquet`, una riga per tiro, con la verifica del risultato che
interrompe la costruzione se i gol calcolati non coincidono con il tabellino.

## 2. File creati e modificati

| File | Cosa fa |
| --- | --- |
| `src/football_analytics/transform.py` | Dagli eventi grezzi alle righe di `shots.parquet`, con i controlli |
| `tests/test_transform.py` | 22 test, nessuno tocca la rete |
| `tests/fixtures/eventi_campione.json` | Una partita inventata che contiene tutte le trappole del conteggio |

## 3. Decisioni tecniche

### Scelta: la colonna si chiama `ha_fotogramma`, non `has_360`

**Alternativa scartata:** il nome previsto dal piano, `has_360`.

**Perché:** descriveva la cosa sbagliata. StatsBomb pubblica due tipi di freeze frame, e il piano li trattava come uno solo:

| | `shot.freeze_frame` | file `three-sixty/` |
| --- | --- | --- |
| Dove | dentro l'evento di tiro | file separato, 6,5 MB a partita |
| Quando | solo al momento del tiro | tutti i ~3.400 eventi |
| Contiene | posizione, **nome**, **ruolo**, compagno sì/no | posizione, compagno, portiere, attore |
| In più | — | area inquadrata dalla telecamera |
| Disponibile | ~97 % dei tiri, in **tutte** le competizioni | solo alcune competizioni |

Al modello xG serve il primo — quello che dice dove stavano i difensori quando è partito il tiro — ed è anche il più ricco dei due. La colonna deve dire cosa contiene.

**Conseguenza sull'architettura:** il confronto fra modello base e modello con le variabili spaziali non è più limitato alle 218 partite dei tornei. Può girare su tutte e 1.753, cioè circa 44.000 tiri invece di 5.500.

### Scelta: i rigori finali restano in tabella, marcati da una colonna

**Alternativa scartata:** escluderli dalla trasformazione.

**Perché:** i tiri del periodo 5 sono 38 su 1.289 in Euro 2020, e valgono **24 gol**. Escluderli perderebbe i tiri dal dischetto che la vista Partite mostra quando racconta una finale decisa ai rigori; includerli senza distinguerli renderebbe sbagliato ogni risultato di ogni partita a eliminazione diretta. Una colonna booleana risolve entrambi i problemi e lascia la scelta a chi legge la tabella.

### Scelta: nessuna distanza né angolo in `shots.parquet`

**Alternativa scartata:** calcolare qui le variabili geometriche, dato che i dati ci sono già.

**Perché:** distanza e angolo sono **variabili del modello**, e vivono in `features.py` (M5-T1). Se domani cambio la definizione dell'angolo di tiro — cosa probabile, è una scelta con diverse convenzioni — non voglio dover ricostruire il magazzino da sei milioni di eventi. In `shots.parquet` restano `x` e `y` grezze.

### Scelta: i tipi delle colonne sono dichiarati, non dedotti

**Alternativa scartata:** lasciare che pandas deduca i tipi.

**Perché:** non è pignoleria, è RAM. Su 44.000 righe, una colonna `object` invece di `category` è la differenza fra due e venti megabyte, e Streamlit Cloud ne ha mille in tutto. Il dizionario `TIPI_TIRI` è anche documentazione: dice quali colonne esistono e cosa contengono, in un posto solo.

### Scelta: la verifica del risultato interrompe, non avvisa

**Alternativa scartata:** registrare le discrepanze e proseguire.

**Perché:** una pipeline che prosegue con dati incoerenti produce numeri che *sembrano* veri. Sono i peggiori: nessuno li controlla, perché non c'è niente di visibilmente rotto. Meglio fermarsi e costringere a capire.

## 4. Numeri misurati

Su 57 partite scaricate — Euro 2020 completa, più tre di Serie A 2015/16 e tre
finali di Champions come campione.

| Competizione | Tiri | Gol | xG StatsBomb | Con `freeze_frame` |
| --- | ---: | ---: | ---: | ---: |
| Euro 2020 | 1.289 | 155 | 163,17 | 1.247 — 97 % |
| Finali Champions (3) | 85 | 11 | 7,22 | 84 — 99 % |
| Serie A 2015/16 (3) | 66 | 7 | 5,80 | 64 — 97 % |
| **Totale** | **1.440** | **173** | **176,19** | **1.395** |

**Partite con risultato non coincidente: 0 su 57.**

Una lettura di controllo: Euro 2020 mostra 155 gol contro 163 di xG, che
sembrerebbe uno scarto. Ma 24 di quei gol sono rigori finali da ~0,76 di xG
ciascuno. Tolti quelli restano 131 gol da tiro contro ~145 di xG, e sommando
gli 11 autogol si arriva a 142 gol reali. Gol e xG praticamente coincidono, che
è ciò che ci si aspetta su un torneo intero.

| Cosa | Valore |
| --- | --- |
| Colonne di `shots.parquet` | 34 |
| Test di `transform.py` | 22, nessuno con rete |
| Copertura di `transform.py` | 88 % |
| Peso di `shots.parquet` | \_\_ |
| Tiri sul dataset completo | \_\_ |

## 5. Problemi incontrati

Il racconto a caldo è in [`NOTES.md`](../../NOTES.md). I due episodi di questa
milestone: la scoperta che `shot.freeze_frame` è presente ovunque — che ha
allargato il modello da 5.500 a 44.000 tiri — e una fixture in cui avevo
dichiarato il risultato sbagliato, smascherata dal test scritto per verificare
proprio i risultati.

## 6. Cosa resta aperto

- **`freeze_frames.parquet` non esiste ancora.** Il contenuto dei fotogrammi
  serve a M5 per calcolare i difensori nel cono di tiro. Sarà una tabella a
  parte, una riga per giocatore inquadrato — una deviazione consapevole dalle
  cinque tabelle previste dal piano, che non poteva prevederla.
- **Il peso di `passes` e `touches` è il rischio principale di M3.** Con 1.517
  partite di campionato, salvare ogni passaggio supererebbe i limiti: andranno
  pre-aggregati a monte.
- **La verifica copre i gol, non ancora i tiri.** Il criterio di M3-T1 nomina
  entrambi; i conteggi dei tiri non hanno una fonte ufficiale con cui
  confrontarsi nell'Open Data.

## 7. Come verificarlo

```bash
uv run pytest -m "not rete" tests/test_transform.py

uv run python -c "from football_analytics import transform, config; \
  df = transform.costruisci_tiri(config.COMPETIZIONI); print(df.shape)"
```

Il secondo comando ricostruisce la tabella dalle partite presenti su disco con
la verifica attiva: se una sola partita avesse il risultato incoerente, si
fermerebbe indicando quale.
