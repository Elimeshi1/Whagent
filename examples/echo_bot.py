"""The smallest useful agent: echo every text message back.

    export WHATSAPP_AGENT_TOKEN=...
    python examples/echo_bot.py
"""

import logging
import os

from whagent import Agent, FileOffsetStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

agent = Agent(
    os.environ["WHATSAPP_AGENT_TOKEN"],
    # Remember where we stopped, so a restart does not replay or skip messages.
    offset_store=FileOffsetStore(".whagent-offset"),
)


@agent.on_text(r"^/start")
def start(ctx):
    ctx.reply(f"Hi {ctx.profile_name or 'there'}! Send me anything and I will echo it.")


@agent.on_text
def echo(ctx):
    if ctx.text.startswith("/start"):
        return
    ctx.reply(f"You said: {ctx.text}")


@agent.on_media
def describe_media(ctx):
    media = ctx.message.media
    ctx.reply(f"Got a {ctx.type} ({media.mime_type}). Media id: {media.id}")


@agent.on_reaction
def reaction(ctx):
    emoji = ctx.message.reaction.emoji
    ctx.reply(f"You reacted with {emoji}" if emoji else "You removed your reaction")


@agent.on_status
def receipt(status):
    logging.info("message %s was %s", status.id, status.status)


if __name__ == "__main__":
    agent.run()
