import asyncio
import logging
import os
import datetime
from pathlib import Path
from dotenv import load_dotenv
import tempfile
from contextlib import contextmanager
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards import (
    keyboard_main,
    keyboard_cancel,
    kb_year_months,
    kb_days,
    kb_export_root,
    kb_export_years,
    kb_export_months,
    kb_export_format
)
from database import init_db, add_note, get_notes, delete_note

# Загрузка .env если есть
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
BOT_TOKEN = os.getenv("TELEGRAM_API_TOKEN")
offset_timezone = datetime.timezone(datetime.timedelta(hours=3), name='MSK') 

# Включаем логирование, чтобы видеть сообщения в консоли
logging.basicConfig(level=logging.INFO, filename="logfile.log",filemode="w",
                    format="%(asctime)s %(levelname)s %(message)s")

# Инициализация бота и диспетчера
if not BOT_TOKEN:
    raise RuntimeError("Не найден TELEGRAM_API_TOKEN в переменных окружения или .env файле.")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Определяем состояния FSM
class AddNoteStates(StatesGroup):
    waiting_for_strength = State()
    waiting_for_text = State()

class DeleteNoteStates(StatesGroup):
    waiting_for_id = State()

# ================= Вспомогательные функции для навигации заметок ====================
MONTH_NAMES_RU = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
]
WEEKDAY_ABBR_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

def _parse_note_datetime(dt_str: str) -> datetime.datetime:
    """Парсит строку даты из БД формата '%d.%m.%Y %H:%M'."""
    return datetime.datetime.strptime(dt_str, "%d.%m.%Y %H:%M")

def group_notes_structure(user_id: int):
    """Возвращает структуру: {year: {month: {day: [notes]}}} + отсортированные списки годов.
    note: tuple(id, strength, text, datetime)
    """
    notes = get_notes(user_id)
    structure = {}
    for n in notes:
        dt = _parse_note_datetime(n[3])
        structure.setdefault(dt.year, {})\
                 .setdefault(dt.month, {})\
                 .setdefault(dt.day, [])\
                 .append(n)
    years = sorted(structure.keys())
    return structure, years

def available_months(structure, year: int):
    """Возвращает отсортированный список месяцев для года."""
    return sorted(structure.get(year, {}).keys())

def available_days(structure, year: int, month: int):
    """Возвращает отсортированный список дней месяца, для которых есть записи."""
    return sorted(structure.get(year, {}).get(month, {}).keys())

def slice_days(days: list[int], page: int, page_size: int = 5):
    """Возвращает срез дней для страницы (0-based page)."""
    start = page * page_size
    end = start + page_size
    return days[start:end]

def total_day_pages(days: list[int], page_size: int = 5) -> int:
    if not days:
        return 0
    from math import ceil
    return ceil(len(days) / page_size)

def month_title(month: int, year: int) -> str:
    return f"{MONTH_NAMES_RU[month-1]} {year}"

def format_notes_for_days(structure, year: int, month: int, days: list[int]) -> str:
    """Формирует текст заметок для выбранных дней (каждый день отдельно)."""
    if not days:
        return "Нет записей."
    parts = []
    for d in days:
        notes = structure[year][month][d]
        for note in notes:
            dt = _parse_note_datetime(note[3])
            dow = WEEKDAY_ABBR_RU[dt.weekday()]
            parts.append(
                f"---id:{note[0]}---\n"
                f"Дата: {dt.strftime('%d.%m.%Y %H:%M')} ({dow})\n"
                f"Сила боли: {note[1]}\n"
                f"Комментарий: {note[2]}\n"
            )
    return "".join(parts)

