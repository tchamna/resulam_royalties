# KPI Tile Differences: Main vs Public Routes

- **File locations**
  - Main authors dashboard KPIs: `src/dashboard/app.py` (cards around the metrics row and callback near the metrics update function).
  - Public dashboard KPIs: `src/dashboard/public.py` (cards around the public metrics row and callback near the public metrics update function).

- **ID naming**
  - Main: `metric-books-sold`, `metric-net-revenue`, `metric-titles`, `metric-authors`, `metric-returns`.
  - Public: `public-metric-books-sold`, `public-metric-titles`, `public-metric-authors`.

- **Number of tiles / fields**
  - Main shows 5 tiles (books sold, net revenue, unique titles, authors, returns).
  - Public shows 3 tiles (books sold, unique titles, authors).

- **Visibility behavior**
  - Main hides the KPI row unless the Sales tab is active.
  - Public keeps the KPI row visible on all tabs.

- **Data/columns assumptions**
  - Public adds a safety layer to ensure `Net Units Sold`, `Units Sold`, royalty columns, and text columns exist (fallbacks/coercion).
  - Main assumes full schema is present (no fallback creation).

- **Filters applied**
  - Main filters: year-store, language, author, book type, book, category; outputs 5 values.
  - Public filters: year-store, language, author, book type, book, category; outputs 3 values.

- **Potential mismatch cause for missing numbers**
  - If the layout uses `public-metric-*` IDs but the callback still targets `metric-*`, values will stay blank. Likewise, missing required columns without the fallback can zero out results on public.

