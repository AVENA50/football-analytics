# Relazioni di milestone

Ogni milestone si chiude con il suo file. Non è documentazione di cortesia:
l'ultimo task di ciascuna milestone è esattamente questo, e **la milestone non
è completa finché il file non esiste**.

Il modello sta in [`_template.md`](_template.md) e si copia **all'inizio** della
milestone, non alla fine. Le note si aggiungono mentre si lavora: un file
scritto a caldo racconta cose che una ricostruzione a posteriori non ricorda
più.

---

## Stato

| # | Milestone | Issue | Stato | Relazione |
| --- | --- | --- | --- | --- |
| M1 | Fondamenta | 7 | 🟢 conclusa | [M1-fondamenta.md](M1-fondamenta.md) |
| M2 | Ingestione | 7 | 🟢 conclusa | [M2-ingestione.md](M2-ingestione.md) |
| M3 | Trasformazione | 8 | 🟢 conclusa | [M3-trasformazione.md](M3-trasformazione.md) |
| M4 | Esplorazione | 3 | 🟢 conclusa | [M4-esplorazione.md](M4-esplorazione.md) |
| M5 | Modello xG | 12 | 🟡 in corso — T1, T2, T3 chiusi | — |
| M6 | Dashboard | 14 | ⚪ da fare | — |
| M7 | Pubblicazione | 7 | ⚪ da fare | — |
| M8 | Portfolio | 6 | ⚪ da fare | — |

Legenda: ⚪ da fare · 🟡 in corso · 🟢 conclusa

## Numeri chiave

Si compilano man mano, e **solo con valori misurati**. Sono gli stessi che
finiranno nel frontmatter del case study: si prendono da qui, non si
ricalcolano a mano.

| Cosa | Valore | Da quale milestone |
| --- | --- | --- |
| Pacchetti bloccati in `uv.lock` | 68 | M1 |
| Competizioni scelte | 9 | M2 |
| Partite scaricate | 1.753 | M2 |
| Di cui con file 360 | 167 | M2 |
| Peso di `data/raw/` | 6,25 GB | M2 |
| Tiri analizzati | 43.849 | M3 |
| Gol | 4.578 | M3 |
| Tiri con freeze frame | 43.264 — 99 % | M3 |
| Peso di `data/processed/` | 2,87 MB | M3 |
| Test automatici | 131 | M3 |
| xG mediano di un tiro | 0,051 | M4 |
| Distanza mediana di tiro | 19 m | M4 |
| Conversione, 2 avversari inquadrati | 38,9 % | M4 |
| Conversione, 8+ avversari inquadrati | 7,2 % | M4 |
| Tiri analizzati | — | M3 |
| Peso di `data/processed/` | — | M3 |
| Brier score, modello base | — | M5 |
| Brier score, modello 360 | — | M5 |
| Scarto medio dall'xG StatsBomb | — | M5 |
| Test automatici | — | M7 |
