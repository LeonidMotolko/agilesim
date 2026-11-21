import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from agilesim.core.constants import HEADER_REQUEST_ID
from agilesim.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    RuleViolationError,
    UnauthorizedError,
    register_error_handlers,
)
from agilesim.core.logging import JsonFormatter, install_request_logging


class Payload(BaseModel):
    count: int


def make_client() -> TestClient:
    app = FastAPI()
    register_error_handlers(app)
    install_request_logging(app)

    @app.get("/not-found")
    def not_found() -> None:
        raise NotFoundError("no such thing")

    @app.get("/conflict")
    def conflict() -> None:
        raise ConflictError("already there")

    @app.get("/rule")
    def rule() -> None:
        raise RuleViolationError("WIP limit Testing 2/2")

    @app.get("/unauthorized")
    def unauthorized() -> None:
        raise UnauthorizedError("log in first")

    @app.get("/forbidden")
    def forbidden() -> None:
        raise ForbiddenError("not your team")

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    @app.post("/payload")
    def payload(body: Payload) -> Payload:
        return body

    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize(
    ("path", "status", "code"),
    [
        ("/not-found", 404, "not_found"),
        ("/conflict", 409, "conflict"),
        ("/rule", 422, "rule_violation"),
        ("/unauthorized", 401, "unauthorized"),
        ("/forbidden", 403, "forbidden"),
    ],
)
def test_domain_errors_map_to_status_and_uniform_body(path: str, status: int, code: str) -> None:
    response = make_client().get(path)

    assert response.status_code == status
    assert response.json()["error"]["code"] == code


def test_unauthorized_asks_for_a_bearer_token() -> None:
    assert make_client().get("/unauthorized").headers["WWW-Authenticate"] == "Bearer"


def test_unexpected_error_hides_internals() -> None:
    response = make_client().get("/boom")

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "Internal server error"}
    }


def test_validation_error_lists_the_fields() -> None:
    response = make_client().post("/payload", json={"count": "many"})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"][0]["field"] == "count"


def test_unknown_route_uses_the_same_error_format() -> None:
    response = make_client().get("/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "http_error"


def test_request_id_is_generated_and_echoed() -> None:
    client = make_client()

    generated = client.get("/not-found").headers[HEADER_REQUEST_ID]
    echoed = client.get("/not-found", headers={HEADER_REQUEST_ID: "abc-123"})

    assert len(generated) == 32
    assert echoed.headers[HEADER_REQUEST_ID] == "abc-123"


def test_json_formatter_writes_one_json_object_with_extra_fields() -> None:
    record = logging.LogRecord(
        "agilesim.test", logging.INFO, __file__, 1, "hello %s", ("you",), None
    )
    record.team_id = "t-1"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "hello you"
    assert payload["level"] == "INFO"
    assert payload["team_id"] == "t-1"
