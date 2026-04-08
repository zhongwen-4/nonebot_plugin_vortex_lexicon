from functools import lru_cache
from nonebot.adapters import Event

from .assign_template import eval_question_assign_expression, parse_question_assign_spec
from .constants import _LEGACY_RANDOM_EXPR_RE, _VAR_TOKEN_RE
from .event_field_template import parse_event_match_expression, eval_event_match_expression
from .random_template import is_random_match, parse_random_spec

_DEPRECATED_RANDOM_NAMES = ("random", "rand", "随机")


def is_legacy_random_token(name: str) -> bool:
    raw = name.strip()
    if _LEGACY_RANDOM_EXPR_RE.fullmatch(raw) is not None:
        return True
    if "=" not in raw:
        return False
    _, right = raw.split("=", 1)
    return _LEGACY_RANDOM_EXPR_RE.fullmatch(right.strip()) is not None


def is_deprecated_random_token(name: str) -> bool:
    raw = name.strip()
    if not raw:
        return False

    def is_old_prefix(value: str) -> bool:
        lowered = value.lower()
        return any(lowered == item or lowered.startswith(f"{item}.") for item in _DEPRECATED_RANDOM_NAMES)

    def is_old_random_op(value: str) -> bool:
        lowered = value.lower()
        return lowered.startswith("随机操作.") and not lowered.startswith("随机操作.取随机数.")

    if is_old_prefix(raw) or is_old_random_op(raw):
        return True
    if "=" not in raw:
        return False
    _, right = raw.split("=", 1)
    right = right.strip()
    return is_old_prefix(right) or is_old_random_op(right)


@lru_cache(maxsize=1024)
def compile_question_template(template: str) -> tuple[tuple[str, str], ...]:
    """编译问题模板为匹配 token。
    Args:
        template: 模板字符串
    用法：
    ```python
    tokens = compile_question_template("你好[name]")
    ```
    """
    tokens: list[tuple[str, str]] = []
    cursor = 0

    for match in _VAR_TOKEN_RE.finditer(template):
        literal = template[cursor:match.start()]
        if literal:
            tokens.append(("lit", literal))

        name = match.group(1).strip()
        if not name:
            tokens.append(("lit", match.group(0)))
        else:
            if is_legacy_random_token(name) or is_deprecated_random_token(name):
                tokens.append(("lit", match.group(0)))
            else:
                assign_spec = parse_question_assign_spec(name)
                if assign_spec is not None:
                    var_name, expr = assign_spec
                    tokens.append(("assign", f"{var_name}={expr}"))
                elif parse_event_match_expression(name) is not None:
                    tokens.append(("event", name))
                elif parse_random_spec(name) is not None:
                    tokens.append(("rand", name))
                else:
                    tokens.append(("var", name))

        cursor = match.end()

    tail = template[cursor:]
    if tail:
        tokens.append(("lit", tail))

    if not tokens:
        tokens.append(("lit", ""))

    return tuple(tokens)


def _char_class(ch: str) -> str:
    if ch.isspace():
        return "space"
    if ch.isdigit():
        return "digit"
    if ch.isalpha():
        if "一" <= ch <= "鿿":
            return "cjk"
        return "alpha"
    return "other"


def _is_natural_boundary(text: str, end: int) -> bool:
    if end <= 0 or end >= len(text):
        return True
    return _char_class(text[end - 1]) != _char_class(text[end])


def _find_literal_starts(text: str, literal: str, start: int) -> list[int]:
    starts: list[int] = []
    pos = text.find(literal, start)
    while pos != -1:
        starts.append(pos)
        pos = text.find(literal, pos + 1)
    return starts


def _next_literal(tokens: tuple[tuple[str, str], ...], idx: int) -> str | None:
    for kind, value in tokens[idx + 1 :]:
        if kind == "lit" and value:
            return value
    return None


