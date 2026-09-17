"""Parsing of the payloads documented in the manual."""

from __future__ import annotations

from datetime import timezone

import pytest

from conftest import update_body

from whagent.models import Media, Message, SendResult, Update, is_user, participant_type


def test_text_message():
    message = Message.from_dict({
        "from": "user:50972923564215",
        "id": "wamid.HBg",
        "timestamp": "1736844652",
        "type": "text",
        "text": {"body": "Hello agent"},
    })

    assert message.text == "Hello agent"
    assert message.sender == "user:50972923564215"
    assert message.media is None and message.caption is None
    assert message.datetime.tzinfo is timezone.utc
    assert message.datetime.year == 2025
    assert not message.is_media and not message.is_reply


def test_image_message_exposes_media_and_caption():
    message = Message.from_dict({
        "from": "user:5", "id": "wamid.1", "timestamp": "1736844652", "type": "image",
        "image": {"id": "998a", "mime_type": "image/jpeg", "sha256": "qMVn", "caption": "look at this"},
    })

    assert message.is_media
    assert message.media_id == "998a"
    assert message.caption == "look at this"
    assert message.media.mime_type == "image/jpeg"
    assert message.media.sha256 == "qMVn"


def test_voice_note_sets_the_voice_flag():
    message = Message.from_dict({
        "from": "user:5", "id": "wamid.1", "timestamp": "1", "type": "audio",
        "audio": {"id": "5f63", "mime_type": "audio/ogg", "voice": True},
    })

    assert message.media.voice is True


def test_sticker_is_not_animated_on_receive():
    message = Message.from_dict({
        "from": "user:5", "id": "wamid.1", "timestamp": "1", "type": "sticker",
        "sticker": {"id": "2c3d", "mime_type": "image/webp", "animated": False},
    })

    assert message.media.animated is False


def test_document_keeps_its_filename():
    message = Message.from_dict({
        "from": "user:5", "id": "wamid.1", "timestamp": "1", "type": "document",
        "document": {"id": "14ef", "mime_type": "application/pdf", "filename": "report.pdf"},
    })

    assert message.media.filename == "report.pdf"


def test_reaction_and_its_removal():
    reacted = Message.from_dict({
        "from": "user:5", "id": "wamid.1", "timestamp": "1", "type": "reaction",
        "reaction": {"message_id": "wamid.QUOTED", "emoji": "👍"},
    })
    removed = Message.from_dict({
        "from": "user:5", "id": "wamid.2", "timestamp": "1", "type": "reaction",
        "reaction": {"message_id": "wamid.QUOTED", "emoji": ""},
    })

    assert reacted.reaction.emoji == "👍" and not reacted.reaction.removed
    assert removed.reaction.removed


def test_context_uses_id_inbound_and_tells_agent_from_user():
    message = Message.from_dict({
        "from": "user:5", "id": "wamid.1", "timestamp": "1", "type": "text",
        "text": {"body": "yes"},
        "context": {"id": "wamid.QUOTED", "from": "agent:123456789"},
    })

    assert message.is_reply
    assert message.context.message_id == "wamid.QUOTED"
    assert message.context.from_agent is True


def test_unknown_message_type_parses_without_losing_the_payload():
    message = Message.from_dict({
        "from": "user:5", "id": "wamid.1", "timestamp": "1", "type": "location",
        "location": {"latitude": 1.0},
    })

    assert message.type == "location"
    assert message.text is None and message.media is None
    assert message.raw["location"] == {"latitude": 1.0}


def test_update_pairs_profile_names_with_messages():
    update = Update.from_dict(update_body(
        messages=[{"from": "user:5", "id": "wamid.1", "timestamp": "1", "type": "text",
                   "text": {"body": "hi"}}],
        contacts=[{"wa_id": "user:5", "profile": {"name": "Alex"}}],
        next_offset=1287,
    ))

    assert update.messages[0].profile_name == "Alex"
    assert update.profile_name("user:5") == "Alex"
    assert update.profile_name("user:999") is None
    assert bool(update) is True
    assert [m.text for m in update] == ["hi"]


def test_update_without_a_profile_name():
    update = Update.from_dict(update_body(
        messages=[{"from": "user:5", "id": "w", "timestamp": "1", "type": "text", "text": {"body": "hi"}}],
        contacts=[{"wa_id": "user:5"}],
    ))

    assert update.messages[0].profile_name is None


def test_statuses_parse_and_an_update_of_only_statuses_is_falsy_only_when_empty():
    update = Update.from_dict(update_body(statuses=[
        {"id": "wamid.OUT", "status": "read", "recipient_id": "user:5", "timestamp": "1736844652"},
    ]))
    empty = Update.from_dict(update_body())

    status = update.statuses[0]
    assert status.read and not status.delivered
    assert status.recipient_id == "user:5"
    assert bool(update) is True
    assert bool(empty) is False


def test_send_result_parses_the_first_element_of_each_array():
    result = SendResult.from_dict({
        "messaging_product": "whatsapp",
        "contacts": [{"input": "user:5", "wa_id": "user:5"}],
        "messages": [{"id": "wamid.OUT"}],
    })

    assert (result.message_id, result.wa_id, result.input) == ("wamid.OUT", "user:5", "user:5")


def test_media_metadata_parses_file_size_as_an_int():
    media = Media.from_dict({"id": "8f3a", "url": "https://x/content", "file_size": "232145"})

    assert media.file_size == 232145


@pytest.mark.parametrize("identifier,expected", [
    ("user:509", "user"),
    ("agent:123", "agent"),
    ("509", None),
    ("group:1", None),
    ("user:", None),
    ("", None),
])
def test_participant_type(identifier, expected):
    assert participant_type(identifier) == expected


def test_is_user():
    assert is_user("user:509") and not is_user("agent:123")
