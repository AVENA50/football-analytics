# M3 — Trasformazione

> I Parquet esistono, sono corretti e sono piccoli. E i tiri portano con sé
> una colonna che il piano non sapeva di poter avere.

**Periodo:** 2026-08-07, in giornata · **Issue chiuse:** 8 / 8 · **Commit:** 5

---

## 1. Cosa è stato costruito

Il magazzino. Cinque tabelle Parquet che pesano **2,87 MB** in tutto e
contengono ciò che serve alle nove viste: 43.849 tiri, 1.753 partite, 4.810
righe di statistiche giocatore, 72.889 archi della rete dei passaggi e 698.395
celle di densità.

Il rapporto che riassume la milestone è questo: **6,25 GB di JSON grezzo
diventano 2,87 MB**, cioè un fattore 2.200. Non per compressione — per
selezione. Sei milioni di eventi contenevano l'informazione di 43.849 tiri e di
alcune migliaia di aggregati; il resto era struttura di supporto che nessuna
vista guarda.

Ma il pezzo che conta più delle dimensioni è un altro: **la costruzione si
interrompe se i numeri non tornano**. Su 1.753 partite, ogni risultato
calcolato dagli eventi viene confrontato con il tabellino ufficiale, e i gol
attribuiti ai giocatori con quelli delle partite. Non è una formalità: durante
questa milestone quel controllo ha trovato un gol del Marsiglia che il codice
perdeva, e l'ha trovato mesi prima che qualcuno aprisse una dashboard.

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

### Il magazzino completo (M3-T7)

Su tutte e 1.753 le partite.

| Tabella | Righe | Colonne | Peso |
| --- | ---: | ---: | ---: |
| `shots.parquet` | 43.849 | 34 | 1,65 MB |
| `touches.parquet` | 698.395 | 8 | 0,79 MB |
| `player_stats.parquet` | 4.810 | 19 | 0,23 MB |
| `passes.parquet` | 72.889 | 7 | 0,16 MB |
| `matches.parquet` | 1.753 | 22 | 0,05 MB |
| **Totale** | | | **2,87 MB** |

| Limite | Valore | Reale | Margine |
| --- | ---: | ---: | ---: |
| Per file (GitHub avverte) | 50 MB | 1,65 MB | 30× |
| Totale del magazzino | 100 MB | 2,87 MB | 35× |
| `passes` + `touches` (M3-T3) | 40 MB | **0,95 MB** | 42× |

**6,25 GB di JSON grezzo diventano 2,87 MB**, un fattore 2.200. Non per
compressione: per selezione.

### I contenuti

| Cosa | Valore |
| --- | ---: |
| Tiri | 43.849 |
| Gol | 4.578 |
| Tiri con `shot.freeze_frame` | 43.264 — **99 %** |
| Rigori finali, marcati ed esclusi dagli aggregati | 190 |
| Giocatori | 4.810, di cui 1.773 sopra i 500 minuti |
| Spezzoni con `to` precedente a `from` | 30 su 2.320 — 1,3 % |
| Squadre con due nomi negli eventi | 2 su 152 |
| Test | 131, nessuno con rete |
| Copertura di `transform.py` | 91 % |

Per gruppo:

| Gruppo | Tiri | Gol | xG StatsBomb |
| --- | ---: | ---: | ---: |
| Campionati 2015/16 | 37.888 | 3.869 | 3.746,8 |
| Tornei per nazionali | 5.367 | 635 | 656,2 |
| Finali di Champions | 594 | 74 | 73,5 |

### La verifica contro il mondo esterno

Le classifiche marcatori calcolate dal magazzino, confrontate con i fatti:

| Giocatore | Competizione | Calcolati | Ufficiali |
| --- | --- | ---: | ---: |
| Luis Suárez | La Liga 2015/16 | 40 | 40 — Pichichi |
| Gonzalo Higuaín | Serie A 2015/16 | 36 | 36 — record di Serie A |
| Cristiano Ronaldo | La Liga 2015/16 | 35 | 35 |
| Lionel Messi | La Liga 2015/16 | 26 | 26 |
| Zlatan Ibrahimović | Ligue 1 2015/16 | 36 | **38** |
| Cristiano Ronaldo | Euro 2020 | 5 | 5 — Scarpa d'Oro |
| Patrik Schick | Euro 2020 | 5 | 5 — Scarpa d'Oro |

**Lo scarto di Ibrahimović non è un difetto della pipeline, ed è spiegabile
esattamente.** Alla Ligue 1 2015/16 mancano 3 partite su 380 — le giornate 14,
23 e 36 ne hanno nove invece di dieci — e il Paris Saint-Germain è fra le sei
squadre a cui ne manca una. I due gol assenti sono in quella partita che
l'Open Data non pubblica.

Vale la pena dirlo così com'è: sapere **quale** partita manca è ciò che
distingue un dato incompleto da un dato sbagliato.

### Scelta: `passes` e `touches` non contengono passaggi e tocchi

**Alternativa scartata:** una riga per passaggio e una per tocco, come suggerisce il nome delle tabelle nel piano.

**Perché:** sarebbero 1,68 milioni e 6,12 milioni di righe, e — cosa che conta di più — **nessuna vista ne ha bisogno**. La rete dei passaggi mostra le posizioni medie e le linee fra i giocatori, spesse in proporzione ai passaggi scambiati: non le serve sapere che al 34' Acquafresca ha passato a Brienza da `[61.0, 40.1]`, le serve sapere che in stagione se lo sono scambiati 214 volte. La heatmap è, per definizione, una densità su griglia.

