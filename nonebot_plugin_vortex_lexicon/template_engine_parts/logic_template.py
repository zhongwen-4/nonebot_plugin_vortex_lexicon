from functools import lru_cache

from nonebot.adapters import Event

from .answer_template import render_answer_template
from .constants import (
    _OP_ALIASES,
    _OP_AND,
    _OP_IN,
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
    raw_tokens: list[tuple[str, str]] = []
    cursor = 0

    for match in _VAR_TOKEN_RE.finditer(template):
        literal = template[cursor:match.start()]
        if literal:
            raw_tokens.append(("text", literal))

        name = match.group(1).strip()
        op = _normalize_op_name(name)
        if op is None:
            raw_tokens.append(("text", match.group(0)))
        else:
            raw_tokens.append(("op", op))
        cursor = match.end()

    tail = template[cursor:]
    if tail:
        raw_tokens.append(("text", tail))

    tokens: list[tuple[str, str]] = []
    buffer: list[str] = []
    for kind, value in raw_tokens:
        if kind == "op":
            atom = "".join(buffer).strip()
            if atom:
                tokens.append(("atom", atom))
            buffer = []
            tokens.append(("op", value))
        else:
            buffer.append(value)

    atom = "".join(buffer).strip()
    if atom:
        tokens.append(("atom", atom))

    if not tokens:
        tokens.append(("atom", ""))
    return tuple(tokens)


def has_logic_ops(tokens: tuple[tuple[str, str], ...]) -> bool:
    return any(kind == "op" for kind, _ in tokens)


def parse_logic_expression(tokens: tuple[tuple[str, str], ...]) -> tuple | None:
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
        node = parse_unary()
        if node is None:
            return None
        while idx < len(tokens) and tokens[idx][0] == "op" and tokens[idx][1] in {_OP_AND}:
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

    root = parse_or()
    if root is None or idx != len(tokens):
        return None
    return root


def _node_has_in_operator(node: tuple) -> bool:
    op = node[0]
    if op in {_OP_IN, _OP_NOT_IN}:
        return True
    if op == "ATOM":
        return False
    if op in {_OP_NOT}:
        return _node_has_in_operator(node[1])
    if len(node) >= 3:
        return _node_has_in_operator(node[1]) or _node_has_in_operator(node[2])
    return False


def eval_logic(
    node: tuple,
    text: str,
    contains_fallback: bool = False,
    event: Event | None = None,
) -> dict[str, str] | None:
    op = node[0]
    if op == "ATOM":
        matched = match_atom_with_event(node[1], text, event)
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
        child = node[1]
        if child[0] == "ATOM":
            return contains_atom_with_event(child[1], text, event)
        return eval_logic(child, text, True, event)

    if op == _OP_NOT_IN:
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
    op = node[0]
    if op == "ATOM":
        atom_template = node[1]
        matched = match_atom_with_event(atom_template, text, event)
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
        return tokenize_logic_expression(template)

    @staticmethod
    def has_ops(tokens: tuple[tuple[str, str], ...]) -> bool:
        return has_logic_ops(tokens)

    @staticmethod
    def parse(tokens: tuple[tuple[str, str], ...]) -> tuple | None:
        return parse_logic_expression(tokens)

    @staticmethod
    def eval_question(ast: tuple, text: str, event: Event | None = None) -> dict[str, str] | None:
        return eval_logic(ast, text, False, event)

    @staticmethod
    def eval_answer(ast: tuple, text: str, variables: dict[str, str], event: Event | None = None) -> str | None:
        return eval_logic_output(ast, text, variables, False, event)
