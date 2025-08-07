
import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from keyboards import keyboard_main
import database
# Включаем логирование, чтобы не пропустить важные сообщения
logging.basicConfig(level=logging.INFO)

# Получаем токен бота из переменной окружения
API_TOKEN = os.getenv("TELEGRAM_API_TOKEN")

# Проверяем, что токен доступен
if not API_TOKEN:
    logging.critical("Не был введен API ключ Телеграма")
    raise ValueError("Необходимо установить переменную окружения TELEGRAM_API_TOKEN")


# Объект бота
bot = Bot(token=API_TOKEN)
# Диспетчер
dp = Dispatcher()

# Хэндлер на команду /start
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    """
    Этот хэндлер будет вызываться при отправке команды /start
    """
    await message.answer("Привет! Я Мигребот. Помогаю вести дневник мигреней", reply_markup=keyboard_main)

# Хэндлер на нажатие инлайн-кнопок
@dp.callback_query()
async def send_random_value(callback: types.CallbackQuery):
    if callback.data == "button_new_note":
        logging.info("Нажата кнопка 'Новая запись'")
        await callback.message.answer("Вы нажали на кнопку 1.")
    elif callback.data == "button_list_notes":
        logging.info("Нажата кнопка 'Посмотреть записи'")
        await callback.message.answer("Вы нажали на кнопку 2.")
    await callback.answer()

# Запуск процесса поллинга новых апдейтов
async def main():
    database.init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
