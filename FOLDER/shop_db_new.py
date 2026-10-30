import sqlite3
import PySimpleGUI as sg

DB_NAME = "shop.db"

# --- Настройка видимости товаров ---
# Если пользователь есть в этом словаре, он видит ТОЛЬКО товары из списка.
# Админ (которого тут нет) видит всё.
USER_ROLES = {
    "user1": ["Молоко", "Хлеб"],
    "user2": ["Яйца", "Картофель", "Яблоки"]
}

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Создает таблицы. УДАЛИТЕ shop.db ПЕРЕД ЗАПУСКОМ, иначе колонка owner_login не добавится."""
    conn = get_connection()
    cursor = conn.cursor()

    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            login TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    ''')

    # Таблица товаров: ДОБАВЛЕНА колонка owner_login
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            owner_login TEXT NOT NULL  -- Кто добавил товар
        )
    ''')

    # Добавляем пользователей, если пусто
    cursor.execute("SELECT count(*) FROM users")
    if cursor.fetchone()[0] == 0:
        initial_users = [
            ("admin", "1234"),
            ("user1", "1234"),
            ("user2", "1234")
        ]
        cursor.executemany("INSERT INTO users (login, password) VALUES (?, ?)", initial_users)

    # Заполняем товары, если пусто. Теперь указываем владельца (admin)
    cursor.execute("SELECT count(*) FROM products")
    if cursor.fetchone()[0] == 0:
        initial_products = [
            ("Молоко", "Молочные", 85, "admin"),
            ("Хлеб", "Хлебобулочные", 45, "admin"),
            ("Яйца", "Молочные", 120, "admin"),
            ("Картофель", "Овощи", 60, "admin"),
            ("Яблоки", "Фрукты", 90, "admin"),
        ]
        cursor.executemany(
            "INSERT INTO products (name, category, price, owner_login) VALUES (?, ?, ?, ?)", 
            initial_products
        )

    conn.commit()
    conn.close()

def get_all_products(current_login=None):
    """
    Возвращает список товаров.
    - Если current_login == 'admin': возвращает ВСЕ товары (включая колонку owner).
    - Иначе: возвращает только товары, где owner_login == current_login.
      (Плюс дополнительная фильтрация по USER_ROLES, если пользователь там есть).
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    if current_login == "admin":
        # Админ видит всё
        cursor.execute("SELECT id, name, category, price, owner_login FROM products ORDER BY id")
    else:
        # Обычный пользователь видит только СВОИ товары
        cursor.execute(
            "SELECT id, name, category, price, owner_login FROM products WHERE owner_login = ? ORDER BY id", 
            (current_login,)
        )
        
    rows = cursor.fetchall()
    conn.close()
    
    products = [
        {"id": r[0], "name": r[1], "category": r[2], "price": r[3], "owner": r[4]} 
        for r in rows
    ]

    # Дополнительная защита: если пользователь в USER_ROLES, 
    # он видит только товары из разрешенного списка, даже если они "его".
    if current_login in USER_ROLES:
        allowed_names = USER_ROLES[current_login]
        products = [p for p in products if p["name"] in allowed_names]
    
    return products

def add_product(name, category, price, owner_login):
    conn = get_connection()
    cursor = conn.cursor()
    # Записываем владельца
    cursor.execute(
        "INSERT INTO products (name, category, price, owner_login) VALUES (?, ?, ?, ?)", 
        (name, category, price, owner_login)
    )
    conn.commit()
    conn.close()

def delete_product(product_id, owner_login):
    conn = get_connection()
    cursor = conn.cursor()
    # Удаляем только свой товар (защита)
    cursor.execute("DELETE FROM products WHERE id = ? AND owner_login = ?", (product_id, owner_login))
    conn.commit()
    conn.close()

