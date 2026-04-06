from typing import Any

from nonebot.adapters import Event

from .segment_field_template import (
    eval_segment_field_expression,
    parse_segment_field_expression,
)
from .constants import _ASSIGN_VAR_RE
from .random_template import (
    parse_random_choice_spec,
    parse_random_spec,
    render_random_choice,
    render_random_number,
)
from .time_template import parse_time_spec, render_time_value


def parse_question_assign_spec(name: str) -> tuple[str, str] | None:
    if "=" not in name:
        return None
    left, right = name.split("=", 1)
    var_name = left.strip()
    expr = right.strip()
    if not var_name or not expr:
        return None
    if (
        parse_random_spec(expr) is None
        and parse_time_spec(expr) is None
        and parse_segment_field_expression(expr) is None
    ):
        return None
    return var_name, expr


def parse_answer_assign_spec(name: str) -> tuple[str, str] | None:
    if "=" not in name:
        return None
    left, right = name.split("=", 1)
    var_name = left.strip()
    expr = right.strip()
    if not var_name or not expr:
        return None
    if _ASSIGN_VAR_RE.fullmatch(var_name) is None:
        return None
    return var_name, expr


def eval_question_assign_expression(expr: str, event: Event | None = None) -> str | None:
    random_number = render_random_number(expr)
    if random_number is not None:
        return random_number

    time_value = render_time_value(expr)
    if time_value is not None:
        return time_value

    if event is not None:
        return eval_segment_field_expression(event, expr)
    return None


def eval_answer_assign_expression(expr: str, variables: dict[str, str]) -> str:
    time_value = render_time_value(expr)
    if time_value is not None:
        return time_value

    random_number = render_random_number(expr)
    if random_number is not None:
        return random_number

    if parse_random_choice_spec(expr) is not None:
        random_choice = render_random_choice(expr, variables)
        return random_choice if random_choice is not None else ""

    return expr


class AssignTemplate:
    @staticmethod
    def parse(spec: str) -> tuple[str, str] | None:
        return parse_question_assign_spec(spec)

    @staticmethod
    def parse_answer(spec: str) -> tuple[str, str] | None:
        return parse_answer_assign_spec(spec)

    @staticmethod
    def eval(expr: str) -> str | None:
        return eval_question_assign_expression(expr)

    @staticmethod
    def eval_with_event(expr: str, event: Event | None = None) -> str | None:
        return eval_question_assign_expression(expr, event)

    @staticmethod
    def eval_answer(expr: str, variables: dict[str, str]) -> str:
        return eval_answer_assign_expression(expr, variables)
