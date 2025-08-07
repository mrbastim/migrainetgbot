
import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Включаем логирование, чтобы не пропустить важные сообщения
logging.basicConfig(level=logging.INFO)

# Получаем токен бота из переменной окружения
API_TOKEN = os.getenv("TELEGRAM_API_TOKEN")

# Проверяем, что токен доступен
if not API_TOKEN:
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
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Кнопка 1", callback_data="button_1_pressed")],
        [InlineKeyboardButton(text="Кнопка 2", callback_data="button_2_pressed")],
    ])
    await message.answer("Привет! Я бот на aiogram.", reply_markup=keyboard)

# Хэндлер на нажатие инлайн-кнопок
@dp.callback_query()
async def send_random_value(callback: types.CallbackQuery):
    if callback.data == "button_1_pressed":
        await callback.message.answer("Вы нажали на кнопку 1.")
    elif callback.data == "button_2_pressed":
        await callback.message.answer("Вы нажали на кнопку 2.")
    await callback.answer()

# Запуск процесса поллинга новых апдейтов
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
