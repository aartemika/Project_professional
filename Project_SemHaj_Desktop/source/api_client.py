"""Запросы к Flask API с тайм-аутом и понятными ошибками."""
from typing import Any
import requests

class ApiClient:
    """Клиент HTTP API с токеном только в оперативной памяти."""
    def __init__(self, base_url: str) -> None:
        """Сохранить базовый адрес сервера."""
        self.base_url = base_url.rstrip("/")
        self.token = ""

    def request(self, method: str, path: str, **kwargs: Any) -> dict:
        """Выполнить запрос и проверить статус и структуру ответа."""
        try:
            response = requests.request(method, self.base_url + path,
                headers={"Authorization": "Bearer " + self.token} if self.token else {}, timeout=(3, 30), **kwargs)
        except requests.RequestException as error:
            raise RuntimeError("Не удалось связаться с сервером. Проверьте адрес и запуск Flask.") from error
        try:
            data = response.json()
        except ValueError as error:
            raise RuntimeError("Сервер вернул неожиданный ответ. Проверьте адрес API.") from error
        if response.status_code == 401:
            raise RuntimeError("Неверные учётные данные или истёк сеанс. Войдите заново.")
        if not response.ok:
            raise RuntimeError(data.get("error", "Ошибка HTTP " + str(response.status_code)))
        return data

    def login(self, username: str, password: str) -> dict:
        """Авторизоваться на сервере и сохранить подписанный токен."""
        result = self.request("POST", "/api/login", json={"username": username, "password": password})
        self.token = result["token"]
        return result

    def references(self) -> dict:
        """Получить справочники для фильтров."""
        return self.request("GET", "/api/references")

    def summary(self, category: str, cities: list[str]) -> dict:
        """Получить аналитику для выбранного среза."""
        params = [("category", category)] + [("city", city) for city in cities]
        return self.request("GET", "/api/summary", params=params)
