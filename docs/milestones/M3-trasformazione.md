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
| `src/football_analytics/transform.py` | Dagli eventi grezzi alle tre tabelle, con i controlli di coerenza |
| `tests/test_transform.py` | 22 test su `shots.parquet`, nessuno tocca la rete |
| `tests/test_partite_giocatori.py` | 19 test su partite e giocatori |
| `tests/fixtures/eventi_campione.json` | Una partita inventata con tutte le trappole del conteggio |
| `tests/fixtures/formazioni_campione.json` | Le formazioni della stessa partita, con uno spezzone invertito |

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

### Scelta: i minuti si misurano agli estremi, non sommando gli spezzoni

**Alternativa scartata:** sommare la durata di ogni spezzone di `positions`, che è il modo ovvio di leggere quella struttura.

**Perché:** produce minuti **negativi**. Nell'1,3 % degli spezzoni — 30 su 2.320 nelle sole 57 partite scaricate — StatsBomb pubblica un `to` precedente al `from`. Un giocatore però entra in campo una volta ed esce una volta: gli spezzoni intermedi esistono solo per registrare i cambi di posizione. Il tempo in campo è quindi `ultima uscita − primo ingresso`, e con quella formula l'anomalia diventa innocua.

È un principio più generale: quando un dato ha una struttura ridondante, conviene calcolare sull'**invariante** invece che sui pezzi. I pezzi possono essere incoerenti fra loro; l'invariante no.

### Scelta: la durata della partita si ferma al quarto periodo

**Alternativa scartata:** `max(Half End)` su tutti i periodi.

**Perché:** dava cinque giocatori francesi in campo per **129 minuti**. Francia-Svizzera finì ai rigori, e il quinto periodo chiude al 128'. Quattro partite di Euro 2020 ne erano affette. È la terza volta che il periodo 5 si intrufola dove non dovrebbe — prima nei gol, poi nei tiri delle statistiche giocatore, ora nella durata — e per questo esiste una costante `ULTIMO_PERIODO_DI_GIOCO` invece di un `5` scritto sul posto.

### Scelta: gli autogol stanno nelle partite ma non nei giocatori

**Alternativa scartata:** il criterio del backlog letto alla lettera — «la somma dei gol per giocatore coincide con quella per partita».

**Perché:** preso alla lettera è falso. Un autogol è un gol della squadra che ne beneficia, ma non si attribuisce al giocatore che lo subisce. `matches.parquet` tiene quindi tre colonne distinte — `gol_casa` (ufficiale), `gol_casa_da_tiro`, `autogol_casa` — e la verifica confronta i giocatori con i **gol da tiro**. Un secondo controllo verifica che `da_tiro + autogol == ufficiale`, che è l'identità che tiene insieme le due letture.

### Scelta: chi non entra in campo non ha una riga

**Alternativa scartata:** una riga a zero minuti per ogni convocato.

**Perché:** su Euro 2020 sono **849 giocatori** mai entrati, contro 1.743 con minuti reali. Una riga di soli zeri non aggiunge informazione e moltiplicherebbe la tabella per uno e mezzo, in un progetto dove ogni megabyte è RAM su Streamlit Cloud.

### Scelta: la chiave dei giocatori include la squadra

**Alternativa scartata:** una riga per giocatore e competizione.

**Perché:** in un campionato un giocatore può cambiare maglia a gennaio. Sommare le due metà della sua stagione sotto un'unica squadra darebbe una riga che non corrisponde a nessuna realtà, e la vista Squadre mostrerebbe fra i suoi giocatori uno che se n'è andato a metà anno.

### Il tempo reale, non i 90 nominali

Un tempo pieno vale circa **95 minuti**, non 90: il cronometro di StatsBomb include il recupero, e `Half End` del primo tempo cade tipicamente al 47'. Ho tenuto il tempo effettivo invece di normalizzare, perché è quello che i dati dicono.

**Conseguenza da dichiarare:** i valori per 90 minuti risultano circa il 5 % più conservativi di quelli pubblicati su siti che considerano un tempo pieno pari a 90. Va scritto nella pagina Metodologia (M6-T11), non lasciato scoprire a chi confronta.

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

### La verifica contro il mondo esterno

Tutti i controlli fino a M3-T1 erano **interni**: i gol calcolati tornano con i
risultati scritti nello stesso file. Una pipeline però può essere
internamente coerente e sbagliata — basta un errore sistematico che si propaga
ovunque. La classifica marcatori di Euro 2020 costruita da
`player_stats.parquet` è il primo confronto con un fatto pubblico:

| Giocatore | Squadra | Min | Partite | Tiri | Gol | xG | Gol/90 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Cristiano Ronaldo | Portogallo | 379 | 4 | 15 | 5 | 4,86 | 1,19 |
| Patrik Schick | Rep. Ceca | 406 | 5 | 16 | 5 | 2,26 | 1,11 |
| Romelu Lukaku | Belgio | 464 | 5 | 13 | 4 | 2,67 | 0,78 |
| Emil Forsberg | Svezia | 376 | 4 | 14 | 4 | 1,67 | 0,96 |
| Harry Kane | Inghilterra | 660 | 7 | 16 | 4 | 3,35 | 0,55 |
| Karim Benzema | Francia | 352 | 4 | 11 | 4 | 2,52 | 1,02 |

**È la classifica ufficiale del torneo.** Ronaldo e Schick vinsero la Scarpa
d'Oro a pari merito con 5 gol, seguiti da quei quattro a 4. Anche i minuti
tornano: Kane a 660 in 7 partite riflette l'Inghilterra arrivata in finale.

Interessante come sottoprodotto: Schick ha segnato 5 gol con 2,26 di xG, cioè
**+2,74** rispetto all'atteso. È il genere di osservazione che alimenterà i
riquadri insight di M6.

### Riepilogo

| Cosa | Valore |
| --- | --- |
| Colonne di `shots.parquet` | 34 |
| Colonne di `matches.parquet` | 22 |
| Colonne di `player_stats.parquet` | 17 |
| Partite trasformate | 57 |
| Righe in `player_stats` | 614 |
| Giocatori mai entrati, esclusi | 849 |
| Spezzoni con `to` precedente a `from` | 30 su 2.320 — 1,3 % |
| Test di `transform.py` | 41, nessuno con rete |
| Copertura di `transform.py` | 93 % |
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
