from nonebot.adapters import Event

from .answer_template import AnswerTemplate
from .assign_template import AssignTemplate
from .logic_template import LogicTemplate
from .question_template import QuestionTemplate
from .random_template import RandomTemplate
from .time_template import TimeTemplate


def _ast_has_if(node: tuple) -> bool:
    op = node[0]
    if op == "IF":
        return True
    if op == "ATOM":
        return False
    for child in node[1:]:
        if isinstance(child, tuple) and _ast_has_if(child):
            return True
    return False


class TemplateLogicEngine:
    def __init__(self) -> None:
        """初始化模板逻辑引擎。
        Args:
            无
        
        用法：
        ```python
        engine = TemplateLogicEngine()
        ```
        """
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
        """匹配问题模板并提取变量。
        Args:
            question_tmpl: 问题模板字符串
            text: 待处理文本
            event: 当前事件对象
        用法：
        ```python
        vars = engine.match_question("你好[name]", "你好世界", event)
        ```
        """
        logic_tokens = self.logic_template.tokenize(question_tmpl)
        logic_ast = self.logic_template.parse(logic_tokens)
        if logic_ast is not None:
            # 约束：question 侧使用逻辑表达式做判断时，必须显式带 [if]
            if self.logic_template.has_ops(logic_tokens) and not _ast_has_if(logic_ast):
                return None
            return self.logic_template.eval_question(logic_ast, text, event)
        return self.question_template.match_with_event(question_tmpl, text, event)

    def render_answer(
        self,
        answer_tmpl: str,
        text: str,
        variables: dict[str, str],
        event: Event | None = None,
    ) -> str | None:
        """渲染答案模板内容。
        Args:
            answer_tmpl: 答案模板字符串
            text: 待处理文本
            variables: 模板变量字典
            event: 当前事件对象
        用法：
        ```python
        reply = engine.render_answer("你好[name]", "你好世界", {"name": "世界"}, event)
        ```
        """
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
        """执行问题匹配并直接渲染答案。
        Args:
            question_tmpl: 问题模板字符串
            answer_tmpl: 答案模板字符串
            text: 待处理文本
            event: 当前事件对象
        用法：
        ```python
        reply = engine.match_and_render("你好[name]", "你好[name]", "你好世界", event)
        ```
        """
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
    """执行模板匹配并渲染回答。
    Args:
        question_tmpl: 问题模板字符串
        answer_tmpl: 答案模板字符串
        text: 待处理文本
        event: 当前事件对象
    用法：
    ```python
    reply = match_and_render("你好[name]", "你好[name]", "你好世界", event)
    ```
    """
    return _template_logic_engine.match_and_render(question_tmpl, answer_tmpl, text, event)
