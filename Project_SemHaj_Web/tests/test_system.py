"""Проверки метрик, доступа, транзакций и экспортов."""
from pathlib import Path
from collections.abc import Iterator
import re
import pandas as pd
import pytest
from flask import Flask
from werkzeug.security import generate_password_hash
from main import create_app
from backend.database.models import db, User, Vacancy
from backend.services import import_dataset, summary
from backend.dataset import load_dataset

@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Flask]:
    """Создать изолированную БД с небольшим известным набором."""
    monkeypatch.setenv("ADMIN_PASSWORD", "testing-password-123")
    data = pd.DataFrame([
        {"vacancy_id": 1, "name": "Программист", "area_name": "Москва", "category": "IT", "salary_from_rub": 100, "salary_to_rub": 200, "responses_count": 10, "is_remote": True},
        {"vacancy_id": 2, "name": "Аналитик", "area_name": "Москва", "category": "IT", "salary_from_rub": 300, "salary_to_rub": 500, "responses_count": 30},
        {"vacancy_id": 3, "name": "Разработчик", "area_name": "Казань", "category": "IT", "salary_from_rub": 200, "responses_count": None},
        {"vacancy_id": 4, "name": "Врач", "area_name": "Казань", "category": "Медицина", "salary_from_rub": None, "responses_count": 2}])
    data.to_csv(tmp_path / "test.csv", index=False)
    application = create_app({"TESTING": True, "SECRET_KEY": "test-key", "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "DATASET_DIR": str(tmp_path)})
    with application.app_context():
        import_dataset(tmp_path / "test.csv")
        db.session.add(User(username="reader", password_hash=generate_password_hash("reader-password"), active=True))
        db.session.commit()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()

def browser_login(client: object, username: str = "admin", password: str = "testing-password-123") -> None:
    """Открыть сессию через настоящую CSRF защищённую форму."""
    page = client.get("/login")
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
    assert client.post("/login", data={"username": username, "password": password, "csrf_token": csrf}).status_code == 302

def test_metrics(app: Flask) -> None:
    """Проверить медиану, пропуски, отклики и общую базу индекса."""
    with app.app_context():
        rows = summary("IT")
        moscow = next(r for r in rows if r["city"] == "Москва")
        kazan = summary("IT", ["Казань"])[0]
        assert moscow["salary"] == 275
        assert moscow["responses"] == 20
        assert moscow["remote"] == 50
        assert kazan["indicator"] == 50
        assert kazan["responses"] is None
        assert summary("Медицина")[0]["salary"] is None

def test_api_access(app: Flask) -> None:
    """Проверить авторизацию JSON API и валидацию входных данных."""
    client = app.test_client()
    assert client.get("/api/summary").status_code == 401
    assert client.post("/api/login", json=[]).status_code == 400
    assert client.post("/api/login", json={"username": "admin", "password": "wrong"}).status_code == 401
    token = client.post("/api/login", json={"username": "admin", "password": "testing-password-123"}).json["token"]
    headers = {"Authorization": "Bearer " + token}
    assert len(client.get("/api/references", headers=headers).json["cities"]) == 2
    assert len(client.get("/api/summary?category=IT&city=Казань", headers=headers).json["rows"]) == 1
    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.username == "admin"))
        user.active = False
        db.session.commit()
    assert client.get("/api/summary", headers=headers).status_code == 401

def test_web_and_exports(app: Flask) -> None:
    """Проверить HTML страницы, PNG, PDF, CSRF и ошибки."""
    client = app.test_client()
    assert client.get("/").status_code == 302
    assert client.post("/logout").status_code == 400
    browser_login(client)
    for path in ["/", "/admin/", "/vacancies", "/help", "/contacts"]:
        assert client.get(path).status_code == 200, path
    assert client.get("/chart.png").data.startswith(b"\x89PNG")
    assert client.get("/chart.png?kind=map").data.startswith(b"\x89PNG")
    assert client.get("/report.pdf").data.startswith(b"%PDF")
    assert client.get("/chart.png?kind=bad").status_code == 400
    assert client.get("/vacancies?page=bad").status_code == 400
    assert client.get("/missing").status_code == 404
    assert client.get("/api/missing").is_json

def test_reader_forbidden(app: Flask) -> None:
    """Запретить аналитику административные действия."""
    client = app.test_client()
    browser_login(client, "reader", "reader-password")
    assert client.get("/admin/").status_code == 403

def test_bad_import_preserves_database(app: Flask, tmp_path: Path) -> None:
    """Не изменять БД при некорректном или пустом CSV."""
    path = tmp_path / "bad.csv"
    path.write_text("vacancy_id,name,area_name,category\n", encoding="utf-8")
    with app.app_context():
        with pytest.raises(ValueError):
            import_dataset(path)
        assert db.session.scalar(db.select(db.func.count()).select_from(Vacancy)) == 4

