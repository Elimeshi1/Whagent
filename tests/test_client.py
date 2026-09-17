"""Requests the client builds, and responses it parses."""

from __future__ import annotations

import pytest

from conftest import FakeResponse, error_body, send_ok, text_message, update_body

import whagent
from whagent import Client, ValidationError, errors


# --------------------------------------------------------------------- #
# Sending
# --------------------------------------------------------------------- #

def test_send_text_builds_the_documented_payload(client, session):
    session.queue(send_ok("wamid.OUT1"))

    result = client.send_text("user:50972923564215", "Hello! How can I help you?")

    assert session.last["method"] == "POST"
    assert session.last["url"] == "https://api.whatsapp.com/agent/v1/messages"
    assert session.last["headers"]["Authorization"] == "Bearer test-token"
    assert session.last_json == {
        "messaging_product": "whatsapp",
        "to": "user:50972923564215",
        "type": "text",
        "text": {"body": "Hello! How can I help you?"},
    }
    assert result.message_id == "wamid.OUT1"
    assert result.wa_id == "user:50972923564215"
    assert str(result) == "wamid.OUT1"


def test_send_text_with_preview_and_quote(client, session):
    session.queue(send_ok())

    client.send_text("user:5", "https://example.com", preview_url=True, reply_to="wamid.IN1")

    assert session.last_json["text"] == {"body": "https://example.com", "preview_url": True}
    assert session.last_json["context"] == {"message_id": "wamid.IN1"}


def test_reply_quotes_the_inbound_message(client, session):
    session.queue(FakeResponse(200, update_body(messages=[text_message()], next_offset=2)))
    message = client.get_updates(offset=1).messages[0]
    session.queue(send_ok())

    client.reply(message, "sure")

    assert session.last_json["to"] == "user:5"
    assert session.last_json["context"] == {"message_id": "wamid.IN1"}


@pytest.mark.parametrize("to", ["agent:123", "50972923564215", "", "user:", None, 12345])
def test_recipient_must_be_a_user_identifier(client, to):
    with pytest.raises(ValidationError):
        client.send_text(to, "hi")


def test_text_over_the_cap_is_rejected_locally(client, session):
    with pytest.raises(ValidationError, match="4096"):
        client.send_text("user:5", "x" * 4097)
    assert session.requests == []


def test_caption_over_the_cap_is_rejected_locally(client):
    with pytest.raises(ValidationError, match="1024"):
        client.send_image("user:5", media_id="abc", caption="y" * 1025)


def test_reactions_cannot_be_sent(client):
    with pytest.raises(ValidationError, match="receive-only"):
        client.send_message("user:5", "reaction", {"message_id": "wamid.1", "emoji": "👍"})


def test_sticker_rejects_a_caption(client):
    with pytest.raises(ValidationError, match="caption is not available"):
        client._send_media("user:5", "sticker", media_id="abc", file=None,
                           mime_type=None, caption="nope")


def test_send_media_needs_exactly_one_source(client):
    with pytest.raises(ValidationError, match="exactly one"):
        client.send_image("user:5")
    with pytest.raises(ValidationError, match="exactly one"):
        client.send_image("user:5", media_id="abc", file=b"bytes")


def test_send_image_uploads_then_sends(client, session, tmp_path):
    path = tmp_path / "cat.png"
    path.write_bytes(b"\x89PNG" + b"0" * 100)
    session.queue(FakeResponse(200, {"id": "media-1"}), send_ok())

    client.send_image("user:5", file=path, caption="look at this")

    upload, send = session.requests
    assert upload["url"].endswith("/media")
    assert upload["data"] == {"messaging_product": "whatsapp", "type": "image/png"}
    assert upload["files"]["file"][0] == "cat.png"
    assert upload["files"]["file"][2] == "image/png"
    assert send["json"]["image"] == {"id": "media-1", "caption": "look at this"}


def test_send_document_defaults_the_filename_to_the_uploaded_file(client, session, tmp_path):
    path = tmp_path / "invoice.pdf"
    path.write_bytes(b"%PDF-1.4 ...")
    session.queue(FakeResponse(200, {"id": "media-2"}), send_ok())

    client.send_document("user:5", file=path)

    assert session.last_json["document"] == {"id": "media-2", "filename": "invoice.pdf"}


# --------------------------------------------------------------------- #
# Updates
# --------------------------------------------------------------------- #

def test_get_updates_sends_offset_limit_and_timeout(client, session):
    session.queue(FakeResponse(200, update_body(messages=[text_message()], next_offset=1288)))

    update = client.get_updates(offset=1287, limit=50, timeout=15)

    assert session.last["params"] == {"offset": 1287, "limit": 50, "timeout": 15}
    assert update.next_offset == 1288
    assert update.agent_id == "123456789"
    assert update.messages[0].text == "Hello agent"


def test_first_poll_without_offset_omits_the_parameter(client, session):
    session.queue(FakeResponse(204))

    assert client.get_updates() is None
    assert "offset" not in session.last["params"]


