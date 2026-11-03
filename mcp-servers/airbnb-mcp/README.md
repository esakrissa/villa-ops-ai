# Airbnb MCP Server

MCP server for live Airbnb search and listing details. Used by the VillaOps AI agent for competitor and market-rate research. The chat UI renders its results as photo cards.

It's a Python port of [openbnb-org/mcp-server-airbnb](https://github.com/openbnb-org/mcp-server-airbnb) (MIT, TypeScript), and keeps the original tool names. Changes from the original:

- **MCP 2.x** (`MCPServer`) over **Streamable HTTP** (`/mcp`), so it runs as a network service instead of over stdio.
- **Updated for Airbnb's 2026 pages.** The embedded state moved from `niobeMinimalClientData` to `niobeClientData`, and listing details now live in `data.node.pdpPresentation`.
- **Photos included.** The original drops them (`contextualPictures` is commented out). Results also include parsed numeric nightly prices, a `currency` option and a min/median/max price summary.
- **Redis caching.** Search results are cached for 6 hours and listing details for 24 hours, so demos don't repeat requests.

## Tools

| Tool | What it does |
|---|---|
| `airbnb_search` | Searches stays in a `location`. Optional: `checkin`/`checkout`, `adults`, `children`, `min_price`/`max_price`, `currency` (default `USD`) and `max_results` (1–10, default 5). |
| `airbnb_listing_details` | Returns description, amenities, house rules, host, rating and photos for a `listing_id` taken from search results. |

## robots.txt

Airbnb's robots.txt disallows `/s/` search pages for bots; listing pages are allowed. As in the original server's `--ignore-robots-txt` flag, robots.txt is respected by default, so `airbnb_search` returns an error unless you opt in:

```bash
AIRBNB_IGNORE_ROBOTS_TXT=true
```

## Run

```bash
pip install -e ".[dev]"
AIRBNB_IGNORE_ROBOTS_TXT=true python -m airbnb_mcp.server    # http://localhost:8003/mcp, health at /health
```

In VillaOps AI it runs as the `airbnb-mcp` service in `docker-compose.yml`, and the backend reaches it at `AIRBNB_MCP_URL=http://airbnb-mcp:8003/mcp`.

## Test

```bash
pytest -q    # uses trimmed recorded pages in tests/fixtures, never calls airbnb.com
```
