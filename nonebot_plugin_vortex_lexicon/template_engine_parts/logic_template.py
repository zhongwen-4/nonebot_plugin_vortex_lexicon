from functools import lru_cache

from nonebot.adapters import Event

from .answer_template import render_answer_template
from .constants import (
    _OP_ALIASES,
    _OP_AND,
    _OP_ELSE,
    _OP_EQ,
    _OP_GE,
    _OP_IF,
    _OP_IN,
    _OP_LE,
    _OP_NE,
    _OP_NOT,
    _OP_NOT_IN,
    _OP_OR,
    _OP_XOR,
    _VAR_TOKEN_RE,
)
from .question_template import (
    contains_atom,
    contains_atom_with_event,
    match_atom,
    match_atom_with_event,
    merge_vars,
)


def _normalize_op_name(name: str) -> str | None:
    normalized = " ".join(name.strip().lower().split())
    for op, aliases in _OP_ALIASES.items():
        if normalized in aliases:
            return op
    return None


@lru_cache(maxsize=1024)
def tokenize_logic_expression(template: str) -> tuple[tuple[str, str], ...]:
    """把逻辑模板拆成原子和操作符。
    Args:
        template: 模板字符串
    用法：
    ```python
    tokens = tokenize_logic_expression("你好[or]世界")
    ```
    """
    raw_tokens: list[tuple[str, str]] = []
    cursor = 0

    for match in _VAR_TOKEN_RE.finditer(template):
        literal = template[cursor:match.start()]
        if literal:
            raw_tokens.append(("text_lit", literal))

        name = match.group(1).strip()
        op = _normalize_op_name(name)
        if op is None:
            raw_tokens.append(("text_var", match.group(0)))
        else:
            raw_tokens.append(("op", op))
        cursor = match.end()

    tail = template[cursor:]
    if tail:
        raw_tokens.append(("text_lit", tail))

    tokens: list[tuple[str, str]] = []
    buffer: list[tuple[str, str]] = []

    def flush_buffer() -> None:
        atom = "".join(part for _, part in buffer).strip()
        if atom:
            tokens.append(("atom", atom))
        buffer.clear()

    for kind, value in raw_tokens:
        if kind == "op":
            flush_buffer()
            tokens.append(("op", value))
            continue

        if kind == "text_var" and buffer:
            var_expr = value[1:-1].strip()
            is_assign_var = "=" in var_expr
            if all(part_kind == "text_var" for part_kind, _ in buffer) or is_assign_var:
                flush_buffer()

        buffer.append((kind, value))

    flush_buffer()

    if not tokens:
        tokens.append(("atom", ""))
    return tuple(tokens)


def has_logic_ops(tokens: tuple[tuple[str, str], ...]) -> bool:
    """判断 token 列表中是否存在逻辑操作符。
    Args:
        tokens: 逻辑 token 序列
    用法：
    ```python
    ok = has_logic_ops(tokenize_logic_expression("你好[or]世界"))
    ```
    """
    return any(kind == "op" for kind, _ in tokens)


