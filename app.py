from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional
import sqlite3

from database import db, init_db, CATEGORIES

app = FastAPI(title="Golf Price Monitor", version="1.0.0")


@app.on_event("startup")
def startup():
    init_db()


# ── Pydantic models ──────────────────────────────────────────────────────────

class ProductCreate(BaseModel):
    name: str
    brand: str = ""
    category: str = "Other"
    description: str = ""
    url: str = ""


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None


class PriceCreate(BaseModel):
    price: float = Field(..., gt=0)
    retailer: str = ""
    notes: str = ""
    recorded_at: Optional[str] = None  # ISO datetime; defaults to now


class AlertCreate(BaseModel):
    threshold_price: float = Field(..., gt=0)
    alert_type: str = "below"  # "below" or "above"
    notes: str = ""


class AlertUpdate(BaseModel):
    threshold_price: Optional[float] = None
    alert_type: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


# ── Helper ───────────────────────────────────────────────────────────────────

def row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def get_product_or_404(conn, product_id: int) -> dict:
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    return row_to_dict(row)


def get_alert_or_404(conn, alert_id: int) -> dict:
    row = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Alert not found")
    return row_to_dict(row)


# ── Products ─────────────────────────────────────────────────────────────────

@app.get("/api/products")
def list_products(category: Optional[str] = None, search: Optional[str] = None):
    with db() as conn:
        query = """
            SELECT p.*,
                   pe.price      AS latest_price,
                   pe.recorded_at AS latest_recorded_at,
                   pe.retailer   AS latest_retailer,
                   (SELECT COUNT(*) FROM price_entries WHERE product_id = p.id) AS price_count
            FROM products p
            LEFT JOIN price_entries pe ON pe.id = (
                SELECT id FROM price_entries
                WHERE product_id = p.id
                ORDER BY recorded_at DESC, id DESC
                LIMIT 1
            )
        """
        params = []
        conditions = []
        if category:
            conditions.append("p.category = ?")
            params.append(category)
        if search:
            conditions.append("(p.name LIKE ? OR p.brand LIKE ? OR p.description LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like, like])
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY p.name"
        rows = conn.execute(query, params).fetchall()
        return [row_to_dict(r) for r in rows]


@app.post("/api/products", status_code=201)
def create_product(body: ProductCreate):
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO products (name, brand, category, description, url) VALUES (?, ?, ?, ?, ?)",
            (body.name, body.brand, body.category, body.description, body.url),
        )
        product_id = cur.lastrowid
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        return row_to_dict(row)


@app.get("/api/products/{product_id}")
def get_product(product_id: int):
    with db() as conn:
        product = get_product_or_404(conn, product_id)
        latest = conn.execute(
            "SELECT * FROM price_entries WHERE product_id = ? ORDER BY recorded_at DESC, id DESC LIMIT 1",
            (product_id,),
        ).fetchone()
        price_count = conn.execute(
            "SELECT COUNT(*) FROM price_entries WHERE product_id = ?", (product_id,)
        ).fetchone()[0]
        product["latest_price"] = row_to_dict(latest) if latest else None
        product["price_count"] = price_count
        return product


@app.put("/api/products/{product_id}")
def update_product(product_id: int, body: ProductUpdate):
    with db() as conn:
        get_product_or_404(conn, product_id)
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE products SET {set_clause} WHERE id = ?",
            list(updates.values()) + [product_id],
        )
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        return row_to_dict(row)


@app.delete("/api/products/{product_id}", status_code=204)
def delete_product(product_id: int):
    with db() as conn:
        get_product_or_404(conn, product_id)
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))


# ── Price entries ─────────────────────────────────────────────────────────────

@app.get("/api/products/{product_id}/prices")
def list_prices(product_id: int, limit: int = 100, offset: int = 0):
    with db() as conn:
        get_product_or_404(conn, product_id)
        rows = conn.execute(
            """SELECT * FROM price_entries WHERE product_id = ?
               ORDER BY recorded_at DESC, id DESC LIMIT ? OFFSET ?""",
            (product_id, limit, offset),
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM price_entries WHERE product_id = ?", (product_id,)
        ).fetchone()[0]
        return {"items": [row_to_dict(r) for r in rows], "total": total}


@app.post("/api/products/{product_id}/prices", status_code=201)
def add_price(product_id: int, body: PriceCreate):
    with db() as conn:
        get_product_or_404(conn, product_id)
        if body.recorded_at:
            cur = conn.execute(
                "INSERT INTO price_entries (product_id, price, retailer, notes, recorded_at) VALUES (?, ?, ?, ?, ?)",
                (product_id, body.price, body.retailer, body.notes, body.recorded_at),
            )
        else:
            cur = conn.execute(
                "INSERT INTO price_entries (product_id, price, retailer, notes) VALUES (?, ?, ?, ?)",
                (product_id, body.price, body.retailer, body.notes),
            )
        entry = row_to_dict(conn.execute("SELECT * FROM price_entries WHERE id = ?", (cur.lastrowid,)).fetchone())

        # Check active alerts and record any that fire
        active_alerts = conn.execute(
            "SELECT * FROM alerts WHERE product_id = ? AND is_active = 1",
            (product_id,),
        ).fetchall()
        triggered = []
        for alert in active_alerts:
            a = row_to_dict(alert)
            fired = (
                (a["alert_type"] == "below" and body.price <= a["threshold_price"])
                or (a["alert_type"] == "above" and body.price >= a["threshold_price"])
            )
            if fired:
                conn.execute(
                    "UPDATE alerts SET triggered_at = datetime('now'), triggered_price = ? WHERE id = ?",
                    (body.price, a["id"]),
                )
                triggered.append(a)
        entry["triggered_alerts"] = triggered
        return entry


