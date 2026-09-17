"""Handler registration and dispatch."""

from __future__ import annotations

import pytest

from conftest import FakeResponse, error_body, send_ok, text_message, update_body

from whagent import Agent, Client, FileOffsetStore, ValidationError
from whagent.models import Update


@pytest.fixture
def agent(client: Client) -> Agent:
    return Agent(client=client, typing=False, mark_read=False)


def make_update(*messages: dict, statuses: list[dict] | None = None, next_offset: int = 1) -> Update:
    return Update.from_dict(update_body(messages=list(messages), statuses=statuses,
                                        next_offset=next_offset))


def media_message(type: str = "image", *, wamid: str = "wamid.M1", caption: str | None = None) -> dict:
    payload = {"id": "media-1", "mime_type": "image/jpeg"}
    if caption:
        payload["caption"] = caption
    return {"from": "user:5", "id": wamid, "timestamp": "1", "type": type, type: payload}


def test_on_text_receives_a_context(agent, session):
    session.queue(send_ok())
    seen = []

    @agent.on_text
    def handle(ctx):
        seen.append(ctx.text)
        ctx.reply(f"You said: {ctx.text}")

    agent.dispatch(make_update(text_message("Hello agent")))

    assert seen == ["Hello agent"]
    assert session.last_json["text"] == {"body": "You said: Hello agent"}
    assert session.last_json["to"] == "user:5"


def test_on_text_with_a_pattern_filters(agent):
    commands, everything = [], []

    @agent.on_text(r"^/start")
    def command(ctx):
        commands.append(ctx.text)

    @agent.on_text
    def catch_all(ctx):
        everything.append(ctx.text)

    agent.dispatch(make_update(text_message("/start now", wamid="a"), text_message("hello", wamid="b")))

    assert commands == ["/start now"]
    assert everything == ["/start now", "hello"]


def test_on_message_filters_by_type(agent):
    images, audios = [], []

    @agent.on_message("image")
    def on_image(ctx):
        images.append(ctx.message.media_id)

    @agent.on_message(["audio", "video"])
    def on_audio(ctx):
        audios.append(ctx.type)

    agent.dispatch(make_update(media_message("image"), media_message("audio", wamid="wamid.M2")))

    assert images == ["media-1"]
    assert audios == ["audio"]


def test_on_media_catches_every_media_type(agent):
    seen = []
    agent.on_media(lambda ctx: seen.append(ctx.type))

    agent.dispatch(make_update(
        media_message("image", wamid="a"),
        media_message("document", wamid="b"),
        text_message("not media", wamid="c"),
    ))

    assert seen == ["image", "document"]


def test_on_reaction(agent):
    seen = []
    agent.on_reaction(lambda ctx: seen.append(ctx.message.reaction.emoji))

    agent.dispatch(make_update({
        "from": "user:5", "id": "wamid.R", "timestamp": "1", "type": "reaction",
        "reaction": {"message_id": "wamid.OUT", "emoji": "👍"},
    }))

    assert seen == ["👍"]


def test_on_status(agent):
    seen = []
    agent.on_status(lambda status: seen.append((status.status, status.id)))

    agent.dispatch(make_update(statuses=[
        {"id": "wamid.OUT", "status": "read", "recipient_id": "user:5", "timestamp": "1"},
    ]))

    assert seen == [("read", "wamid.OUT")]


def test_on_update_sees_the_whole_payload(agent):
    seen = []
    agent.on_update(lambda update: seen.append(update.next_offset))

    agent.dispatch(make_update(text_message(), next_offset=42))

    assert seen == [42]


def test_an_unknown_message_type_is_rejected_at_registration(agent):
    with pytest.raises(ValidationError, match="Unknown message type"):
        agent.on_message("carrier-pigeon")(lambda ctx: None)


def test_a_message_is_handled_once_even_if_the_offset_replays(agent):
    seen = []
    agent.on_text(lambda ctx: seen.append(ctx.text))

    agent.dispatch(make_update(text_message("once", wamid="wamid.SAME")))
    agent.dispatch(make_update(text_message("once", wamid="wamid.SAME")))

    assert seen == ["once"]


def test_replays_can_be_allowed(client):
    agent = Agent(client=client, typing=False, mark_read=False, skip_own_replays=False)
    seen = []
    agent.on_text(lambda ctx: seen.append(ctx.text))

    agent.dispatch(make_update(text_message("twice", wamid="wamid.SAME")))
    agent.dispatch(make_update(text_message("twice", wamid="wamid.SAME")))

    assert seen == ["twice", "twice"]


def test_typing_marks_read_and_shows_the_indicator(client, session):
    agent = Agent(client=client, typing=True)
    session.queue(FakeResponse(200, {"success": True}), send_ok())
    agent.on_text(lambda ctx: ctx.reply("hi"))

    agent.dispatch(make_update(text_message()))

    status_call, send_call = session.requests
    assert status_call["url"].endswith("/statuses")
    assert status_call["json"]["typing_indicator"] == {"type": "text"}
    assert send_call["url"].endswith("/messages")


def test_mark_read_without_typing(client, session):
    agent = Agent(client=client, typing=False, mark_read=True)
    session.queue(FakeResponse(200, {"success": True}))
    agent.on_text(lambda ctx: None)

    agent.dispatch(make_update(text_message()))

    assert "typing_indicator" not in session.last_json


def test_a_plain_receipt_is_sent_after_the_handlers_run(client, session):
    agent = Agent(client=client, typing=False, mark_read=True)
    session.queue(send_ok(), FakeResponse(200, {"success": True}))
    agent.on_text(lambda ctx: ctx.reply("hi"))

    agent.dispatch(make_update(text_message()))

    send_call, status_call = session.requests
    assert send_call["url"].endswith("/messages")
    assert status_call["url"].endswith("/statuses")


