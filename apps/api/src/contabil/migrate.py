from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config


def main() -> None:
    root = Path(os.environ.get("APP_HOME", "/app"))
    config = Config(str(root / "alembic.ini"))
    command.upgrade(config, "head")
    from contabil.platform.settings import get_settings

    settings = get_settings()
    if settings.object_storage_create_buckets:
        from contabil.platform.storage import ensure_configured_buckets

        ensure_configured_buckets()
    if settings.seed_demo:
        from contabil.seed.run import seed

        seed()


if __name__ == "__main__":
    main()
