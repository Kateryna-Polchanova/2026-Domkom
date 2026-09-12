import asyncio
from telegram import Update
from telegram.ext import (Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, CallbackContext, JobQueue)
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import json
import os
import re
import aiofiles
from dotenv import load_dotenv
from FileHandler import AsyncFileHandler
from Logging1 import Logging
# from Logging1 import get_list_of_members_dict
# from Logging1 import list_of_members_dict
#
#
load_dotenv()
bot_token = os.getenv('BOT_TOKEN')
#
# """Екземпляр класу для роботи зі списком зареєстрованих користувачів"""
list_of_users1 = AsyncFileHandler(filename="list_of_users1.json")
#
#
# async def call_list_of_members():
#     return await get_list_of_members_dict()
#
# """Перевірка поточного часу для вибору відповідної папки з json-файлами"""
current_date = datetime.now()
#
# """Поточний рік"""
year = str(current_date.year)
#
# """Поточний місяць"""
month = current_date.strftime('%B')
#
#
class AsyncFileHandler2: #Клас для відкриття json - файлу для відповідного користувача
    route = "balance/payments/"

    def __init__(self, year1, month1, filename):
        self.filename = filename
        self.year = year1
        self.month = month1

    async def read_file(self):
        file_path = os.path.join(self.route, self.year, self.month, self.filename)
        if os.path.exists(file_path):
            async with aiofiles.open(file_path, "r") as f:
                content = await f.read()
                return json.loads(content)
        else:
            raise FileNotFoundError(f"File not found: {file_path}")
#
#
async def get_debit_credit(user_file_handler: AsyncFileHandler2):
    data = await user_file_handler.read_file()
    return data['current_balance'], data['arrears']


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):  # Універсальний хендлер або видає баланс,
                                                                               # або робить перевірку
    user_message = update.message.text
    username = update.message.from_user.username
#     context.user_data['last_message'] = user_message1
    possible_phone = Logging(update.message.text)
#     user_id = update.message.from_user.id
    try:
        if user_message.lower() == "balance":
            user_access = AsyncGrantAccess(username)
            if await user_access.check_if_user():
                user_file = AsyncFileHandler2(year, month, f"{username}.json")
                try:
                    if os.path.exists(user_file.route + "/" + user_file.year + "/" + user_file.month + "/"
                                   + user_file.filename):
                        result = get_debit_credit(user_file)
                    await update.message.reply_text(f"Ваш баланс: {result[0]}, ваш борг: {result[1]}")
                except FileNotFoundError as e:
                    await update.message.reply_text("Файл не знайдено.")
            else:
                await update.message.reply_text("Ви не зареєстровані. Введіть номер телефону.")
        elif re.match(r'^\+380\d{9}$', user_message):
            print(f"Спроба реєстрації з телефоном: {user_message}")
            grant_access = AsyncGrantAccess(username)
            success = await grant_access.grant_access(user_message)

            if success:
                await update.message.reply_text(
                    "✅ Ви пройшли перевірку!\n"
                    "Введіть ім'я, прізвище, номер квартири у форматі:\n"
                    "Ivanov Ivan 33"
                )
                context.user_data['registration_step'] = 'name_input'
            else:
                await update.message.reply_text(
                        "❌ Телефон не знайдено в системі.\n"
                        "Спробуйте інший номер або зверніться до адміністратора."
                )
        elif context.user_data.get('registration_step') == 'name_input':
            await update.message.reply_text("✅ Реєстрація завершена!")
            context.user_data.pop('registration_step', None)

        else:
            await update.message.reply_text(
                "Невідома команда. Доступні опції:\n"
                "- Введіть номер телефону для реєстрації\n"
                "- Напишіть 'balance' для перевірки балансу"
            )
    except Exception as e:
        print(f"Помилка: {e}")
        await update.message.reply_text("Сталася помилка. Спробуйте ще раз.")
                                                                                   #




