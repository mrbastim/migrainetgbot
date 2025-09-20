from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Базовые статические клавиатуры

keyboard_main = InlineKeyboardMarkup(inline_keyboard=[ # в неск строк
        [InlineKeyboardButton(text="Новая запись", callback_data="button_new_note")],
        [InlineKeyboardButton(text="Посмотреть записи", callback_data="button_list_notes")],
    ])

keyboard_list_notes = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="Удалить запись\n по номеру", callback_data="button_delete_note"),
        InlineKeyboardButton(text="Главное меню", callback_data="button_main_menu")
    ]
])

# ================= Динамические клавиатуры =====================

def kb_year_months(year: int, months: list[int], has_prev: bool, has_next: bool) -> InlineKeyboardMarkup:
    rows = []
    # Месяцы в 3 столбца
    line = []
    for m in months:
        line.append(InlineKeyboardButton(text=str(m), callback_data=f"sel_month:{year}:{m}"))
        if len(line) == 3:
            rows.append(line)
            line = []
    if line:
        rows.append(line)
    nav = []
    if has_prev:
        nav.append(InlineKeyboardButton(text="<<", callback_data=f"nav_year:{year}:prev"))
    nav.append(InlineKeyboardButton(text="Главное меню", callback_data="button_main_menu"))
    if has_next:
        nav.append(InlineKeyboardButton(text=">>", callback_data=f"nav_year:{year}:next"))
    rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_days(year: int, month: int, days_slice: list[int], page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows = []
    # дни по 5 (в одну строку или перенести?) оставим в ряд
    day_buttons = [InlineKeyboardButton(text=str(d), callback_data=f"sel_day:{year}:{month}:{d}") for d in days_slice]
    # разбить на 5 максимум
    rows.append(day_buttons)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="< Дни", callback_data=f"nav_days:{year}:{month}:{page-1}"))
    nav.append(InlineKeyboardButton(text="Месяцы", callback_data=f"back_months:{year}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="Дни >", callback_data=f"nav_days:{year}:{month}:{page+1}"))
    rows.append(nav)
    rows.append([InlineKeyboardButton(text="Главное меню", callback_data="button_main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_after_notes() -> InlineKeyboardMarkup:
    return keyboard_list_notes

# =================================================================