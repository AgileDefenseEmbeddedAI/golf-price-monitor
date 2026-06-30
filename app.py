from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional
import sqlite3

from database import db, init_db, CATEGORIES
from auth import get_current_user, hash_password, verify_password, create_token

app = FastAPI(title="Golf Price Monitor", version="2.0.0")


@app.on_event("startup")
def startup():
    init_db()


# ── Pydantic models ──────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=6)
    email: str = ""


class UserLogin(BaseModel):
    username: str
    password: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)


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


# ── Helpers ──────────────────────────────────────────────────────────────────

def row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def get_product_or_404(conn, product_id: int, user_id: int) -> dict:
    row = conn.execute(
        "SELECT * FROM products WHERE id = ? AND user_id = ?", (product_id, user_id)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    return row_to_dict(row)


# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.post("/api/auth/register", status_code=201)
def register(body: UserRegister):
    with db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (body.username,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Username already taken")
        cur = conn.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (body.username, body.email, hash_password(body.password)),
        )
        user_id = cur.lastrowid
    token = create_token(user_id, body.username)
    return {"access_token": token, "user": {"id": user_id, "username": body.username}}


@app.post("/api/auth/login")
def login(body: UserLogin):
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (body.username,)
        ).fetchone()
    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_token(row["id"], row["username"])
    return {"access_token": token, "user": {"id": row["id"], "username": row["username"]}}


@app.get("/api/auth/me")
def me(user: dict = Depends(get_current_user)):
    with db() as conn:
        row = conn.execute(
            "SELECT id, username, email, created_at FROM users WHERE id = ?", (user["id"],)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return row_to_dict(row)


@app.put("/api/auth/password")
def change_password(body: PasswordChange, user: dict = Depends(get_current_user)):
    with db() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE id = ?", (user["id"],)
        ).fetchone()
        if not row or not verify_password(body.current_password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Current password is incorrect")
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(body.new_password), user["id"]),
        )
    return {"message": "Password updated"}


# ── Products ─────────────────────────────────────────────────────────────────

@app.get("/api/products")
def list_products(
    category: Optional[str] = None,
    search: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    with db() as conn:
        query = """
            SELECT p.*,
                   pe.price       AS latest_price,
                   pe.recorded_at AS latest_recorded_at,
                   pe.retailer    AS latest_retailer,
                   (SELECT COUNT(*) FROM price_entries WHERE product_id = p.id) AS price_count
            FROM products p
            LEFT JOIN price_entries pe ON pe.id = (
                SELECT id FROM price_entries
                WHERE product_id = p.id
                ORDER BY recorded_at DESC, id DESC
                LIMIT 1
            )
            WHERE p.user_id = ?
        """
        params = [user["id"]]
        if category:
            query += " AND p.category = ?"
            params.append(category)
        if search:
            query += " AND (p.name LIKE ? OR p.brand LIKE ? OR p.description LIKE ?)"
            like = f"%{search}%"
            params.extend([like, like, like])
        query += " ORDER BY p.name"
        rows = conn.execute(query, params).fetchall()
        return [row_to_dict(r) for r in rows]


@app.post("/api/products", status_code=201)
def create_product(body: ProductCreate, user: dict = Depends(get_current_user)):
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO products (user_id, name, brand, category, description, url) VALUES (?, ?, ?, ?, ?, ?)",
            (user["id"], body.name, body.brand, body.category, body.description, body.url),
        )
        product_id = cur.lastrowid
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        return row_to_dict(row)


@app.get("/api/products/{product_id}")
def get_product(product_id: int, user: dict = Depends(get_current_user)):
    with db() as conn:
        product = get_product_or_404(conn, product_id, user["id"])
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
def update_product(product_id: int, body: ProductUpdate, user: dict = Depends(get_current_user)):
    with db() as conn:
        get_product_or_404(conn, product_id, user["id"])
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
def delete_product(product_id: int, user: dict = Depends(get_current_user)):
    with db() as conn:
        get_product_or_404(conn, product_id, user["id"])
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))


# ── Price entries ─────────────────────────────────────────────────────────────

@app.get("/api/products/{product_id}/prices")
def list_prices(product_id: int, limit: int = 100, offset: int = 0, user: dict = Depends(get_current_user)):
    with db() as conn:
        get_product_or_404(conn, product_id, user["id"])
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
def add_price(product_id: int, body: PriceCreate, user: dict = Depends(get_current_user)):
    with db() as conn:
        get_product_or_404(conn, product_id, user["id"])
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
        row = conn.execute("SELECT * FROM price_entries WHERE id = ?", (cur.lastrowid,)).fetchone()
        return row_to_dict(row)


@app.delete("/api/prices/{price_id}", status_code=204)
def delete_price(price_id: int, user: dict = Depends(get_current_user)):
    with db() as conn:
        row = conn.execute(
            """SELECT pe.id FROM price_entries pe
               JOIN products p ON p.id = pe.product_id
               WHERE pe.id = ? AND p.user_id = ?""",
            (price_id, user["id"]),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Price entry not found")
        conn.execute("DELETE FROM price_entries WHERE id = ?", (price_id,))


# ── Metadata & stats ──────────────────────────────────────────────────────────

@app.get("/api/categories")
def get_categories():
    return CATEGORIES


@app.get("/api/stats")
def get_stats(user: dict = Depends(get_current_user)):
    with db() as conn:
        total_products = conn.execute(
            "SELECT COUNT(*) FROM products WHERE user_id = ?", (user["id"],)
        ).fetchone()[0]
        total_prices = conn.execute(
            """SELECT COUNT(*) FROM price_entries pe
               JOIN products p ON p.id = pe.product_id
               WHERE p.user_id = ?""",
            (user["id"],),
        ).fetchone()[0]
        categories = conn.execute(
            """SELECT category, COUNT(*) as count FROM products
               WHERE user_id = ? GROUP BY category ORDER BY count DESC""",
            (user["id"],),
        ).fetchall()
        price_drops = conn.execute(
            """SELECT COUNT(DISTINCT product_id) FROM (
                SELECT pe.product_id,
                       pe.price,
                       LAG(pe.price) OVER (
                           PARTITION BY pe.product_id ORDER BY pe.recorded_at, pe.id
                       ) AS prev_price
                FROM price_entries pe
                JOIN products p ON p.id = pe.product_id
                WHERE p.user_id = ?
            )
            WHERE prev_price IS NOT NULL AND price < prev_price""",
            (user["id"],),
        ).fetchone()[0]
        return {
            "total_products": total_products,
            "total_price_entries": total_prices,
            "price_drops": price_drops,
            "categories": [row_to_dict(r) for r in categories],
        }


# ── Static files & SPA fallback ───────────────────────────────────────────────

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def serve_index():
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
