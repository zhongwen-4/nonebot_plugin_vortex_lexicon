import asyncio
import re

from nonebot.adapters import Bot, Event
from nonebot.exception import MatcherException
from nonebot.log import logger
from nonebot.matcher import Matcher
from nonebot.typing import T_State
from nonebot_plugin_orm import async_scoped_session

from .lexicon_service import LexiconService
from .permission_policy import can_use_entry
from .scope import resolve_scope_group_id
from .template_engine_parts import (
    DEFAULT_AWAIT_PROMPT,
    build_await_state,
    clear_await_state,
    event_to_text,
    extract_await_templates,
    match_and_render,
    next_await_step,
    render_await_variables,
    render_segment_field_template,
    run_api_action,
    save_await_state,
    strip_await_templates,
)
from .template_engine_parts.time_template import split_time_actions

_EVENT_RULE_RE = re.compile(r"\[\s*event\.", re.IGNORECASE)


async def send_rendered_chunks(
    matcher: type[Matcher],
    event: Event,
    text: str,
    *,
    finish_last: bool,
) -> None:
    """按时间模板拆分并发送文本片段。
    Args:
        matcher: 当前处理事件的 matcher
        event: 当前事件对象
        text: 待发送文本
        finish_last: 是否在最后一段使用 finish
    用法示例:
    ```python
    await send_rendered_chunks(matcher, event, "前[时间.休眠.1]后", finish_last=True)
    ```
    """
    chunks = split_time_actions(text)
    if not chunks:
        return

    rendered_chunks: list[tuple[float, str]] = []
    for delay, chunk in chunks:
        rendered_chunk = render_segment_field_template(event, chunk)
        if rendered_chunk:
            rendered_chunks.append((delay, rendered_chunk))

    if not rendered_chunks:
        return

    for idx, (delay, rendered_chunk) in enumerate(rendered_chunks):
        if delay > 0:
            await asyncio.sleep(delay)

        if finish_last and idx == len(rendered_chunks) - 1:
            await matcher.finish(rendered_chunk)
        else:
            await matcher.send(rendered_chunk)


def is_self_message(bot: Bot, event: Event) -> bool:
    """判断当前事件是否为机器人自身发送的消息。
    Args:
        bot: 当前 Bot 对象
        event: 当前事件对象
    用法示例:
    ```python
    if is_self_message(bot, event):
        return
    ```
    """
    try:
        user_id = event.get_user_id()
    except Exception:
        user_id = ""
    if user_id and str(user_id) == str(bot.self_id):
        return True

    data = getattr(event, "data", None)
    sender_id = getattr(data, "sender_id", None) if data is not None else None
    return sender_id is not None and str(sender_id) == str(bot.self_id)


async def render_or_wait(
    matcher: type[Matcher],
    bot: Bot,
    event: Event,
    state: dict[str, object],
    text: str,
    variables: dict[str, str] | None = None,
    *,
    allow_await: bool = True,
) -> None:
    """执行 answer 渲染，支持 await 流程暂停与继续。
    Args:
        matcher: 当前处理事件的 matcher
        bot: 当前 Bot 对象
        event: 当前事件对象
        state: matcher 状态字典
        text: 待渲染文本
        variables: 模板变量
        allow_await: 是否启用 await 模板
    用法示例:
    ```python
    await render_or_wait(matcher, bot, event, state, "文本[await.10.msg][msg]")
    ```
    """
    current_variables = dict(variables or {})

    if not allow_await:
        rendered_text = render_await_variables(strip_await_templates(text), current_variables)
        remaining_text = await run_api_action(bot, event, rendered_text)
        final_text = render_await_variables(strip_await_templates(remaining_text), current_variables)
        await send_rendered_chunks(matcher, event, final_text, finish_last=True)
        return

    rendered_text = render_await_variables(text, current_variables)
    remaining_text = await run_api_action(bot, event, rendered_text)
    await_step = next_await_step(remaining_text, current_variables)
    logger.debug(
        f"词库 await 渲染阶段: rendered_text={rendered_text!r}, remaining_text={remaining_text!r}, has_next={await_step is not None}"
    )

    if await_step is None:
        final_text = render_await_variables(remaining_text, current_variables)
        logger.debug(f"词库 await 最终输出: final_text={final_text!r}")
        await send_rendered_chunks(matcher, event, final_text, finish_last=True)
        return

    if await_step.prefix:
        await send_rendered_chunks(matcher, event, await_step.prefix, finish_last=False)

    save_await_state(
        state,
        build_await_state(
            await_step.remaining,
            await_step.variable,
            await_step.timeout,
            current_variables,
        ),
    )
    logger.debug(
        f"词库 await 等待输入: variable={await_step.variable}, timeout={await_step.timeout}, remaining={await_step.remaining!r}"
    )
    await matcher.reject(DEFAULT_AWAIT_PROMPT)


def is_event_rule(question: str) -> bool:
    """判断 question 是否包含 event 规则模板。
    Args:
        question: question 模板
    用法示例:
    ```python
    ok = is_event_rule("[event.group_mute]")
    ```
    """
    return _EVENT_RULE_RE.search(question) is not None


async def handle_non_message_event(
    matcher: type[Matcher],
    bot: Bot,
    event: Event,
    session: async_scoped_session,
    state: T_State,
) -> None:
    """处理 notice/request 类型事件词条匹配。
    Args:
        matcher: 当前处理事件的 matcher
        bot: 当前 Bot 对象
        event: 当前事件对象
        session: ORM 会话
        state: matcher 状态字典
    用法示例:
    ```python
    await handle_non_message_event(matcher, bot, event, session, state)
    ```
    """
    group_id = resolve_scope_group_id(event)
    service = LexiconService(session)
    entries = await service.list_for_message(group_id)
    text = event_to_text(event).strip()

    for entry in entries:
        if not is_event_rule(entry.question):
            continue
        if not can_use_entry(event, entry.permission, entry.allow_users):
            continue

        await_prefix = extract_await_templates(entry.question)
        question_template = strip_await_templates(entry.question) if await_prefix else entry.question
        reply = match_and_render(question_template, entry.answer, text, event)
        if reply is None:
            continue

        try:
            merged_text = f"{await_prefix}{reply}" if await_prefix else reply
            await render_or_wait(matcher, bot, event, state, merged_text, allow_await=False)
        except MatcherException:
            raise
        except Exception as e:
            clear_await_state(state)
            await matcher.finish(f"API调用失败: {e}")
        return
