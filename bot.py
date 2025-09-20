import asyncio
import logging
import os
import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards import (
    keyboard_main,
    keyboard_list_notes,
    kb_year_months,
    kb_days,
    kb_after_notes
)
from database import init_db, add_note, get_notes, delete_note

BOT_TOKEN = os.getenv("TELEGRAM_API_TOKEN")
offset_timezone = datetime.timezone(datetime.timedelta(hours=3), name='MSK') 

# Включаем логирование, чтобы видеть сообщения в консоли
logging.basicConfig(level=logging.INFO, filename="logfile.log",filemode="w",
                    format="%(asctime)s %(levelname)s %(message)s")

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Определяем состояния FSM
class AddNoteStates(StatesGroup):
    waiting_for_strength = State()
    waiting_for_text = State()

class DeleteNoteStates(StatesGroup):
    waiting_for_id = State()
    delete_note_by_id = State()

# ================= Вспомогательные функции для навигации заметок ====================
MONTH_NAMES_RU = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
]

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
            parts.append(f"---{note[0]}---\nДата: {note[3]}\nСила боли: {note[1]}\nКомментарий: {note[2]}\n")
    return "".join(parts)

# ================= Конец вспомогательных функций ====================

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
        await callback.message.answer("Давайте добавим новую запись. \nНа сколько сильно болит голова по 10-балльной шкале?")
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
        await callback.message.edit_text(f"{month_title(month, year)}\nДни (стр {page+1}/{total_pages}):", reply_markup=kb_days(year, month, days_slice, page, total_pages))
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

    # Выбор дня -> показываем записи выбранного дня (и соседних в той же странице?) требование: вывод записей (текущий формат) по выбранным дням страницы.
    if data.startswith("sel_day:"):
        _, year_str, month_str, day_str = data.split(":")
        year = int(year_str); month = int(month_str)
        st = await state.get_data()
        structure = st.get("view_structure")
        days = available_days(structure, year, month)
        page = st.get("current_day_page", 0)
        days_slice = slice_days(days, page)
        # Формируем текст всех дней текущей страницы (по ТЗ: выводить даты по неделям - интерпретируем как страницы по 5 дней)
        text = format_notes_for_days(structure, year, month, days_slice)
        header = f"{month_title(month, year)} | Дни {', '.join(str(d) for d in days_slice)}\n\n"
        await callback.message.edit_text(header + text, reply_markup=kb_days(year, month, days_slice, page, total_day_pages(days)))
        await callback.answer()
        return

    # Главное меню
    if data == "button_main_menu":
        await callback.message.answer("Выберите действие.", reply_markup=keyboard_main)
        await callback.answer()
        return

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
        kb = kb_days(year, month, days_slice, page, total_pages)
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
        kb = kb_days(year, month, days_slice, page, total_pages)
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
        header = f"[Удаление] {month_title(month, year)} | Дни {', '.join(str(d) for d in days_slice)}\n\n"
        await callback.message.edit_text(header + text + "\nОтправьте id записи, которую хотите удалить.")
        await state.set_state(DeleteNoteStates.waiting_for_id)
        await callback.answer(); return

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

# Хэндлер, который удаляет запись в БД по id
@dp.message(DeleteNoteStates.delete_note_by_id)
async def process_delete_note(message: types.Message, state: FSMContext):
    data = await state.get_data()
    try:
        note_id = data['note_id']
        delete_note(note_id=note_id)
        logging.debug(f"Удалена запись с id={note_id} user_id={message.from_user.id}")
        logging.info("Удалена запись.")
        await message.answer("Запись удалена")
    except Exception as err:
        logging.critical(f"Ошибка при удалении записи в БД: {err}")

async def main():
    # Создаем таблицу при запуске
    init_db()
    # Запускаем бота
    logging.debug("Запуск бота.")
    print("Запуск бота...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
