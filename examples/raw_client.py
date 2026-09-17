"""The same loop without the Agent layer, using Client directly.

Useful when you want to own the control flow — a queue, a thread pool, or
your own storage of the poll offset.
"""

import os

from whagent import Client

with Client(os.environ["WHATSAPP_AGENT_TOKEN"]) as client:
    offset = None  # start at the head; pass 0 to replay up to 30 days of backlog

    while True:
        update = client.get_updates(offset=offset, limit=50, timeout=25)
        if update is None:
            continue  # timed out with nothing to deliver: re-poll with the same offset

        offset = update.next_offset

        for status in update.statuses:
            print(f"{status.id} -> {status.status}")

        for message in update.messages:
            print(f"{message.sender}: {message.text or message.type}")
            client.mark_read(message.id, typing=True)
            if message.type == "text":
                client.send_text(message.sender, f"You said: {message.text}")
