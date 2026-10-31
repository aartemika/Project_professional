"""Схема и проверка форм редактора данных."""
from datetime import datetime, timezone
from typing import Any
from werkzeug.security import generate_password_hash
from ..database.models import db, City, Category, WorkFormat

FIELDS = {
    "users": [("username", "Логин", "text"), ("password", "Пароль (при изменении можно оставить пустым)", "password"),
              ("is_admin", "Администратор", "bool"), ("active", "Доступ активен", "bool")],
    "cities": [("name", "Название", "text")], "categories": [("name", "Название", "text")],
    "formats": [("name", "Название", "text")],
    "vacancies": [("id", "ID источника", "text"), ("name", "Название", "text"),
        ("city_id", "Город", "city"), ("category_id", "Область", "category"), ("format_id", "Формат", "format"),
        ("company", "Работодатель", "text"), ("salary", "Зарплата руб./месяц", "number"),
        ("responses", "Отклики", "number"), ("remote", "Удалённо", "bool"), ("hybrid", "Гибрид", "bool"),
        ("on_site", "Офис", "bool"), ("publication_time", "Дата публикации", "text"),
        ("snapshot_date", "Дата снимка", "text")],
    "imports": [("filename", "Имя источника", "text"), ("rows", "Число строк", "integer"),
                ("created_at", "Дата UTC (ISO 8601, пустая = сейчас)", "datetime")]}

def validated_values(entity: str, payload: dict, item: Any = None) -> dict:
    """Проверить типы, диапазоны, обязательные поля и внешние ключи."""
    result = {}
    allowed = {field[0] for field in FIELDS[entity]}
    if set(payload) - allowed:
        raise ValueError("Обнаружены неизвестные поля")
    for name, label, kind in FIELDS[entity]:
        value = payload.get(name, getattr(item, name, None) if item else None)
        if kind == "password":
            if value:
                if not isinstance(value, str) or len(value) < 10:
                    raise ValueError("Пароль должен содержать не менее 10 символов")
                result["password_hash"] = generate_password_hash(value)
            elif item is None:
                raise ValueError("Для нового пользователя нужен пароль")
            continue
        if name == "id" and item is not None:
            if str(value) != str(item.id):
                raise ValueError("ID существующей записи менять нельзя")
            continue
        if kind == "bool":
            if value not in [True, False, 0, 1, "true", "false", "on", "", None]:
                raise ValueError("Некорректное логическое значение: " + label)
            result[name] = value in [True, 1, "true", "on"]
        elif kind in {"number", "integer"}:
            if value in ("", None) and kind == "number":
                result[name] = None
            else:
                try:
                    number = float(value)
                except (ValueError, TypeError):
                    raise ValueError("Введите число: " + label) from None
                import math
                if not math.isfinite(number) or number < 0 or (kind == "integer" and not number.is_integer()):
                    raise ValueError("Недопустимое число: " + label)
                result[name] = int(number) if kind == "integer" else number
        elif kind in {"city", "category", "format"}:
            model = {"city": City, "category": Category, "format": WorkFormat}[kind]
            try:
                identifier = int(value)
            except (TypeError, ValueError):
                raise ValueError("Выберите значение: " + label) from None
            if not db.session.get(model, identifier):
                raise ValueError("Запись справочника не найдена: " + label)
            result[name] = identifier
        elif kind == "datetime":
            try:
                parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value) if value else datetime.now(timezone.utc)
                result[name] = parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
            except (ValueError, TypeError):
                raise ValueError("Дата должна быть в формате ISO 8601") from None
        else:
            if value is None:
                value = ""
            if not isinstance(value, str) or len(value.strip()) > 300:
                raise ValueError("Слишком длинный или некорректный текст: " + label)
            value = value.strip()
            if not value and name in {"id", "name", "username", "filename"}:
                raise ValueError("Заполните поле: " + label)
            if name == "username" and not 3 <= len(value) <= 40:
                raise ValueError("Логин должен содержать от 3 до 40 символов")
            result[name] = value
    return result
