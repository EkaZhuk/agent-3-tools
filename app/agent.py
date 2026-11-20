import logging
import os

from langchain.agents import create_agent
from langchain.agents.middleware import wrap_tool_call
from langchain_openai import ChatOpenAI

from app.tools import TOOLS

log = logging.getLogger("agent")

SYSTEM_PROMPT = """Ты помощник. Отвечай на русском, кратко.
Инструменты:
- calculator — для любых вычислений;
- get_weather — для погоды в городе;
- currency_rate — для курсов валют ЦБ РФ.
Если вопрос не требует инструментов, отвечай сам. Помни, что пользователь говорил раньше в диалоге."""


@wrap_tool_call
def log_tool_call(request, handler):
    name, args = request.tool_call["name"], request.tool_call["args"]
    log.info("Агент выбрал инструмент: %s | аргументы: %s", name, args)
    result = handler(request)
    log.info("Результат %s: %s", name, result.content)
    return result


def build_agent(checkpointer):
    llm = ChatOpenAI(
        model=os.getenv("MODEL", "gpt-4o-mini"),
        api_key=os.environ["AITUNNEL_API_KEY"],
        base_url=os.getenv("BASE_URL", "https://api.aitunnel.ru/v1/"),
        temperature=0,
    )
    return create_agent(
        model=llm,
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
        middleware=[log_tool_call],
        checkpointer=checkpointer,
    )