def _token_kind(tokens: tuple[tuple[str, str], ...], idx: int) -> str | None:
    if idx >= len(tokens):
        return None
    return tokens[idx][0]


def _ordered_candidate_ends(
    text: str,
    start: int,
    ends: list[int],
    adjacent_variable: bool,
) -> list[int]:
    if not ends:
        return []

    if not adjacent_variable:
        return sorted(ends)

    natural = [end for end in ends if _is_natural_boundary(text, end)]
    natural_set = set(natural)
    other = [end for end in ends if end not in natural_set]
    return sorted(natural, reverse=True) + sorted(other, reverse=True)


def _match_template(
    tokens: tuple[tuple[str, str], ...],
    text: str,
    event: Event | None = None,
) -> dict[str, str] | None:
    def dfs(idx: int, pos: int, variables: dict[str, str]) -> dict[str, str] | None:
        if idx >= len(tokens):
            return variables if pos == len(text) else None

        kind, value = tokens[idx]
        if kind == "lit":
            if not text.startswith(value, pos):
                return None
            return dfs(idx + 1, pos + len(value), variables)

        if kind == "rand":
            next_lit = _next_literal(tokens, idx)
            adjacent_variable = _token_kind(tokens, idx + 1) in {"var", "rand", "assign"}
            if next_lit is None:
                candidate_ends = list(range(pos + 1, len(text) + 1))
            else:
                candidate_ends = _find_literal_starts(text, next_lit, pos + 1)

            for end in _ordered_candidate_ends(text, pos, candidate_ends, adjacent_variable):
                if not is_random_match(value, text[pos:end]):
                    continue
                matched = dfs(idx + 1, end, variables)
                if matched is not None:
                    return matched
            return None

        if kind == "event":
            if event is None:
                return None
            matched = eval_event_match_expression(event, value)
            if matched is not True:
                return None
            return dfs(idx + 1, pos, variables)

        if kind == "assign":
            assign_spec = parse_question_assign_spec(value)
            if assign_spec is None:
                return None
            var_name, expr = assign_spec
            if var_name in variables:
                return dfs(idx + 1, pos, variables)

            assigned = eval_question_assign_expression(expr, event)
            if assigned is None:
                return None
            variables[var_name] = assigned
            matched = dfs(idx + 1, pos, variables)
            if matched is not None:
                return matched
            variables.pop(var_name, None)
            return None

        name = value
        if name in variables:
            existed = variables[name]
            if not text.startswith(existed, pos):
                return None
            return dfs(idx + 1, pos + len(existed), variables)

        next_lit = _next_literal(tokens, idx)
        adjacent_variable = _token_kind(tokens, idx + 1) in {"var", "rand", "assign"}
        if next_lit is None:
            candidate_ends = list(range(pos + 1, len(text) + 1))
        else:
            candidate_ends = _find_literal_starts(text, next_lit, pos + 1)

        for end in _ordered_candidate_ends(text, pos, candidate_ends, adjacent_variable):
            variables[name] = text[pos:end]
            matched = dfs(idx + 1, end, variables)
            if matched is not None:
                return matched
            variables.pop(name, None)

        return None

    return dfs(0, 0, {})


def match_atom(atom_template: str, text: str) -> dict[str, str] | None:
    """按原子模板精确匹配文本。
    Args:
        atom_template: 原子模板字符串
        text: 待处理文本
    用法：
    ```python
    matched = match_atom("你好[name]", "你好世界")
    ```
    """
    tokens = compile_question_template(atom_template)
    return _match_template(tokens, text)


def match_atom_with_event(atom_template: str, text: str, event: Event | None = None) -> dict[str, str] | None:
    """按原子模板结合事件上下文匹配文本。
    Args:
        atom_template: 原子模板字符串
        text: 待处理文本
        event: 当前事件对象
    用法：
    ```python
    matched = match_atom_with_event("[uid=at.user_id]", "@某人", event)
    ```
    """
    tokens = compile_question_template(atom_template)
    matched = _match_template(tokens, text, event)
    if matched is not None:
        return matched
    if text:
        return _match_template(tokens, "", event)
    return None


