from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from contabil.platform.settings import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_admin_engine() -> Engine:
    settings = get_settings()
    return create_engine(settings.database_admin_url or settings.database_url, pool_pre_ping=True)


def session_factory(admin: bool = False) -> sessionmaker:
    engine = get_admin_engine() if admin else get_engine()
    return sessionmaker(bind=engine, expire_on_commit=False)
