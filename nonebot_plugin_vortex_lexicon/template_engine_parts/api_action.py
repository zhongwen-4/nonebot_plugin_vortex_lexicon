import json
import re
from typing import Any

from nonebot.adapters import Bot, Event

_API_BLOCK_RE = re.compile(r"^\[(?P<spec>[^\[\]]+)\](?P<tail>.*)$", re.DOTALL)
_INT_RE = re.compile(r"^-?\d+$")
_KV_SPLIT_RE = re.compile(r"\.(?=[A-Za-z_]\w*=)")
_GET_EXPR_RE = re.compile(r"\.get\((?P<fields>[^()]*)\)\s*$")
_TRUE_VALUES = {"true", "yes", "on", "y", "是", "真", "开启"}
_FALSE_VALUES = {"false", "no", "off", "n", "否", "假", "关闭"}
_CONST_ALIASES = {
    "group_id": "group_id",
    "groupid": "group_id",
    "$group_id": "group_id",
    "{group_id}": "group_id",
    "群号": "group_id",
    "user_id": "user_id",
    "userid": "user_id",
    "$user_id": "user_id",
    "{user_id}": "user_id",
    "用户qq号": "user_id",
    "reply_user_id": "reply_user_id",
    "replyuserid": "reply_user_id",
    "$reply_user_id": "reply_user_id",
    "{reply_user_id}": "reply_user_id",
    "被回复qq号": "reply_user_id",
    "message_id": "message_id",
    "messageid": "message_id",
    "$message_id": "message_id",
    "{message_id}": "message_id",
    "消息id": "message_id",
    "reply_message_id": "reply_message_id",
    "reply_message_seq": "reply_message_id",
    "replymessageid": "reply_message_id",
    "replymessageseq": "reply_message_id",
    "$reply_message_id": "reply_message_id",
    "$reply_message_seq": "reply_message_id",
    "{reply_message_id}": "reply_message_id",
    "{reply_message_seq}": "reply_message_id",
    "被回复消息id": "reply_message_id",
}
_TRUE_VALUES.update({"true", "yes", "on", "y", "是", "对", "真", "开启", "开"})
_FALSE_VALUES.update({"false", "no", "off", "n", "否", "不", "假", "关闭", "关"})


def _coerce_value(raw: str) -> Any:
    text = raw.strip()
    if (
        len(text) >= 2
        and text[0] == text[-1]
        and text[0] in {"'", '"'}
    ):
        inner = text[1:-1].strip()
        lowered_inner = inner.lower()
        if lowered_inner in _TRUE_VALUES:
            return True
        if lowered_inner in _FALSE_VALUES:
            return False
        if lowered_inner in {"none", "null"}:
            return None
        return inner

    lowered = text.lower()
    if lowered in _TRUE_VALUES:
        return True
    if lowered in _FALSE_VALUES:
        return False
    if lowered in {"none", "null"}:
        return None
    if _INT_RE.fullmatch(text):
        return int(text)
    return text


def parse_api_action(
    answer_text: str,
) -> tuple[str, dict[str, Any], list[str], str] | None:
    matched = _API_BLOCK_RE.match(answer_text)
    if matched is None:
        return None

    spec = matched.group("spec").strip()
    if not spec:
        return None

    raw_spec = spec
    if raw_spec.startswith("api."):
        raw_spec = raw_spec[4:]

    if not raw_spec:
        return None

    get_fields: list[str] = []
    get_expr_match = _GET_EXPR_RE.search(raw_spec)
    if get_expr_match:
        raw_fields = get_expr_match.group("fields")
        get_fields = [item.strip() for item in raw_fields.split(",") if item.strip()]
        raw_spec = raw_spec[: get_expr_match.start()]

    api_name = raw_spec
    args_str = ""
    first_kv_match = _KV_SPLIT_RE.search(raw_spec)
    if first_kv_match:
        api_name = raw_spec[: first_kv_match.start()]
        args_str = raw_spec[first_kv_match.start() + 1 :]

    api_name = api_name.strip()
    if not api_name:
        return None

    if args_str:
        arg_parts = [part for part in _KV_SPLIT_RE.split(args_str) if part]
    else:
        arg_parts = []

    kwargs: dict[str, Any] = {}
    for part in arg_parts:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        if not key:
            continue
        kwargs[key] = _coerce_value(value)

    tail = matched.group("tail")
    return api_name, kwargs, get_fields, tail


async def run_api_action(bot: Bot, event: Event, answer_text: str) -> str:
    parsed = parse_api_action(answer_text)
    if parsed is None:
        return answer_text

    api_name, kwargs, get_fields, tail = parsed
    context = _extract_context_values(event)
    kwargs = _fill_context_kwargs(kwargs, context)

    if api_name == "send_group_announcement":
        result = await _run_send_group_announcement(bot, kwargs)
    else:
        result = await bot.call_api(api_name, **kwargs)
    remaining = tail.lstrip()
    if remaining:
        return remaining
    if get_fields:
        return _pick_fields_text(result, get_fields)
    return _format_api_result(result)


