import re
from typing import Any

from nonebot.adapters import Event

_EVENT_PREFIX = "event."
_EVENT_MATCH_RE = re.compile(r"^event\.(?P<path>[^!=]+?)(?:(?P<op>==|!=|=)(?P<value>.*))?$")


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


def _extract_field(data: Any, field_path: str) -> Any:
    current = data
    for part in field_path.split("."):
        key = part.strip()
        if not key:
            return None

        if isinstance(current, dict):
            current = current.get(key)
            continue

        attr = getattr(current, key, None)
        if attr is not None:
            if callable(attr):
                try:
                    current = attr()
                except TypeError:
                    return None
            else:
                current = attr
            continue

        dumped = _to_plain_dict(current)
        if dumped is None:
            return None
        current = dumped.get(key)
    return current


def _event_builtin_value(event: Event, field_path: str) -> Any:
    key = field_path.strip().lower()
    if key == "type":
        try:
            return event.get_type()
        except Exception:
            return None
    if key in {"name", "event_name"}:
        try:
            return event.get_event_name()
        except Exception:
            return None
    if key == "event_type":
        return getattr(event, "event_type", None) or getattr(event, "__event_type__", None)
    return None


def _current_event_type(event: Event) -> str:
    raw = _event_builtin_value(event, "event_type")
    if raw is not None:
        return str(raw)
    return ""


def parse_event_field_expression(expr: str) -> str | None:
    """解析事件字段模板表达式。
    Args:
        expr: 表达式字符串
    用法示例:
    ```python
    path = parse_event_field_expression("event.data.group_id")
    ```
    """
    raw = expr.strip()
    if not raw.lower().startswith(_EVENT_PREFIX):
        return None
    path = raw[len(_EVENT_PREFIX) :].strip()
    if not path:
        return None
    return path


def eval_event_field_expression(event: Event, expr: str) -> str | None:
    """读取事件对象中的字段文本值。
    Args:
        event: 当前事件对象
        expr: 表达式字符串
    用法示例:
    ```python
    text = eval_event_field_expression(event, "event.event_type")
    ```
    """
    path = parse_event_field_expression(expr)
    if path is None:
        return None
    value = eval_event_field_value(event, path)
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def eval_event_field_value(event: Event, field_path: str) -> Any:
    """读取事件对象中的字段原始值。
    Args:
        event: 当前事件对象
        field_path: 字段路径
    用法示例:
    ```python
    value = eval_event_field_value(event, "data.group_id")
    ```
    """
    builtin = _event_builtin_value(event, field_path)
    if builtin is not None:
        return builtin

    value = _extract_field(event, field_path)
    if value is not None:
        return value

    # 兼容简写：event.xxx 自动回退到 event.data.xxx
    # 例如 event.peer_id -> event.data.peer_id
    if not field_path.startswith("data."):
        return _extract_field(event, f"data.{field_path}")
    return None


def parse_event_match_expression(expr: str) -> tuple[str, str | None, str | None] | None:
    """解析事件匹配模板。
    Args:
        expr: 表达式字符串
    用法示例:
    ```python
    spec = parse_event_match_expression("event.event_type=message_receive")
    ```
    """
    raw = expr.strip()
    matched = _EVENT_MATCH_RE.fullmatch(raw)
    if matched is None:
        return None

    path = matched.group("path").strip()
    op = matched.group("op")
    value = matched.group("value")
    if not path:
        return None
    if op is not None:
        op = "==" if op == "=" else op
    if value is not None:
        value = value.strip()
    return path, op, value


def _coerce_literal(text: str | None) -> Any:
    if text is None:
        return None
    raw = text.strip()
    if not raw:
        return ""
    lowered = raw.lower()
    if lowered in {"true", "yes", "on"}:
        return True
    if lowered in {"false", "no", "off"}:
        return False
    if lowered in {"none", "null"}:
        return None
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def eval_event_match_expression(event: Event, expr: str) -> bool | None:
    """执行事件模板匹配。
    Args:
        event: 当前事件对象
        expr: 表达式字符串
    用法示例:
    ```python
    ok = eval_event_match_expression(event, "event.event_type=message_receive")
    ```
    """
    spec = parse_event_match_expression(expr)
    if spec is None:
        return None

    path, op, expected = spec
    actual = eval_event_field_value(event, path)

    if op is None:
        lowered_path = path.strip().lower()
        if "." not in path and lowered_path not in {"type", "name", "event_name", "event_type"}:
            return _current_event_type(event).lower() == lowered_path
        if actual is None:
            return False
        if isinstance(actual, str):
            return bool(actual.strip())
        return True

    expected_value = _coerce_literal(expected)

    if op == "==":
        if actual == expected_value:
            return True
        return str(actual) == str(expected_value)

    if op == "!=":
        if actual == expected_value:
            return False
        return str(actual) != str(expected_value)

    return None


class EventFieldTemplate:
    @staticmethod
    def parse_field(expr: str) -> str | None:
        """解析事件字段模板。
        Args:
            expr: 表达式字符串
        用法示例:
        ```python
        path = EventFieldTemplate.parse_field("event.data.group_id")
        ```
        """
        return parse_event_field_expression(expr)

    @staticmethod
    def parse_match(expr: str) -> tuple[str, str | None, str | None] | None:
        """解析事件匹配模板。
        Args:
            expr: 表达式字符串
        用法示例:
        ```python
        spec = EventFieldTemplate.parse_match("event.event_type=message_receive")
        ```
        """
        return parse_event_match_expression(expr)

    @staticmethod
    def eval_field(event: Event, expr: str) -> str | None:
        """读取事件字段文本值。
        Args:
            event: 当前事件对象
            expr: 表达式字符串
        用法示例:
        ```python
        value = EventFieldTemplate.eval_field(event, "event.type")
        ```
        """
        return eval_event_field_expression(event, expr)

    @staticmethod
    def eval_match(event: Event, expr: str) -> bool | None:
        """执行事件匹配判断。
        Args:
            event: 当前事件对象
            expr: 表达式字符串
        用法示例:
        ```python
        ok = EventFieldTemplate.eval_match(event, "event.type=notice")
        ```
        """
        return eval_event_match_expression(event, expr)
