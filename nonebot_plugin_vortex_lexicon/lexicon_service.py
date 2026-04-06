from sqlalchemy import case, or_, select

from nonebot_plugin_orm import async_scoped_session

from .models import Lexicon

GLOBAL_GROUP_ID = 0


class LexiconService:
    def __init__(self, session: async_scoped_session):
        self.session = session

    async def get_entry(self, group_id: int, question: str) -> Lexicon | None:
        return await self.session.scalar(
            select(Lexicon).where(
                Lexicon.group_id == group_id,
                Lexicon.question == question,
            )
        )

    async def upsert_entry(
        self,
        group_id: int,
        question: str,
        answer: str,
        permission: str = "all",
        allow_users: str = "",
    ) -> bool:
        entry = await self.get_entry(group_id, question)
        if entry is None:
            self.session.add(
                Lexicon(
                    group_id=group_id,
                    question=question,
                    answer=answer,
                    permission=permission,
                    allow_users=allow_users,
                )
            )
            await self.session.commit()
            return False

        entry.answer = answer
        entry.permission = permission
        entry.allow_users = allow_users
        await self.session.commit()
        return True

    async def update_entry(self, group_id: int, question: str, answer: str) -> bool:
        entry = await self.get_entry(group_id, question)
        if entry is None:
            return False

        entry.answer = answer
        await self.session.commit()
        return True

    async def delete_entry(self, group_id: int, question: str) -> bool:
        entry = await self.get_entry(group_id, question)
        if entry is None:
            return False

        await self.session.delete(entry)
        await self.session.commit()
        return True

    async def list_for_message(self, group_id: int) -> list[Lexicon]:
        if group_id == GLOBAL_GROUP_ID:
            return list(
                (
                    await self.session.scalars(
                        select(Lexicon)
                        .where(Lexicon.group_id == GLOBAL_GROUP_ID)
                        .order_by(Lexicon.id.asc())
                    )
                ).all()
            )

        local_first_order = case((Lexicon.group_id == group_id, 0), else_=1)
        return list(
            (
                await self.session.scalars(
                    select(Lexicon)
                    .where(Lexicon.group_id.in_([group_id, GLOBAL_GROUP_ID]))
                    .order_by(local_first_order.asc(), Lexicon.id.asc())
                )
            ).all()
        )

    async def search_entries(self, group_id: int, keyword: str | None = None) -> list[Lexicon]:
        stmt = select(Lexicon).where(Lexicon.group_id == group_id)
        if keyword:
            pattern = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    Lexicon.question.like(pattern),
                    Lexicon.answer.like(pattern),
                )
            )
        stmt = stmt.order_by(Lexicon.id.asc())
        return list((await self.session.scalars(stmt)).all())
