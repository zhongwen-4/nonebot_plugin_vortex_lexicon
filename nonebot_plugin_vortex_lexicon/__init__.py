from nonebot import get_plugin_config, on_message, on_notice, on_request, require
from nonebot.adapters import Bot, Event
from nonebot.exception import MatcherException
from nonebot.log import logger
from nonebot.typing import T_State

require("nonebot_plugin_alconna")
require("nonebot_plugin_orm")

from nonebot_plugin_alconna import Alconna, Args, Match, Subcommand, on_alconna  # noqa: E402
from nonebot_plugin_orm import async_scoped_session  # noqa: E402

from .config import Config  # noqa: E402
from .lexicon_service import GLOBAL_GROUP_ID, LexiconService  # noqa: E402
from .permission_policy import can_use_entry, normalize_allow_users, normalize_permission  # noqa: E402
from .query_output import normalize_threshold, send_query_result  # noqa: E402
from .runtime_helpers import handle_non_message_event, is_self_message, render_or_wait  # noqa: E402
from .scope import is_group_message, resolve_scope_group_id  # noqa: E402
from .template_engine_parts import (  # noqa: E402
    clear_await_state,
    event_to_text,
    extract_await_templates,
    is_await_expired,
    load_await_state,
    match_and_render,
    strip_await_templates,
)

plugin_config = get_plugin_config(Config)

alc = Alconna(
    "词库",
    Subcommand(
        "分群",
        Subcommand("添加", Args["question", str]["answer", str]["permission?", str]["allow_users?", str]),
        Subcommand("修改", Args["question", str]),
        Subcommand("删除", Args["question", str]),
        Subcommand("查询", Args["keyword?", str]),
    ),
    Subcommand(
        "全局",
        Subcommand("添加", Args["question", str]["answer", str]["permission?", str]["allow_users?", str]),
        Subcommand("修改", Args["question", str]),
        Subcommand("删除", Args["question", str]),
        Subcommand("查询", Args["keyword?", str]),
    ),
)

lexion = on_alconna(alc)
lexion_matcher = on_message(priority=20, block=False)
lexion_notice_matcher = on_notice(priority=20, block=False)
lexion_request_matcher = on_request(priority=20, block=False)


@lexion.assign("分群.添加")
async def group_add_handle(
    event: Event,
    question: Match[str],
    answer: Match[str],
    permission: Match[str],
    allow_users: Match[str],
    session: async_scoped_session,
):
    if not question.available or not answer.available:
        await lexion.finish("用法: 词库 分群 添加 <问题> <答案> [权限] [成员白名单]")
    if not is_group_message(event):
        await lexion.finish("分群词库只能在群聊使用")

    q = question.result.strip()
    a = answer.result.strip()
    if not q or not a:
        await lexion.finish("问题和答案都不能为空")

    permission_value = normalize_permission(permission.result if permission.available else "")
    allow_users_value = normalize_allow_users(allow_users.result if allow_users.available else "")

    group_id = resolve_scope_group_id(event)
    service = LexiconService(session)
    existed = await service.upsert_entry(
        group_id,
        q,
        a,
        permission=permission_value,
        allow_users=allow_users_value,
    )
    if not existed:
        await lexion.finish(f"分群词条添加成功: {q}")

    await lexion.finish(f"分群词条已存在，已覆盖: {q}")


@lexion.assign("分群.修改")
async def group_update_handle(
    event: Event,
    question: Match[str],
    session: async_scoped_session,
):
    if not question.available:
        await lexion.finish("用法: 词库 分群 修改 <问题>")
    if not is_group_message(event):
        await lexion.finish("分群词库只能在群聊使用")

    q = question.result.strip()
    if not q:
        await lexion.finish("问题不能为空")

    group_id = resolve_scope_group_id(event)
    service = LexiconService(session)
    entry = await service.get_entry(group_id, q)
    if entry is None:
        await lexion.finish(f"词条不存在: {q}")

    resp = await lexion.prompt(f"当前答案: {entry.answer}\n请输入新答案:", timeout=60)
    if resp is None:
        await lexion.finish("修改超时，已取消")

    new_answer = str(resp).strip()
    if not new_answer:
        await lexion.finish("新答案不能为空")

    await service.update_entry(group_id, q, new_answer)
    await lexion.finish(f"分群词条修改成功: {q}")


@lexion.assign("分群.删除")
async def group_delete_handle(
    event: Event,
    question: Match[str],
    session: async_scoped_session,
):
    if not question.available:
        await lexion.finish("用法: 词库 分群 删除 <问题>")
    if not is_group_message(event):
        await lexion.finish("分群词库只能在群聊使用")

    q = question.result.strip()
    if not q:
        await lexion.finish("问题不能为空")

    group_id = resolve_scope_group_id(event)
    service = LexiconService(session)
    deleted = await service.delete_entry(group_id, q)
    if not deleted:
        await lexion.finish(f"词条不存在: {q}")

    await lexion.finish(f"分群词条删除成功: {q}")


@lexion.assign("全局.添加")
async def global_add_handle(
    question: Match[str],
    answer: Match[str],
    permission: Match[str],
    allow_users: Match[str],
    session: async_scoped_session,
):
    if not question.available or not answer.available:
        await lexion.finish("用法: 词库 全局 添加 <问题> <答案> [权限] [成员白名单]")

    q = question.result.strip()
    a = answer.result.strip()
    if not q or not a:
        await lexion.finish("问题和答案都不能为空")

    permission_value = normalize_permission(permission.result if permission.available else "")
    allow_users_value = normalize_allow_users(allow_users.result if allow_users.available else "")

    service = LexiconService(session)
    existed = await service.upsert_entry(
        GLOBAL_GROUP_ID,
        q,
        a,
        permission=permission_value,
        allow_users=allow_users_value,
    )
    if not existed:
        await lexion.finish(f"全局词条添加成功: {q}")

    await lexion.finish(f"全局词条已存在，已覆盖: {q}")