async def handle_registration(update: Update, context: CallbackContext) -> int:
    phone = context.user_data['last_message']

    user_message2 = update.message.text
    user_id = update.message.from_user.id

    input_handler = InputHandler(user_message2)
    name, surname, apt = None, None, None
    try:
        name, surname, apt = input_handler.handle_input()
        if not name or not surname or not apt:
            raise ValueError("Неповний набір даних введено.")
        await update.message.reply_text(f"Ви успішно зареєструвались.")

        new_member, all_members = await possible_phone.sign_up(name, surname, apt)
    except ValueError as e:
        await update.message.reply_text(f"Неправильний ввід даних. Спробуйте ще раз у форматі:"
                                        f"Ivanov Ivan 33")

    possibly_new_user = AsyncGrantAccess(user_id)

    if possibly_new_user.check_if_user():
        possibly_new_user.grant_access(phone)


class InputHandler:
    def __init__(self, input_data):
        self.input_data = input_data  # Вхідні дані

    def handle_input(self):
        # Локальні змінні для обробки
        try:
            name, surname, apt = self.input_data.split()
            return name, surname, apt
        except ValueError:
            return None, None, None


class AsyncGrantAccess(object):

    def __init__(self, username):
        self.username = username

    async def check_if_user(self):
        all_members = await list_of_users1.eval_file() or []

        # Checks if all_members is a list
        if isinstance(all_members, list):
            for member_data in all_members:
                # Assuming each member is a dictionary and contains 'username' field
                if member_data.get('username') == self.username:
                    return True
        elif isinstance(all_members, dict):
            for _, member_data in all_members.items():
                if member_data.get('username') == self.username:
                    return True

        return False

    async def grant_access(self, user_phone):
        try:
            all_users = await list_of_users1.eval_file() or []

            if isinstance(all_users, list):
                for user_data in all_users:
                    phone = user_data.get("phone")
                    print(f"Перевіряємо телефон: {phone}")
                    if phone == user_phone:
                        # Користувач вже існує в системі
                        print(f"Користувач {self.username} вже зареєстрований")
                        return True

            # Якщо телефон не знайдено в існуючих користувачах, додаємо нового
            new_member = {"username": self.username, "phone": user_phone}
            all_users.append(new_member)
            await list_of_users1.write_file(all_users)
            print(f"Користувач {self.username} успішно зареєстрований")
            return True

        except Exception as e:
            print(f"Помилка: {e}")
            return False

#Дізнаємося поточний час. У разі настання 19 - ї години - розсилаємо інформацію про заборгованість."""


# async def check_time(context: CallbackContext):
#     current_time = datetime.now()
#     if current_time.hour == 19:
#         await handle_message2(context)


# async def handle_message2(context: CallbackContext):
#     user_data = context.user_data
#     chat_id = context.job.chat_id
#     user_file = FileHandler2(year, month, chat_id)
#     try:
#         if os.path.exists(user_file.route + "/" + user_file.year + "/" + user_file.month + "/"
#                                   + user_file.filename):
#             result = get_debit_credit(user_file)
#             await context.bot.send_message(chat_id=chat_id, text=result)
#     except FileNotFoundError as e:
#         print(f"Error: {e}")

# async def save_members_data(members_dict):
#     async with aiofiles.open('members_data.json', 'w') as f:
#         await f.write(json.dumps(members_dict))
#
#
# async def save_members_list():
#     members_dict = await get_list_of_members_dict()
#     await save_members_data(members_dict)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):  # Бот перевіряє, чи є користувач зареєстрованим.
                                                                      # Якщо ні, проводить перевірку та реєстрацію.
    username = username = update.message.from_user.username
    user_access = AsyncGrantAccess(username)
    if await user_access.check_if_user():
        await update.message.reply_text(
            "З поверненням в бот ДОМКОМ!\n"
            "Введіть 'balance' для отримання інформації про баланс"
        )

    else:
        await update.message.reply_text(f"Вітаємо! Для реєстрації введіть номер телефону у форматі +380XXXXXXXXX")


async def main():

    application = Application.builder().token(bot_token).build()

    application.add_handler(CommandHandler("start", start))

    application.add_handler(MessageHandler(filters.TEXT, handle_message))
    # application.add_handler(CallbackQueryHandler(button_callback))
    # application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_registration))
    # application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message2))
    # job_queue: JobQueue = application.job_queue
    # job_queue.run_repeating(check_time, interval=3600, first=0)

    await application.run_polling()


if __name__ == '__main__':
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(main())
