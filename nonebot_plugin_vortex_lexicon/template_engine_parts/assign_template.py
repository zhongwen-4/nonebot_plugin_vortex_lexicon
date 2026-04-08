from nonebot.adapters import Event

from .event_field_template import (
    eval_event_field_expression,
    parse_event_field_expression,
)
from .segment_field_template import (
    eval_segment_field_expression,
    parse_segment_field_expression,
)
from .constants import _ASSIGN_VAR_RE
from .random_template import (
    parse_random_choice_spec,
    render_random_choice,
    render_random_number,
)
from .time_template import render_time_value


def parse_question_assign_spec(name: str) -> tuple[str, str] | None:
    """解析问题模板中的赋值表达式。
    Args:
        name: 模板表达式
    用法：
    ```python
    spec = parse_question_assign_spec("num=随机操作.取随机数.1.10")
    ```
    """
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


def parse_answer_assign_spec(name: str) -> tuple[str, str] | None:
    """解析答案模板中的赋值表达式。
    Args:
        name: 模板表达式
    用法：
    ```python
    spec = parse_answer_assign_spec("msg=时间.取时间戳_秒")
    ```
    """
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
    """计算问题模板赋值表达式的结果。
    Args:
        expr: 表达式字符串
        event: 当前事件对象
    用法：
    ```python
    value = eval_question_assign_expression("时间.取时间戳_秒", event)
    ```
    """
    random_number = render_random_number(expr)
    if random_number is not None:
        return random_number

    time_value = render_time_value(expr)
    if time_value is not None:
        return time_value

    segment_spec = parse_segment_field_expression(expr)
    if segment_spec is not None:
        if event is None:
            return None
        return eval_segment_field_expression(event, expr)

    event_spec = parse_event_field_expression(expr)
    if event_spec is not None:
        if event is None:
            return None
        return eval_event_field_expression(event, expr)

    return expr


def eval_answer_assign_expression(expr: str, variables: dict[str, str]) -> str:
    """计算答案模板赋值表达式的结果。
    Args:
        expr: 表达式字符串
        variables: 模板变量字典
    用法：
    ```python
    value = eval_answer_assign_expression("随机操作.从列表.msg", {"msg": "甲||乙"})
    ```
    """
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
        """解析问题模板赋值规则。
        Args:
            spec: 模板表达式
        用法：
        ```python
        spec = AssignTemplate.parse("num=随机操作.取随机数.1.10")
        ```
        """
        return parse_question_assign_spec(spec)

    @staticmethod
    def parse_answer(spec: str) -> tuple[str, str] | None:
        """解析答案模板赋值规则。
        Args:
            spec: 模板表达式
        用法：
        ```python
        spec = AssignTemplate.parse_answer("msg=时间.取时间戳_秒")
        ```
        """
        return parse_answer_assign_spec(spec)

    @staticmethod
    def eval(expr: str) -> str | None:
        """计算不依赖事件的问题赋值表达式。
        Args:
            expr: 表达式字符串
        用法：
        ```python
        value = AssignTemplate.eval("时间.取时间戳_秒")
        ```
        """
        return eval_question_assign_expression(expr)

    @staticmethod
    def eval_with_event(expr: str, event: Event | None = None) -> str | None:
        """计算带事件上下文的问题赋值表达式。
        Args:
            expr: 表达式字符串
            event: 当前事件对象
        用法：
        ```python
        value = AssignTemplate.eval_with_event("at.user_id", event)
        ```
        """
        return eval_question_assign_expression(expr, event)

    @staticmethod
    def eval_answer(expr: str, variables: dict[str, str]) -> str:
        """计算答案赋值表达式。
        Args:
            expr: 表达式字符串
            variables: 模板变量字典
        用法：
        ```python
        value = AssignTemplate.eval_answer("随机操作.从列表.msg", {"msg": "甲||乙"})
        ```
        """
        return eval_answer_assign_expression(expr, variables)
