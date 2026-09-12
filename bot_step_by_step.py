from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
import json
import os
import re
import aiofiles
from dotenv import load_dotenv
from FileHandler import AsyncFileHandler
from Logging1 import get_list_of_members_dict
from Logging1 import Logging
load_dotenv()
bot_token = os.getenv('BOT_TOKEN')

list_of_users1 = AsyncFileHandler(filename="list_of_users1.json")
all_members_handler = AsyncFileHandler(filename="all_members.json")


async def call_list_of_members():
    """Отримуємо список всіх потенційних членів"""
    try:
        return await all_members_handler.eval_file() or []
    except Exception as e:
        print(f"Помилка при читанні файлу всіх членів: {e}")
        return []


current_date = datetime.now()
year = str(current_date.year)
month = current_date.strftime('%B')



async def debug_members_data():
    """Функція для діагностики даних про членів"""
    try:
        all_members = await call_list_of_members()
        print("=" * 50)
        print("ДІАГНОСТИКА ДАНИХ ПРО ЧЛЕНІВ:")
        print("=" * 50)

        print(f"Тип даних: {type(all_members)}")
        print(f"Вміст: {all_members}")

        if isinstance(all_members, dict):
            print("\nДетальний вміст словника:")
            for user_id, user_data in all_members.items():
                print(f"ID: {user_id}, Дані: {user_data}")
                print(f"  Телефон: {user_data.get('phone')}")

        elif isinstance(all_members, list):
            print("\nДетальний вміст списку:")
            for i, user_data in enumerate(all_members):
                print(f"Індекс: {i}, Дані: {user_data}")
                print(f"  Телефон: {user_data.get('phone')}")

        print("=" * 50)
        return all_members

    except Exception as e:
        print(f"Помилка при отриманні даних: {e}")
        return {}


class AsyncGrantAccess(object):
    def __init__(self, username):
        self.username = username

    async def check_if_user(self):
        all_members = await list_of_users1.eval_file() or []
        if isinstance(all_members, list):
            for member_data in all_members:
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

            # Використовуємо той самий файл для перевірки
            all_members = all_users

            print(f"Шукаємо телефон: {user_phone}")

            if isinstance(all_members, list):
                for user_data in all_members:
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


class AsyncFileHandler2:
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


async def get_debit_credit(user_file_handler: AsyncFileHandler2):
    data = await user_file_handler.read_file()
    return data['current_balance'], data['arrears']


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    username = update.message.from_user.username

    print(f"Отримано повідомлення: {user_message} від {username}")

    try:
        if user_message.lower() == "balance":
            user_access = AsyncGrantAccess(username)
            if await user_access.check_if_user():
                user_file = AsyncFileHandler2(year, month, f"{username}.json")
                try:
                    result = await get_debit_credit(user_file)
                    await update.message.reply_text(f"Ваш баланс: {result[0]}, ваш борг: {result[1]}")
                except FileNotFoundError:
                    await update.message.reply_text("Файл не знайдено.")
            else:
                await update.message.reply_text("Ви не зареєстровані. Введіть номер телефону.")

        elif re.match(r'^\+380\d{9}$', user_message):
            print(f"Спроба реєстрації з телефоном: {user_message}")
            grant_access = AsyncGrantAccess(username)
            success = await grant_access.grant_access(user_message)

            if success:
                context.user_data['phone_number'] = user_message
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
            try:
                surname, name, apt = user_message.split()
            except ValueError:
                await update.message.reply_text("⚠️ Формат невірний. Спробуйте ще раз: Ivanov Ivan 33")
                return

                # ✅ Save registration data
            context.user_data['name'] = name
            context.user_data['surname'] = surname
            context.user_data['apt'] = apt

            await update.message.reply_text("✅ Дані збережено. Реєстрація завершується...")
            phone = context.user_data.get('phone_number')
            context.user_data.pop('registration_step', None)
            new_member, all_members = await phone.register_member(
                name, surname, apt)
            await update.message.reply_text(f"🎉 Реєстрація завершена!")
        else:
            await update.message.reply_text(
                "Невідома команда. Доступні опції:\n"
                "- Введіть номер телефону для реєстрації\n"
                "- Напишіть 'balance' для перевірки балансу"
            )

    except Exception as e:
        print(f"Помилка: {e}")
        await update.message.reply_text("Сталася помилка. Спробуйте ще раз.")








async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.from_user.username
    user_access = AsyncGrantAccess(username)
    user_check_up = Logging(username)
    if await user_access.check_if_user():
        await update.message.reply_text(
            "З поверненням в бот ДОМКОМ!\n"
            "Введіть 'balance' для отримання інформації про баланс"
        )
    elif await user_check_up.check_if_member():
        await update.message.reply_text("Вітаємо! Для реєстрації введіть номер телефону у форматі +380XXXXXXXXX")
    else:
        await update.message.reply_text("Користувача з таким номером телефону не знайдено")


def main():
    # if not os.path.exists("list_of_users1.json"):
    #     print("Створюємо пустий файл list_of_users1.json...")
    #     with open("list_of_users1.json", "w") as f:
    #         json.dump([], f)
    #
    # try:
    #     with open("list_of_users1.json", "r") as f:
    #         content = f.read()
    #         print(f"Вміст list_of_users1.json: {content}")
    # except Exception as e:
    #     print(f"Помилка читання файлу: {e}")

    application = Application.builder().token(bot_token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT, handle_message))
    print("Бот запущено...")
    application.run_polling()


if __name__ == '__main__':
    main()
