import asyncio
from logging.config import fileConfig

from sqlalchemy.engine import Connection

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import SQLModel

# Imported for their side effect: defining these models registers their tables
# on SQLModel.metadata, which is what autogenerate diffs against.
from api.user.models import User  # noqa: F401
from api.conversation.models import Session, Message  # noqa: F401
from api.core.config import DB_ASYNC_CONNECTION_STR

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = SQLModel.metadata

def run_migrations_offline():
   url = DB_ASYNC_CONNECTION_STR
   context.configure(
       url=url,
       target_metadata=target_metadata,
       literal_binds=True,
       dialect_opts={"paramstyle": "named"},
   )

   with context.begin_transaction():
       context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )
    with context.begin_transaction():
       context.run_migrations()


async def run_migrations_online():
   config_section = config.get_section(config.config_ini_section)
   url = DB_ASYNC_CONNECTION_STR
   config_section["sqlalchemy.url"] = url

   connectable = AsyncEngine(
       engine_from_config(
           config_section,
           prefix="sqlalchemy.",
           poolclass=pool.NullPool,
           future=True,
       )
   )

   async with connectable.connect() as connection:
       await connection.run_sync(do_run_migrations)

   await connectable.dispose()


if context.is_offline_mode():
   run_migrations_offline()
else:
   asyncio.run(run_migrations_online())
