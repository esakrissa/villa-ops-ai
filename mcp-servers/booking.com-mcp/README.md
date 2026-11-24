# Booking.com MCP Server

MCP server for live Booking.com hotel data, via the [Booking.com API on RapidAPI](https://rapidapi.com/DataCrawler/api/booking-com15) (`booking-com15`). Used by the VillaOps AI agent for competitor and market-rate research. The chat UI renders its results as photo cards.

It's built from [`esakrissa/hotels_mcp_server`](https://github.com/esakrissa/hotels_mcp_server) and the earlier `booking.com-mcp`, with these updates:

- **MCP 2.x** (`MCPServer`) over **Streamable HTTP** (`/mcp`), so it runs as a network service instead of over stdio.
- **Fixed destination lookup.** The API now returns `city_ufi: null`, so searches use `dest_id` plus `search_type`.
- **Structured JSON results** with photos, nightly prices and a min/median/max price summary, instead of formatted text.
- **Redis caching.** The free plan allows 600 requests a month, so repeated searches don't use quota.

## Tools

| Tool | What it does | RapidAPI calls |
|---|---|---|
| `booking_search_hotels` | Looks up the destination, then searches hotels. Takes `location`, dates, `adults`, `rooms`, `currency`, `sort_by` (`popularity` / `price` / `rating` / `stars`) and `max_results` (1–10, default 5). | 2 on a cold cache; destination lookups are cached for 30 days |
| `booking_hotel_details` | Returns photos, facilities, room types, price and the booking.com URL for one `hotel_id`. | 1 |

Both tools are read-only. On failure they return `{"error": ...}` instead of raising.

## Run

```bash
cp .env.example .env    # add RAPIDAPI_KEY
pip install -e ".[dev]"
python -m booking_com_mcp.server      # http://localhost:8002/mcp, health at /health
```

In VillaOps AI it runs as the `booking-mcp` service in `docker-compose.yml`, and the backend reaches it at `BOOKING_MCP_URL=http://booking-mcp:8002/mcp`.

## Test

```bash
pytest -q    # uses recorded API responses in tests/fixtures, never calls the live API
```
