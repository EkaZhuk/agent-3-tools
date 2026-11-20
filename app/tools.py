import ast
import operator

import requests
from langchain_core.tools import tool

TIMEOUT = 10

OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv, ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        return OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
        return OPS[type(node.op)](_eval(node.operand))
    raise ValueError("недопустимое выражение")


@tool
def calculator(expression: str) -> str:
    """Вычисляет арифметическое выражение, например '2 + 2 * 3' или '(15 - 3) / 4' или '2 ** 10'."""
    try:
        result = _eval(ast.parse(expression, mode="eval").body)
        return f"{expression} = {round(result, 6)}"
    except ZeroDivisionError:
        return "Ошибка: деление на ноль."
    except Exception as e:
        return f"Ошибка вычисления: {e}"


@tool
def get_weather(city: str) -> str:
    """Текущая погода в городе: температура и ветер. city - название города, например 'Москва'."""
    try:
        geo = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                           params={"name": city, "count": 1, "language": "ru"}, timeout=TIMEOUT).json()
        if not geo.get("results"):
            return f"Город '{city}' не найден."
        place = geo["results"][0]
        cur = requests.get("https://api.open-meteo.com/v1/forecast", timeout=TIMEOUT, params={
            "latitude": place["latitude"], "longitude": place["longitude"], "current_weather": True,
        }).json()["current_weather"]
        return f"{place['name']} ({place.get('country', '')}): {cur['temperature']}°C, ветер {cur['windspeed']} км/ч"
    except requests.RequestException as e:
        return f"Ошибка сервиса погоды: {e}"


@tool
def currency_rate(code: str) -> str:
    """Официальный курс валюты ЦБ РФ к рублю на сегодня. code - код валюты: USD, EUR, CNY, GBP и т.д."""
    try:
        data = requests.get("https://www.cbr-xml-daily.ru/daily_json.js", timeout=TIMEOUT).json()
    except requests.RequestException as e:
        return f"Ошибка сервиса курсов: {e}"
    v = data["Valute"].get(code.strip().upper())
    if not v:
        return f"Валюта '{code}' не найдена. Примеры кодов: USD, EUR, CNY."
    return (f"{v['Nominal']} {v['CharCode']} ({v['Name']}) = {v['Value']:.4f} руб. "
            f"(вчера {v['Previous']:.4f}), дата {data['Date'][:10]}")


TOOLS = [calculator, get_weather, currency_rate]
