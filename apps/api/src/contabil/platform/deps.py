from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from contabil.platform.auth import authenticate
from contabil.platform.db import session_factory
from contabil.platform.errors import DomainError
from contabil.platform.principal import Principal

_bearer = HTTPBearer(auto_error=False)


@dataclass
class Ctx:
    principal: Principal
    session: Session


def get_context(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> Iterator[Ctx]:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise DomainError(401, "Não autenticado", "Envie um token Bearer.")
    session = session_factory()()
    try:
        principal = authenticate(session, credentials.credentials)
        yield Ctx(principal=principal, session=session)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