def test_no_receipt_is_sent_when_nothing_handles_the_message(client, session):
    agent = Agent(client=client, typing=True)
    agent.on_message("image")(lambda ctx: None)

    agent.dispatch(make_update(text_message()))

    assert session.requests == []


def test_a_failed_receipt_does_not_stop_the_handler(client, session, caplog):
    agent = Agent(client=client, typing=True)
    session.queue(FakeResponse(403, error_body(131005, "not the creator")), send_ok())
    handled = []
    agent.on_text(lambda ctx: handled.append(ctx.reply("hi")))

    agent.dispatch(make_update(text_message()))

    assert len(handled) == 1


def test_a_handler_exception_reaches_on_error_and_the_loop_survives(agent):
    errors_seen = []

    @agent.on_text
    def boom(ctx):
        raise RuntimeError("handler exploded")

    @agent.on_error
    def record(exc, ctx):
        errors_seen.append((str(exc), ctx.message.id))

    agent.dispatch(make_update(text_message(wamid="wamid.X")))

    assert errors_seen == [("handler exploded", "wamid.X")]


def test_without_an_error_handler_the_exception_is_logged(agent, caplog):
    agent.on_text(lambda ctx: 1 / 0)

    agent.dispatch(make_update(text_message()))

    assert "failed" in caplog.text


def test_context_helpers(agent, session):
    session.queue(FakeResponse(200, {"id": "media-9"}), send_ok())
    captured = {}

    @agent.on_text
    def handle(ctx):
        captured["sender"] = ctx.sender
        captured["name"] = ctx.profile_name
        ctx.reply_image(file=b"\x89PNG-bytes", mime_type="image/png", caption="here", quote=True)

    update = Update.from_dict(update_body(
        messages=[text_message()],
        contacts=[{"wa_id": "user:5", "profile": {"name": "Alex"}}],
    ))
    agent.dispatch(update)

    assert captured == {"sender": "user:5", "name": "Alex"}
    assert session.last_json["image"] == {"id": "media-9", "caption": "here"}
    assert session.last_json["context"] == {"message_id": "wamid.IN1"}


def test_context_download(agent, session):
    session.queue(
        FakeResponse(200, {"id": "media-1", "url": "https://lookaside.fbsbx.com/x/content"}),
        FakeResponse(200, content=b"image-bytes"),
    )
    downloaded = []
    agent.on_media(lambda ctx: downloaded.append(ctx.download()))

    agent.dispatch(make_update(media_message("image")))

    assert downloaded == [b"image-bytes"]


def test_context_download_on_a_text_message_raises(agent):
    seen = []
    agent.on_text(lambda ctx: ctx.download())
    agent.on_error(lambda exc, ctx: seen.append(type(exc)))

    agent.dispatch(make_update(text_message()))

    assert seen == [ValidationError]


def test_caption_is_exposed_as_text_on_media(agent):
    seen = []
    agent.on_media(lambda ctx: seen.append(ctx.text))

    agent.dispatch(make_update(media_message("image", caption="look at this")))

    assert seen == ["look at this"]


# --------------------------------------------------------------------- #
# run() and offsets
# --------------------------------------------------------------------- #

def test_run_polls_and_dispatches(client, session):
    agent = Agent(client=client, typing=False, mark_read=False)
    session.queue(
        FakeResponse(200, update_body(messages=[text_message("one", wamid="a")], next_offset=2)),
        FakeResponse(204),
    )
    seen = []
    agent.on_text(lambda ctx: seen.append(ctx.text))

    agent.run(max_polls=2)

    assert seen == ["one"]
    assert "offset" not in session.requests[0]["params"], "start='new' must omit the offset"
    assert session.requests[1]["params"]["offset"] == 2


def test_start_beginning_replays_the_backlog(client, session):
    agent = Agent(client=client, start="beginning", typing=False, mark_read=False)
    session.queue(FakeResponse(204))

    agent.run(max_polls=1)

    assert session.last["params"]["offset"] == 0


def test_an_explicit_start_offset(client, session):
    agent = Agent(client=client, start=99, typing=False, mark_read=False)
    session.queue(FakeResponse(204))

    agent.run(max_polls=1)

    assert session.last["params"]["offset"] == 99


def test_an_invalid_start_is_rejected(client, session):
    agent = Agent(client=client, start="yesterday")

    with pytest.raises(ValidationError, match="start must be"):
        agent.run(max_polls=1)


def test_the_offset_store_resumes_and_persists(client, session, tmp_path):
    store = FileOffsetStore(tmp_path / "offset")
    store.save(500)
    agent = Agent(client=client, offset_store=store, typing=False, mark_read=False)
    session.queue(
        FakeResponse(200, update_body(messages=[text_message()], next_offset=501)),
        FakeResponse(204),
    )

    agent.run(max_polls=2)

    assert session.requests[0]["params"]["offset"] == 500
    assert store.load() == 501


def test_a_missing_offset_file_falls_back_to_start(client, session, tmp_path):
    agent = Agent(client=client, offset_store=FileOffsetStore(tmp_path / "nope"),
                  start="beginning", typing=False, mark_read=False)
    session.queue(FakeResponse(204))

    agent.run(max_polls=1)

    assert session.last["params"]["offset"] == 0


def test_agent_needs_a_token_or_a_client(client):
    with pytest.raises(ValidationError):
        Agent()
    with pytest.raises(ValidationError):
        Agent("token", client=client)


def test_agent_builds_its_own_client_from_a_token():
    with Agent("a-token", rate_limit=False) as agent:
        assert agent.client.token == "a-token"
