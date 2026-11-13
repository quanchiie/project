import sqlite3
from datetime import datetime
from flask import (Flask, session, request, redirect, url_for,
                   render_template, flash)

DB_NAME = "shop.db"

USER_ROLES = {
    "user1": ["Молоко", "Хлеб"],
    "user2": ["Яйца", "Картофель", "Яблоки"]
}

THEMES = ["light", "dark", "blue"]

app = Flask(__name__)
app.secret_key = "replace-with-random-secret-string"


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            login TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            owner_login TEXT NOT NULL
        )
    ''')

    # Заказы: кто купил, когда, на какую сумму
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_login TEXT NOT NULL,
            created_at TEXT NOT NULL,
            total REAL NOT NULL
        )
    ''')

    # Позиции заказа: что именно куплено
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
            product_name TEXT NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL
        )
    ''')

    cursor.execute("SELECT count(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO users (login, password) VALUES (?, ?)",
            [("admin", "1234"), ("user1", "1234"), ("user2", "1234")]
        )

    cursor.execute("SELECT count(*) FROM products")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO products (name, category, price, owner_login) VALUES (?, ?, ?, ?)",
            [
                ("Молоко", "Молочные", 85, "admin"),
                ("Хлеб", "Хлебобулочные", 45, "admin"),
                ("Яйца", "Молочные", 120, "admin"),
                ("Картофель", "Овощи", 60, "admin"),
                ("Яблоки", "Фрукты", 90, "admin"),
            ]
        )

    conn.commit()
    conn.close()


def get_all_products(current_login=None):
    """Админ видит всё, обычный пользователь — свои товары плюс разрешённые в USER_ROLES."""
    conn = get_connection()
    cursor = conn.cursor()

    if current_login == "admin":
        cursor.execute(
            "SELECT id, name, category, price, owner_login FROM products ORDER BY id"
        )
    else:
        allowed_names = USER_ROLES.get(current_login, [])
        placeholders = ",".join("?" for _ in allowed_names)
        if allowed_names:
            cursor.execute(
                f"SELECT id, name, category, price, owner_login FROM products "
                f"WHERE owner_login = ? OR name IN ({placeholders}) ORDER BY id",
                [current_login, *allowed_names]
            )
        else:
            cursor.execute(
                "SELECT id, name, category, price, owner_login FROM products "
                "WHERE owner_login = ? ORDER BY id",
                (current_login,)
            )

    rows = cursor.fetchall()
    conn.close()

    return [
        {"id": r[0], "name": r[1], "category": r[2], "price": r[3], "owner": r[4]}
        for r in rows
    ]


def add_product(name, category, price, owner_login):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO products (name, category, price, owner_login) VALUES (?, ?, ?, ?)",
        (name, category, price, owner_login)
    )
    conn.commit()
    conn.close()


def delete_product(product_id, owner_login):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM products WHERE id = ? AND owner_login = ?",
        (product_id, owner_login)
    )
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def create_order(user_login, items):
    """items: список (product_id, quantity). Возвращает id заказа."""
    conn = get_connection()
    cursor = conn.cursor()

    total = 0.0
    rows = []
    for product_id, qty in items:
        cursor.execute(
            "SELECT name, price FROM products WHERE id = ?", (product_id,)
        )
        row = cursor.fetchone()
        if row:  # товар ещё существует
            name, price = row
            total += price * qty
            rows.append((name, price, qty))

    cursor.execute(
        "INSERT INTO orders (user_login, created_at, total) VALUES (?, ?, ?)",
        (user_login, datetime.now().strftime("%d.%m.%Y %H:%M"), total)
    )
    order_id = cursor.lastrowid

    cursor.executemany(
        "INSERT INTO order_items (order_id, product_name, price, quantity) "
        "VALUES (?, ?, ?, ?)",
        [(order_id, n, p, q) for n, p, q in rows]
    )
    conn.commit()
    conn.close()
    return order_id


def get_user_orders(user_login):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, created_at, total FROM orders "
        "WHERE user_login = ? ORDER BY id DESC",
        (user_login,)
    )
    orders = []
    for order_id, created_at, total in cursor.fetchall():
        cursor.execute(
            "SELECT product_name, price, quantity FROM order_items WHERE order_id = ?",
            (order_id,)
        )
        items = cursor.fetchall()
        orders.append({"id": order_id, "created": created_at,
                       "total": total, "items": items})
    conn.close()
    return orders


def check_credentials(login, password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM users WHERE login = ? AND password = ?",
                   (login, password))
    ok = cursor.fetchone() is not None
    conn.close()
    return ok


def get_theme():
    theme = session.get("theme", "light")
    return theme if theme in THEMES else "light"

def admin_blocked():
    """True — если корзину надо заблокировать (админ)."""
    return session.get("login") == "admin"

def get_cart():
    """Корзина в сессии: {id_товара: количество}."""
    cart = session.get("cart", {})
    return cart if isinstance(cart, dict) else {}


def get_cart_details():
    """Разворачивает корзину в список товаров из базы + считает сумму."""
    cart = get_cart()
    if not cart:
        return [], 0.0

    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ",".join("?" for _ in cart)
    cursor.execute(
        f"SELECT id, name, price FROM products WHERE id IN ({placeholders})",
        list(cart.keys())
    )
    rows = cursor.fetchall()
    conn.close()

    items = []
    total = 0.0
    for pid, name, price in rows:
        qty = cart.get(str(pid), 1)
        items.append({"id": pid, "name": name, "price": price,
                      "qty": qty, "sum": price * qty})
        total += price * qty
    return items, total


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("login"):
        return redirect(url_for("index"))

    if request.method == "POST":
        login_name = request.form.get("login", "").strip()
        password = request.form.get("password", "").strip()
        if check_credentials(login_name, password):
            session["login"] = login_name
            return redirect(url_for("index"))
        flash("Неверный логин или пароль", "error")
    return render_template("login.html", theme=get_theme())


@app.route("/logout")
def logout():
    session.pop("login", None)
    session.pop("cart", None)  # выходим — корзина очищается
    return redirect(url_for("login"))


@app.route("/theme/<name>")
def set_theme(name):
    if name in THEMES:
        session["theme"] = name
    return redirect(request.referrer or url_for("index"))


@app.route("/", methods=["GET"])
def index():
    if not session.get("login"):
        return redirect(url_for("login"))

    current_login = session["login"]
    products = get_all_products(current_login)

    categories = ["Все"] + sorted(set(p["category"] for p in products))
    cat = request.args.get("category", "Все")
    if cat not in categories:
        cat = "Все"

    query = request.args.get("q", "").strip().lower()
    if query:
        products = [p for p in products if query in p["name"].lower()]
    if cat != "Все":
        products = [p for p in products if p["category"] == cat]

    return render_template(
        "main.html",
        theme=get_theme(),
        login=current_login,
        products=products,
        categories=categories,
        cat=cat,
        query=request.args.get("q", ""),
    )


@app.route("/add", methods=["GET", "POST"])
def add():
    if not session.get("login"):
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        cat = request.form.get("category", "").strip()
        price_str = request.form.get("price", "").strip()

        if not any(c.isalpha() for c in name):
            flash("В названии должна быть хотя бы одна буква!", "error")
        elif not cat:
            flash("Заполните категорию!", "error")
        else:
            try:
                price = float(price_str)
                if price < 0:
                    flash("Цена не может быть отрицательной!", "error")
                else:
                    add_product(name, cat, price, session["login"])
                    flash(f"Товар «{name}» добавлен", "success")
                    return redirect(url_for("index"))
            except ValueError:
                flash(f"Некорректная цена! Вы ввели: '{price_str}'. Введите число.", "error")

    return render_template("add.html", theme=get_theme())


@app.route("/delete/<int:product_id>", methods=["POST"])
def delete(product_id):
    if not session.get("login"):
        return redirect(url_for("login"))

    if delete_product(product_id, session["login"]):
        cart = get_cart()
        cart.pop(str(product_id), None)
        session["cart"] = cart
        flash(f"Товар с ID {product_id} удалён", "success")
    else:
        flash("Это не ваш товар — удалить его нельзя", "error")
    return redirect(url_for("index"))


@app.route("/cart")
def cart():
    if not session.get("login"):
        return redirect(url_for("login"))
    if admin_blocked():
        flash("Администратору корзина недоступна", "error")
        return redirect(url_for("index"))
    items, total = get_cart_details()
    return render_template("cart.html", theme=get_theme(),
                           items=items, total=total)


@app.route("/cart/add/<int:product_id>", methods=["POST"])
def cart_add(product_id):
    if not session.get("login"):
        return redirect(url_for("login"))
    if admin_blocked():
        flash("Администратору корзина недоступна", "error")
        return redirect(url_for("index"))

    visible_ids = {p["id"] for p in get_all_products(session["login"])}
    if product_id not in visible_ids:
        flash("Такого товара нет или он вам недоступен", "error")
        return redirect(url_for("index"))

    cart = get_cart()
    cart[str(product_id)] = cart.get(str(product_id), 0) + 1
    session["cart"] = cart
    flash("Товар добавлен в корзину", "success")
    return redirect(url_for("index"))


@app.route("/cart/remove/<int:product_id>", methods=["POST"])
def cart_remove(product_id):
    if not session.get("login"):
        return redirect(url_for("login"))
    if admin_blocked():
        flash("Администратору корзина недоступна", "error")
        return redirect(url_for("index"))

    cart = get_cart()
    cart.pop(str(product_id), None)
    session["cart"] = cart
    return redirect(url_for("cart"))


@app.route("/cart/clear", methods=["POST"])
def cart_clear():
    if not session.get("login"):
        return redirect(url_for("login"))
    if admin_blocked():
        flash("Администратору корзина недоступна", "error")
        return redirect(url_for("index"))

    session["cart"] = {}
    flash("Корзина очищена", "success")
    return redirect(url_for("cart"))


@app.route("/cart/checkout", methods=["POST"])
def cart_checkout():
    if not session.get("login"):
        return redirect(url_for("login"))
    if admin_blocked():
        flash("Администратору корзина недоступна", "error")
        return redirect(url_for("index"))

    items, total = get_cart_details()
    if not items:
        flash("Корзина пуста — нечего оформлять", "error")
        return redirect(url_for("cart"))

    order_id = create_order(session["login"],
                            [(item["id"], item["qty"]) for item in items])
    session["cart"] = {}
    flash(f"Заказ №{order_id} оформлен! Сумма: {total:.2f} ₽", "success")
    return redirect(url_for("orders"))

@app.route("/orders")
def orders():
    if not session.get("login"):
        return redirect(url_for("login"))
    return render_template("orders.html", theme=get_theme(),
                           orders=get_user_orders(session["login"]))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