def parse_logic_expression(tokens: tuple[tuple[str, str], ...]) -> tuple | None:
    """把逻辑 token 解析为语法树。
    Args:
        tokens: 逻辑 token 序列
    用法：
    ```python
    ast = parse_logic_expression(tokenize_logic_expression("你好[or]世界"))
    ```
    """
    idx = 0

    def parse_or() -> tuple | None:
        nonlocal idx
        node = parse_xor()
        if node is None:
            return None
        while idx < len(tokens) and tokens[idx][0] == "op" and tokens[idx][1] in {_OP_OR}:
            op = tokens[idx][1]
            idx += 1
            right = parse_xor()
            if right is None:
                return None
            node = (op, node, right)
        return node

    def parse_xor() -> tuple | None:
        nonlocal idx
        node = parse_and()
        if node is None:
            return None
        while idx < len(tokens) and tokens[idx][0] == "op" and tokens[idx][1] in {_OP_XOR}:
            op = tokens[idx][1]
            idx += 1
            right = parse_and()
            if right is None:
                return None
            node = (op, node, right)
        return node

    def parse_and() -> tuple | None:
        nonlocal idx
        node = parse_compare()
        if node is None:
            return None
        while idx < len(tokens) and tokens[idx][0] == "op" and tokens[idx][1] in {_OP_AND}:
            op = tokens[idx][1]
            idx += 1
            right = parse_compare()
            if right is None:
                return None
            node = (op, node, right)
        return node

    def parse_compare() -> tuple | None:
        nonlocal idx
        node = parse_membership()
        if node is None:
            return None
        while idx < len(tokens) and tokens[idx][0] == "op" and tokens[idx][1] in {
            _OP_EQ,
            _OP_NE,
            _OP_LE,
            _OP_GE,
        }:
            op = tokens[idx][1]
            idx += 1
            right = parse_membership()
            if right is None:
                return None
            node = (op, node, right)
        return node

    def parse_membership() -> tuple | None:
        nonlocal idx
        node = parse_unary()
        if node is None:
            return None
        while idx < len(tokens) and tokens[idx][0] == "op" and tokens[idx][1] in {_OP_IN, _OP_NOT_IN}:
            op = tokens[idx][1]
            idx += 1
            right = parse_unary()
            if right is None:
                return None
            node = (op, node, right)
        return node

    def parse_unary() -> tuple | None:
        nonlocal idx
        if idx < len(tokens) and tokens[idx][0] == "op":
            op = tokens[idx][1]
            if op in {_OP_NOT, _OP_IN, _OP_NOT_IN}:
                idx += 1
                child = parse_unary()
                if child is None:
                    return None
                return (op, child)
        return parse_primary()

    def parse_primary() -> tuple | None:
        nonlocal idx
        if idx >= len(tokens):
            return None
        kind, value = tokens[idx]
        if kind != "atom":
            return None
        idx += 1
        return ("ATOM", value)

    def parse_if_else() -> tuple | None:
        nonlocal idx
        if idx < len(tokens) and tokens[idx][0] == "op" and tokens[idx][1] == _OP_IF:
            idx += 1
            condition = parse_or()
            if condition is None:
                return None
            if idx >= len(tokens):
                return condition
            true_branch = parse_if_else()
            if true_branch is None:
                return None
            if idx >= len(tokens) or tokens[idx][0] != "op" or tokens[idx][1] != _OP_ELSE:
                return None
            idx += 1
            false_branch = parse_if_else()
            if false_branch is None:
                return None
            return (_OP_IF, condition, true_branch, false_branch)

        # 不再支持中缀分支语法：A [if] B [else] C
        return parse_or()

    root = parse_if_else()
    if root is None or idx != len(tokens):
        return None
    return root


def _node_has_in_operator(node: tuple) -> bool:
    op = node[0]
    if op in {_OP_IN, _OP_NOT_IN}:
        return True
    if op == "ATOM":
        return False
    if op == _OP_IF:
        return (
            _node_has_in_operator(node[1])
            or _node_has_in_operator(node[2])
            or _node_has_in_operator(node[3])
        )
    if op in {_OP_NOT}:
        return _node_has_in_operator(node[1])
    if len(node) >= 3:
        return _node_has_in_operator(node[1]) or _node_has_in_operator(node[2])
    return False


def _resolve_atom_text(
    atom_template: str,
    text: str,
    event: Event | None = None,
) -> tuple[str, dict[str, str]]:
    matched = match_atom_with_event(atom_template, text, event)
    if matched is None:
        matched = match_atom_with_event(atom_template, "", event)
    if matched is None:
        matched = contains_atom_with_event(atom_template, text, event)
    if matched is None:
        return atom_template, {}

    matched_vars = {str(key): str(value) for key, value in matched.items()}
    rendered = render_answer_template(atom_template, dict(matched_vars))
    return rendered, matched_vars


def _eval_binary_in_logic(
    left: tuple,
    right: tuple,
    text: str,
    event: Event | None = None,
    *,
    negate: bool = False,
) -> dict[str, str] | None:
    if left[0] != "ATOM" or right[0] != "ATOM":
        return None

    container, right_vars = _resolve_atom_text(right[1], text, event)
    needle = render_answer_template(left[1], dict(right_vars))
    contained = needle in container

    if negate:
        if contained:
            return None
        return dict(right_vars)

    if contained:
        return dict(right_vars)
    return None


def _parse_number(text: str) -> float | None:
    raw = text.strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _eval_binary_compare_logic(
    op: str,
    left: tuple,
    right: tuple,
    text: str,
    event: Event | None = None,
) -> dict[str, str] | None:
    if left[0] != "ATOM" or right[0] != "ATOM":
        return None

    left_text, left_vars = _resolve_atom_text(left[1], text, event)
    right_text, right_vars = _resolve_atom_text(right[1], text, event)

    merged = merge_vars(left_vars, right_vars)
    if merged is None:
        return None

    left_num = _parse_number(left_text)
    right_num = _parse_number(right_text)

    if op == _OP_EQ:
        return merged if left_text == right_text else None
    if op == _OP_NE:
        return merged if left_text != right_text else None
    if op == _OP_LE:
        if left_num is not None and right_num is not None:
            return merged if left_num <= right_num else None
        return merged if left_text <= right_text else None
    if op == _OP_GE:
        if left_num is not None and right_num is not None:
            return merged if left_num >= right_num else None
        return merged if left_text >= right_text else None

    return None


