# Golf Price Monitor

Web application for tracking and monitoring golf-related product prices with historical data and basic alert mechanisms.

**Source PRD / Epic:** https://bytecubed.atlassian.net/wiki/spaces/EA/pages/4658397185/PRD+Golf+Price+Monitoring+Application+2026-06-30

> ⚙️ This is an auto-generated prototype. A primary build workflow builds the
> foundation directly on the default branch; follow-on tickets live as GitHub issues
> and [Claude Code](https://github.com/anthropics/claude-code-action) implements each
> one as a pull request. Pull requests are merged by a human. See `CLAUDE.md`.

## Features

- **Product catalog** — track any golf equipment (drivers, irons, wedges, putters, balls, bags, shoes, apparel, accessories)
- **Manual price entry** — record price snapshots with date, retailer, and notes
- **Price history chart** — line chart of price over time for each product
- **Price change indicators** — see at a glance if the price went up or down
- **Lowest / highest price tracking** — summary stats per product
- **Search & filter** — find products by name, brand, or category
- **Stats dashboard** — total products, price entries, and detected price drops in the header

## Running

**Requirements:** Python 3.10+

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. (Optional) Load sample data to see the app with content
python seed.py

# 3. Start the server
python app.py
```

Then open **http://localhost:8000** in your browser.

The SQLite database (`golf_prices.db`) is created automatically on first run in the current directory. Override the path with the `DATABASE_PATH` environment variable.

## Project structure

```
golf-price-monitor/
├── app.py          # FastAPI application + REST API
├── database.py     # SQLite schema and connection helpers
├── seed.py         # Optional sample data loader
├── requirements.txt
└── static/
    ├── index.html  # Single-page application shell
    ├── app.js      # Frontend logic (vanilla JS + Chart.js)
    └── style.css   # Styles
```

## API

The REST API is available at `/api/` and auto-documented at **http://localhost:8000/docs**.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/products` | List products (supports `?search=` and `?category=`) |
| `POST` | `/api/products` | Create a product |
| `GET` | `/api/products/{id}` | Get product detail |
| `PUT` | `/api/products/{id}` | Update a product |
| `DELETE` | `/api/products/{id}` | Delete a product and its price history |
| `GET` | `/api/products/{id}/prices` | List price history |
| `POST` | `/api/products/{id}/prices` | Add a price entry |
| `DELETE` | `/api/prices/{id}` | Delete a price entry |
| `GET` | `/api/categories` | List available categories |
| `GET` | `/api/stats` | Aggregate stats |