Salvare il dato grezzo per poi aggregarlo a ogni caricamento significa far fare a Streamlit Cloud, dentro un gigabyte di RAM, un lavoro che va fatto una volta sola qui.

Risultato: 72.889 archi invece di 1,68 milioni di passaggi, 698.395 celle invece di 6,12 milioni di tocchi. **0,95 MB contro un limite di 40.**

Le posizioni medie — i nodi della rete — stanno in `player_stats.parquet`, che ha già la grana giusta. E non vengono dalla griglia ma dalle coordinate esatte: approssimare un nodo al centro di una cella sposterebbe un giocatore fino a 2,5 metri per nessun guadagno.

### Scelta: `Pressure` non è un tocco

**Alternativa scartata:** contare come tocco ogni evento con una posizione e un giocatore.

**Perché:** la pressione è un'azione **senza** palla, registrata alla posizione di chi pressa. Sono 310 eventi a partita, il 9 % del totale, e includerli riempirebbe la heatmap di un mediano di zone in cui non ha mai toccato il pallone. La heatmap risponde alla domanda «dove ha giocato», non «dove è stato».

### Scelta: l'identità di una squadra è il suo identificativo

**Alternativa scartata:** confrontare per nome, che è leggibile e sembra funzionare.

**Perché:** non funziona. Due squadre su 152 compaiono negli eventi con un nome diverso da quello del file partite — «Marseille» contro «Olympique de Marseille», «Caen» contro «Stade Malherbe Caen» — e il confronto per nome faceva risultare a zero i loro gol. È lo stesso principio già applicato ai giocatori poche ore prima, e non applicato alle squadre: vedi la sezione 5.

## 5. Problemi incontrati

Il racconto a caldo è in [`NOTES.md`](../../NOTES.md). Quattro episodi, e i due
più istruttivi riguardano i controlli stessi.

**`shot.freeze_frame` era ovunque.** L'architettura si reggeva sull'idea che
solo alcune competizioni permettessero il modello con le variabili spaziali. È
presente nel **99 %** dei 43.849 tiri, campionati del 2015/16 compresi. Il
confronto fra i due modelli passa da ~5.500 a ~44.000 tiri.

**Una fixture in cui avevo dichiarato il risultato sbagliato**, smascherata dal
test scritto per verificare proprio i risultati. E un test che guastava una
tabella scrivendoci il valore che aveva già, quindi non verificava nulla.

**Il gol del Marsiglia**, perso perché confrontavo le squadre per nome. È lo
stesso errore dei giocatori sdoppiati di poche ore prima, con un'altra
maschera: avevo imparato la regola su un caso e non l'avevo cercata altrove.

**Due tiri a 20 centimetri oltre la linea di porta**, e qui il controllo aveva
torto: rumore di misura del tracciamento, non dati sbagliati. Corretto il
controllo, non i dati.

Gli ultimi due casi insieme sono la lezione della milestone: **un controllo che
si allarma va prima capito, non subito obbedito né subito allentato.** Con il
Marsiglia aveva ragione e ho corretto il codice; con i due tiri aveva torto e
ho corretto il controllo. Sbagliare la distinzione nella prima direzione
lascia passare dati falsi; nella seconda produce falsi allarmi, e un controllo
che dà falsi allarmi viene disattivato — e da quel momento non trova più
nemmeno i problemi veri.

## 6. Cosa resta aperto

- **I Parquet non sono versionati, e non ancora di proposito.** M7-T1 li vuole
  in git, ma finché si rigenerano a ogni passo ogni versione sarebbe una copia
  intera nella cronologia — git non fa diff dei binari — e `main` è protetto
  contro il force push, quindi non si tornerebbe indietro. Sono esclusi da
  `.gitignore` con un promemoria esplicito per M7-T1.
- **`freeze_frames.parquet` non esiste ancora.** Il contenuto dei fotogrammi
  serve a M5 per calcolare i difensori nel cono di tiro. Sarà una tabella a
  parte, una riga per giocatore inquadrato — una deviazione consapevole dalle
  cinque tabelle previste dal piano, che non poteva prevederla.
- **La rete dei passaggi è a livello di competizione, non di partita.** Le nove
  viste non chiedono la rete di una singola partita, ma è una porta che si
  chiude: riaprirla significa passare a 350.000 archi invece di 73.000, ancora
  ampiamente gestibili.
- **La verifica copre i gol, non i tiri.** Il criterio di M3-T1 nomina
  entrambi; i conteggi dei tiri non hanno una fonte ufficiale con cui
  confrontarsi nell'Open Data.
- **Alla Ligue 1 2015/16 mancano 3 partite su 380.** È un limite della fonte,
  non della pipeline, ma va dichiarato nella vista Metodologia: i totali di
  quel campionato sono leggermente inferiori a quelli ufficiali.

## 7. Come verificarlo

```bash
uv run pytest -m "not rete"
uv run python scripts/build_dataset.py
```

Il secondo comando ricostruisce l'intero magazzino con tutti i controlli
attivi. Se una sola partita fra 1.753 avesse il risultato incoerente, o un
tiro finisse fuori dal campo oltre la tolleranza, si fermerebbe indicando quale
— **senza scrivere niente**.

Rilanciarlo produce file identici: le righe delle tabelle aggregate escono
ordinate per chiave proprio per questo.
