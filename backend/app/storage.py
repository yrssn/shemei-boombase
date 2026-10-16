from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .schemas import HistoryItem


class Base(DeclarativeBase):
    pass


class History(Base):
    __tablename__ = "history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    shortcode: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    author: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    caption: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sentiment_label: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    operator: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    written_to_doc: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)


class Storage:
    def __init__(self, database_url: str):
        kwargs: dict = {"pool_pre_ping": True, "pool_recycle": 3600}
        if database_url.startswith("sqlite"):
            kwargs = {"connect_args": {"check_same_thread": False}}
        self.engine = create_engine(database_url, **kwargs)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def init_db(self) -> None:
        Base.metadata.create_all(self.engine)

    def add(self, *, url: str, shortcode: str, author: str, caption: str, sentiment_label: str,
            operator: str, written_to_doc: bool) -> int:
        with self.session_factory() as session, session.begin():
            row = History(url=url, shortcode=shortcode, author=author, caption=caption,
                          sentiment_label=sentiment_label, operator=operator, written_to_doc=written_to_doc)
            session.add(row)
            session.flush()
            return row.id

    def list(self, limit: int = 50) -> list[HistoryItem]:
        with self.session_factory() as session:
            rows = session.scalars(select(History).order_by(History.id.desc()).limit(limit)).all()
        return [
            HistoryItem(
                id=r.id, url=r.url, shortcode=r.shortcode, author=r.author, caption=r.caption,
                sentiment_label=r.sentiment_label, operator=r.operator, written_to_doc=r.written_to_doc,
                created_at=r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            )
            for r in rows
        ]
