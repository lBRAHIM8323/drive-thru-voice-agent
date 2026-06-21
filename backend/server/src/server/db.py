"""Database engine, session dependency, and startup migration/seeding.

On startup we (1) create the target database if it's missing, (2) create any
missing tables (idempotent ``create_all`` — the "migration" the app runs on init),
and (3) seed singletons (parser config) plus optional bootstrap data (a default
branch and an env-provided admin user).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator

from sqlalchemy import text
from sqlalchemy.engine.url import make_url
from sqlmodel import Session, SQLModel, create_engine, select

from .models import Branch, ParserConfigRecord, User
from .security import hash_password
from .settings import get_settings

logger = logging.getLogger("server.db")

_settings = get_settings()


def _ensure_sqlite_dir(url: str) -> None:
    if url.startswith("sqlite:///"):
        parent = os.path.dirname(url.removeprefix("sqlite:///"))
        if parent:
            os.makedirs(parent, exist_ok=True)


def _ensure_database_exists(url: str) -> None:
    """For Postgres, CREATE DATABASE if the target db doesn't exist yet."""
    if not url.startswith("postgresql"):
        return
    target = make_url(url)
    db_name = target.database
    admin_url = target.set(database="postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("select 1 from pg_database where datname = :n"), {"n": db_name}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                logger.info("created database %s", db_name)
    finally:
        admin_engine.dispose()


_ensure_sqlite_dir(_settings.database_url)

engine = create_engine(
    _settings.database_url,
    connect_args={"check_same_thread": False}
    if _settings.database_url.startswith("sqlite")
    else {},
)


def _migrate(session: Session) -> None:
    """Idempotent schema migrations for existing databases (Postgres).
    ``SQLModel.metadata.create_all`` only creates *new* tables; it does not
    add columns to existing tables, so we run minimal ALTER TABLE statements
    here for each release that adds a column.
    """
    if not _settings.is_postgres:
        return
    import sqlalchemy as sa

    conn = session.connection()
    inspector = sa.inspect(conn)

    # v0.2.0 — add ``branch_id`` to the ``users`` table.
    cols = {c["name"] for c in inspector.get_columns("users")}
    if "branch_id" not in cols:
        conn.execute(
            sa.text(
                "ALTER TABLE users ADD COLUMN branch_id UUID REFERENCES branches(id)"
            )
        )
        logger.info("migrated users: added branch_id column")

    # v0.3.0 — dietary info, favourites, serving size and limited-time offers
    # on ``menu_items``.
    menu_cols = {c["name"] for c in inspector.get_columns("menu_items")}
    menu_additions = {
        "dietary": "VARCHAR",
        "tags": "JSON DEFAULT '[]'::json",
        "serves": "INTEGER",
        "is_favorite": "BOOLEAN NOT NULL DEFAULT FALSE",
        "offer_price": "NUMERIC(12, 2)",
        "offer_until": "TIMESTAMPTZ",
    }
    for name, ddl in menu_additions.items():
        if name not in menu_cols:
            conn.execute(sa.text(f"ALTER TABLE menu_items ADD COLUMN {name} {ddl}"))
            logger.info("migrated menu_items: added %s column", name)


def _seed(session: Session) -> None:
    # Singleton parser config.
    if session.exec(select(ParserConfigRecord)).first() is None:
        session.add(ParserConfigRecord())

    # Default branch so menu/sessions/orders always have one to reference.
    if session.exec(select(Branch)).first() is None:
        session.add(Branch(name="Main", slug="main"))

    # Optional bootstrap admin from env.
    if _settings.admin_username and _settings.admin_password:
        existing = session.exec(
            select(User).where(User.username == _settings.admin_username)
        ).first()
        if existing is None:
            session.add(
                User(
                    username=_settings.admin_username,
                    hashed_password=hash_password(_settings.admin_password),
                    role="admin",
                )
            )
    session.commit()


def init_db() -> None:
    """Run on FastAPI startup: create db + tables if missing, then seed."""
    from . import models  # noqa: F401  (register tables on SQLModel.metadata)

    _ensure_database_exists(_settings.database_url)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        _migrate(session)
        _seed(session)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
