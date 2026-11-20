import argparse
import logging
import os
import uuid

from dotenv import load_dotenv
from langchain_core.messages import ToolMessage
from langgraph.checkpoint.postgres import PostgresSaver

load_dotenv()

from app.agent import build_agent  # noqa: E402

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("logs/agent.log", encoding="utf-8")],
)
for noisy in ("httpx", "httpcore", "openai", "urllib3"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
log = logging.getLogger("agent")

DEMO = [
    "Привет! Меня зовут Анна, я живу в Казани.",
    "Сколько будет (125 + 375) * 4 / 8?",
    "Какая сейчас погода в моём городе?",
    "Какой сегодня курс доллара и евро?",
    "Сколько рублей стоят 250 долларов по сегодняшнему курсу?",
    "Как меня зовут и где я живу?",
]


def langfuse_callbacks():
    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        log.warning("Ключи Langfuse не заданы — трейсинг выключен")
        return []
    from langfuse.langchain import CallbackHandler
    return [CallbackHandler()]


def ask(agent, question, session_id, callbacks):
    log.info("Сессия %s | Вопрос: %s", session_id, question)
    config = {
        "configurable": {"thread_id": session_id},
        "callbacks": callbacks,
        "metadata": {"langfuse_session_id": session_id},
    }
    before = len(agent.get_state(config).values.get("messages", []))
    result = agent.invoke({"messages": [{"role": "user", "content": question}]}, config=config)
    new = result["messages"][before:]
    used = [m.name for m in new if isinstance(m, ToolMessage)]
    if not used:
        log.info("Инструменты не понадобились, агент ответил сам")
    answer = result["messages"][-1].content
    log.info("Ответ: %s", answer)
    return answer


def main():
    parser = argparse.ArgumentParser(description="Агент с 3 инструментами")
    parser.add_argument("--session", default=os.getenv("SESSION_ID"), help="id диалога (память)")
    parser.add_argument("--demo", action="store_true", help="прогнать готовые вопросы")
    args = parser.parse_args()

    callbacks = langfuse_callbacks()
    with PostgresSaver.from_conn_string(os.environ["DATABASE_URL"]) as checkpointer:
        checkpointer.setup()
        agent = build_agent(checkpointer)
        session = args.session or (f"demo-{uuid.uuid4().hex[:6]}" if args.demo else "user-1")

        if args.demo:
            for q in DEMO:
                print(f"\nВы: {q}\nАгент: {ask(agent, q, session, callbacks)}")
        else:
            print(f"Сессия: {session}. Команды: /new — новый диалог, /exit — выход.")
            while True:
                try:
                    q = input("\nВы: ").strip()
                    # чиним "битые" символы, которые появляются при стирании кириллицы в терминале Docker
                    q = q.encode("utf-8", "surrogateescape").decode("utf-8", "replace").replace("\ufffd", "")
                except (EOFError, KeyboardInterrupt):
                    break
                if not q:
                    continue
                if q == "/exit":
                    break
                if q == "/new":
                    session = f"user-{uuid.uuid4().hex[:6]}"
                    print(f"Новая сессия: {session}")
                    continue
                print(f"Агент: {ask(agent, q, session, callbacks)}")

    if callbacks:
        from langfuse import get_client
        get_client().flush()


if __name__ == "__main__":
    main()
