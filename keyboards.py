from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Базовые статические клавиатуры

keyboard_main = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Новая запись", callback_data="button_new_note")],
    [InlineKeyboardButton(text="Посмотреть записи", callback_data="button_list_notes")],
    [InlineKeyboardButton(text="Удалить запись", callback_data="button_delete_note")],
    [InlineKeyboardButton(text="Экспорт TXT", callback_data="export_txt"), InlineKeyboardButton(text="Экспорт PDF", callback_data="export_pdf")],
    [InlineKeyboardButton(text="Фильтр экспорта", callback_data="export_open_filter")]
])

keyboard_list_notes = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="Удалить запись\n по номеру", callback_data="button_delete_note"),
        InlineKeyboardButton(text="Главное меню", callback_data="button_main_menu")
    ],
    [
        InlineKeyboardButton(text="Экспорт TXT", callback_data="export_txt"),
        InlineKeyboardButton(text="Экспорт PDF", callback_data="export_pdf")
    ]
])

keyboard_strength = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Отмена", callback_data="button_cancel")]
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
    # Навигация по страницам (неделям) при просмотре записей
    page_nav = []
    if total_pages > 1:
        if page > 0:
            page_nav.append(InlineKeyboardButton(text="< Неделя", callback_data=f"page_week:{year}:{month}:{page-1}"))
        page_nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            page_nav.append(InlineKeyboardButton(text="Неделя >", callback_data=f"page_week:{year}:{month}:{page+1}"))
    if page_nav:
        rows.append(page_nav)
    rows.append([InlineKeyboardButton(text="Главное меню", callback_data="button_main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_after_notes() -> InlineKeyboardMarkup:
    return keyboard_list_notes

# =================================================================

def kb_export_root() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Все", callback_data="export_scope:all")],
        [InlineKeyboardButton(text="По году", callback_data="export_scope:year")],
        [InlineKeyboardButton(text="По месяцу", callback_data="export_scope:month")],
        [InlineKeyboardButton(text="Отмена", callback_data="export_cancel")]
    ])

def kb_export_years(years: list[int]) -> InlineKeyboardMarkup:
    rows = []
    line = []
    for y in years:
        line.append(InlineKeyboardButton(text=str(y), callback_data=f"export_year:{y}"))
        if len(line) == 3:
            rows.append(line); line=[]
    if line:
        rows.append(line)
    rows.append([InlineKeyboardButton(text="Назад", callback_data="export_back_root")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_export_months(year: int, months: list[int]) -> InlineKeyboardMarkup:
    rows = []
    line = []
    for m in months:
        line.append(InlineKeyboardButton(text=str(m), callback_data=f"export_month:{year}:{m}"))
        if len(line) == 4:
            rows.append(line); line=[]
    if line:
        rows.append(line)
    rows.append([InlineKeyboardButton(text="Назад", callback_data="export_back_years")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_export_format(scope: str, year: int | None = None, month: int | None = None) -> InlineKeyboardMarkup:
    base = f"{scope}"
    if year is not None:
        base += f":{year}"
    if month is not None:
        base += f":{month}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="TXT", callback_data=f"export_make:txt:{base}")],
        [InlineKeyboardButton(text="PDF", callback_data=f"export_make:pdf:{base}")],
        [InlineKeyboardButton(text="Отмена", callback_data="export_cancel")]
    ])