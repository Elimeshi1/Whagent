"""Receive a file, download it, and send one back.

    export WHATSAPP_AGENT_TOKEN=...
    python examples/media_bot.py
"""

import os
import tempfile
from pathlib import Path

from whagent import Agent

agent = Agent(os.environ["WHATSAPP_AGENT_TOKEN"])


@agent.on_message(["image", "document", "audio", "video"])
def save_incoming(ctx):
    media = ctx.message.media
    suffix = Path(media.filename or "").suffix or ""
    destination = Path(tempfile.gettempdir()) / f"{media.id}{suffix}"

    ctx.download(destination)
    size = destination.stat().st_size
    ctx.reply(f"Saved your {ctx.type} ({size} bytes) to {destination}.")

    # Media is stored for 30 days; delete what you no longer need.
    ctx.client.delete_media(media.id)


@agent.on_text(r"^/report")
def send_report(ctx):
    report = Path(tempfile.gettempdir()) / "report.txt"
    report.write_text("Everything is fine.\n")

    # file= uploads first, then sends — or pass media_id= to reuse an upload.
    ctx.reply_document(file=report, caption="Today's report")


@agent.on_text(r"^/photo")
def send_photo(ctx):
    photo = os.environ.get("WHAGENT_DEMO_IMAGE")
    if not photo:
        ctx.reply("Set WHAGENT_DEMO_IMAGE to a .jpg or .png path first.")
        return
    ctx.reply_image(file=photo, caption="Here you go")


if __name__ == "__main__":
    agent.run()
