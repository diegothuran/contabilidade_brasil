from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from contabil.platform.settings import get_settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
database_admin_url = settings.database_admin_url or settings.database_url
config.set_main_option("sqlalchemy.url", database_admin_url.replace("%", "%%"))


def run_migrations_offline() -> None:
    context.configure(url=database_admin_url, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(database_admin_url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