def check_credentials(login, password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE login = ? AND password = ?", (login, password))
    result = cursor.fetchone()
    conn.close()
    return result is not None

# --- Вспомогательные функции для UI ---
def get_table_data(current_login=None):
    products = get_all_products(current_login)
    
    # Если админ — показываем 5 колонок: ID, Название, Категория, Цена, Пользователь
    # Если обычный юзер — показываем 4 колонки: ID, Название, Категория, Цена
    if current_login == "admin":
        return [[p["id"], p["name"], p["category"], p["price"], p["owner"]] for p in products]
    else:
        return [[p["id"], p["name"], p["category"], p["price"]] for p in products]

def create_layout_login():
    return [
        [sg.Text("Логин:", size=(8, 1)), sg.Input(key="-LOGIN-", size=(20, 1))],
        [sg.Text("Пароль:", size=(8, 1)), sg.Input(password_char="*", key="-PASS-", size=(20, 1))],
        [sg.Button("Войти", key="-LOGIN_BTN-")],
        [sg.Text("", size=(30, 1), text_color="red", key="-MSG-")],
    ]

def create_layout_main(theme_name, current_login):
    sg.theme(theme_name)
    products = get_all_products(current_login)
    categories = ["Все"] + sorted(set(p["category"] for p in products))
    
    # Определяем заголовки и ширину колонок в зависимости от роли
    if current_login == "admin":
        headings = ["ID", "Название", "Категория", "Цена (₽)", "Пользователь (Автор)"]
        col_widths = [10, 25, 20, 10, 20]
    else:
        headings = ["ID", "Название", "Категория", "Цена (₽)"]
        col_widths = [10, 35, 30, 15]

    return [
        [
            sg.Text("Категория:", size=(10, 1)),
            sg.Combo(categories, default_value="Все", key="-CAT_FILTER-", enable_events=True),
        ],
        [sg.Input(placeholder="Поиск по названию...", key="-SEARCH-", enable_events=True)],
        [sg.Table(
            values=get_table_data(current_login),
            headings=headings,
            key="-TABLE-",
            col_widths=col_widths,
            num_rows=10,
            alternating_row_color="#f5f5f5",
            select_mode=sg.TABLE_SELECT_MODE_BROWSE,
        )],
        [
            sg.Button("Добавить товар", key="-ADD_BTN-"),
            sg.Button("Удалить выбранный", key="-DEL_BTN-"),
        ],
        [
            sg.Text("Стиль (тема):"),
            sg.Combo(sg.theme_list(), default_value=theme_name, key="-THEME_CHOICE-", enable_events=True),
        ],
        [sg.Button("Выйти", key="-LOGOUT-")],
        [sg.Text(f"Текущий пользователь: {current_login}", text_color="blue", font=("Arial", 10))]
    ]

def create_layout_add():
    return [
        [sg.Text("Название:", size=(10, 1)), sg.Input(key="-ADD_NAME-", size=(30, 1))],
        [sg.Text("Категория:", size=(10, 1)), sg.Input(key="-ADD_CAT-", size=(30, 1))],
        [sg.Text("Цена (₽):", size=(10, 1)), sg.Input(key="-ADD_PRICE-", size=(30, 1))],
        [sg.Button("Сохранить", key="-SAVE_ADD-"), sg.Button("Отмена", key="-CANCEL_ADD-")],
    ]

# --- Основной цикл ---
def main():
    init_db()
    sg.theme("LightBlue")
    window_login = sg.Window("Авторизация — Продуктовый магазин", create_layout_login(), finalize=True)
    window_main = window_add = None
    current_theme = "LightBlue"
    logged_in = False
    current_user_login = None

    while True:
        if not logged_in:
            active_window = window_login
        elif window_add:
            active_window = window_add
        elif window_main:
            active_window = window_main
        else:
            break

        event, values = active_window.read()

        if event == sg.WIN_CLOSED:
            if window_main: window_main.close(); window_main = None
            if window_add: window_add.close(); window_add = None
            if window_login: window_login.close()
            break

        if event == "-LOGOUT-":
            if window_main: window_main.close(); window_main = None
            if window_add: window_add.close(); window_add = None
            logged_in = False
            current_user_login = None
            window_login.un_hide()
            continue

        if not logged_in and event == "-LOGIN_BTN-":
            login = values["-LOGIN-"].strip()
            password = values["-PASS-"].strip()
            
            if check_credentials(login, password):
                logged_in = True
                current_user_login = login
                window_login.hide()
                current_theme = "LightBlue"
                window_main = sg.Window("Продуктовый магазин", create_layout_main(current_theme, current_user_login), finalize=True)
            else:
                window_login["-MSG-"].update("Неверный логин или пароль")
            continue

        if not logged_in:
            continue

        if event == "-THEME_CHOICE-":
            current_theme = values["-THEME_CHOICE-"]
            if window_main: 
                window_main.close()
                window_main = sg.Window("Продуктовый магазин", create_layout_main(current_theme, current_user_login), finalize=True)
            continue

        if event == "-CAT_FILTER-":
            cat = values["-CAT_FILTER-"]
            products = get_all_products(current_user_login)
            filtered = products if cat == "Все" else [p for p in products if p["category"] == cat]
            table_vals = get_table_data_from_products(filtered, current_user_login)
            window_main["-TABLE-"].update(table_vals)
            continue

        if event == "-SEARCH-":
            q = values["-SEARCH-"].lower()
            products = get_all_products(current_user_login)
            filtered = [p for p in products if q in p["name"].lower()]
            table_vals = get_table_data_from_products(filtered, current_user_login)
            window_main["-TABLE-"].update(table_vals)
            continue

        if event == "-ADD_BTN-":
            window_add = sg.Window("Добавить товар", create_layout_add(), finalize=True)
            continue

        if window_add and event == "-SAVE_ADD-":       
            name = values["-ADD_NAME-"].strip()
            cat = values["-ADD_CAT-"].strip()
            price_str = values["-ADD_PRICE-"].strip()

            if not any(c.isalpha() for c in name):
                sg.popup("В названии должна быть хотя бы одна буква!", title="Ошибка")
                continue

            if not cat:
                sg.popup_warn("Заполните категорию!", title="Ошибка")
                continue

            try:
                price = float(price_str)
                if price < 0:
                    sg.popup_warn("Цена не может быть отрицательной!", title="Ошибка")
                    continue
            except ValueError:
                sg.popup_warn(f"Некорректная цена! Вы ввели: '{price_str}'.\nВведите число.", title="Ошибка")
                continue

            # ГЛАВНОЕ: передаем current_user_login как владельца
            add_product(name, cat, price, current_user_login)

            window_add.close()
            window_add = None
            
            # Обновляем таблицу
            window_main["-TABLE-"].update(get_table_data(current_user_login))
            window_main["-CAT_FILTER-"].update("Все")
            window_main["-SEARCH-"].update("")
            continue   

        if window_add and event == "-CANCEL_ADD-":
            window_add.close()
            window_add = None
            continue

        if event == "-DEL_BTN-":
            selected = values["-TABLE-"]
            if not selected:
                sg.popup("Выберите строку для удаления", title="Внимание")
                continue

            row_index = selected[0]
            # Получаем данные заново, чтобы точно знать ID
            all_data = get_table_data(current_user_login)

            if row_index < 0 or row_index >= len(all_data):
                sg.popup("Некорректный выбор", title="Ошибка")
                window_main["-TABLE-"].update(all_data)
                continue

            target_id = all_data[row_index][0]

            confirm = sg.popup_yes_no(f"Удалить товар с ID {target_id}?", title="Подтверждение")
            
            if confirm == "Yes":
                # Передаем владельца для проверки прав на удаление
                delete_product(target_id, current_user_login)
                window_main["-TABLE-"].update(get_table_data(current_user_login))
                window_main["-CAT_FILTER-"].update("Все")
                window_main["-SEARCH-"].update("")
            continue

    if window_login:
        window_login.close()

# Вспомогательная функция для фильтрации данных таблицы при поиске/фильтре
def get_table_data_from_products(products_list, current_login):
    if current_login == "admin":
        return [[p["id"], p["name"], p["category"], p["price"], p["owner"]] for p in products_list]
    else:
        return [[p["id"], p["name"], p["category"], p["price"]] for p in products_list]

if __name__ == "__main__":
    main()
