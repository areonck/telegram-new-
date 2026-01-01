from __future__ import annotations

import datetime as dt
import enum
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class AccountRole(str, enum.Enum):
    ADMIN = "admin"  # The controlling admin bot account (for completeness)
    MAIN = "main"  # The account that posts questions
    BOT = "bot"  # Managed accounts that post answers
    REAL = "real"  # The detected real user


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, unique=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[AccountRole] = mapped_column(Enum(AccountRole), nullable=False, default=AccountRole.BOT)
    session_path: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    bot_answers: Mapped[list["BotAnswer"]] = relationship("BotAnswer", back_populates="account")
    reminder_scenarios: Mapped[list["ReminderScenario"]] = relationship(
        "ReminderScenario", back_populates="account"
    )


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_chat_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    interviews: Mapped[list["InterviewSession"]] = relationship("InterviewSession", back_populates="chat")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    bot_answers: Mapped[list["BotAnswer"]] = relationship("BotAnswer", back_populates="question")


class BotAnswer(Base):
    __tablename__ = "bot_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    delay_min_seconds: Mapped[int] = mapped_column(Integer, default=60)
    delay_max_seconds: Mapped[int] = mapped_column(Integer, default=240)
    typing_min_seconds: Mapped[int] = mapped_column(Integer, default=10)
    typing_max_seconds: Mapped[int] = mapped_column(Integer, default=16)

    question: Mapped[Question] = relationship("Question", back_populates="bot_answers")
    account: Mapped[Account] = relationship("Account", back_populates="bot_answers")


class ReminderScenario(Base):
    __tablename__ = "reminder_scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    weight: Mapped[int] = mapped_column(Integer, default=1)

    account: Mapped[Account] = relationship("Account", back_populates="reminder_scenarios")


class InterviewStatus(str, enum.Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ABORTED = "aborted"


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id"), nullable=False)
    status: Mapped[InterviewStatus] = mapped_column(Enum(InterviewStatus), default=InterviewStatus.IDLE)
    started_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime, nullable=True)
    current_question_index: Mapped[int] = mapped_column(Integer, default=0)

    chat: Mapped[Chat] = relationship("Chat", back_populates="interviews")
    events: Mapped[list["EventLog"]] = relationship("EventLog", back_populates="session")


class EventType(str, enum.Enum):
    QUESTION_SENT = "question_sent"
    BOT_ANSWER_SENT = "bot_answer_sent"
    USER_ANSWER_RECEIVED = "user_answer_received"
    REMINDER_SENT = "reminder_sent"
    SESSION_STARTED = "session_started"
    SESSION_COMPLETED = "session_completed"
    SESSION_ABORTED = "session_aborted"
    WARNING = "warning"
    ERROR = "error"


class EventLog(Base):
    __tablename__ = "event_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("interview_sessions.id"), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    event_type: Mapped[EventType] = mapped_column(Enum(EventType), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)

    session: Mapped[InterviewSession] = relationship("InterviewSession", back_populates="events")


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)
