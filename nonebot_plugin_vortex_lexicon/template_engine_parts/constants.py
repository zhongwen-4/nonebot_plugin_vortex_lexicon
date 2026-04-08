import re

_VAR_TOKEN_RE = re.compile(r"\[([^\[\]]+)\]")

_OP_OR = "OR"
_OP_AND = "AND"
_OP_NOT = "NOT"
_OP_XOR = "XOR"
_OP_IN = "IN"
_OP_NOT_IN = "NOT_IN"
_OP_EQ = "EQ"
_OP_NE = "NE"
_OP_LE = "LE"
_OP_GE = "GE"
_OP_IF = "IF"
_OP_ELSE = "ELSE"

_OP_ALIASES: dict[str, set[str]] = {
    _OP_OR: {"or", "或者", "或", "||"},
    _OP_AND: {"and", "并且", "且", "同时", "&&", "&"},
    _OP_NOT: {"not", "非", "不是", "!"},
    _OP_XOR: {"xor", "异或"},
    _OP_IN: {"in", "包含", "contains"},
    _OP_NOT_IN: {"not in", "notin", "不包含"},
    _OP_EQ: {"==", "eq", "equals", "等于"},
    _OP_NE: {"!=", "ne", "not equals", "not equals to", "不等于"},
    _OP_LE: {"<=", "le", "lte", "小于等于"},
    _OP_GE: {">=", "ge", "gte", "大于等于"},
    _OP_IF: {"if", "如果"},
    _OP_ELSE: {"else", "否则"},
}

_RANDOM_NAME_ALIASES = {"随机操作"}
_RANDOM_CHOICE_ALIASES = {"从列表"}
_RANDOM_NUMBER_ALIASES = {"取随机数"}

_INT_RE = re.compile(r"^-?\d+$")
_DEFAULT_RANDOM_MIN = 0
_DEFAULT_RANDOM_MAX = 100
_LEGACY_RANDOM_EXPR_RE = re.compile(r"^(?:随机操作)\s*\([^()]*\)$", re.IGNORECASE)
_ASSIGN_VAR_RE = re.compile(r"^[^\W\d]\w*$", re.UNICODE)
