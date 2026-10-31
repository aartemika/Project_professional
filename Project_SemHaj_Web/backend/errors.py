"""Единые HTML и JSON ответы об ошибках."""
from flask import Flask, request, render_template, jsonify
from werkzeug.exceptions import HTTPException
from .database.models import db

def register_errors(app: Flask) -> None:
    """Зарегистрировать обработчики HTTP и внутренних ошибок."""
    @app.errorhandler(HTTPException)
    def http_error(error: HTTPException) -> tuple:
        """Вернуть ожидаемую ошибку в формате клиента."""
        messages = {400: "Некорректный запрос", 401: "Требуется авторизация", 403: "Доступ запрещён",
                    404: "Страница или запись не найдена", 405: "Метод не поддерживается"}
        message = messages.get(error.code, error.name)
        if error.code == 400:
            message = error.description
        if request.path.startswith("/api/"):
            return jsonify(error=message), error.code
        return render_template("error.html", code=error.code, message=message), error.code

    @app.errorhandler(Exception)
    def internal_error(error: Exception) -> tuple:
        """Откатить транзакцию и скрыть внутренние сведения от клиента."""
        db.session.rollback()
        app.logger.exception("Ошибка обработки запроса")
        if request.path.startswith("/api/"):
            return jsonify(error="Внутренняя ошибка сервера"), 500
        return render_template("error.html", code=500, message="Внутренняя ошибка сервера"), 500
