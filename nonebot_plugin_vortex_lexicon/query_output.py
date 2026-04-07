from nonebot.adapters import Bot, Event
from nonebot.adapters.milky import Message, MessageSegment

from .models import Lexicon

def normalize_threshold(value: int) -> int:
    """规范化查询结果直发阈值。
    Args:
        value: 待处理数值
    用法：
    ```python
    threshold = normalize_threshold(5)
    ```
    """
    if value <= 0:
        return 1
    return value


def build_query_lines(entries: list[Lexicon]) -> list[str]:
    """把词条列表格式化为文本行。
    Args:
        entries: 词条列表
    用法：
    ```python
    lines = build_query_lines(entries)
    ```
    """
    lines: list[str] = []
    for index, entry in enumerate(entries, start=1):
        lines.append(f"{index}. Q: {entry.question}\nA: {entry.answer}")
    return lines


async def send_query_result(
    bot: Bot,
    event: Event,
    entries: list[Lexicon],
    threshold: int,
) -> None:
    """按阈值发送查询结果。
    Args:
        bot: 当前 Bot 实例
        event: 当前事件对象
        entries: 词条列表
        threshold: 查询结果直发阈值
    用法：
    ```python
    await send_query_result(bot, event, entries, 10)
    ```
    """
    lines = build_query_lines(entries)
    if len(lines) <= threshold:
        await bot.send(event, "\n\n".join(lines))
        return

    try:
        sender_id = int(bot.self_id)
    except ValueError:
        try:
            sender_id = int(event.get_user_id())
        except ValueError:
            sender_id = 0

    nodes = [
        MessageSegment.node(
            user_id=sender_id,
            name="词库查询",
            segments=Message(line),
        )
        for line in lines
    ]
    try:
        await bot.send(event, MessageSegment.forward(nodes))
    except Exception:
        await bot.send(event, "\n\n".join(lines))