def eval_logic(
    node: tuple,
    text: str,
    contains_fallback: bool = False,
    event: Event | None = None,
) -> dict[str, str] | None:
    """执行问题侧逻辑匹配。
    Args:
        node: 逻辑语法树节点
        text: 待处理文本
        contains_fallback: 是否启用包含匹配回退
        event: 当前事件对象
    用法：
    ```python
    matched = eval_logic(ast, "你好", False, event)
    ```
    """
    op = node[0]
    if op == "ATOM":
        matched = match_atom_with_event(node[1], text, event)
        if matched is None:
            matched = match_atom_with_event(node[1], "", event)
        if matched is not None:
            return matched
        if contains_fallback:
            return contains_atom_with_event(node[1], text, event)
        return None

    if op == _OP_NOT:
        child = eval_logic(node[1], text, contains_fallback, event)
        if child is None:
            return {}
        return None

    if op == _OP_IN:
        if len(node) == 3:
            return _eval_binary_in_logic(node[1], node[2], text, event)
        child = node[1]
        if child[0] == "ATOM":
            return contains_atom_with_event(child[1], text, event)
        return eval_logic(child, text, True, event)

    if op == _OP_NOT_IN:
        if len(node) == 3:
            return _eval_binary_in_logic(node[1], node[2], text, event, negate=True)
        child = node[1]
        if child[0] == "ATOM":
            contained = contains_atom_with_event(child[1], text, event)
            if contained is None:
                return {}
            return None
        matched = eval_logic(child, text, True, event)
        if matched is None:
            return {}
        return None

    if op in {_OP_EQ, _OP_NE, _OP_LE, _OP_GE}:
        return _eval_binary_compare_logic(op, node[1], node[2], text, event)

    if op == _OP_IF:
        condition = eval_logic(node[1], text, contains_fallback, event)
        if condition is not None:
            true_result = eval_logic(node[2], text, contains_fallback, event)
            if true_result is None:
                return None
            return merge_vars(condition, true_result)
        return eval_logic(node[3], text, contains_fallback, event)

    left_has_in = _node_has_in_operator(node[1])
    right_has_in = _node_has_in_operator(node[2])
    left_fallback = contains_fallback or right_has_in
    right_fallback = contains_fallback or left_has_in

    if op == _OP_OR:
        left = eval_logic(node[1], text, left_fallback, event)
        if left is not None:
            return left
        return eval_logic(node[2], text, right_fallback, event)

    if op == _OP_XOR:
        left = eval_logic(node[1], text, left_fallback, event)
        right = eval_logic(node[2], text, right_fallback, event)
        left_ok = left is not None
        right_ok = right is not None
        if left_ok == right_ok:
            return None
        return left if left_ok else right

    if op == _OP_AND:
        left = eval_logic(node[1], text, left_fallback, event)
        if left is None:
            return None
        right = eval_logic(node[2], text, right_fallback, event)
        if right is None:
            return None
        return merge_vars(left, right)

    return None