def test_out_of_range_poll_arguments_are_clamped(client, session):
    session.queue(FakeResponse(204))

    client.get_updates(offset=-5, limit=500, timeout=99)

    assert session.last["params"] == {"offset": 0, "limit": 100, "timeout": 25}


def test_read_timeout_outlasts_the_long_poll(client, session):
    session.queue(FakeResponse(204))

    client.get_updates(timeout=25)

    connect_timeout, read_timeout = session.last["timeout"]
    assert read_timeout > 25


def test_poll_updates_tracks_the_offset_and_skips_empty_polls(client, session):
    session.queue(
        FakeResponse(200, update_body(messages=[text_message("one")], next_offset=11)),
        FakeResponse(204),  # timed out: no next_offset, so the offset must not move
        FakeResponse(200, update_body(messages=[text_message("two")], next_offset=12)),
    )
    saved: list[int] = []

    updates = list(client.poll_updates(offset=10, max_polls=3, on_offset=saved.append))

    assert [u.messages[0].text for u in updates] == ["one", "two"]
    assert [r["params"].get("offset") for r in session.requests] == [10, 11, 11]
    assert saved == [11, 12]


def test_poll_updates_backs_off_and_reuses_the_offset_after_a_rate_limit(client, session):
    session.queue(
        FakeResponse(429, error_body(130429), headers={"Retry-After": "0"}),
        FakeResponse(200, update_body(messages=[text_message()], next_offset=8)),
    )

    updates = list(client.poll_updates(offset=7, max_polls=2))

    assert len(updates) == 1
    assert [r["params"]["offset"] for r in session.requests] == [7, 7]


def test_poll_updates_stops_when_asked(client, session):
    session.queue(FakeResponse(200, update_body(messages=[text_message()], next_offset=2)))
    calls = {"n": 0}

    def stop() -> bool:
        calls["n"] += 1
        return calls["n"] > 1

    assert len(list(client.poll_updates(offset=1, stop=stop))) == 1


def test_a_replaced_poll_is_raised_not_retried(client, session):
    session.queue(FakeResponse(409, error_body(1752041, "newer poll")))

    with pytest.raises(errors.PollReplacedError):
        list(client.poll_updates(offset=1, max_polls=1))


# --------------------------------------------------------------------- #
# Statuses
# --------------------------------------------------------------------- #

def test_mark_read(client, session):
    session.queue(FakeResponse(200, {"success": True}))

    assert client.mark_read("wamid.IN1") is True
    assert session.last["url"].endswith("/statuses")
    assert session.last_json == {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": "wamid.IN1",
    }


def test_send_typing_marks_read_in_the_same_call(client, session):
    session.queue(FakeResponse(200, {"success": True}))

    client.send_typing("wamid.IN1")

    assert session.last_json["typing_indicator"] == {"type": "text"}
    assert session.last_json["status"] == "read"


# --------------------------------------------------------------------- #
# Media
# --------------------------------------------------------------------- #

def test_upload_media_from_bytes_with_an_explicit_mime_type(client, session):
    session.queue(FakeResponse(200, {"id": "media-9"}))

    assert client.upload_media(b"%PDF-1.4", mime_type="application/pdf", filename="r.pdf") == "media-9"
    assert session.last["files"]["file"] == ("r.pdf", b"%PDF-1.4", "application/pdf")


def test_upload_media_rejects_an_unaccepted_mime_type(client, session):
    with pytest.raises(ValidationError, match="not accepted"):
        client.upload_media(b"MZ", mime_type="application/x-msdownload", filename="a.exe")
    assert session.requests == []


def test_upload_media_enforces_the_size_limit_of_its_category(client):
    with pytest.raises(ValidationError, match="limit for sticker"):
        client.upload_media(b"0" * (600 * 1024), mime_type="image/webp", filename="s.webp")


def test_upload_media_needs_a_mime_type_it_cannot_guess(client):
    with pytest.raises(ValidationError, match="mime_type"):
        client.upload_media(b"data", filename="mystery.unknownext")


def test_upload_media_refuses_an_empty_file(client):
    with pytest.raises(ValidationError, match="empty"):
        client.upload_media(b"", mime_type="image/png", filename="empty.png")


def test_get_media_parses_metadata(client, session):
    session.queue(FakeResponse(200, {
        "url": "https://lookaside.fbsbx.com/agent/v1/media/8f3a/content",
        "mime_type": "application/pdf",
        "sha256": "a8c5",
        "file_size": 232145,
        "id": "8f3a",
        "messaging_product": "whatsapp",
    }))

    media = client.get_media("8f3a")

    assert media.file_size == 232145
    assert media.mime_type == "application/pdf"
    assert media.url.endswith("/content")


def test_download_media_fetches_the_url_with_the_token(client, session, tmp_path):
    session.queue(
        FakeResponse(200, {"id": "8f3a", "url": "https://lookaside.fbsbx.com/x/content"}),
        FakeResponse(200, content=b"file-bytes"),
    )

    assert client.download_media("8f3a") == b"file-bytes"
    assert session.last["url"] == "https://lookaside.fbsbx.com/x/content"
    assert session.last["headers"]["Authorization"] == "Bearer test-token"