def test_deduplication_and_monthly_salary(tmp_path: Path) -> None:
    """Не считать дубли и почасовые предложения месячной зарплатой."""
    path = tmp_path / "input.csv"
    pd.DataFrame([
        {"vacancy_id": 1, "name": "A", "area_name": "X", "category": "IT", "snapshot_date": "2026-01-01", "salary_mode": "MONTH", "salary_from_rub": 100},
        {"vacancy_id": 1, "name": "A", "area_name": "X", "category": "IT", "snapshot_date": "2026-01-02", "salary_mode": "HOUR", "salary_from_rub": 200},
        {"vacancy_id": 2, "name": None, "area_name": "X", "category": "IT"}]).to_csv(path, index=False)
    data, report = load_dataset(path)
    assert len(data) == 1
    assert data.salary.isna().all()
    assert report["removed_rows"] == 2


@pytest.mark.parametrize("entity,payload,change", [
    ("cities", {"name": "Тестовый город"}, {"name": "Новый город"}),
    ("categories", {"name": "Тестовая область"}, {"name": "Новая область"}),
    ("formats", {"name": "Тестовый формат"}, {"name": "Новый формат"}),
    ("users", {"username": "tester", "password": "testing-12345", "active": True, "is_admin": False}, {"username": "tester2"}),
    ("imports", {"filename": "manual.csv", "rows": 10}, {"rows": 11})])
def test_crud_roundtrip(app: Flask, entity: str, payload: dict, change: dict) -> None:
    """Выполнить создание, чтение, изменение и удаление каждой таблицы."""
    client = app.test_client()
    token = client.post("/api/login", json={"username": "admin", "password": "testing-password-123"}).json["token"]
    headers = {"Authorization": "Bearer " + token}
    base = "/api/admin/" + entity
    response = client.post(base, json=payload, headers=headers)
    assert response.status_code == 201, response.json
    identifier = str(response.json["id"])
    assert client.get(base + "/" + identifier, headers=headers).status_code == 200
    assert client.get(base, headers=headers).json["total"] > 0
    assert client.put(base + "/" + identifier, json=change, headers=headers).status_code == 200
    assert client.delete(base + "/" + identifier, headers=headers).status_code == 200
    assert client.get(base + "/" + identifier, headers=headers).status_code == 404
    browser_login(client)
    assert client.get("/admin/data/" + entity).status_code == 200

def test_vacancy_crud_and_links(app: Flask) -> None:
    """Проверить CRUD вакансии, внешние ключи и запрет удаления занятого города."""
    client = app.test_client()
    token = client.post("/api/login", json={"username": "admin", "password": "testing-password-123"}).json["token"]
    headers = {"Authorization": "Bearer " + token}
    refs = {key: client.get("/api/admin/" + key, headers=headers).json["rows"][0]["id"] for key in ["cities", "categories", "formats"]}
    payload = {"id": "extra-1", "name": "Новая вакансия", "city_id": refs["cities"],
        "category_id": refs["categories"], "format_id": refs["formats"], "salary": 100000, "remote": True}
    url = "/api/admin/vacancies"
    assert client.post(url, json=payload, headers=headers).status_code == 201
    assert client.get(url + "/extra-1", headers=headers).json["salary"] == 100000
    assert client.put(url + "/extra-1", json={"salary": 120000}, headers=headers).status_code == 200
    assert client.delete("/api/admin/cities/" + str(refs["cities"]), headers=headers).status_code == 400
    assert client.put(url + "/extra-1", json={"city_id": 999999}, headers=headers).status_code == 400
    assert client.put(url + "/extra-1", json={"salary": -1}, headers=headers).status_code == 400
    assert client.delete(url + "/extra-1", headers=headers).status_code == 200
    token = client.post("/api/login", json={"username": "reader", "password": "reader-password"}).json["token"]
    assert client.get(url, headers={"Authorization": "Bearer " + token}).status_code == 403

def test_import_transaction_rollback(app: Flask, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Сохранить старые данные при сбое уже внутри транзакции импорта."""
    with app.app_context():
        original = db.session.execute
        def broken(statement: object, *args: object, **kwargs: object) -> object:
            """Имитировать сбой вставки вакансий после удаления старого набора."""
            if getattr(statement, "is_insert", False):
                raise RuntimeError("Имитированный сбой записи")
            return original(statement, *args, **kwargs)
        monkeypatch.setattr(db.session, "execute", broken)
        with pytest.raises(RuntimeError):
            import_dataset(tmp_path / "test.csv")
        monkeypatch.setattr(db.session, "execute", original)
        assert db.session.scalar(db.select(db.func.count()).select_from(Vacancy)) == 4
