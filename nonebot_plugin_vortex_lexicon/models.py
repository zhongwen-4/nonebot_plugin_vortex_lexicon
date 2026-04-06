from sqlalchemy import BigInteger, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from nonebot_plugin_orm import Model


class Lexicon(Model):
    __table_args__ = (
        UniqueConstraint("group_id", "question"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(BigInteger, index=True, default=0)
    question: Mapped[str] = mapped_column(String(255), index=True)
    answer: Mapped[str] = mapped_column(String(2000))
    permission: Mapped[str] = mapped_column(
        String(32),
        default="all",
        server_default=text("'all'"),
    )
    allow_users: Mapped[str] = mapped_column(
        String(2000),
        default="",
        server_default=text("''"),
    )
