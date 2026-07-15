# c:/Stock_Price_Forecast/backend/db.py
"""
PostgreSQL永続化レイヤー（REQUIREMENTS_v2.md 5.5参照）。

現状main.pyのインメモリ辞書（_CACHE等）はプロセス再起動のたびに消えてしまうため、
スコア・チャート・ニュース・開示・バックテスト結果をDBに保存し、
再起動をまたいで保持できるようにする。
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# DATABASE_URL未設定でも `import db` 自体は失敗させない（DBを使わないテストの
# importを壊さないため）。実際に接続が必要になった時点で初めて例外を出す。
_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        url = os.getenv("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL が設定されていません（.env.example参照）")
        _engine = create_async_engine(url, pool_pre_ping=True)
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPIの`Depends(get_session)`で使うセッション依存性。"""
    async with _get_session_factory()() as session:
        yield session


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """リクエストコンテキスト外（自律クローラー等のバックグラウンドタスク）から使うためのヘルパー。"""
    async with _get_session_factory()() as session:
        yield session