@app.delete("/api/prices/{price_id}", status_code=204)
def delete_price(price_id: int):
    with db() as conn:
        row = conn.execute("SELECT id FROM price_entries WHERE id = ?", (price_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Price entry not found")
        conn.execute("DELETE FROM price_entries WHERE id = ?", (price_id,))


# ── Metadata & stats ──────────────────────────────────────────────────────────

@app.get("/api/categories")
def get_categories():
    return CATEGORIES


@app.get("/api/stats")
def get_stats():
    with db() as conn:
        total_products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        total_prices = conn.execute("SELECT COUNT(*) FROM price_entries").fetchone()[0]
        categories = conn.execute(
            "SELECT category, COUNT(*) as count FROM products GROUP BY category ORDER BY count DESC"
        ).fetchall()
        price_drops = conn.execute("""
            SELECT COUNT(DISTINCT product_id) FROM (
                SELECT product_id,
                       price,
                       LAG(price) OVER (PARTITION BY product_id ORDER BY recorded_at, id) AS prev_price
                FROM price_entries
            )
            WHERE prev_price IS NOT NULL AND price < prev_price
        """).fetchone()[0]
        total_alerts = conn.execute("SELECT COUNT(*) FROM alerts WHERE is_active = 1").fetchone()[0]
        triggered_alerts = conn.execute(
            "SELECT COUNT(*) FROM alerts WHERE is_active = 1 AND triggered_at IS NOT NULL"
        ).fetchone()[0]
        return {
            "total_products": total_products,
            "total_price_entries": total_prices,
            "price_drops": price_drops,
            "total_alerts": total_alerts,
            "triggered_alerts": triggered_alerts,
            "categories": [row_to_dict(r) for r in categories],
        }


# ── Alerts ────────────────────────────────────────────────────────────────────

@app.get("/api/alerts")
def list_all_alerts():
    with db() as conn:
        rows = conn.execute("""
            SELECT a.*, p.name AS product_name, p.brand AS product_brand,
                   pe.price AS current_price
            FROM alerts a
            JOIN products p ON p.id = a.product_id
            LEFT JOIN price_entries pe ON pe.id = (
                SELECT id FROM price_entries
                WHERE product_id = a.product_id
                ORDER BY recorded_at DESC, id DESC
                LIMIT 1
            )
            ORDER BY a.created_at DESC
        """).fetchall()
        return [row_to_dict(r) for r in rows]


@app.get("/api/products/{product_id}/alerts")
def list_product_alerts(product_id: int):
    with db() as conn:
        get_product_or_404(conn, product_id)
        rows = conn.execute(
            "SELECT * FROM alerts WHERE product_id = ? ORDER BY created_at DESC",
            (product_id,),
        ).fetchall()
        return [row_to_dict(r) for r in rows]


@app.post("/api/products/{product_id}/alerts", status_code=201)
def create_alert(product_id: int, body: AlertCreate):
    if body.alert_type not in ("below", "above"):
        raise HTTPException(status_code=400, detail="alert_type must be 'below' or 'above'")
    with db() as conn:
        get_product_or_404(conn, product_id)
        cur = conn.execute(
            "INSERT INTO alerts (product_id, threshold_price, alert_type, notes) VALUES (?, ?, ?, ?)",
            (product_id, body.threshold_price, body.alert_type, body.notes),
        )
        row = conn.execute("SELECT * FROM alerts WHERE id = ?", (cur.lastrowid,)).fetchone()
        return row_to_dict(row)


@app.put("/api/alerts/{alert_id}")
def update_alert(alert_id: int, body: AlertUpdate):
    with db() as conn:
        get_alert_or_404(conn, alert_id)
        updates = {}
        if body.threshold_price is not None:
            updates["threshold_price"] = body.threshold_price
        if body.alert_type is not None:
            if body.alert_type not in ("below", "above"):
                raise HTTPException(status_code=400, detail="alert_type must be 'below' or 'above'")
            updates["alert_type"] = body.alert_type
        if body.notes is not None:
            updates["notes"] = body.notes
        if body.is_active is not None:
            updates["is_active"] = 1 if body.is_active else 0
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE alerts SET {set_clause} WHERE id = ?",
            list(updates.values()) + [alert_id],
        )
        row = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        return row_to_dict(row)


@app.delete("/api/alerts/{alert_id}", status_code=204)
def delete_alert(alert_id: int):
    with db() as conn:
        get_alert_or_404(conn, alert_id)
        conn.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))


# ── Static files & SPA fallback ───────────────────────────────────────────────

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def serve_index():
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
