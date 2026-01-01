from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Account,
    AccountRole,
    BotAnswer,
    Chat,
    EventLog,
    EventType,
    InterviewSession,
    InterviewStatus,
    Question,
    ReminderScenario,
)

logger = logging.getLogger(__name__)


@dataclass
class InterviewContext:
    session: InterviewSession
    chat: Chat
    main_account: Account
    bot_accounts: list[Account]
    real_user: Optional[Account]
    questions: list[Question]


class InterviewService:
    def __init__(self, db: Session):
        self.db = db

    def list_chats(self) -> list[Chat]:
        return self.db.scalars(select(Chat).where(Chat.is_active.is_(True))).all()

    def add_chat(self, chat_id: int, title: str | None = None) -> Chat:
        chat = self.db.scalars(select(Chat).where(Chat.telegram_chat_id == chat_id)).first()
        if chat:
            if title:
                chat.title = title
            self.db.commit()
            return chat
        chat = Chat(telegram_chat_id=chat_id, title=title)
        self.db.add(chat)
        self.db.commit()
        self.db.refresh(chat)
        return chat

    def add_account(self, *, phone: str | None, session_path: str, role: AccountRole, title: str | None = None) -> Account:
        account = self.db.scalars(select(Account).where(Account.session_path == session_path)).first()
        if account:
            account.phone_number = phone or account.phone_number
            account.role = role
            account.title = title or account.title
            self.db.commit()
            return account
        account = Account(phone_number=phone, session_path=session_path, role=role, title=title)
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return account

    def list_accounts(self, role: Optional[AccountRole] = None) -> list[Account]:
        stmt = select(Account)
        if role:
            stmt = stmt.where(Account.role == role)
        return self.db.scalars(stmt).all()

    def ensure_session(self, chat: Chat) -> InterviewSession:
        session = self.db.scalars(
            select(InterviewSession)
            .where(InterviewSession.chat_id == chat.id)
            .order_by(InterviewSession.id.desc())
        ).first()
        if session and session.status == InterviewStatus.RUNNING:
            return session
        session = InterviewSession(chat_id=chat.id, status=InterviewStatus.IDLE)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def start_session(self, session: InterviewSession) -> InterviewSession:
        session.status = InterviewStatus.RUNNING
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        self.log_event(session, EventType.SESSION_STARTED, payload="Session started")
        return session

    def complete_session(self, session: InterviewSession) -> InterviewSession:
        session.status = InterviewStatus.COMPLETED
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        self.log_event(session, EventType.SESSION_COMPLETED, payload="Session completed")
        return session

    def next_question(self, session: InterviewSession, questions: Iterable[Question]) -> Optional[Question]:
        questions_sorted = sorted([q for q in questions if q.is_active], key=lambda q: q.order)
        if session.current_question_index >= len(questions_sorted):
            return None
        question = questions_sorted[session.current_question_index]
        session.current_question_index += 1
        self.db.commit()
        return question

    def pick_reminder(self, reminders: Iterable[ReminderScenario]) -> Optional[ReminderScenario]:
        pool = []
        for reminder in reminders:
            if reminder.is_active:
                pool.extend([reminder] * max(reminder.weight, 1))
        if not pool:
            return None
        return random.choice(pool)

    def log_event(self, session: InterviewSession, event_type: EventType, payload: str) -> EventLog:
        event = EventLog(session_id=session.id, event_type=event_type, payload=payload)
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event
