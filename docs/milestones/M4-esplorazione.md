# M4 — Esplorazione

> Sappiamo cosa c'è nei dati prima di modellarli — e sappiamo una cosa che, se
> l'avessimo scoperta a M5, avrebbe corrotto il modello.

**Periodo:** 2026-08-07, in giornata · **Issue chiuse:** 3 / 3 · **Commit:** 1

---

## 1. Cosa è stato costruito

Un notebook che gira dall'inizio alla fine sui 43.849 tiri del magazzino, sei
osservazioni misurate, e le tre domande a cui la dashboard risponderà —
scritte nel README, non tenute in testa.

Ma il risultato che giustifica la milestone è uno solo: **la scoperta che sui
rigori la presenza del freeze frame dipende dall'esito del tiro**. È
distorsione da selezione, e sarebbe entrata nel modello di M5 senza che nulla
segnalasse un problema.

## 2. File creati e modificati

| File | Cosa fa |
| --- | --- |
| `notebooks/esplorazione.ipynb` | 27 celle: sei osservazioni, ognuna con il grafico e il commento |
| `README.md` | Le tre domande, con i numeri che le motivano |
| `pyproject.toml` | `jupyterlab` e `nbformat` fra le dipendenze di sviluppo |

## 3. Decisioni tecniche

### Scelta: Jupyter fra le dipendenze di sviluppo, non fra quelle del progetto

**Alternativa scartata:** aggiungerlo alle dipendenze principali.

**Perché:** Streamlit Cloud installa da `requirements.txt`, che rispecchia le dipendenze runtime. Un notebook non serve all'app: farlo installare in produzione significherebbe centinaia di megabyte per niente, dentro un gigabyte di RAM.

### Scelta: i rigori restano fuori dal modello xG

**Alternativa scartata:** includerli, dato che sono tiri come gli altri.

**Perché:** due ragioni, e la seconda l'ha trovata questa milestone. La prima è nota: un rigore ha xG praticamente fisso — 0,78 — e non dipende da dove sono i difensori, quindi non insegna niente al modello e ne sposta la calibrazione. La seconda è la distorsione da selezione descritta nella sezione 4: il fotogramma dei rigori è presente quasi solo quando il rigore sbaglia.

### Scelta: `ha_fotogramma` non sarà mai una variabile del modello

**Alternativa scartata:** usarla, dato che la colonna esiste ed è informativa.

**Perché:** è informativa **nel modo sbagliato**. Sui rigori predice l'esito all'88 % — non perché il fotogramma cambi il tiro, ma perché viene registrato quando il tiro fallisce. Un modello imparerebbe volentieri quella regola, e sarebbe un artefatto di raccolta travestito da conoscenza calcistica.

## 4. Numeri misurati

Tutti dal notebook, sui 43.659 tiri di gioco (esclusi i 190 rigori finali).

### La distribuzione dell'xG

| Cosa | Valore |
| --- | ---: |
| Media | 0,0991 |
| Mediana | 0,0509 |
| 90° percentile | 0,233 |
| 99° percentile | 0,784 |
| Tiri sotto 0,05 di xG | 49,3 % |
| Gol prodotti da quei tiri | 11,7 % |

Metà dei tiri ha meno di una probabilità su venti. **Con una classe positiva
intorno al 10 %, l'accuratezza è inutilizzabile:** un modello che risponde
sempre «non è gol» arriva al 90 %.

### La distanza

| Fascia | Tiri | Quota tiri | Quota gol | Conversione |
| --- | ---: | ---: | ---: | ---: |
| 0-6 m | 1.196 | 2,7 % | 11,8 % | 43,7 % |
| 6-11 m | 7.090 | 16,2 % | 29,2 % | 18,3 % |
| 11-16 m | 8.845 | 20,3 % | 32,8 % | 16,5 % |
| 16-22 m | 9.480 | 21,7 % | 15,5 % | 7,3 % |
| 22-30 m | 11.963 | 27,4 % | 8,7 % | 3,2 % |
| 30+ m | 5.085 | 11,6 % | 2,0 % | 1,7 % |

Distanza mediana di tiro: **19 metri**, ben oltre il limite dell'area.

### Gli avversari nel fotogramma — la domanda centrale

Solo tiri su azione, 41.179.

| Avversari inquadrati | Tiri | Conversione | Distanza media |
| ---: | ---: | ---: | ---: |
| ≤ 2 | 38 | 38,9 % | 16,2 m |
| 3 | 306 | 28,8 % | 16,4 m |
| 4 | 893 | 23,1 % | 16,2 m |
| 5 | 1.725 | 19,2 % | 16,4 m |
| 6 | 2.943 | 16,8 % | 17,3 m |
| 7 | 5.389 | 12,0 % | 18,3 m |
| 8+ | 31.885 | 7,2 % | 20,3 m |

