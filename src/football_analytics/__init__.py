"""Football Analytics.

Pipeline sui dati evento per evento di StatsBomb Open Data: ingestione,
trasformazione in Parquet compatti, modello xG e dashboard Streamlit.

I dati provengono da StatsBomb Open Data. Chiunque pubblichi analisi basate su
questi dati e' tenuto a citare la fonte: vedi il README.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
