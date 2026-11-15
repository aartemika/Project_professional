"""Проверка серверного поиска SuperJob без сетевых запросов."""

from io import BytesIO
import socket
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse

from test_system import app, browser_login
from backend.api import superjob_api


def test_search_uses_server_key_and_shows_source(app, monkeypatch):
    monkeypatch.setenv("SUPERJOB_API_KEY", "test-secret")
    requests = []

    def fake_urlopen(req, timeout):
        requests.append(req)
        assert timeout == 12
        return BytesIO(b'{"total":1,"objects":[{"profession":"Programmer","firm_name":"Acme","town":{"title":"Kazan"},"payment_from":100000,"payment_to":150000,"currency":"rub","link":"https://kazan.superjob.ru/vakansii/123.html"}]}')

    monkeypatch.setattr(superjob_api, "urlopen", fake_urlopen)
    client = app.test_client()
    browser_login(client)
    result = client.get("/superjob?search=1&keyword=Programmer&town=Kazan")
    assert result.status_code == 200
    assert "Programmer" in result.text
    assert "https://kazan.superjob.ru/vakansii/123.html" in result.text
    assert "test-secret" not in result.text
    assert requests[0].get_header("X-api-app-id") == "test-secret"
    assert parse_qs(urlparse(requests[0].full_url).query)["town"] == ["Kazan"]


def test_missing_key_does_not_call_superjob(app, monkeypatch):
    monkeypatch.delenv("SUPERJOB_API_KEY", raising=False)
    monkeypatch.setattr(superjob_api, "KEY_FILE", superjob_api.KEY_FILE.with_name("missing-key-for-test"))
    monkeypatch.setattr(superjob_api, "urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected request")))
    client = app.test_client()
    browser_login(client)
    result = client.get("/superjob?search=1&keyword=Programmer")
    assert result.status_code == 200
    assert "Ключ SuperJob ещё не добавлен" in result.text


def test_dns_failure_names_the_server_computer_without_exposing_key(app, monkeypatch):
    monkeypatch.setenv("SUPERJOB_API_KEY", "test-secret")
    monkeypatch.setattr(superjob_api, "urlopen", lambda *args, **kwargs: (
        _ for _ in ()).throw(URLError(socket.gaierror("getaddrinfo failed"))))
    client = app.test_client()
    browser_login(client)
    result = client.get("/superjob?search=1&keyword=Welder&town=Moscow")
    assert result.status_code == 200
    assert "Не удаётся найти адрес API SuperJob" in result.text
    assert "test-secret" not in result.text


def test_more_results_keeps_search_and_appends_next_page(app, monkeypatch):
    monkeypatch.setenv("SUPERJOB_API_KEY", "test-secret")
    requested_pages = []

    def fake_urlopen(req, timeout):
        page = int(parse_qs(urlparse(req.full_url).query)["page"][0])
        requested_pages.append(page)
        assert parse_qs(urlparse(req.full_url).query)["keyword"] == ["Welder"]
        assert parse_qs(urlparse(req.full_url).query)["town"] == ["Moscow"]
        body = ('{"total":45,"more":true,"objects":[{"profession":"Job %s","link":"https://moskva.superjob.ru/vakansii/%s.html"}]}' % (page, page)).encode()
        return BytesIO(body)

    monkeypatch.setattr(superjob_api, "urlopen", fake_urlopen)
    client = app.test_client()
    browser_login(client)
    first = client.get("/superjob?search=1&keyword=Welder&town=Moscow")
    assert first.status_code == 200
    assert 'id="sj-more"' in first.text
    assert "Вакансии SuperJob" in first.text
    second = client.get("/superjob/more?keyword=Welder&town=Moscow&page=1")
    assert second.status_code == 200
    assert "Job 1" in second.json["html"]
    assert second.json["next_page"] == 2
    assert second.json["has_more"] is True
    assert requested_pages == [0, 1]
    assert client.get("/superjob/more?keyword=Welder&page=25").status_code == 400


def test_more_button_shows_actual_remaining_count(app, monkeypatch):
    monkeypatch.setenv("SUPERJOB_API_KEY", "test-secret")
    monkeypatch.setattr(superjob_api, "urlopen", lambda req, timeout: BytesIO(
        b'{"total":25,"more":true,"objects":[' +
        b','.join(b'{"profession":"Welder"}' for _ in range(20)) + b']}'))
    client = app.test_client()
    browser_login(client)
    result = client.get("/superjob?search=1&keyword=Welder&town=Moscow")
    assert result.status_code == 200
    assert "Показать ещё 5 вакансий" in result.text