async def _run_send_group_announcement(bot: Bot, kwargs: dict[str, Any]) -> Any:
    group_id = kwargs.get("group_id")
    content = kwargs.get("content")
    if group_id is None or content is None:
        raise ValueError("send_group_announcement 需要 group_id 和 content")

    # 兼容 Milky 文档风格参数：image_uri 可选
    image_uri = kwargs.get("image_uri")
    if image_uri:
        if not hasattr(bot, "_call"):
            raise ValueError("当前适配器不支持底层 _call，无法使用 image_uri 参数")
        payload = {"group_id": group_id, "content": content, "image_uri": image_uri}
        return await bot._call("send_group_announcement", payload)  # type: ignore[attr-defined]

    # 兼容无图公告：Milky 高层 API 会强制 to_uri，这里改用底层调用
    binary_keys = {"url", "path", "base64", "raw"}
    if not binary_keys.intersection(kwargs):
        if not hasattr(bot, "_call"):
            # 非 Milky 适配器退回默认行为
            return await bot.call_api("send_group_announcement", **kwargs)
        payload = {"group_id": group_id, "content": content}
        return await bot._call("send_group_announcement", payload)  # type: ignore[attr-defined]

    # 保留 Milky 高层写法（url/path/base64/raw）
    return await bot.call_api("send_group_announcement", **kwargs)


def _format_api_result(result: Any) -> str:
    if result is None:
        return ""

    payload = result
    model_dump = getattr(result, "model_dump", None)
    to_dict = getattr(result, "dict", None)
    if callable(model_dump):
        payload = model_dump(mode="json")
    elif callable(to_dict):
        payload = to_dict()

    if isinstance(payload, str):
        return payload

    try:
        return json.dumps(payload, ensure_ascii=False)
    except TypeError:
        return str(payload)


def _extract_field(data: Any, field_path: str) -> Any:
    current = data
    for part in field_path.split("."):
        key = part.strip()
        if not key:
            return None
        if isinstance(current, dict):
            current = current.get(key)
            continue
        if hasattr(current, key):
            current = getattr(current, key)
            continue
        model_dump = getattr(current, "model_dump", None)
        if callable(model_dump):
            dumped = model_dump(mode="json")
            if isinstance(dumped, dict):
                current = dumped.get(key)
                continue
            return None
        to_dict = getattr(current, "dict", None)
        if callable(to_dict):
            dumped = to_dict()
            if isinstance(dumped, dict):
                current = dumped.get(key)
                continue
            return None
        return None
    return current


def _value_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)


def _pick_fields_text(result: Any, fields: list[str]) -> str:
    values = [_value_to_text(_extract_field(result, field)) for field in fields]
    return "".join(values)


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _extract_context_values(event: Event) -> dict[str, Any]:
    group_id: int | None = None
    user_id: int | None = None
    reply_user_id: int | None = None
    reply_message_id: int | None = None
    message_id: int | None = None

    data = getattr(event, "data", None)
    if data is not None:
        message_scene = getattr(data, "message_scene", None)
        if message_scene == "group":
            group_id = _to_int(getattr(data, "peer_id", None))

        data_group_id = getattr(data, "group_id", None)
        if group_id is None and data_group_id is not None:
            group_id = _to_int(data_group_id)

        sender_id = getattr(data, "sender_id", None)
        if sender_id is None:
            sender_id = getattr(data, "user_id", None)
        if sender_id is not None:
            user_id = _to_int(sender_id)

        message_seq = getattr(data, "message_seq", None)
        if message_seq is not None:
            message_id = _to_int(message_seq)

    if user_id is None:
        try:
            user_id = int(event.get_user_id())
        except (ValueError, TypeError):
            user_id = None

    event_message_id = getattr(event, "message_id", None)
    if message_id is None and event_message_id is not None:
        message_id = _to_int(event_message_id)

    reply = getattr(event, "reply", None)
    if reply is not None:
        sender = getattr(reply, "sender_id", None)
        if sender is None and isinstance(reply, dict):
            sender = reply.get("sender_id")
        if sender is not None:
            reply_user_id = _to_int(sender)

        reply_msg = getattr(reply, "message_seq", None)
        if reply_msg is None and isinstance(reply, dict):
            reply_msg = reply.get("message_seq")
        if reply_msg is not None:
            reply_message_id = _to_int(reply_msg)

    return {
        "group_id": group_id,
        "user_id": user_id,
        "reply_user_id": reply_user_id,
        "reply_message_id": reply_message_id,
        "message_id": message_id,
    }


def _resolve_const_value(raw: Any, context: dict[str, Any]) -> Any:
    if not isinstance(raw, str):
        return raw
    key = _CONST_ALIASES.get(raw.strip().lower())
    if key is None:
        return raw
    value = context.get(key)
    return value if value is not None else raw


def _is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    return isinstance(value, str) and not value.strip()


def _fill_context_kwargs(kwargs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    filled: dict[str, Any] = {k: _resolve_const_value(v, context) for k, v in kwargs.items()}

    auto_fill_map: dict[str, str] = {
        "group_id": "group_id",
        "user_id": "user_id",
        "message_id": "message_id",
        "message_seq": "message_id",
    }
    for param_key, context_key in auto_fill_map.items():
        if param_key not in filled:
            continue
        if _is_empty_value(filled[param_key]):
            context_value = context.get(context_key)
            if context_value is not None:
                filled[param_key] = context_value

    return filled
