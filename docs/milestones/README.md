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
| M2 | Ingestione | 7 | 🟡 in corso | [M2-ingestione.md](M2-ingestione.md) |
| M3 | Trasformazione | 8 | ⚪ da fare | — |
| M4 | Esplorazione | 3 | ⚪ da fare | — |
| M5 | Modello xG | 12 | ⚪ da fare | — |
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
| Partite disponibili | 1.753 | M2 |
| Di cui con dati 360 | 218 | M2 |
| Partite scaricate | 51 | M2 |
| Peso di `data/raw/` | 516,9 MB | M2 |
| Tiri analizzati | — | M3 |
| Peso di `data/processed/` | — | M3 |
| Brier score, modello base | — | M5 |
| Brier score, modello 360 | — | M5 |
| Scarto medio dall'xG StatsBomb | — | M5 |
| Test automatici | — | M7 |
