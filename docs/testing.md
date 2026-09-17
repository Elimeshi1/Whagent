# Testing

## Testing your handlers

A handler takes a `Context`, so the simplest test builds one and calls the handler — no HTTP at all:

```python
from whagent import Client, Context
from whagent.models import Message, Update

def make_context(text, sender="user:5"):
    message = Message.from_dict({
        "from": sender, "id": "wamid.TEST", "timestamp": "1736844652",
        "type": "text", "text": {"body": text},
    })
    return Context(client=FakeClient(), message=message, update=Update())
```

More realistic, and usually better: drive the real `Agent` with a fake HTTP session, so the request your handler produces is asserted end to end.

## A fake session

`Client` accepts any object with a `request()` method, so a stand-in is a few lines:

```python
import json

class FakeResponse:
    def __init__(self, status_code=200, body=None, content=b""):
        self.status_code = status_code
        self._body = body
        self.headers = {}
        self.content = content or (json.dumps(body).encode() if body is not None else b"")
        self.text = self.content.decode()

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body

    def iter_content(self, chunk_size=1024):
        yield self.content

class FakeSession:
    def __init__(self):
        self.responses = []
        self.requests = []

    def request(self, method, url, **kwargs):
        self.requests.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0) if self.responses else FakeResponse(200, {"success": True})

    def close(self):
        pass
```

Then:

```python
from whagent import Agent, Client

def test_echo():
    session = FakeSession()
    session.responses = [
        FakeResponse(200, {                     # one poll with one message
            "object": "whatsapp_agent_platform",
            "entry": [{"id": "1", "changes": [{"field": "messages", "value": {
                "messaging_product": "whatsapp",
                "contacts": [{"wa_id": "user:5", "profile": {"name": "Alex"}}],
                "messages": [{"from": "user:5", "id": "wamid.A", "timestamp": "1736844652",
                              "type": "text", "text": {"body": "hello"}}],
                "statuses": [],
            }}]}],
            "next_offset": 2,
        }),
        FakeResponse(200, {"success": True}),   # the read receipt
        FakeResponse(200, {                     # the reply
            "messaging_product": "whatsapp",
            "contacts": [{"input": "user:5", "wa_id": "user:5"}],
            "messages": [{"id": "wamid.OUT"}],
        }),
        FakeResponse(204),                      # second poll: nothing
    ]

    client = Client("test-token", session=session, rate_limit=False)
    agent = Agent(client=client)

    @agent.on_text
    def echo(ctx):
        ctx.reply(f"You said: {ctx.text}")

    agent.run(max_polls=2)

    sent = session.requests[-1]
    assert sent["url"].endswith("/messages")
    assert sent["json"]["text"] == {"body": "You said: hello"}
```

`max_polls` and `stop` exist so `run()` terminates in a test.

## Useful switches

| | |
|---|---|
| `Client(..., rate_limit=False)` | no sleeping between calls |
| `Client(..., max_retries=0)` | a failure surfaces immediately instead of being retried |
| `Client(..., base_url="http://127.0.0.1:PORT/agent/v1")` | point at a local stub server for an end-to-end test |
| `Agent(..., typing=False, mark_read=False)` | no `POST /statuses` calls to stub out |
| `Agent(..., skip_own_replays=False)` | dispatch the same message id more than once |
| `agent.dispatch(update)` | feed one update in without polling at all |

## The library's own tests

```bash
git clone https://github.com/Elimeshi1/Whagent.git
cd Whagent
pip install -U pip        # editable installs need pip 21.3 or newer
pip install -e ".[dev]"
pytest
```

143 tests, no network. They assert the exact requests the library builds against the payloads in the developer manual — [`tests/conftest.py`](https://github.com/Elimeshi1/Whagent/blob/main/tests/conftest.py) has a fuller version of the fake session above, and is a reasonable thing to copy.
