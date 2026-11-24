# Tripadvisor MCP Server

MCP server for Tripadvisor places in Bali: top attractions, restaurants and hotels around an area, with ratings, review counts and photos. Used by the VillaOps AI agent for guest recommendations and local market research. The chat UI renders its results as photo cards.

It's a rewrite of the earlier `tripadvisor-mcp` (MIT, by Pavel Shklovsky), moved to the **Tripadvisor Terra Partner API**.

## Why the old server stopped working

Tripadvisor retired the legacy Content API (`api.content.tripadvisor.com/api/v1`, key sent as `?key=`). Terra keys are UUIDs, and Terra rejects requests to the old host with *"User is not authorized to access this resource with an explicit deny"*. That 403 comes from the API version, not from an IP allowlist.

| | Legacy Content API | Terra |
|---|---|---|
| Base URL | `api.content.tripadvisor.com/api/v1` | `terra.tripadvisor.com/api` (`?version=1`) |
| Auth | `?key=` query param | `X-API-Key` header |
| Photos | separate endpoint | `include_photo=true` on nearby; photo `key` → `media-cdn.tripadvisor.com/media/photo-s/...` |

## Tools

| Tool | Endpoint | Billing |
|---|---|---|
| `tripadvisor_search_nearby_locations` | `GET /locations/nearby` around a Bali area (`ubud`, `canggu`, `seminyak`, …) or lat/lon. Takes `category`, `radius_km`, `min_rating`, `sort_by` and `max_results`. | 1 per place returned |
| `tripadvisor_search_locations` | `GET /locations/search` for a place by name | 1 per place returned |
| `tripadvisor_get_location_details` | `GET /locations/{id}` plus `/photos` | 1–2 per call |

## Cost and policy notes

- **Billing.** Terra bills per location returned. The first 1,000 are free, and that allowance is one-time. Every tool sends `size` equal to `max_results` (default 5), never the API default of 20.
- **No caching.** The [caching policy](https://docs.terra.tripadvisor.com/docs/caching-policy) forbids storing content, so unlike the Booking.com and Airbnb servers there is no Redis cache.
- **Display rules.** Photos are hot-linked from Tripadvisor's CDN, never re-hosted, and every card links back to Tripadvisor, as the display requirements ask.
- **Not in this key's package.** The Recommendations (agentic search) endpoint returns 403 "API Key does not have access to endpoint".

## Run

```bash
cp .env.example .env    # add TRIPADVISOR_API_KEY
pip install -e ".[dev]"
python -m tripadvisor_mcp.server      # http://localhost:8004/mcp, health at /health
```

In VillaOps AI it runs as the `tripadvisor-mcp` service in `docker-compose.yml`, and the backend reaches it at `TRIPADVISOR_MCP_URL=http://tripadvisor-mcp:8004/mcp`.

## Test

```bash
pytest -q    # uses recorded Terra responses in tests/fixtures, never calls the live API
```
