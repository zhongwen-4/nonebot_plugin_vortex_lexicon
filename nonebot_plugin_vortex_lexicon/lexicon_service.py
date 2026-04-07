from sqlalchemy import case, or_, select

from nonebot_plugin_orm import async_scoped_session

from .models import Lexicon

GLOBAL_GROUP_ID = 0


class LexiconService:
    def __init__(self, session: async_scoped_session):
        """初始化词库服务。
        Args:
            session: 数据库会话对象
        用法：
        ```python
        service = LexiconService(session)
        ```
        """
        self.session = session

    async def get_entry(self, group_id: int, question: str) -> Lexicon | None:
        """按群号和问题获取单条词条。
        Args:
            group_id: 词条作用域群号
            question: 词条问题文本
        用法：
        ```python
        entry = await service.get_entry(123456, "你好")
        ```
        """
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
        """新增或覆盖词条。
        Args:
            group_id: 词条作用域群号
            question: 词条问题文本
            answer: 词条答案文本
            permission: 权限标识字符串
            allow_users: 白名单用户 ID 字符串
        用法：
        ```python
        await service.upsert_entry(123456, "你好", "世界", permission="all")
        ```
        """
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
        """更新指定词条的答案。
        Args:
            group_id: 词条作用域群号
            question: 词条问题文本
            answer: 词条答案文本
        用法：
        ```python
        await service.update_entry(123456, "你好", "新的回答")
        ```
        """
        entry = await self.get_entry(group_id, question)
        if entry is None:
            return False

        entry.answer = answer
        await self.session.commit()
        return True

    async def delete_entry(self, group_id: int, question: str) -> bool:
        """删除指定词条。
        Args:
            group_id: 词条作用域群号
            question: 词条问题文本
        用法：
        ```python
        await service.delete_entry(123456, "你好")
        ```
        """
        entry = await self.get_entry(group_id, question)
        if entry is None:
            return False

        await self.session.delete(entry)
        await self.session.commit()
        return True

    async def list_for_message(self, group_id: int) -> list[Lexicon]:
        """按消息作用域列出可参与匹配的词条。
        Args:
            group_id: 词条作用域群号
        用法：
        ```python
        entries = await service.list_for_message(123456)
        ```
        """
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
        """按群号和关键词查询词条。
        Args:
            group_id: 词条作用域群号
            keyword: 查询关键词
        用法：
        ```python
        entries = await service.search_entries(123456, "你好")
        ```
        """
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
