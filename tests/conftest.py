"""A fake HTTP session, so the tests never touch the network."""

from __future__ import annotations

import json as jsonlib
from typing import Any

import pytest

import whagent
from whagent import Client


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        json_body: Any = None,
        *,
        content: bytes = b"",
        text: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._json = json_body
        self.headers = headers or {}
        self.content = content if content else (
            jsonlib.dumps(json_body).encode() if json_body is not None else b""
        )
        self.text = text if text is not None else self.content.decode("utf-8", "replace")

    def json(self) -> Any:
        if self._json is None:
            raise ValueError("no json body")
        return self._json

    def iter_content(self, chunk_size: int = 1024):
        for start in range(0, len(self.content), chunk_size):
            yield self.content[start : start + chunk_size]


class FakeSession:
    """Serves queued responses and records every request it was asked to make."""

    def __init__(self, responses: list[FakeResponse] | None = None) -> None:
        self.responses = list(responses or [])
        self.requests: list[dict[str, Any]] = []
        self.closed = False
        self.default = FakeResponse(200, {"ok": True})

    def queue(self, *responses: FakeResponse) -> "FakeSession":
        self.responses.extend(responses)
        return self

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.requests.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0) if self.responses else self.default

    def close(self) -> None:
        self.closed = True

    # -- assertions helpers -------------------------------------------- #

    @property
    def last(self) -> dict[str, Any]:
        return self.requests[-1]

    @property
    def last_json(self) -> Any:
        return self.requests[-1].get("json")


def error_body(code: int, message: str = "boom", details: str | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"message": message, "type": "OAuthException", "code": code,
                             "fbtrace_id": "AW7bqWj4"}
    if details:
        error["error_data"] = {"messaging_product": "whatsapp", "details": details}
    return {"error": error}


def send_ok(wamid: str = "wamid.HBgTEST", wa_id: str = "user:50972923564215") -> FakeResponse:
    return FakeResponse(200, {
        "messaging_product": "whatsapp",
        "contacts": [{"input": wa_id, "wa_id": wa_id}],
        "messages": [{"id": wamid}],
    })


def update_body(
    *,
    messages: list[dict] | None = None,
    statuses: list[dict] | None = None,
    contacts: list[dict] | None = None,
    next_offset: int = 1,
) -> dict[str, Any]:
    return {
        "object": "whatsapp_agent_platform",
        "entry": [{
            "id": "123456789",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "contacts": contacts if contacts is not None else [],
                    "messages": messages or [],
                    "statuses": statuses or [],
                },
            }],
        }],
        "next_offset": next_offset,
    }


def text_message(body: str = "Hello agent", *, wamid: str = "wamid.IN1", sender: str = "user:5") -> dict:
    return {"from": sender, "id": wamid, "timestamp": "1736844652", "type": "text",
            "text": {"body": body}}


@pytest.fixture
def session() -> FakeSession:
    return FakeSession()


@pytest.fixture
def client(session: FakeSession) -> Client:
    return Client("test-token", session=session, rate_limit=False, max_retries=0)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make retry backoffs instant."""
    monkeypatch.setattr(whagent.client.time, "sleep", lambda _seconds: None)