def format_notes_for_day(structure, year: int, month: int, day: int) -> str:
    """Формирует текст заметок для выбранного дня."""
    if day not in structure.get(year, {}).get(month, {}):
        return "Нет записей."
    parts = []
    notes = structure[year][month][day]
    for note in notes:
        dt = _parse_note_datetime(note[3])
        parts.append(
            f"---id:{note[0]}---\n"
            f"Дата: {dt.strftime('%d.%m.%Y %H:%M')}\n"
            f"Сила боли: {note[1]}\n"
            f"Комментарий: {note[2]}\n"
        )
    return "".join(parts)

# ================= Конец вспомогательных функций ====================

def fmt_date(y: int, m: int, d: int) -> str:
    return f"{d:02d}.{m:02d}.{y}"

def fmt_date_dow(y: int, m: int, d: int) -> str:
    try:
        dt = datetime.date(y, m, d)
        return f"{d:02d}.{m:02d}.{y} ({WEEKDAY_ABBR_RU[dt.weekday()]})"
    except Exception:
        return f"{d:02d}.{m:02d}.{y}"

def export_notes_text(user_id: int) -> str:
    notes = get_notes(user_id)
    if not notes:
        return "Нет записей."
    lines = ["Экспорт заметок", "=================", ""]
    for note in notes:
        dt = _parse_note_datetime(note[3])
        dow = WEEKDAY_ABBR_RU[dt.weekday()]
        lines.append(f"ID: {note[0]}")
        lines.append(f"Дата: {dt.strftime('%d.%m.%Y %H:%M')} ({dow})")
        lines.append(f"Сила: {note[1]}")
        lines.append(f"Комментарий: {note[2]}")
        lines.append("")
    return "\n".join(lines)

def export_notes_filtered_text(user_id: int, scope: str, year: int | None = None, month: int | None = None) -> str:
    notes = get_notes(user_id)
    if not notes:
        return "Нет записей."
    filtered = []
    for n in notes:
        dt = _parse_note_datetime(n[3])
        if scope == 'all':
            filtered.append(n)
        elif scope == 'year' and year == dt.year:
            filtered.append(n)
        elif scope == 'month' and year == dt.year and month == dt.month:
            filtered.append(n)
    if not filtered:
        return "Нет записей."
    lines = ["Экспорт заметок", f"Область: {scope} {year or ''} {month or ''}", "=================", ""]
    for note in filtered:
        dt = _parse_note_datetime(note[3])
        dow = WEEKDAY_ABBR_RU[dt.weekday()]
        lines.append(f"ID: {note[0]}")
        lines.append(f"Дата: {dt.strftime('%d.%m.%Y %H:%M')} ({dow})")
        lines.append(f"Сила: {note[1]}")
        lines.append(f"Комментарий: {note[2]}")
        lines.append("")
    return "\n".join(lines)

@contextmanager
def tmp_file(suffix: str):
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    try:
        yield path
    finally:
        if os.path.exists(path):
            os.remove(path)

def find_cyr_font():
    """Ищет ttf шрифт с поддержкой кириллицы среди типичных Windows шрифтов и локальной папки fonts/. 
    Возвращает (name, path) или None."""
    candidates_fixed = [
        'C:/Windows/Fonts/arial.ttf',
        'C:/Windows/Fonts/Arial.ttf',
        'C:/Windows/Fonts/segoeui.ttf',
        'C:/Windows/Fonts/tahoma.ttf',
        'C:/Windows/Fonts/verdana.ttf',
        'C:/Windows/Fonts/calibri.ttf',
        'C:/Windows/Fonts/times.ttf',
        'C:/Windows/Fonts/timesbd.ttf',
        'C:/Windows/Fonts/DejaVuSans.ttf',
        'C:/Windows/Fonts/DejaVuSansCondensed.ttf'
    ]
    fonts_dir = Path(__file__).parent / 'fonts'
    dynamic = []
    if fonts_dir.exists():
        for p in fonts_dir.glob('*.ttf'):
            dynamic.append(str(p))
    for p in dynamic + candidates_fixed:
        if os.path.exists(p):
            # имя шрифта берём из имени файла без расширения, убирая пробелы
            name = Path(p).stem.replace(' ', '_')
            return name, p
    return None

