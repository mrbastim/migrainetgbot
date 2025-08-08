import asyncio
import logging
import os
import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards import keyboard_main, keyboard_list_notes
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
    if callback.data == "button_new_note":
        logging.debug(f"Нажата кнопка 'Новая запись' user_id={callback.from_user.id}")
        await callback.message.answer("Давайте добавим новую запись. \nНа сколько сильно болит голова по 10-балльной шкале?")
        await state.set_state(AddNoteStates.waiting_for_strength)

    elif callback.data == "button_list_notes":
        logging.debug(f"Нажата кнопка 'Посмотреть записи' user_id={callback.from_user.id}")
        notes = get_notes(callback.from_user.id)
        if not notes:
            await callback.message.answer("У вас пока нет ни одной записи.")
        else:
            response = "Вот ваши записи:\n\n"
            for note in notes:
                response += f"---{note[0]}---\n"
                response += f"Дата: {note[3]}\n"
                response += f"Сила боли: {note[1]}\n"
                response += f"Комментарий: {note[2]}\n"
            await callback.message.answer(response, reply_markup=keyboard_list_notes)
    elif callback.data == "button_main_menu":
        await callback.message.answer("Выберите действие.", reply_markup=keyboard_main)
    elif callback.data == "button_delete_note":
        await callback.message.reply("Напишите id записи.")
        await state.set_state(DeleteNoteStates.waiting_for_id)
    # else:
    #     await callback.message.answer("В разработке.")
    await callback.answer()

# Хэндлер, который ловит ответ пользователя о силе боли
@dp.message(AddNoteStates.waiting_for_strength)
async def process_strength(message: types.Message, state: FSMContext):
    try:
        strength = int(message.text.strip())
        if 1 <= strength <= 10:
            await state.update_data(strength=strength)
            logging.debug(f"Получена сила боли: {strength} user_id={callback.from_user.id}")
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
    logging.debug(f"Получены комментарий: {text} user_id={callback.from_user.id}")

    user_data = await state.get_data()
    add_note(
        user_id=message.from_user.id,
        strength=user_data['strength'],
        text=user_data['text'],
        datetime=datetime.datetime.now(offset_timezone).strftime("%d.%m.%Y %H:%M")
    )
    
    await message.reply("Готово! Запись сохранена.", reply_markup=keyboard_main)
    logging.debug(f"Новая запись для user_id={callback.from_user.id}")
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