def eval_logic_output(
    node: tuple,
    text: str,
    base_variables: dict[str, str],
    contains_fallback: bool = False,
    event: Event | None = None,
) -> str | None:
    """执行答案侧逻辑渲染。
    Args:
        node: 逻辑语法树节点
        text: 待处理文本
        base_variables: 基础变量字典
        contains_fallback: 是否启用包含匹配回退
        event: 当前事件对象
    用法：
    ```python
    result = eval_logic_output(ast, "你好", {}, False, event)
    ```
    """
    op = node[0]
    if op == "ATOM":
        atom_template = node[1]
        matched = match_atom_with_event(atom_template, text, event)
        if matched is None:
            matched = match_atom_with_event(atom_template, "", event)
        if matched is None and contains_fallback:
            matched = contains_atom_with_event(atom_template, text, event)
        if matched is None:
            return None
        merged = merge_vars(base_variables, matched)
        if merged is None:
            return None
        return render_answer_template(atom_template, merged)

    if op == _OP_NOT:
        child = eval_logic_output(node[1], text, base_variables, contains_fallback, event)
        if child is None:
            return ""
        return None

    if op == _OP_IN:
        if len(node) == 3:
            matched = _eval_binary_in_logic(node[1], node[2], text, event)
            if matched is None:
                return None
            merged = merge_vars(base_variables, matched)
            if merged is None:
                return None
            return ""
        child = node[1]
        if child[0] == "ATOM":
            matched = contains_atom_with_event(child[1], text, event)
            if matched is None:
                return None
            merged = merge_vars(base_variables, matched)
            if merged is None:
                return None
            return render_answer_template(child[1], merged)
        return eval_logic_output(child, text, base_variables, True, event)

    if op == _OP_NOT_IN:
        if len(node) == 3:
            matched = _eval_binary_in_logic(node[1], node[2], text, event, negate=True)
            if matched is None:
                return None
            merged = merge_vars(base_variables, matched)
            if merged is None:
                return None
            return ""
        child = node[1]
        if child[0] == "ATOM":
            matched = contains_atom_with_event(child[1], text, event)
            if matched is None:
                return ""
            return None
        matched = eval_logic_output(child, text, base_variables, True, event)
        if matched is None:
            return ""
        return None

    if op in {_OP_EQ, _OP_NE, _OP_LE, _OP_GE}:
        matched = _eval_binary_compare_logic(op, node[1], node[2], text, event)
        if matched is None:
            return None
        merged = merge_vars(base_variables, matched)
        if merged is None:
            return None
        return ""

    if op == _OP_IF:
        condition = eval_logic(node[1], text, contains_fallback, event)
        if condition is not None:
            merged_base = merge_vars(base_variables, condition)
            if merged_base is None:
                return None
            return eval_logic_output(node[2], text, merged_base, contains_fallback, event)
        return eval_logic_output(node[3], text, base_variables, contains_fallback, event)

    left_has_in = _node_has_in_operator(node[1])
    right_has_in = _node_has_in_operator(node[2])
    left_fallback = contains_fallback or right_has_in
    right_fallback = contains_fallback or left_has_in

    if op == _OP_OR:
        left = eval_logic_output(node[1], text, base_variables, left_fallback, event)
        if left is not None:
            return left
        return eval_logic_output(node[2], text, base_variables, right_fallback, event)

    if op == _OP_XOR:
        left = eval_logic_output(node[1], text, base_variables, left_fallback, event)
        right = eval_logic_output(node[2], text, base_variables, right_fallback, event)
        left_ok = left is not None
        right_ok = right is not None
        if left_ok == right_ok:
            return None
        return left if left_ok else right

    if op == _OP_AND:
        left = eval_logic_output(node[1], text, base_variables, left_fallback, event)
        if left is None:
            return None
        right = eval_logic_output(node[2], text, base_variables, right_fallback, event)
        if right is None:
            return None
        return f"{left}{right}"

    return None


class LogicTemplate:
    @staticmethod
    def tokenize(template: str) -> tuple[tuple[str, str], ...]:
        """拆分逻辑模板 token。
        Args:
            template: 模板字符串
        用法：
        ```python
        tokens = LogicTemplate.tokenize("你好[or]世界")
        ```
        """
        return tokenize_logic_expression(template)

    @staticmethod
    def has_ops(tokens: tuple[tuple[str, str], ...]) -> bool:
        """判断是否存在逻辑操作符。
        Args:
            tokens: 逻辑 token 序列
        用法：
        ```python
        ok = LogicTemplate.has_ops(tokens)
        ```
        """
        return has_logic_ops(tokens)

    @staticmethod
    def parse(tokens: tuple[tuple[str, str], ...]) -> tuple | None:
        """解析逻辑模板语法树。
        Args:
            tokens: 逻辑 token 序列
        用法：
        ```python
        ast = LogicTemplate.parse(tokens)
        ```
        """
        return parse_logic_expression(tokens)

    @staticmethod
    def eval_question(ast: tuple, text: str, event: Event | None = None) -> dict[str, str] | None:
        """执行问题侧逻辑计算。
        Args:
            ast: 逻辑语法树
            text: 待处理文本
            event: 当前事件对象
        用法：
        ```python
        matched = LogicTemplate.eval_question(ast, "你好", event)
        ```
        """
        return eval_logic(ast, text, False, event)

    @staticmethod
    def eval_answer(ast: tuple, text: str, variables: dict[str, str], event: Event | None = None) -> str | None:
        """执行答案侧逻辑计算。
        Args:
            ast: 逻辑语法树
            text: 待处理文本
            variables: 模板变量字典
            event: 当前事件对象
        用法：
        ```python
        result = LogicTemplate.eval_answer(ast, "你好", {}, event)
        ```
        """
        return eval_logic_output(ast, text, variables, False, event)
