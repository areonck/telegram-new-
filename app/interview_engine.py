from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Callable, Dict, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from telethon import TelegramClient

from app.models import Account, AccountRole, EventType, InterviewSession, Question, ReminderScenario
from app.services import InterviewService

logger = logging.getLogger(__name__)


@dataclass
class TimingConfig:
    question_timeout_range: tuple[int, int] = (60, 180)  # seconds
    bot_delay_range: tuple[int, int] = (60, 240)  # seconds
    typing_range: tuple[int, int] = (10, 16)  # seconds
    reminder_after_bot_answer: int = 120  # seconds


class InterviewEngine:
    """Coordinates question posting, bot answers, and reminders per chat/session."""

    def __init__(self, scheduler: Optional[AsyncIOScheduler] = None) -> None:
        self.scheduler = scheduler or AsyncIOScheduler()
        self.scheduler.start()
        self._locks: Dict[int, asyncio.Lock] = {}

    def _lock_for(self, chat_id: int) -> asyncio.Lock:
        if chat_id not in self._locks:
            self._locks[chat_id] = asyncio.Lock()
        return self._locks[chat_id]

    async def run_session(
        self,
        *,
        service: InterviewService,
        session: InterviewSession,
        questions: list[Question],
        main_client: TelegramClient,
        bot_clients: Dict[int, TelegramClient],
        real_user_id: int,
        chat_telegram_id: int,
        timing: TimingConfig,
        send_typing: Callable[[TelegramClient, int, int], None],
        reminders: Optional[list[ReminderScenario]],
        on_log: Callable[[str], None] | None = None,
    ) -> None:
        lock = self._lock_for(chat_telegram_id)
        async with lock:
            service.start_session(session)
            for question in sorted([q for q in questions if q.is_active], key=lambda q: q.order):
                await self._post_question(
                    service=service,
                    session=session,
                    question=question,
                    main_client=main_client,
                    chat_telegram_id=chat_telegram_id,
                )
                await self._handle_question_flow(
                    service=service,
                    session=session,
                    question=question,
                    bot_clients=bot_clients,
                    real_user_id=real_user_id,
                    chat_telegram_id=chat_telegram_id,
                    timing=timing,
                    send_typing=send_typing,
                    reminders=reminders,
                )
            service.complete_session(session)
            if on_log:
                on_log("Session completed")

    async def _post_question(
        self,
        *,
        service: InterviewService,
        session: InterviewSession,
        question: Question,
        main_client: TelegramClient,
        chat_telegram_id: int,
    ) -> None:
        await main_client.send_message(entity=chat_telegram_id, message=question.text)
        service.log_event(session, EventType.QUESTION_SENT, payload=question.text)

    async def _handle_question_flow(
        self,
        *,
        service: InterviewService,
        session: InterviewSession,
        question: Question,
        bot_clients: Dict[int, TelegramClient],
        real_user_id: int,
        chat_telegram_id: int,
        timing: TimingConfig,
        send_typing: Callable[[TelegramClient, int, int], None],
        reminders: list | None = None,
    ) -> None:
        timeout_seconds = random.randint(*timing.question_timeout_range)
        bot_delay_seconds = random.randint(*timing.bot_delay_range)
        typing_seconds = random.randint(*timing.typing_range)

        event = asyncio.Event()

        async def wait_for_user_answer() -> None:
            try:
                await asyncio.wait_for(event.wait(), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                logger.info("User did not answer within %s seconds", timeout_seconds)

        async def schedule_bot_answers() -> None:
            await asyncio.sleep(bot_delay_seconds)
            for answer in question.bot_answers:
                client = bot_clients.get(answer.account_id)
                if not client:
                    continue
                send_typing(client, chat_telegram_id, typing_seconds)
                await asyncio.sleep(typing_seconds)
                await client.send_message(entity=chat_telegram_id, message=answer.answer_text)
                service.log_event(
                    session,
                    EventType.BOT_ANSWER_SENT,
                    payload=f"Bot {answer.account_id}: {answer.answer_text}",
                )

            try:
                await asyncio.wait_for(event.wait(), timeout=timing.reminder_after_bot_answer)
            except asyncio.TimeoutError:
                reminder = service.pick_reminder(reminders=reminders or [])
                if reminder:
                    client = bot_clients.get(reminder.account_id)
                    if client:
                        await client.send_message(
                            entity=chat_telegram_id,
                            message=reminder.text,
                            parse_mode="html",
                        )
                        service.log_event(
                            session,
                            EventType.REMINDER_SENT,
                            payload=f"Reminder from {reminder.account_id}: {reminder.text}",
                        )

        await asyncio.gather(wait_for_user_answer(), schedule_bot_answers())

    def schedule_at(self, dt, func, **kwargs):  # pragma: no cover - helper
        self.scheduler.add_job(func, DateTrigger(run_date=dt), kwargs=kwargs)