**Un fattore cinque nella conversione, con la distanza quasi costante fra 3 e 7
avversari.** È il segnale che il modello spaziale dovrà catturare.

### Le quattro leghe, stessa stagione

| Lega | Gol/partita | Tiri/partita | xG/partita | Gol su xG |
| --- | ---: | ---: | ---: | ---: |
| La Liga | 2,74 | 24,13 | 2,58 | 1,035 |
| Premier League | 2,70 | 26,07 | 2,56 | 1,017 |
| Serie A | 2,58 | 26,31 | 2,42 | 1,033 |
| Ligue 1 | 2,52 | 23,38 | 2,32 | 1,047 |

### Il vantaggio di campo

| | In casa | In trasferta |
| --- | ---: | ---: |
| Gol | 2.284 — 57,1 % | 1.713 |
| xG | 2.110 — 56,3 % | 1.637 |
| Gol rispetto all'xG | **+8,2 %** | +4,7 % |

## 5. Problemi incontrati

### La trappola dei rigori

È l'osservazione che vale la milestone.

| Rigori | Numero | Conversione |
| --- | ---: | ---: |
| **senza** fotogramma | 426 | **81,9 %** |
| **con** fotogramma | 54 | **11,1 %** |

Il fotogramma di un rigore contiene **solo il portiere**, e StatsBomb lo allega
quasi esclusivamente quando il rigore non entra: serve a registrare la
posizione del portiere per analizzare la parata.

**La presenza del dato dipende dal risultato.** Un modello che usasse
`ha_fotogramma` come variabile imparerebbe «fotogramma presente, quindi
sbagliato» — che non è calcio, è un artefatto di raccolta.

Il modo in cui è emersa merita di essere raccontato: nel gruppo con zero o un
avversario inquadrato, la conversione era del 12,7 % con un xG medio di 0,788.
Un xG da rigore con una conversione da tiro da trenta metri. **Un numero che
non torna con un altro numero** — non un errore, non un'eccezione: una
contraddizione interna che ha richiesto di essere spiegata.

### La verifica che salva il progetto

| Tipo di tiro | Copertura del fotogramma |
| --- | ---: |
| Gioco aperto | **100 %** — 41.179 su 41.179 |
| Calci di punizione | **100 %** — 1.987 su 1.987 |
| Rigori | 11 % — 54 su 480 |

**La distorsione è confinata ai rigori.** Sui tiri su azione la copertura è
totale, quindi la presenza del dato non dice nulla sull'esito e il confronto
fra modello base e modello spaziale si può fare su tutti i 41.179 tiri senza
correzioni.

Se la copertura fosse stata parziale anche lì, M5 sarebbe stato un problema
molto diverso.

## 6. Cosa resta aperto

- **Il fotogramma è usato solo per contare gli avversari.** È
  l'approssimazione più grezza possibile: non distingue un difensore piazzato
  fra pallone e porta da uno alle spalle dell'attaccante. Le variabili vere —
  difensori nel cono di tiro, distanza del portiere — sono M5-T2.
- **Non è stata verificata la persistenza dello scarto gol−xG.** La domanda 2
  chiede «per quanto tempo», e rispondere richiede di dividere le stagioni in
  due metà e correlare. Va in M5 o nella vista Giocatori.
- **Le leghe sovraperformano l'xG dell'1,7-4,7 %, i tornei lo sottoperformano.**
  Non è chiaro se sia un effetto reale o una differenza di versione del modello
  xG di StatsBomb fra dati del 2015/16 e dati recenti. Va indagato quando ci
  sarà un modello proprio con cui confrontarsi.
- **I grafici sono pre-aggregati prima di passarli a Plotly.** L'istogramma
  dell'xG, scritto nel modo ovvio, avrebbe incorporato nell'output del notebook
  tutti i 43.659 valori grezzi — quasi un megabyte per un grafico che mostra
  sessanta barre. È lo stesso principio di M3-T3: aggregare a monte ciò che a
  valle serve solo aggregato.

## 7. Come verificarlo

```bash
uv sync --all-extras
uv run jupyter lab notebooks/esplorazione.ipynb
```

Eseguire tutte le celle dall'inizio alla fine. Ogni numero citato in questo
file compare nell'output di una cella; ogni grafico ha sopra o sotto un
commento che dice cosa mostra.

Le tre domande sono in `README.md`, sezione **Le tre domande**.
