import re
import time
from dataclasses import dataclass

from nonebot.adapters import Event

_AWAIT_TOKEN_RE = re.compile(r"\[await\.([^\[\].]+)\.([^\[\].]+)\]")
_VAR_TOKEN_RE = re.compile(r"\[([^\[\]]+)\]")
_DEFAULT_TIMEOUT = 120.0
DEFAULT_AWAIT_PROMPT = "请输入内容"
_AWAIT_STATE_KEY = "_vortex_await_state"


@dataclass(slots=True)
class AwaitStep:
    prefix: str
    timeout: float
    variable: str
    remaining: str


def _parse_timeout(raw: str) -> float:
    try:
        timeout = float(raw)
    except (TypeError, ValueError):
        return _DEFAULT_TIMEOUT
    return max(0.0, timeout)


def render_await_variables(text: str, variables: dict[str, str]) -> str:
    """渲染 await 流程里已采集到的变量。
    Args:
        text: 待渲染文本
        variables: 已采集变量字典

    用法：
    ```python
    text = render_await_variables("[name]", {"name": "小明"})
    print(text)
    ```
    """
    if not variables:
        return text

    def _replace(match: re.Match[str]) -> str:
        name = match.group(1).strip()
        return variables.get(name, match.group(0))

    return _VAR_TOKEN_RE.sub(_replace, text)


def event_to_text(event: Event) -> str:
    """提取事件中的纯文本内容。
    Args:
        event: 当前事件对象
    用法：
    ```python
    text = event_to_text(event)
    ```
    """
    plaintext_getter = getattr(event, "get_plaintext", None)
    if callable(plaintext_getter):
        try:
            plain = plaintext_getter()
        except Exception:
            plain = ""
        if plain:
            return str(plain)

    try:
        message = event.get_message()
    except Exception:
        return ""

    try:
        plain = message.extract_plain_text()
    except Exception:
        plain = ""
    if plain:
        return plain

    try:
        return str(message)
    except Exception:
        return ""


def next_await_step(text: str, variables: dict[str, str]) -> AwaitStep | None:
    """获取下一段 await 等待步骤。
    Args:
        text: 待处理文本
        variables: 模板变量字典
    用法：
    ```python
    step = next_await_step("前缀[await.10.msg][msg]", {})
    ```
    """
    matched = _AWAIT_TOKEN_RE.search(text)
    if matched is None:
        return None

    variable = matched.group(2).strip()
    if not variable:
        return None

    return AwaitStep(
        prefix=render_await_variables(text[: matched.start()], variables),
        timeout=_parse_timeout(matched.group(1)),
        variable=variable,
        remaining=text[matched.end() :],
    )


def build_await_state(
    remaining_text: str,
    variable: str,
    timeout: float,
    variables: dict[str, str],
) -> dict[str, object]:
    """构造 await 续跑状态。
    Args:
        remaining_text: 等待输入后的剩余模板文本
        variable: 等待输入保存的变量名
        timeout: 等待超时时间（秒）
        variables: 模板变量字典
    用法：
    ```python
    state = build_await_state("[msg]", "msg", 10, {})
    ```
    """
    return {
        "remaining_text": remaining_text,
        "variable": variable,
        "deadline": time.time() + max(0.0, timeout),
        "variables": dict(variables),
    }


def load_await_state(state: dict[str, object]) -> dict[str, object] | None:
    """读取 matcher 状态中的 await 信息。
    Args:
        state: matcher 状态字典
    用法：
    ```python
    payload = load_await_state(state)
    ```
    """
    raw = state.get(_AWAIT_STATE_KEY)
    return raw if isinstance(raw, dict) else None


def save_await_state(state: dict[str, object], payload: dict[str, object]) -> None:
    """保存 await 续跑状态到 matcher。
    Args:
        state: matcher 状态字典
        payload: await 状态载荷
    用法：
    ```python
    save_await_state(state, payload)
    ```
    """
    state[_AWAIT_STATE_KEY] = payload


def clear_await_state(state: dict[str, object]) -> None:
    """清除 matcher 中的 await 状态。
    Args:
        state: matcher 状态字典
    用法：
    ```python
    clear_await_state(state)
    ```
    """
    state.pop(_AWAIT_STATE_KEY, None)


def is_await_expired(payload: dict[str, object]) -> bool:
    """判断 await 状态是否已超时。
    Args:
        payload: await 状态载荷
    用法：
    ```python
    expired = is_await_expired(payload)
    ```
    """
    deadline = payload.get("deadline")
    if not isinstance(deadline, (int, float)):
        return False
    return time.time() > float(deadline)


def contains_await_templates(text: str) -> bool:
    """判断文本中是否包含 await 模板。
    Args:
        text: 待处理文本
    用法：
    ```python
    has_await = contains_await_templates("测试[await.10.msg]")
    ```
    """
    return _AWAIT_TOKEN_RE.search(text) is not None


def strip_await_templates(text: str) -> str:
    """移除文本中的 await 模板。
    Args:
        text: 待处理文本
    用法：
    ```python
    plain = strip_await_templates("测试[await.10.msg]")
    ```
    """
    return _AWAIT_TOKEN_RE.sub("", text)


def extract_await_templates(text: str) -> str:
    """提取文本中的 await 模板片段。
    Args:
        text: 待处理文本
    用法：
    ```python
    part = extract_await_templates("测试[await.10.msg]")
    ```
    """
    return "".join(match.group(0) for match in _AWAIT_TOKEN_RE.finditer(text))


class AwaitTemplate:
    @staticmethod
    def contains(text: str) -> bool:
        """判断文本中是否存在 await 模板。
        Args:
            text: 待处理文本
        用法：
        ```python
        ok = AwaitTemplate.contains("测试[await.10.msg]")
        ```
        """
        return contains_await_templates(text)

    @staticmethod
    def strip(text: str) -> str:
        """去除文本中的 await 模板。
        Args:
            text: 待处理文本
        用法：
        ```python
        plain = AwaitTemplate.strip("测试[await.10.msg]")
        ```
        """
        return strip_await_templates(text)

    @staticmethod
    def extract(text: str) -> str:
        """提取文本中的 await 模板。
        Args:
            text: 待处理文本
        用法：
        ```python
        part = AwaitTemplate.extract("测试[await.10.msg]")
        ```
        """
        return extract_await_templates(text)

    @staticmethod
    def next_step(text: str, variables: dict[str, str]) -> AwaitStep | None:
        """解析下一段 await 步骤。
        Args:
            text: 待处理文本
            variables: 模板变量字典
        用法：
        ```python
        step = AwaitTemplate.next_step("[await.10.msg][msg]", {})
        ```
        """
        return next_await_step(text, variables)

    @staticmethod
    def render_variables(text: str, variables: dict[str, str]) -> str:
        """渲染 await 过程中已采集的变量。
        Args:
            text: 待处理文本
            variables: 模板变量字典
        用法：
        ```python
        text = AwaitTemplate.render_variables("[msg]", {"msg": "你好"})
        ```
        """
        return render_await_variables(text, variables)