def test_download_media_writes_to_a_path(client, session, tmp_path):
    destination = tmp_path / "out.pdf"
    session.queue(
        FakeResponse(200, {"id": "8f3a", "url": "https://lookaside.fbsbx.com/x/content"}),
        FakeResponse(200, content=b"pdf-bytes"),
    )

    assert client.download_media("8f3a", destination) == destination
    assert destination.read_bytes() == b"pdf-bytes"


def test_expired_media_url_raises_media_not_found(client, session):
    session.queue(
        FakeResponse(200, {"id": "8f3a", "url": "https://lookaside.fbsbx.com/x/content"}),
        FakeResponse(404, error_body(100, "unknown media id")),
    )

    with pytest.raises(errors.MediaNotFoundError):
        client.download_media("8f3a")


def test_delete_media(client, session):
    session.queue(FakeResponse(200, {"success": True}))

    assert client.delete_media("8f3a") is True
    assert session.last["method"] == "DELETE"
    assert session.last["url"].endswith("/media/8f3a")


# --------------------------------------------------------------------- #
# Errors and retries
# --------------------------------------------------------------------- #

def test_401_raises_authentication_error(client, session):
    session.queue(FakeResponse(401, error_body(190, "missing header")))

    with pytest.raises(errors.AuthenticationError) as excinfo:
        client.send_text("user:5", "hi")
    assert excinfo.value.code == 190
    assert excinfo.value.status == 401


def test_403_raises_forbidden_with_details(client, session):
    session.queue(FakeResponse(403, error_body(131005, "not the creator", "recipient must be creator")))

    with pytest.raises(errors.ForbiddenError) as excinfo:
        client.send_text("user:5", "hi")
    assert excinfo.value.details == "recipient must be creator"
    assert "recipient must be creator" in str(excinfo.value)


def test_503_131016_is_retried(session):
    client = whagent.Client("t", session=session, rate_limit=False, max_retries=2)
    session.queue(FakeResponse(503, error_body(131016, "not accepted")), send_ok("wamid.RETRY"))

    assert client.send_text("user:5", "hi").message_id == "wamid.RETRY"
    assert len(session.requests) == 2


def test_429_is_retried_up_to_max_retries(session):
    client = whagent.Client("t", session=session, rate_limit=False, max_retries=1)
    session.queue(
        FakeResponse(429, error_body(130429), headers={"Retry-After": "0"}),
        FakeResponse(429, error_body(130429), headers={"Retry-After": "0"}),
    )

    with pytest.raises(errors.RateLimitError) as excinfo:
        client.send_text("user:5", "hi")
    assert excinfo.value.retry_after == 0
    assert len(session.requests) == 2


def test_a_500_on_send_is_not_retried_by_default(session):
    client = whagent.Client("t", session=session, rate_limit=False, max_retries=3)
    session.queue(FakeResponse(500, error_body(2, "internal")))

    with pytest.raises(errors.ServerError):
        client.send_text("user:5", "hi")
    assert len(session.requests) == 1, "a retried send may deliver the message twice"


def test_a_500_on_send_is_retried_when_opted_in(session):
    client = whagent.Client("t", session=session, rate_limit=False, max_retries=2,
                            retry_send_on_server_error=True)
    session.queue(FakeResponse(500, error_body(2)), send_ok("wamid.AGAIN"))

    assert client.send_text("user:5", "hi").message_id == "wamid.AGAIN"


def test_a_500_on_a_read_is_retried(session):
    client = whagent.Client("t", session=session, rate_limit=False, max_retries=2)
    session.queue(FakeResponse(500, error_body(2)), FakeResponse(200, {"success": True}))

    assert client.delete_media("m1") is True
    assert len(session.requests) == 2


def test_a_non_json_error_body_still_raises(client, session):
    session.queue(FakeResponse(502, None, text="<html>bad gateway</html>"))

    with pytest.raises(errors.ServerError) as excinfo:
        client.mark_read("wamid.1")
    assert excinfo.value.status == 502


# --------------------------------------------------------------------- #
# Client plumbing
# --------------------------------------------------------------------- #

def test_a_token_is_required():
    with pytest.raises(ValidationError):
        Client("")


def test_context_manager_closes_an_owned_session(monkeypatch):
    client = Client("t")
    closed: list[bool] = []
    monkeypatch.setattr(client._session, "close", lambda: closed.append(True))
    with client:
        pass
    assert closed == [True]


def test_a_supplied_session_is_left_open(session):
    with Client("t", session=session):
        pass
    assert session.closed is False


def test_the_rate_limiter_paces_requests(session, monkeypatch):
    now = {"t": 0.0}
    slept: list[float] = []
    client = Client("t", session=session, rate_limit=True, max_retries=0)
    client._limiter._monotonic = lambda: now["t"]

    def sleep(seconds: float) -> None:
        slept.append(seconds)
        now["t"] += seconds

    client._limiter._sleep = sleep
    session.queue(*[send_ok() for _ in range(13)])

    for _ in range(13):  # the cap is 12 sends per minute
        client.send_text("user:5", "hi")

    assert len(slept) == 1 and slept[0] == pytest.approx(60.0)
