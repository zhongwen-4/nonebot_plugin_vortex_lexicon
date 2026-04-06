from nonebot.adapters import Event

from .answer_template import AnswerTemplate
from .assign_template import AssignTemplate
from .logic_template import LogicTemplate
from .question_template import QuestionTemplate
from .random_template import RandomTemplate
from .time_template import TimeTemplate


class TemplateLogicEngine:
    def __init__(self) -> None:
        self.random_template = RandomTemplate()
        self.time_template = TimeTemplate()
        self.assign_template = AssignTemplate()
        self.question_template = QuestionTemplate()
        self.answer_template = AnswerTemplate()
        self.logic_template = LogicTemplate()

    def match_question(
        self,
        question_tmpl: str,
        text: str,
        event: Event | None = None,
    ) -> dict[str, str] | None:
        logic_tokens = self.logic_template.tokenize(question_tmpl)
        logic_ast = self.logic_template.parse(logic_tokens)
        if logic_ast is not None:
            return self.logic_template.eval_question(logic_ast, text, event)
        return self.question_template.match_with_event(question_tmpl, text, event)

    def render_answer(
        self,
        answer_tmpl: str,
        text: str,
        variables: dict[str, str],
        event: Event | None = None,
    ) -> str | None:
        answer_tokens = self.logic_template.tokenize(answer_tmpl)
        if not self.logic_template.has_ops(answer_tokens):
            return self.answer_template.render(answer_tmpl, variables)

        answer_ast = self.logic_template.parse(answer_tokens)
        if answer_ast is None:
            return self.answer_template.render(answer_tmpl, variables)
        return self.logic_template.eval_answer(answer_ast, text, variables, event)

    def match_and_render(
        self,
        question_tmpl: str,
        answer_tmpl: str,
        text: str,
        event: Event | None = None,
    ) -> str | None:
        variables = self.match_question(question_tmpl, text, event)
        if variables is None:
            return None
        return self.render_answer(answer_tmpl, text, variables, event)


_template_logic_engine = TemplateLogicEngine()


def match_and_render(
    question_tmpl: str,
    answer_tmpl: str,
    text: str,
    event: Event | None = None,
) -> str | None:
    return _template_logic_engine.match_and_render(question_tmpl, answer_tmpl, text, event)
