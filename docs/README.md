# whagent documentation

A Python library for the [WhatsApp Agent Platform](https://www.whatsapp.com/developer/WhatsApp-Agent-Platform-Developer-Manual.pdf) API (`https://api.whatsapp.com/agent/v1`), covering version 1 of the developer manual.

## Start here

| Page | What it covers |
|---|---|
| [Getting started](getting-started.md) | Install, get an API token, run your first agent |
| [Concepts](concepts.md) | How the platform works: polling, identifiers, what an agent may do |

## The two layers

| Page | What it covers |
|---|---|
| [Agent](agent.md) | Handlers, `Context`, the poll loop, offset persistence |
| [Client](client.md) | Construction, configuration, session and lifecycle |

## Endpoints

| Page | Endpoint |
|---|---|
| [Sending messages](sending.md) | `POST /messages` |
| [Receiving updates](receiving.md) | `GET /updates` |
| [Receipts and typing](receipts.md) | `POST /statuses` |
| [Media](media.md) | `POST` / `GET` / `DELETE /media` |

## Reference

| Page | What it covers |
|---|---|
| [Models](models.md) | `Update`, `Message`, `Status`, `Media`, identifiers |
| [Errors](errors.md) | Exception hierarchy, error codes, retry policy |
| [Rate limits](rate-limits.md) | Per-method caps and the built-in limiter |
| [Limits and formats](limits.md) | Length caps, media sizes, accepted MIME types and codecs |

## Practice

| Page | What it covers |
|---|---|
| [Recipes](recipes.md) | Persistence, long work, shutdown, threads, structuring a real agent |
| [Testing](testing.md) | Testing your agent without touching the network |

---

Source: [github.com/Elimeshi1/Whagent](https://github.com/Elimeshi1/Whagent) · [Examples](../examples)
