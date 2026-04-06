import re

from .assign_template import eval_answer_assign_expression, parse_answer_assign_spec
from .constants import _VAR_TOKEN_RE
from .random_template import render_random_choice, render_random_number
from .time_template import render_time_value


def render_answer_template(template: str, variables: dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        name = match.group(1).strip()
        assign_spec = parse_answer_assign_spec(name)
        if assign_spec is not None:
            var_name, expr = assign_spec
            variables[var_name] = eval_answer_assign_expression(expr, variables)
            return ""

        random_choice = render_random_choice(name, variables)
        if random_choice is not None:
            return random_choice

        time_value = render_time_value(name)
        if time_value is not None:
            return time_value

        random_number = render_random_number(name)
        if random_number is not None:
            return random_number

        return variables.get(name, match.group(0))

    return _VAR_TOKEN_RE.sub(repl, template)


class AnswerTemplate:
    @staticmethod
    def render(template: str, variables: dict[str, str]) -> str:
        return render_answer_template(template, variables)
