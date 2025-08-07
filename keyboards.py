from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

keyboard_main = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Новая запись", callback_data="button_new_note")],
        [InlineKeyboardButton(text="Посмотреть записи", callback_data="button_list_notes")],
    ])