# Хэндлер на команду /start
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    """
    Этот хэндлер будет вызываться при отправке команды /start
    """
    await message.answer("Привет! Я Мигребот. Помогаю вести дневник мигреней", reply_markup=keyboard_main)

# Хэндлер на нажатие инлайн-кнопок
@dp.callback_query()
async def handle_callback(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data
    user_id = callback.from_user.id

    # Новая запись
    if data == "button_new_note":
        logging.debug(f"Нажата кнопка 'Новая запись' user_id={user_id}")
        await callback.message.answer("Давайте добавим новую запись. \nНа сколько сильно болит голова по 10-балльной шкале?", reply_markup=keyboard_cancel)
        await state.set_state(AddNoteStates.waiting_for_strength)
        await callback.answer()
        return

    # Просмотр записей: выбор года/месяца
    if data == "button_list_notes":
        logging.debug(f"Нажата кнопка 'Посмотреть записи' user_id={user_id}")
        structure, years = group_notes_structure(user_id)
        if not years:
            await callback.message.answer("У вас пока нет ни одной записи.")
            await callback.answer()
            return
        # Берем последний (самый новый) год
        current_year = years[-1]
        months = available_months(structure, current_year)
        has_prev = len(years) > 1 and current_year != years[0]
        has_next = False  # так как выбран последний
        if current_year != years[-1]:
            has_next = True
        await state.update_data(view_structure=structure, years=years, current_year=current_year)
        await callback.message.answer(f"Год: {current_year}\nВыберите месяц:", reply_markup=kb_year_months(current_year, months, has_prev, has_next))
        await callback.answer()
        return

    # Навигация по годам
    if data.startswith("nav_year:"):
        _, year_str, direction = data.split(":")
        st = await state.get_data()
        structure = st.get("view_structure")
        years = st.get("years", [])
        if not structure or not years:
            await callback.answer()
            return
        current_index = years.index(int(year_str)) if int(year_str) in years else len(years)-1
        if direction == "prev" and current_index > 0:
            current_index -= 1
        elif direction == "next" and current_index < len(years)-1:
            current_index += 1
        current_year = years[current_index]
        months = available_months(structure, current_year)
        has_prev = current_index > 0
        has_next = current_index < len(years)-1
        await state.update_data(current_year=current_year)
        await callback.message.edit_text(f"Год: {current_year}\nВыберите месяц:", reply_markup=kb_year_months(current_year, months, has_prev, has_next))
        await callback.answer()
        return

    # Выбор месяца -> показываем дни (пагинация по 5)
    if data.startswith("sel_month:"):
        _, year_str, month_str = data.split(":")
        year = int(year_str); month = int(month_str)
        st = await state.get_data()
        structure = st.get("view_structure")
        days = available_days(structure, year, month)
        page = 0
        total_pages = total_day_pages(days)
        days_slice = slice_days(days, page)
        await state.update_data(current_year=year, current_month=month, current_day_page=page)
        await callback.message.edit_text(f"{month_title(month, year)}\nДни (стр {page+1}/{total_pages}):", reply_markup=kb_days(year, month, days_slice, page, total_pages))
        await callback.answer()
        return

    # Пагинация дней
    if data.startswith("nav_days:"):
        _, year_str, month_str, page_str = data.split(":")
        year = int(year_str); month = int(month_str); page = int(page_str)
        st = await state.get_data()
        structure = st.get("view_structure")
        days = available_days(structure, year, month)
        total_pages = total_day_pages(days)
        page = max(0, min(page, total_pages-1))
        days_slice = slice_days(days, page)
        await state.update_data(current_day_page=page)
        text = format_notes_for_days(structure, year, month, days_slice)
        header = f"{month_title(month, year)} | Даты: {', '.join(fmt_date_dow(year, month, d) for d in days_slice)}\n\n"
        await callback.message.edit_text(header + text, reply_markup=kb_days(year, month, days_slice, page, total_pages))
        await callback.answer()
        return

    # Быстрая навигация по неделям (страницам) из режима просмотра
    if data.startswith("page_week:"):
        _, year_str, month_str, page_str = data.split(":")
        year = int(year_str); month = int(month_str); page = int(page_str)
        st = await state.get_data()
        structure = st.get("view_structure")
        days = available_days(structure, year, month)
        total_pages = total_day_pages(days)
        page = max(0, min(page, total_pages-1))
        days_slice = slice_days(days, page)
        await state.update_data(current_day_page=page)
        text = format_notes_for_days(structure, year, month, days_slice)
        header = f"{month_title(month, year)} | Даты: {', '.join(fmt_date_dow(year, month, d) for d in days_slice)}\n\n"
        await callback.message.edit_text(header + text, reply_markup=kb_days(year, month, days_slice, page, total_pages))
        await callback.answer(); return

    # Просмотр всего месяца
    if data.startswith("view_month:"):
        _, year_str, month_str = data.split(":")
        year = int(year_str); month = int(month_str)
        st = await state.get_data()
        structure = st.get("view_structure")
        if not structure or month not in structure.get(year, {}):
            await callback.answer("Нет записей в этом месяце.")
            return
        days = available_days(structure, year, month)
        text = format_notes_for_days(structure, year, month, days)
        header = f"{month_title(month, year)} | Весь месяц\n\n"
        page = 0
        total_pages = total_day_pages(days)
        days_slice = slice_days(days, page)
        await callback.message.edit_text(header + text, reply_markup=kb_days(year, month, days_slice, page, total_pages))
        await callback.answer(); return

    if data == "noop":
        await callback.answer()
        return

    # Возврат к месяцам
    if data.startswith("back_months:"):
        _, year_str = data.split(":")
        year = int(year_str)
        st = await state.get_data()
        structure = st.get("view_structure")
        years = st.get("years", [])
        if not structure or year not in years:
            await callback.answer()
            return
        idx = years.index(year)
        months = available_months(structure, year)
        has_prev = idx > 0
        has_next = idx < len(years)-1
        await callback.message.edit_text(f"Год: {year}\nВыберите месяц:", reply_markup=kb_year_months(year, months, has_prev, has_next))
        await callback.answer()
        return

    # Выбор дня -> показываем записи выбранного дня требование: вывод записей (текущий формат) по выбранным дням страницы.
    if data.startswith("sel_day:"):
        _, year_str, month_str, day_str = data.split(":")
        year = int(year_str); month = int(month_str)
        st = await state.get_data()
        structure = st.get("view_structure")
        day = int(day_str)
        if day not in structure.get(year, {}).get(month, {}):
            await callback.answer("Нет записей в этот день.")
            return
        page = st.get("current_day_page", 0)
        # Формируем текст всех дней текущей страницы
        text = format_notes_for_day(structure, year, month, day)
        header = f"{month_title(month, year)} | Дата: {fmt_date_dow(year, month, day)}\n\n"
        await callback.message.edit_text(header + text, reply_markup=kb_days(year, month, [day], page, total_day_pages([day])))
        # Дополнительная клавиатура действий (экспорт / удаление / главное меню) - перегрузка интерфейса
        # await callback.message.answer("Действия:", reply_markup=kb_after_notes())
        await callback.answer()
        return

    # Главное меню
    if data == "button_main_menu":
        await callback.message.answer("Выберите действие.", reply_markup=keyboard_main)
        await callback.answer()
        return

    if data == "export_open_filter":
        await callback.message.answer("Область экспорта:", reply_markup=kb_export_root())
        await callback.answer(); return

    # Экспорт TXT
    if data == "export_txt":
        txt = export_notes_text(user_id)
        if txt.strip() == "Нет записей.":
            await callback.message.answer("Нет записей для экспорта.")
            await callback.answer(); return
        with tmp_file('.txt') as path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(txt)
            await callback.message.answer_document(types.FSInputFile(path, filename='notes_export.txt'))
        await callback.answer(); return

    # Экспорт PDF (попытка через reportlab)
    if data == "export_pdf":
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
        except ImportError:
            await callback.message.answer("Модуль reportlab не установлен. Установите: pip install reportlab")
            await callback.answer(); return
        txt = export_notes_text(user_id)
        if txt.strip() == "Нет записей.":
            await callback.message.answer("Нет записей для экспорта.")
            await callback.answer(); return
        with tmp_file('.pdf') as path:
            c = canvas.Canvas(path, pagesize=A4)
            width, height = A4
            y = height - 40
            max_chars = 100
            font_info = find_cyr_font()
            font_name = 'Helvetica'
            if font_info:
                try:
                    pdfmetrics.registerFont(TTFont(font_info[0], font_info[1]))
                    font_name = font_info[0]
                except Exception:
                    pass
            c.setFont(font_name, 11)
            for line in txt.split('\n'):
                # перенос длинных строк
                parts = [line[i:i+max_chars] for i in range(0, len(line), max_chars)] or ['']
                for part in parts:
                    if y < 50:
                        c.showPage(); y = height - 40
                        c.setFont(font_name, 11)
                    c.drawString(40, y, part)
                    y -= 14
            c.save()
            await callback.message.answer_document(types.FSInputFile(path, filename='notes_export.pdf'))
        await callback.answer(); return

    # ===== Расширенный экспорт с фильтром =====
    if data == 'export_scope:all':
        await callback.message.answer("Выберите формат:", reply_markup=kb_export_format('all'))
        await callback.answer(); return
    if data == 'export_scope:year':
        structure, years = group_notes_structure(user_id)
        if not years:
            await callback.message.answer("Нет данных.")
            await callback.answer(); return
        await callback.message.answer("Выберите год:", reply_markup=kb_export_years(years))
        await callback.answer(); return
    if data == 'export_scope:month':
        structure, years = group_notes_structure(user_id)
        if not years:
            await callback.message.answer("Нет данных.")
            await callback.answer(); return
        await callback.message.answer("Сначала выберите год:", reply_markup=kb_export_years(years))
        await callback.answer(); return
    if data == 'export_cancel':
        await callback.message.answer("Экспорт отменён.")
        await callback.answer(); return
    if data == 'export_back_root':
        await callback.message.answer("Область экспорта:", reply_markup=kb_export_root())
        await callback.answer(); return
    if data == 'export_back_years':
        structure, years = group_notes_structure(user_id)
        await callback.message.answer("Выберите год:", reply_markup=kb_export_years(years))
        await callback.answer(); return
    if data.startswith('export_year:'):
        _, year_str = data.split(':')
        year = int(year_str)
        # Если сценарий был "по месяцу", дадим выбор месяцев
        # Определить сценарий: просто повторно спросим выбор формата/или месяцев.
        structure, years = group_notes_structure(user_id)
        months = available_months(structure, year)
        if months:
            # await callback.message.answer("Выберите месяц или формат для всего года:", reply_markup=kb_export_months(year, months))
            # Также отдельно можно предложить форматы для года
            await callback.message.answer("Формат: ", reply_markup=kb_export_format('year', year))
        else:
            await callback.message.answer("Нет месяцев в этом году.")
        await callback.answer(); return
    if data.startswith('export_month:'):
        _, year_str, month_str = data.split(':')
        year = int(year_str); month = int(month_str)
        await callback.message.answer("Выберите формат:", reply_markup=kb_export_format('month', year, month))
        await callback.answer(); return
    if data.startswith('export_make:'):
        parts = data.split(':')
        # export_make : fmt : scope (: year) (: month)
        fmt = parts[1]
        scope = parts[2]
        year = int(parts[3]) if len(parts) > 3 else None
        month = int(parts[4]) if len(parts) > 4 else None
        txt = export_notes_filtered_text(user_id, scope, year, month)
        if txt.strip() == 'Нет записей.':
            await callback.message.answer("Нет записей под выбранный фильтр.")
            await callback.answer(); return
        if fmt == 'txt':
            with tmp_file('.txt') as path:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(txt)
                fname = 'notes_export.txt'
                if scope == 'year' and year:
                    fname = f'notes_{year}.txt'
                if scope == 'month' and year and month:
                    fname = f'notes_{year}_{month}.txt'
                await callback.message.answer_document(types.FSInputFile(path, filename=fname))
        elif fmt == 'pdf':
            try:
                from reportlab.lib.pagesizes import A4
                from reportlab.pdfgen import canvas
                from reportlab.pdfbase import pdfmetrics
                from reportlab.pdfbase.ttfonts import TTFont
            except ImportError:
                await callback.message.answer("reportlab не установлен.")
                await callback.answer(); return
            with tmp_file('.pdf') as path:
                c = canvas.Canvas(path, pagesize=A4)
                width, height = A4
                y = height - 40
                max_chars = 100
                font_info = find_cyr_font()
                font_name = 'Helvetica'
                if font_info:
                    try:
                        pdfmetrics.registerFont(TTFont(font_info[0], font_info[1]))
                        font_name = font_info[0]
                    except Exception:
                        pass
                c.setFont(font_name, 11)
                for line in txt.split('\n'):
                    parts_line = [line[i:i+max_chars] for i in range(0, len(line), max_chars)] or ['']
                    for pl in parts_line:
                        if y < 50:
                            c.showPage(); y = height - 40
                            c.setFont(font_name, 11)
                        c.drawString(40, y, pl)
                        y -= 14
                c.save()
                fname = 'notes_export.pdf'
                if scope == 'year' and year:
                    fname = f'notes_{year}.pdf'
                if scope == 'month' and year and month:
                    fname = f'notes_{year}_{month}.pdf'
                await callback.message.answer_document(types.FSInputFile(path, filename=fname))
        await callback.answer(); return

    # Удаление: запускаем ту же навигацию, но с префиксом режима удаления
    if data == "button_delete_note":
        structure, years = group_notes_structure(user_id)
        if not years:
            await callback.message.answer("Нет записей для удаления.")
            await callback.answer()
            return
        current_year = years[-1]
        months = available_months(structure, current_year)
        has_prev = len(years) > 1 and current_year != years[0]
        has_next = False
        await state.update_data(del_structure=structure, del_years=years, del_current_year=current_year)
        # Используем ту же клавиатуру, но callback менять префиксы через замену (простое решение)
        kb = kb_year_months(current_year, months, has_prev, has_next)
        # Перезаписываем callback_data в режиме удаления
        for row in kb.inline_keyboard:
            for btn in row:
                if btn.callback_data and btn.callback_data.startswith("sel_month:"):
                    btn.callback_data = btn.callback_data.replace("sel_month:", "del_sel_month:")
                if btn.callback_data and btn.callback_data.startswith("nav_year:"):
                    btn.callback_data = btn.callback_data.replace("nav_year:", "del_nav_year:")
        await callback.message.answer(f"[Удаление] Год: {current_year}\nВыберите месяц:", reply_markup=kb)
        await callback.answer()
        return

    # Навигация по годам (удаление)
    if data.startswith("del_nav_year:"):
        _, year_str, direction = data.split(":")
        st = await state.get_data()
        structure = st.get("del_structure")
        years = st.get("del_years", [])
        if not structure or not years:
            await callback.answer(); return
        current_index = years.index(int(year_str)) if int(year_str) in years else len(years)-1
        if direction == "prev" and current_index > 0:
            current_index -= 1
        elif direction == "next" and current_index < len(years)-1:
            current_index += 1
        current_year = years[current_index]
        months = available_months(structure, current_year)
        has_prev = current_index > 0
        has_next = current_index < len(years)-1
        await state.update_data(del_current_year=current_year)
        kb = kb_year_months(current_year, months, has_prev, has_next)
        for row in kb.inline_keyboard:
            for btn in row:
                if btn.callback_data and btn.callback_data.startswith("sel_month:"):
                    btn.callback_data = btn.callback_data.replace("sel_month:", "del_sel_month:")
                if btn.callback_data and btn.callback_data.startswith("nav_year:"):
                    btn.callback_data = btn.callback_data.replace("nav_year:", "del_nav_year:")
        await callback.message.edit_text(f"[Удаление] Год: {current_year}\nВыберите месяц:", reply_markup=kb)
        await callback.answer(); return

    # Выбор месяца (удаление)
    if data.startswith("del_sel_month:"):
        _, year_str, month_str = data.split(":")
        year = int(year_str); month = int(month_str)
        st = await state.get_data()
        structure = st.get("del_structure")
        days = available_days(structure, year, month)
        page = 0
        total_pages = total_day_pages(days)
        days_slice = slice_days(days, page)
        await state.update_data(del_current_year=year, del_current_month=month, del_current_day_page=page)
        kb = kb_days(year, month, days_slice, page, total_pages, include_view_month=False)
        for row in kb.inline_keyboard:
            for btn in row:
                if btn.callback_data and btn.callback_data.startswith("sel_day:"):
                    btn.callback_data = btn.callback_data.replace("sel_day:", "del_sel_day:")
                if btn.callback_data and btn.callback_data.startswith("nav_days:"):
                    btn.callback_data = btn.callback_data.replace("nav_days:", "del_nav_days:")
                if btn.callback_data and btn.callback_data.startswith("back_months:"):
                    btn.callback_data = btn.callback_data.replace("back_months:", "del_back_months:")
        await callback.message.edit_text(f"[Удаление] {month_title(month, year)}\nДни (стр {page+1}/{total_pages}):", reply_markup=kb)
        await callback.answer(); return

    # Пагинация дней (удаление)
    if data.startswith("del_nav_days:"):
        _, year_str, month_str, page_str = data.split(":")
        year = int(year_str); month = int(month_str); page = int(page_str)
        st = await state.get_data()
        structure = st.get("del_structure")
        days = available_days(structure, year, month)
        total_pages = total_day_pages(days)
        page = max(0, min(page, total_pages-1))
        days_slice = slice_days(days, page)
        await state.update_data(del_current_day_page=page)
        kb = kb_days(year, month, days_slice, page, total_pages, include_view_month=False)
        for row in kb.inline_keyboard:
            for btn in row:
                if btn.callback_data and btn.callback_data.startswith("sel_day:"):
                    btn.callback_data = btn.callback_data.replace("sel_day:", "del_sel_day:")
                if btn.callback_data and btn.callback_data.startswith("nav_days:"):
                    btn.callback_data = btn.callback_data.replace("nav_days:", "del_nav_days:")
                if btn.callback_data and btn.callback_data.startswith("back_months:"):
                    btn.callback_data = btn.callback_data.replace("back_months:", "del_back_months:")
        await callback.message.edit_text(f"[Удаление] {month_title(month, year)}\nДни (стр {page+1}/{total_pages}):", reply_markup=kb)
        await callback.answer(); return

    # Возврат к месяцам (удаление)
    if data.startswith("del_back_months:"):
        _, year_str = data.split(":")
        year = int(year_str)
        st = await state.get_data()
        structure = st.get("del_structure")
        years = st.get("del_years", [])
        if not structure or year not in years:
            await callback.answer(); return
        idx = years.index(year)
        months = available_months(structure, year)
        has_prev = idx > 0
        has_next = idx < len(years)-1
        kb = kb_year_months(year, months, has_prev, has_next)
        for row in kb.inline_keyboard:
            for btn in row:
                if btn.callback_data and btn.callback_data.startswith("sel_month:"):
                    btn.callback_data = btn.callback_data.replace("sel_month:", "del_sel_month:")
                if btn.callback_data and btn.callback_data.startswith("nav_year:"):
                    btn.callback_data = btn.callback_data.replace("nav_year:", "del_nav_year:")
        await callback.message.edit_text(f"[Удаление] Год: {year}\nВыберите месяц:", reply_markup=kb)
        await callback.answer(); return

    # Выбор дня (удаление) -> показать записи текущей страницы и попросить id
    if data.startswith("del_sel_day:"):
        _, year_str, month_str, day_str = data.split(":")
        year = int(year_str); month = int(month_str)
        st = await state.get_data()
        structure = st.get("del_structure")
        days = available_days(structure, year, month)
        page = st.get("del_current_day_page", 0)
        days_slice = slice_days(days, page)
        text = format_notes_for_days(structure, year, month, days_slice)
        header = f"[Удаление] {month_title(month, year)} | Даты: {', '.join(fmt_date_dow(year, month, d) for d in days_slice)}\n\n"
        await callback.message.edit_text(header + text + "\nОтправьте id записи, которую хотите удалить.")
        await state.set_state(DeleteNoteStates.waiting_for_id)
        await callback.answer(); return
    
    if data.startswith("button_cancel"):
        await callback.message.answer("Действие отменено. Выберите действие.", reply_markup=keyboard_main)
        await state.clear()

    await callback.answer()

# Хэндлер, который ловит ответ пользователя о силе боли
@dp.message(AddNoteStates.waiting_for_strength)
async def process_strength(message: types.Message, state: FSMContext):
    try:
        strength = int(message.text.strip())
        if 1 <= strength <= 10:
            await state.update_data(strength=strength)
            logging.debug(f"Получена сила боли: {strength} user_id={message.from_user.id}")
            await message.reply("Отлично. Теперь ваши комментарии.")
            await state.set_state(AddNoteStates.waiting_for_text)
        else:
            await message.reply("Пожалуйста, введите число от 1 до 10.")
    except (ValueError, TypeError):
        await message.reply("Это не похоже на число. Пожалуйста, введите число от 1 до 10.")

# Хэндлер, который ловит текст
@dp.message(AddNoteStates.waiting_for_text)
async def process_text(message: types.Message, state: FSMContext):
    text = message.text
    await state.update_data(text=text)
    logging.debug(f"Получены комментарий: {text} user_id={message.from_user.id}")

    user_data = await state.get_data()
    add_note(
        user_id=message.from_user.id,
        strength=user_data['strength'],
        text=user_data['text'],
        datetime=datetime.datetime.now(offset_timezone).strftime("%d.%m.%Y %H:%M")
    )
    
    await message.reply("Готово! Запись сохранена.", reply_markup=keyboard_main)
    logging.debug(f"Новая запись для user_id={message.from_user.id}")
    logging.info("Новая запись в БД")
    await state.clear()

# Хэндлер, который ловит id записи на удаление
@dp.message(DeleteNoteStates.waiting_for_id)
async def process_get_note_id(message: types.Message, state: FSMContext):
    try: 
        note_id = int(message.text.strip())
        await state.update_data(note_id=note_id)
        try:
            delete_note(note_id=note_id)
            logging.debug(f"Удалена запись с id={note_id} user_id={message.from_user.id}")
            logging.info("Удалена запись.")
            await message.answer("Запись удалена. \nВыберите действие.", reply_markup=keyboard_main)
        except Exception as err:
            logging.error(f"Ошибка при удалении записи в БД: {err}")
    except (ValueError, TypeError):
        await message.reply("Это не похоже на число. Пожалуйста, введите число.")

    

async def main():
    # Создаем таблицу при запуске
    init_db()
    # Запускаем бота
    logging.debug("Запуск бота.")
    print("Запуск бота...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
