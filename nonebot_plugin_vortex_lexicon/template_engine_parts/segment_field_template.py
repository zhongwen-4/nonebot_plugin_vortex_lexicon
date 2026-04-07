import re
from typing import Any

from nonebot.adapters import Event

_FIELD_EXPR_RE = re.compile(r"\[([^\[\]\s]+)\]")
_SEGMENT_ALIASES: dict[str, str] = {
    "mention": "mention",
    "at": "mention",
    "image": "image",
    "img": "image",
    "face": "face",
    "emoji": "face",
    "reply": "reply",
    "text": "text",
    "file": "file",
}
_JOINER = " "


def _to_plain_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json")
        if isinstance(dumped, dict):
            return dumped

    to_dict = getattr(value, "dict", None)
    if callable(to_dict):
        dumped = to_dict()
        if isinstance(dumped, dict):
            return dumped

    return None


def _normalize_segments_from_message(message: Any) -> list[dict[str, Any]]:
    raw_segments = getattr(message, "segments", None)
    if not isinstance(raw_segments, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in raw_segments:
        seg = _to_plain_dict(item)
        if seg is None:
            continue

        seg_type = seg.get("type")
        if not isinstance(seg_type, str):
            continue

        seg_data = _to_plain_dict(seg.get("data")) or {}
        normalized.append({"type": seg_type, "data": seg_data})
    return normalized


def _normalize_segments(event: Event) -> list[dict[str, Any]]:
    segments = _normalize_segments_from_message(getattr(event, "data", None))
    reply_segments = _normalize_segments_from_message(getattr(event, "reply", None))
    return [*segments, *reply_segments]


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

        dumped = _to_plain_dict(current)
        if dumped is None:
            return None
        current = dumped.get(key)
    return current


def _value_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return str(value)


def _collect_field_values(segments: list[dict[str, Any]], field_path: str) -> list[str]:
    values: list[str] = []
    for segment in segments:
        value = _extract_field(segment.get("data", {}), field_path)
        text = _value_to_text(value)
        if text:
            values.append(text)
    return values


def _missing_field_message(seg_type: str, field_path: str, expr: str) -> str:
    return f"{seg_type} 中没有 {field_path}\n原始内容：{expr}"


def _missing_value_target_message(seg_type: str, expr: str) -> str:
    return f"{seg_type} 必须指定取值内容\n原始内容：{expr}"


def parse_segment_field_expression(expr: str) -> tuple[str, str] | None:
    """解析消息段字段模板。
    Args:
        expr: 表达式字符串
    用法：
    ```python
    parsed = parse_segment_field_expression("at.user_id")
    ```
    """
    parts = [part.strip() for part in expr.split(".") if part.strip()]
    if len(parts) < 1:
        return None

    seg_type = _SEGMENT_ALIASES.get(parts[0].lower())
    if seg_type is None:
        return None

    field_parts = parts[1:]
    field_path = ".".join(field_parts) if field_parts else ""
    return seg_type, field_path


def eval_segment_field_expression(event: Event, expr: str) -> str | None:
    """读取事件中的消息段字段值。
    Args:
        event: 当前事件对象
        expr: 表达式字符串
    用法：
    ```python
    value = eval_segment_field_expression(event, "image.file_id")
    ```
    """
    parsed = parse_segment_field_expression(expr)
    if parsed is None:
        return None

    seg_type, field_path = parsed
    if not field_path:
        return _missing_value_target_message(seg_type, expr)

    segments = _normalize_segments(event)
    if not segments:
        return _missing_field_message(seg_type, field_path, expr)

    matched_segments = [seg for seg in segments if seg["type"] == seg_type]
    if not matched_segments:
        return _missing_field_message(seg_type, field_path, expr)

    values = _collect_field_values(matched_segments, field_path)
    if not values:
        return _missing_field_message(seg_type, field_path, expr)

    return _JOINER.join(values)


def render_segment_field_template(event: Event, text: str) -> str:
    """渲染文本中的消息段字段模板。
    Args:
        event: 当前事件对象
        text: 待处理文本
    用法：
    ```python
    result = render_segment_field_template(event, "QQ是[at.user_id]")
    ```
    """
    if "[" not in text or "]" not in text:
        return text

    def repl(match: re.Match[str]) -> str:
        expr = match.group(1).strip()
        if not expr:
            return match.group(0)
        value = eval_segment_field_expression(event, expr)
        return match.group(0) if value is None else value

    return _FIELD_EXPR_RE.sub(repl, text)