def contains_atom(atom_template: str, text: str) -> dict[str, str] | None:
    """判断文本是否包含原子模板。
    Args:
        atom_template: 原子模板字符串
        text: 待处理文本
    用法：
    ```python
    matched = contains_atom("世界", "你好世界")
    ```
    """
    atom_template = atom_template.strip()
    if not atom_template:
        return {}

    if "[" not in atom_template and "]" not in atom_template:
        return {} if atom_template in text else None

    for start in range(len(text)):
        for end in range(start + 1, len(text) + 1):
            variables = match_atom(atom_template, text[start:end])
            if variables is not None:
                return variables
    return None


def contains_atom_with_event(atom_template: str, text: str, event: Event | None = None) -> dict[str, str] | None:
    """结合事件上下文判断文本是否包含原子模板。
    Args:
        atom_template: 原子模板字符串
        text: 待处理文本
        event: 当前事件对象
    用法：
    ```python
    matched = contains_atom_with_event("[uid=at.user_id]", "测试@某人", event)
    ```
    """
    atom_template = atom_template.strip()
    if not atom_template:
        return {}

    if "[" not in atom_template and "]" not in atom_template:
        return {} if atom_template in text else None

    for start in range(len(text)):
        for end in range(start + 1, len(text) + 1):
            variables = match_atom_with_event(atom_template, text[start:end], event)
            if variables is not None:
                return variables
    return None


def merge_vars(left: dict[str, str], right: dict[str, str]) -> dict[str, str] | None:
    """合并两组模板变量。
    Args:
        left: 左侧变量字典
        right: 右侧变量字典
    用法：
    ```python
    merged = merge_vars({"a": "1"}, {"b": "2"})
    ```
    """
    merged = dict(left)
    for key, value in right.items():
        existed = merged.get(key)
        if existed is not None and existed != value:
            return None
        merged[key] = value
    return merged


class QuestionTemplate:
    @staticmethod
    def compile(template: str) -> tuple[tuple[str, str], ...]:
        """编译问题模板。
        Args:
            template: 模板字符串
        用法：
        ```python
        tokens = QuestionTemplate.compile("你好[name]")
        ```
        """
        return compile_question_template(template)

    @staticmethod
    def match(template: str, text: str) -> dict[str, str] | None:
        """精确匹配问题模板。
        Args:
            template: 模板字符串
            text: 待处理文本
        用法：
        ```python
        matched = QuestionTemplate.match("你好[name]", "你好世界")
        ```
        """
        return match_atom(template, text)

    @staticmethod
    def match_with_event(template: str, text: str, event: Event | None = None) -> dict[str, str] | None:
        """结合事件上下文匹配问题模板。
        Args:
            template: 模板字符串
            text: 待处理文本
            event: 当前事件对象
        用法：
        ```python
        matched = QuestionTemplate.match_with_event("[uid=at.user_id]", "@某人", event)
        ```
        """
        return match_atom_with_event(template, text, event)

    @staticmethod
    def contains(template: str, text: str) -> dict[str, str] | None:
        """判断文本是否包含问题模板。
        Args:
            template: 模板字符串
            text: 待处理文本
        用法：
        ```python
        matched = QuestionTemplate.contains("世界", "你好世界")
        ```
        """
        return contains_atom(template, text)

    @staticmethod
    def contains_with_event(template: str, text: str, event: Event | None = None) -> dict[str, str] | None:
        """结合事件上下文判断文本是否包含问题模板。
        Args:
            template: 模板字符串
            text: 待处理文本
            event: 当前事件对象
        用法：
        ```python
        matched = QuestionTemplate.contains_with_event("[uid=at.user_id]", "测试@某人", event)
        ```
        """
        return contains_atom_with_event(template, text, event)
