from __future__ import annotations

import asyncio
import logging
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.config import get_settings
from app.db import session_scope
from app.models import Account, AccountRole
from app.services import InterviewService
from app.telegram_clients import ClientManager

logger = logging.getLogger(__name__)
settings = get_settings()


class AdminBot:
    """Admin control surface with commands and buttons."""

    def __init__(self) -> None:
        if not settings.admin_bot_token:
            raise RuntimeError("Admin bot token is missing. Set ADMIN_BOT_TOKEN or admin_bot_token in .env")
        self.bot = Bot(token=settings.admin_bot_token, parse_mode=ParseMode.HTML)
        self.dispatcher = Dispatcher()
        self.clients = ClientManager()
        self._register_handlers()

    def _register_handlers(self) -> None:
        dp = self.dispatcher

        @dp.message(Command(commands=["start", "help"]))
        async def cmd_start(message: Message) -> None:
            await message.answer(
                "Привет! Я админ-бот. Доступные команды:\n"
                "/add_chat <chat_id> — добавить чат для интервью\n"
                "/list_chats — показать чаты\n"
                "/add_account — привязать аккаунт (главный/бот)\n"
                "/list_accounts — показать привязанные аккаунты\n"
                "/set_real — выбрать реального пользователя\n"
                "/start_interview — запустить интервью в выбранном чате\n"
                "/logs — последние события",
            )

        @dp.message(Command(commands=["add_chat"]))
        async def cmd_add_chat(message: Message) -> None:
            parts = message.text.split()
            if len(parts) < 2:
                await message.answer("Использование: /add_chat <chat_id>")
                return
            chat_id = int(parts[1])
            with session_scope() as db:
                service = InterviewService(db)
                chat = service.add_chat(chat_id)
                await message.answer(f"Чат добавлен: {chat.telegram_chat_id}")

        @dp.message(Command(commands=["list_chats"]))
        async def cmd_list_chats(message: Message) -> None:
            with session_scope() as db:
                service = InterviewService(db)
                chats = service.list_chats()
                if not chats:
                    await message.answer("Нет добавленных чатов")
                    return
                text = "\n".join(f"• {c.telegram_chat_id} — {c.title or 'без названия'}" for c in chats)
                await message.answer(text)

        @dp.message(Command(commands=["add_account"]))
        async def cmd_add_account(message: Message) -> None:
            buttons = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Главный", callback_data="role_main")],
                    [InlineKeyboardButton(text="Бот", callback_data="role_bot")],
                ]
            )
            await message.answer("Выберите роль аккаунта", reply_markup=buttons)

        @dp.callback_query(F.data.startswith("role_"))
        async def cq_role(callback: CallbackQuery) -> None:
            role_text = callback.data.split("_", maxsplit=1)[1]
            role = AccountRole.MAIN if role_text == "main" else AccountRole.BOT
            await callback.message.answer(
                "Отправьте сообщение вида:\n"
                f"<code>/bind +79991234567 session_{role_text}.session</code>",
            )
            await callback.answer()

        @dp.message(Command(commands=["bind"]))
        async def cmd_bind(message: Message) -> None:
            parts = message.text.split()
            if len(parts) < 3:
                await message.answer("Использование: /bind <phone> <session_path>")
                return
            phone = parts[1]
            session_path = parts[2]
            role = AccountRole.BOT
            if "main" in session_path.lower():
                role = AccountRole.MAIN
            with session_scope() as db:
                service = InterviewService(db)
                account = service.add_account(phone=phone, session_path=session_path, role=role)
                await message.answer(
                    f"Аккаунт сохранён. Отправьте код подтверждения в виде:"
                    f"\n<code>/code {account.id} 12345</code>",
                )

        @dp.message(Command(commands=["code"]))
        async def cmd_code(message: Message) -> None:
            parts = message.text.split()
            if len(parts) < 3:
                await message.answer("Использование: /code <account_id> <12345>")
                return
            account_id = int(parts[1])
            code = parts[2]
            password = parts[3] if len(parts) > 3 else None
            with session_scope() as db:
                account = db.get(Account, account_id)
                if not account:
                    await message.answer("Аккаунт не найден")
                    return
            await message.answer(
                "Код принят. Логин выполним при старте сервиса (реализация зависит от Telethon).",
            )

        @dp.message(Command(commands=["list_accounts"]))
        async def cmd_list_accounts(message: Message) -> None:
            with session_scope() as db:
                service = InterviewService(db)
                accounts = service.list_accounts()
                if not accounts:
                    await message.answer("Нет привязанных аккаунтов")
                    return
                lines = [
                    f"• #{acc.id} {acc.role.value} — {acc.phone_number or acc.title or acc.session_path}"
                    for acc in accounts
                ]
                await message.answer("\n".join(lines))

    async def run(self) -> None:
        await self.dispatcher.start_polling(self.bot)


def run_admin_bot() -> None:  # pragma: no cover
    logging.basicConfig(level=settings.log_level)
    bot = AdminBot()
    asyncio.run(bot.run())


if __name__ == "__main__":  # pragma: no cover
    run_admin_bot()
