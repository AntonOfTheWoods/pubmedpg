from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from pubmedpg.core.config import settings

# an Engine, which the Session will use for connection
# resources
sync_engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)

# a sessionmaker(), also in the same scope as the engine
sync_session = sessionmaker(sync_engine)

async_engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI_ASYNC,
    pool_pre_ping=True,
    pool_size=settings.SQLALCHEMY_POOL_SIZE,
    max_overflow=settings.SQLALCHEMY_POOL_MAX_OVERFLOW,
    # echo=True,
)
async_session: sessionmaker = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_session() -> AsyncSession:
    return sessionmaker(
        bind=create_async_engine(
            settings.SQLALCHEMY_DATABASE_URI_ASYNC,
            pool_pre_ping=True,
            pool_size=settings.SQLALCHEMY_POOL_SIZE,
            max_overflow=settings.SQLALCHEMY_POOL_MAX_OVERFLOW,
            # echo=True,
        ),
        class_=AsyncSession,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )()
