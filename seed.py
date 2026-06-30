"""
Populate the database with sample golf equipment and price history.
Run once after initializing the database: python seed.py
"""
from database import init_db, db

PRODUCTS = [
    {
        "name": "TaylorMade Stealth 2 Driver",
        "brand": "TaylorMade",
        "category": "Drivers",
        "description": "60-layer carbon twist face for maximum ball speed.",
        "url": "",
    },
    {
        "name": "Callaway Paradym Irons (5-PW)",
        "brand": "Callaway",
        "category": "Irons",
        "description": "Forged 360 Face Cup with Urethane Microspheres.",
        "url": "",
    },
    {
        "name": "Titleist Pro V1 Golf Balls (Dozen)",
        "brand": "Titleist",
        "category": "Golf Balls",
        "description": "Consistent flight, penetrating trajectory, Drop-and-Stop control.",
        "url": "",
    },
    {
        "name": "Scotty Cameron Special Select Newport 2",
        "brand": "Scotty Cameron",
        "category": "Putters",
        "description": "Precision milled 303 stainless steel blade putter.",
        "url": "",
    },
    {
        "name": "Vokey SM9 Wedge 56° Sand Wedge",
        "brand": "Titleist",
        "category": "Wedges",
        "description": "Tour-proven spin and versatility around the green.",
        "url": "",
    },
]

PRICES = [
    # product index, [(price, retailer, days_ago)]
    (0, [(549.99, "Golf Galaxy", 90), (499.99, "Amazon", 60), (479.99, "PGA Tour Superstore", 30), (459.99, "Dick's Sporting Goods", 7)]),
    (1, [(899.99, "Callaway Golf", 80), (849.99, "Golf Galaxy", 45), (829.99, "Amazon", 14)]),
    (2, [(54.99, "Titleist.com", 120), (49.99, "Amazon", 60), (47.99, "Walmart", 30), (52.99, "Golf Galaxy", 7)]),
    (3, [(399.99, "Scotty Cameron", 200), (389.99, "eBay", 90), (379.99, "2nd Swing Golf", 14)]),
    (4, [(179.99, "Titleist.com", 45), (159.99, "Amazon", 21), (169.99, "Golf Galaxy", 5)]),
]


def main():
    init_db()
    with db() as conn:
        existing = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if existing > 0:
            print("Database already has data. Skipping seed.")
            return

        product_ids = []
        for p in PRODUCTS:
            cur = conn.execute(
                "INSERT INTO products (name, brand, category, description, url) VALUES (?, ?, ?, ?, ?)",
                (p["name"], p["brand"], p["category"], p["description"], p["url"]),
            )
            product_ids.append(cur.lastrowid)
            print(f"  Added product: {p['name']}")

        for prod_idx, price_list in PRICES:
            pid = product_ids[prod_idx]
            for price, retailer, days_ago in price_list:
                conn.execute(
                    "INSERT INTO price_entries (product_id, price, retailer, recorded_at) VALUES (?, ?, ?, datetime('now', ?))",
                    (pid, price, retailer, f"-{days_ago} days"),
                )

    print(f"\nSeeded {len(PRODUCTS)} products with price history.")
    print("Run: python app.py")


if __name__ == "__main__":
    main()
