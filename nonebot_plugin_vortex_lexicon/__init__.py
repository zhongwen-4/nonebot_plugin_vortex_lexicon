import asyncio

from nonebot import get_plugin_config, on_message, require
from nonebot.adapters import Bot, Event

require("nonebot_plugin_alconna")
require("nonebot_plugin_orm")

from nonebot_plugin_alconna import Alconna, Args, Match, Subcommand, on_alconna  # noqa: E402
from nonebot_plugin_orm import async_scoped_session  # noqa: E402

from .config import Config  # noqa: E402
from .lexicon_service import GLOBAL_GROUP_ID, LexiconService  # noqa: E402
from .permission_policy import can_use_entry, normalize_allow_users, normalize_permission  # noqa: E402
from .query_output import normalize_threshold, send_query_result  # noqa: E402
from .scope import is_group_message, resolve_scope_group_id  # noqa: E402
from .template_engine_parts import match_and_render, render_segment_field_template, run_api_action  # noqa: E402
from .template_engine_parts.time_template import split_time_actions  # noqa: E402

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
):
    text = event.get_plaintext().strip()
    if not text or text.startswith("词库"):
        return

    group_id = resolve_scope_group_id(event)
    service = LexiconService(session)
    entries = await service.list_for_message(group_id)

    for entry in entries:
        if not can_use_entry(event, entry.permission, entry.allow_users):
            continue

        reply = match_and_render(entry.question, entry.answer, text, event)
        if reply is None:
            continue

        try:
            remaining_text = await run_api_action(bot, event, reply)
            chunks = split_time_actions(remaining_text)
        except Exception as e:
            await lexion_matcher.finish(f"API调用失败: {e}")

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

            if idx == len(rendered_chunks) - 1:
                await lexion_matcher.finish(rendered_chunk)
            else:
                await lexion_matcher.send(rendered_chunk)
        return
