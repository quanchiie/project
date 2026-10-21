import PySimpleGUI as sg

# --- Данные ---
products = [
    {"id": 1, "name": "Молоко", "category": "Молочные", "price": 85},
    {"id": 2, "name": "Хлеб", "category": "Хлебобулочные", "price": 45},
    {"id": 3, "name": "Яйца", "category": "Молочные", "price": 120},
    {"id": 4, "name": "Картофель", "category": "Овощи", "price": 60},
    {"id": 5, "name": "Яблоки", "category": "Фрукты", "price": 90},
]

users = {"admin": "1234"}

def get_table_data():
    return [[p["id"], p["name"], p["category"], p["price"]] for p in products]

def create_layout_login():
    return [
        [sg.Text("Логин:", size=(8, 1)), sg.Input(key="-LOGIN-", size=(20, 1))],
        [sg.Text("Пароль:", size=(8, 1)), sg.Input(password_char="*", key="-PASS-", size=(20, 1))],
        [sg.Button("Войти", key="-LOGIN_BTN-")],
        [sg.Text("", size=(30, 1), text_color="red", key="-MSG-")],
    ]

def create_layout_main(theme_name):
    sg.theme(theme_name)
    categories = ["Все"] + sorted(set(p["category"] for p in products))
    return [
        [
            sg.Text("Категория:", size=(10, 1)),
            sg.Combo(categories, default_value="Все", key="-CAT_FILTER-", enable_events=True),
        ],
        [sg.Input(placeholder="Поиск по названию...", key="-SEARCH-", enable_events=True)],
        [sg.Table(
            values=get_table_data(),
            headings=["ID", "Название", "Категория", "Цена (₽)"],
            key="-TABLE-",
            col_widths=[10, 25, 20, 10],
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
    ]

def create_layout_add():
    return [
        [sg.Text("Название:", size=(10, 1)), sg.Input(key="-ADD_NAME-", size=(30, 1))],
        [sg.Text("Категория:", size=(10, 1)), sg.Input(key="-ADD_CAT-", size=(30, 1))],
        [sg.Text("Цена (₽):", size=(10, 1)), sg.Input(key="-ADD_PRICE-", size=(30, 1))],
        [sg.Button("Сохранить", key="-SAVE_ADD-"), sg.Button("Отмена", key="-CANCEL_ADD-")],
    ]

def main():
    sg.theme("LightBlue")
    window_login = sg.Window("Авторизация — Продуктовый магазин", create_layout_login(), finalize=True)
    window_main = window_add = None
    current_theme = "LightBlue"
    logged_in = False

    while True:
        if not logged_in:
            active_window = window_login
        elif window_add:
            active_window = window_add
        else:
            active_window = window_main

        event, values = active_window.read()

        # Закрытие / выход
        if event in (sg.WIN_CLOSED, "-LOGOUT-"):
            if window_main:
                window_main.close()
                window_main = None
            if window_add:
                window_add.close()
                window_add = None
            logged_in = False
            window_login.un_hide()
            continue

        # Авторизация
        if not logged_in and event == "-LOGIN_BTN-":
            login = values["-LOGIN-"].strip()
            password = values["-PASS-"].strip()
            if login in users and users[login] == password:
                logged_in = True
                window_login.hide()
                current_theme = "LightBlue"
                window_main = sg.Window("Продуктовый магазин", create_layout_main(current_theme), finalize=True)
            else:
                window_login["-MSG-"].update("Неверный логин или пароль")
            continue

        if not logged_in:
            continue

        # Смена темы
        if event == "-THEME_CHOICE-":
            current_theme = values["-THEME_CHOICE-"]
            window_main.close()
            window_main = sg.Window("Продуктовый магазин", create_layout_main(current_theme), finalize=True)
            continue

        # Фильтр по категории
        if event == "-CAT_FILTER-":
            cat = values["-CAT_FILTER-"]
            filtered = products if cat == "Все" else [p for p in products if p["category"] == cat]
            table_vals = [[p["id"], p["name"], p["category"], p["price"]] for p in filtered]
            window_main["-TABLE-"].update(table_vals)
            continue

        # Поиск
        if event == "-SEARCH-":
            q = values["-SEARCH-"].lower()
            filtered = [p for p in products if q in p["name"].lower()]
            table_vals = [[p["id"], p["name"], p["category"], p["price"]] for p in filtered]
            window_main["-TABLE-"].update(table_vals)
            continue

        # Добавление
        if event == "-ADD_BTN-":
            window_add = sg.Window("Добавить товар", create_layout_add(), finalize=True)
            continue

        if window_add and event == "-SAVE_ADD-":
            name = values["-ADD_NAME-"].strip()
            cat = values["-ADD_CAT-"].strip()
            try:
                price = float(values["-ADD_PRICE-"])
            except ValueError:
                sg.popup("Цена должна быть числом", icon=sg.ICON_WARNING)
                continue
            if not name or not cat:
                sg.popup("Заполните название и категорию", icon=sg.ICON_WARNING)
                continue
            new_id = max((p["id"] for p in products), default=0) + 1
            products.append({"id": new_id, "name": name, "category": cat, "price": price})
            window_add.close()
            window_add = None
            window_main["-TABLE-"].update(get_table_data())
            window_main["-CAT_FILTER-"].update("Все")
            window_main["-SEARCH-"].update("")
            continue

        if window_add and event == "-CANCEL_ADD-":
            window_add.close()
            window_add = None
            continue

        # Удаление — самая важная часть
        if event == "-DEL_BTN-":
            selected = values["-TABLE-"]
            if not selected:
                sg.popup("Выберите строку для удаления", icon=sg.ICON_INFO)
                continue

            row_index = selected[0]
            table_data = get_table_data()

            if row_index < 0 or row_index >= len(table_data):
                sg.popup("Некорректный выбор", icon=sg.ICON_ERROR)
                window_main["-TABLE-"].update(get_table_data())
                continue

            target_id = table_data[row_index][0]  # ID — первый столбец

            product_to_remove = None
            for p in products:
                if p["id"] == target_id:
                    product_to_remove = p
                    break

            if product_to_remove is None:
                sg.popup("Товар не найден в базе", icon=sg.ICON_ERROR)
                window_main["-TABLE-"].update(get_table_data())
                continue

            confirm = sg.popup_yes_no(f"Удалить товар: {product_to_remove['name']}?")
            if confirm == "Yes":
                products.remove(product_to_remove)
                window_main["-TABLE-"].update(get_table_data())
                window_main["-CAT_FILTER-"].update("Все")
                window_main["-SEARCH-"].update("")
            continue


    window_login.close()

if __name__ == "__main__":
    main()
