import asyncio
import re
from datetime import datetime

_TIME_NAME_ALIASES = {"时间", "time"}
_TIME_TIMESTAMP_ALIASES = {"取时间戳_秒", "timestamp"}
_TIME_TIMESTAMP_MS_ALIASES = {"取时间戳_毫秒", "timestamp_ms"}
_TIME_FORMAT_ALIASES = {"格式化", "format"}
_TIME_SLEEP_ALIASES = {"休眠", "sleep"}
_DEFAULT_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
_TEMPLATE_TOKEN_RE = re.compile(r"\[([^\[\]]+)\]")


def parse_time_spec(name: str) -> tuple[str, str | None] | None:
    """解析时间模板参数。
    Args:
        name: 模板表达式
    用法：
    ```python
    spec = parse_time_spec("时间.格式化.%Y-%m-%d")
    ```
    """
    raw_name = name.strip()
    if not raw_name:
        return None

    parts = [part.strip() for part in raw_name.split(".")]
    if len(parts) < 2:
        return None
    if parts[0] not in _TIME_NAME_ALIASES:
        return None

    mode = parts[1]
    if mode in _TIME_TIMESTAMP_ALIASES and len(parts) == 2:
        return ("timestamp", None)
    if mode in _TIME_TIMESTAMP_MS_ALIASES and len(parts) == 2:
        return ("timestamp_ms", None)
    if mode in _TIME_FORMAT_ALIASES:
        fmt = ".".join(parts[2:]).strip() if len(parts) > 2 else _DEFAULT_TIME_FORMAT
        if not fmt:
            fmt = _DEFAULT_TIME_FORMAT
        return ("format", fmt)
    if mode in _TIME_SLEEP_ALIASES:
        duration = ".".join(parts[2:]).strip() if len(parts) > 2 else ""
        return ("sleep", duration)
    return None


def parse_sleep_seconds(name: str) -> float | None:
    """解析休眠模板秒数。
    Args:
        name: 模板表达式
    用法：
    ```python
    seconds = parse_sleep_seconds("时间.休眠.2")
    ```
    """
    spec = parse_time_spec(name)
    if spec is None:
        return None

    mode, payload = spec
    if mode != "sleep":
        return None

    if payload is None or payload == "":
        return 0.0

    try:
        seconds = float(payload)
    except (TypeError, ValueError):
        return None
    return max(0.0, seconds)


def split_time_actions(text: str) -> list[tuple[float, str]]:
    """把带休眠模板的文本拆成发送片段。
    Args:
        text: 待处理文本
    用法：
    ```python
    chunks = split_time_actions("前面[时间.休眠.2]后面")
    ```
    """
    if "[" not in text or "]" not in text:
        return [(0.0, text)] if text else []

    chunks: list[tuple[float, str]] = []
    cursor = 0
    pending_delay = 0.0

    for match in _TEMPLATE_TOKEN_RE.finditer(text):
        expr = match.group(1).strip()
        seconds = parse_sleep_seconds(expr)
        if seconds is None:
            continue

        chunk = text[cursor:match.start()]
        if chunk:
            chunks.append((pending_delay, chunk))
            pending_delay = 0.0

        pending_delay += seconds
        cursor = match.end()

    tail = text[cursor:]
    if tail:
        chunks.append((pending_delay, tail))

    if not chunks and cursor == 0 and text:
        return [(0.0, text)]
    return chunks


async def apply_time_actions(text: str) -> str:
    """按时间模板顺序执行文本片段。
    Args:
        text: 待处理文本
    用法：
    ```python
    result = await apply_time_actions("前面[时间.休眠.2]后面")
    ```
    """
    if "[" not in text or "]" not in text:
        return text

    parts: list[str] = []
    for delay, chunk in split_time_actions(text):
        if delay > 0:
            await asyncio.sleep(delay)
        parts.append(chunk)
    return "".join(parts)


def render_time_value(name: str) -> str | None:
    """渲染当前时间模板结果。
    Args:
        name: 模板表达式
    用法：
    ```python
    value = render_time_value("时间.取时间戳_秒")
    ```
    """
    spec = parse_time_spec(name)
    if spec is None:
        return None

    mode, payload = spec
    now = datetime.now()

    if mode == "timestamp":
        return str(int(now.timestamp()))
    if mode == "timestamp_ms":
        return str(int(now.timestamp() * 1000))
    if mode == "format":
        fmt = payload or _DEFAULT_TIME_FORMAT
        try:
            return now.strftime(fmt)
        except Exception:
            return ""
    if mode == "sleep":
        return None
    return None


class TimeTemplate:
    @staticmethod
    def parse(spec: str) -> tuple[str, str | None] | None:
        """解析时间模板。
        Args:
            spec: 模板表达式
        用法：
        ```python
        parsed = TimeTemplate.parse("时间.格式化.%Y-%m-%d")
        ```
        """
        return parse_time_spec(spec)

    @staticmethod
    async def apply_actions(text: str) -> str:
        """执行带休眠的时间动作文本。
        Args:
            text: 待处理文本
        用法：
        ```python
        result = await TimeTemplate.apply_actions("前面[时间.休眠.1]后面")
        ```
        """
        return await apply_time_actions(text)

    @staticmethod
    def split_actions(text: str) -> list[tuple[float, str]]:
        """拆分时间动作片段。
        Args:
            text: 待处理文本
        用法：
        ```python
        chunks = TimeTemplate.split_actions("前面[时间.休眠.1]后面")
        ```
        """
        return split_time_actions(text)

    @staticmethod
    def render(spec: str) -> str | None:
        """渲染时间模板结果。
        Args:
            spec: 模板表达式
        用法：
        ```python
        value = TimeTemplate.render("时间.取时间戳_秒")
        ```
        """
        return render_time_value(spec)
