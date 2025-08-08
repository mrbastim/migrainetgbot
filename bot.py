import asyncio
import logging
import os
import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards import keyboard_main
from database import init_db, add_note, get_notes

BOT_TOKEN = os.getenv("TELEGRAM_API_TOKEN")

# Включаем логирование, чтобы видеть сообщения в консоли
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Определяем состояния FSM
class AddNoteStates(StatesGroup):
    waiting_for_strength = State()
    waiting_for_text = State()

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
        logging.info("Нажата кнопка 'Новая запись', переход в состояние 'waiting_for_strength'")
        await callback.message.answer("Давай добавим новую запись. \nНа сколько сильно болит голова по 10-балльной шкале?")
        await state.set_state(AddNoteStates.waiting_for_strength)

    elif callback.data == "button_list_notes":
        logging.info("Нажата кнопка 'Посмотреть записи'")
        notes = get_notes()
        if not notes:
            await callback.message.answer("У вас пока нет ни одной записи.")
        else:
            response = "Вот ваши записи:\n\n"
            for note in notes:
                response += f"Дата: {note[4]}\n"
                response += f"Сила боли: {note[1]}\n"
                response += f"text: {note[2]}\n"
                response += f"Триггеры: {note[3]}\n"
                response += "------\n"
            await callback.message.answer(response)
    
    await callback.answer()

# Хэндлер, который ловит ответ пользователя о силе боли
@dp.message(AddNoteStates.waiting_for_strength)
async def process_strength(message: types.Message, state: FSMContext):
    try:
        strength = int(message.text.strip())
        if 1 <= strength <= 10:
            await state.update_data(strength=strength)
            logging.info(f"Получена сила боли: {strength}")

            await message.reply("Отлично. Теперь твои комментарии.")

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
    logging.info(f"Получены комментарий: {text}")

    user_data = await state.get_data()
    await add_note(
        user_id=message.from_user.id,
        strength=user_data['strength'],
        text=user_data['text'],
        datetime=datetime
    )
    
    await message.reply("Готово! Запись сохранена.", reply_markup=keyboard_main)
    
    await state.clear()


async def main():
    # Создаем таблицу при запуске
    init_db()
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