@lexion.assign("全局.修改")
async def global_update_handle(
    question: Match[str],
    session: async_scoped_session,
):
    if not question.available:
        await lexion.finish("用法: 词库 全局 修改 <问题>")

    q = question.result.strip()
    if not q:
        await lexion.finish("问题不能为空")

    service = LexiconService(session)
    entry = await service.get_entry(GLOBAL_GROUP_ID, q)
    if entry is None:
        await lexion.finish(f"词条不存在: {q}")

    resp = await lexion.prompt(f"当前答案: {entry.answer}\n请输入新答案:", timeout=60)
    if resp is None:
        await lexion.finish("修改超时，已取消")

    new_answer = str(resp).strip()
    if not new_answer:
        await lexion.finish("新答案不能为空")

    await service.update_entry(GLOBAL_GROUP_ID, q, new_answer)
    await lexion.finish(f"全局词条修改成功: {q}")


@lexion.assign("全局.删除")
async def global_delete_handle(
    question: Match[str],
    session: async_scoped_session,
):
    if not question.available:
        await lexion.finish("用法: 词库 全局 删除 <问题>")

    q = question.result.strip()
    if not q:
        await lexion.finish("问题不能为空")

    service = LexiconService(session)
    deleted = await service.delete_entry(GLOBAL_GROUP_ID, q)
    if not deleted:
        await lexion.finish(f"词条不存在: {q}")

    await lexion.finish(f"全局词条删除成功: {q}")


@lexion.assign("分群.查询")
async def group_query_handle(
    bot: Bot,
    event: Event,
    session: async_scoped_session,
    keyword: Match[str],
):
    if not is_group_message(event):
        await lexion.finish("分群词库只能在群聊使用")

    scope_group_id = resolve_scope_group_id(event)
    service = LexiconService(session)
    entries = await service.search_entries(
        scope_group_id,
        keyword.result.strip() if keyword.available else None,
    )
    if not entries:
        await lexion.finish("分群词库暂无匹配结果")

    threshold = normalize_threshold(plugin_config.vortex_lexicon_query_threshold)
    await send_query_result(bot, event, entries, threshold)
    await lexion.finish()


@lexion.assign("全局.查询")
async def global_query_handle(
    bot: Bot,
    event: Event,
    session: async_scoped_session,
    keyword: Match[str],
):
    service = LexiconService(session)
    entries = await service.search_entries(
        GLOBAL_GROUP_ID,
        keyword.result.strip() if keyword.available else None,
    )
    if not entries:
        await lexion.finish("全局词库暂无匹配结果")

    threshold = normalize_threshold(plugin_config.vortex_lexicon_query_threshold)
    await send_query_result(bot, event, entries, threshold)
    await lexion.finish()


@lexion_matcher.handle()
async def lexion_matcher_handle(
    bot: Bot,
    event: Event,
    session: async_scoped_session,
    state: T_State,
):
    if is_self_message(bot, event):
        logger.debug("词库 matcher 忽略机器人自身消息，避免自触发循环")
        return

    pending_await = load_await_state(state)
    if pending_await is not None:
        clear_await_state(state)
        if is_await_expired(pending_await):
            await lexion_matcher.finish("等待输入已超时")

        variable = pending_await.get("variable")
        remaining_text = pending_await.get("remaining_text")
        variables = pending_await.get("variables")
        if not isinstance(variable, str) or not isinstance(remaining_text, str) or not isinstance(variables, dict):
            await lexion_matcher.finish("等待状态已失效")

        current_variables = {str(key): str(value) for key, value in variables.items()}
        input_text = event_to_text(event)
        current_variables[variable] = input_text
        logger.debug(f"词库 await 收到输入: variable={variable}, text={input_text!r}")
        try:
            await render_or_wait(lexion_matcher, bot, event, state, remaining_text, current_variables)
        except MatcherException:
            raise
        except Exception as e:
            clear_await_state(state)
            await lexion_matcher.finish(f"API调用失败: {e}")
        return

    text = event.get_plaintext().strip()
    if not text or text.startswith("词库"):
        return

    group_id = resolve_scope_group_id(event)
    service = LexiconService(session)
    entries = await service.list_for_message(group_id)

    for entry in entries:
        if not can_use_entry(event, entry.permission, entry.allow_users):
            continue

        await_prefix = extract_await_templates(entry.question)
        question_template = strip_await_templates(entry.question) if await_prefix else entry.question
        reply = match_and_render(question_template, entry.answer, text, event)
        if reply is None:
            continue

        try:
            merged_text = f"{await_prefix}{reply}" if await_prefix else reply
            await render_or_wait(lexion_matcher, bot, event, state, merged_text)
        except MatcherException:
            raise
        except Exception as e:
            clear_await_state(state)
            await lexion_matcher.finish(f"API调用失败: {e}")
        return


@lexion_notice_matcher.handle()
async def lexion_notice_matcher_handle(
    bot: Bot,
    event: Event,
    session: async_scoped_session,
    state: T_State,
):
    await handle_non_message_event(lexion_notice_matcher, bot, event, session, state)


@lexion_request_matcher.handle()
async def lexion_request_matcher_handle(
    bot: Bot,
    event: Event,
    session: async_scoped_session,
    state: T_State,
):
    await handle_non_message_event(lexion_request_matcher, bot, event, session, state)
