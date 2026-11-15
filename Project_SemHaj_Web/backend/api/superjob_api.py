"""Поиск открытых вакансий SuperJob без сохранения их в учебную базу."""

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from flask import Blueprint, jsonify, render_template, request

from .auth_api import login_required

bp = Blueprint("superjob", __name__)
KEY_FILE = Path(__file__).resolve().parents[2] / "private" / "superjob.key"
API_URL = "https://api.superjob.ru/2.0/vacancies/"
PAGE_SIZE = 20
MAX_RESULTS = 500


def secret_key() -> str:
    """Ключ задаётся вне Git: переменной окружения или локальным файлом."""
    value = os.getenv("SUPERJOB_API_KEY", "").strip()
    if value:
        return value
    try:
        return KEY_FILE.read_text(encoding="utf-8-sig").strip()
    except FileNotFoundError:
        return ""


def source_link(item: dict) -> str | None:
    """Пропускать только ссылки на вакансии SuperJob по HTTPS."""
    link = item.get("link", "")
    if not isinstance(link, str):
        return None
    parsed = urlparse(link)
    if parsed.scheme == "https" and parsed.hostname and (parsed.hostname == "superjob.ru" or parsed.hostname.endswith(".superjob.ru")):
        return link
    return None


def salary_label(item: dict) -> str:
    low = item.get("payment_from") or 0
    high = item.get("payment_to") or 0
    currency = item.get("currency", "rub")
    if currency != "rub":
        return "Уточняйте в вакансии"
    if low and high:
        return f"{low:,}–{high:,} ₽".replace(",", " ")
    if low:
        return f"от {low:,} ₽".replace(",", " ")
    if high:
        return f"до {high:,} ₽".replace(",", " ")
    return "Не указана"


def search_vacancies(keyword: str, town: str, page: int) -> tuple[list[dict], int, bool]:
    params = {"keyword": keyword, "count": PAGE_SIZE, "page": page}
    if town:
        params["town"] = town
    api_request = Request(API_URL + "?" + urlencode(params), headers={
        "X-Api-App-Id": secret_key(), "Accept": "application/json"
    })
    with urlopen(api_request, timeout=12) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or payload.get("error"):
        raise ValueError("Unexpected SuperJob response")
    rows = []
    for item in payload.get("objects", []):
        city = item.get("town") or {}
        rows.append({
            "name": item.get("profession") or "Вакансия без названия",
            "company": item.get("firm_name") or "Работодатель не указан",
            "city": city.get("title", "") if isinstance(city, dict) else "",
            "salary": salary_label(item),
            "link": source_link(item),
        })
    total = payload.get("total", 0)
    more = bool(payload.get("more", total > (page + 1) * PAGE_SIZE))
    return rows, total, more and (page + 1) * PAGE_SIZE < MAX_RESULTS


@bp.get("/superjob")
@login_required
def search_page() -> str:
    keyword = request.args.get("keyword", "").strip()[:100]
    town = request.args.get("town", "").strip()[:80]
    submitted = "search" in request.args
    rows: list[dict] = []
    error = ""
    total = None
    has_more = False
    configured = bool(secret_key())

    if submitted and not configured:
        error = "Ключ SuperJob ещё не добавлен. Откройте private/superjob.key и вставьте туда Secret key."
    elif submitted and not keyword:
        error = "Укажите профессию или название вакансии."
    elif submitted:
        try:
            rows, total, has_more = search_vacancies(keyword, town, 0)
        except HTTPError as exc:
            error = "SuperJob отклонил запрос. Проверьте ключ или повторите поиск позже." if exc.code in {401, 403} else "SuperJob временно не отвечает. Повторите поиск позже."
        except (URLError, TimeoutError, ValueError, OSError):
            error = "Не удалось получить вакансии SuperJob. Проверьте интернет и повторите поиск."

    next_count = min(PAGE_SIZE, max(0, min(total or 0, MAX_RESULTS) - len(rows)))
    return render_template("superjob.html", keyword=keyword, town=town,
                           submitted=submitted, configured=configured,
                           rows=rows, total=total, has_more=has_more,
                           next_count=next_count, error=error)


@bp.get("/superjob/more")
@login_required
def more_vacancies():
    keyword = request.args.get("keyword", "").strip()[:100]
    town = request.args.get("town", "").strip()[:80]
    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        page = -1
    if not keyword or not 1 <= page < MAX_RESULTS // PAGE_SIZE:
        return jsonify(error="Неверный запрос."), 400
    if not secret_key():
        return jsonify(error="Ключ SuperJob не настроен."), 503
    try:
        rows, total, has_more = search_vacancies(keyword, town, page)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        return jsonify(error="Не удалось загрузить вакансии. Попробуйте ещё раз."), 502
    return jsonify(html=render_template("superjob_cards.html", rows=rows),
                   added=len(rows), total=total, has_more=has_more, next_page=page + 1)
