from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

keyboard_main = InlineKeyboardMarkup(inline_keyboard=[ # в неск строк
        [InlineKeyboardButton(text="Новая запись", callback_data="button_new_note")],
        [InlineKeyboardButton(text="Посмотреть записи", callback_data="button_list_notes")],
    ])

keyboard_list_notes = InlineKeyboardMarkup(inline_keyboard=[
    [ # в одну строку 
        InlineKeyboardButton(text="Удалить запись\n по номеру", callback_data="button_delete_note"),
        InlineKeyboardButton(text="Главное меню", callback_data="button_main_menu")
    ]
])