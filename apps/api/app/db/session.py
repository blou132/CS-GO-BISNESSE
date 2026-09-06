from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def build_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            **({"poolclass": StaticPool} if ":memory:" in url else {}),
        )

        @event.listens_for(engine, "connect")
        def foreign_keys(connection: object, _: object) -> None:
            from sqlite3 import Connection

            if isinstance(connection, Connection):
                connection.execute("PRAGMA foreign_keys=ON")

        return engine
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=5,
        max_overflow=5,
        connect_args={"connect_timeout": 5, "application_name": "cs2-arbitrage-hub"},
    )


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)
