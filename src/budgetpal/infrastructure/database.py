from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


class DatabaseConfig:
    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            # Use project directory for development
            project_root = Path(__file__).parent.parent.parent.parent
            db_path = project_root / "budget.db"

        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_url = f"sqlite:///{db_path}"
        self.async_db_url = f"sqlite+aiosqlite:///{db_path}"


class Database:
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.engine = create_engine(
            self.config.db_url,
            connect_args={"check_same_thread": False},
            echo=False,
        )
        self.async_engine = create_async_engine(
            self.config.async_db_url,
            echo=False,
        )
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )
        self.AsyncSessionLocal = async_sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.async_engine,
            class_=AsyncSession,
        )

    def create_tables(self) -> None:
        Base.metadata.create_all(bind=self.engine)

    async def create_tables_async(self) -> None:
        async with self.async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    def get_session(self) -> Session:
        return self.SessionLocal()

    @asynccontextmanager
    async def get_async_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.AsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()