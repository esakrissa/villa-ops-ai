# VillaOps AI — Demo Recording Script

Step-by-step script for recording a full product demo. Each scene is designed to showcase a key feature with specific actions and expected results.

---

## Prerequisites

```bash
# 1. Start services on EC2
./scripts/dev.sh up

# 2. Open SSH tunnels
./scripts/dev.sh tunnel

# 3. Seed demo data (if not already seeded)
ssh remote-workspace "cd /home/remote/workspace/villa-ops-ai && \
  docker compose exec -T backend python -m scripts.seed_data"

# 4. Open browser to http://localhost:3000
```

**Demo credentials:**

| Field    | Value              |
|----------|--------------------|
| Email    | demo@villaops.ai   |
| Password | demo1234           |

---

## Scene 1: Landing Page + Registration (30s)

**Goal:** Show the product landing page and registration flow.

1. Open `http://localhost:3000` — show the landing page
2. Click **Get Started** or **Sign Up**
3. Fill in registration form:
   - Name: `Test User`
   - Email: `test@example.com`
   - Password: `test1234`
4. Submit — should redirect to dashboard
5. Log out

**What to highlight:**
- Clean landing page with feature overview
- Smooth registration flow
- Automatic free tier subscription on signup

---

## Scene 2: OAuth Login (20s)

**Goal:** Show social login works.

1. Click **Sign In**
2. Click **Continue with Google** (or GitHub)
3. Complete OAuth flow
4. Lands on dashboard — user profile shows avatar from provider

**What to highlight:**
- Multi-provider OAuth (Google + GitHub)
- Avatar pulled from provider
- Seamless redirect back to app

---

## Scene 3: Login with Demo Account (10s)

**Goal:** Switch to the seeded demo account with real data.

1. Log out of test account
2. Sign in with `demo@villaops.ai` / `demo1234`
3. Dashboard loads with properties and data

---

## Scene 4: AI Chat — Booking Search (45s)

**Goal:** Show the AI agent searching bookings with real-time tool calls.

1. Open **Chat** from sidebar
2. Type: `Show me all confirmed bookings for the next 2 weeks`
3. Watch the response stream:
   - Tool call card appears (`booking_search`)
   - Results stream in with booking details
4. Follow up: `Which guests have special dietary requirements?`
5. Watch `guest_lookup` tool call and response

**What to highlight:**
- SSE streaming (tokens appear in real-time)
- Tool call cards show what the agent is doing
- Natural language queries against real data
- Multi-turn conversation context

---

## Scene 5: AI Chat — Create a Booking (45s)

**Goal:** Show the agent creating data through natural language.

1. In the same chat, type:
   ```
   Book Le Ayu Villa Canggu for a new guest named Alex Rivera
   (alex@example.com) from March 1 to March 5, 2 adults.
   Special request: early check-in if possible.
   ```
2. Watch the agent:
   - Call `guest_create` to create the new guest
   - Call `booking_create` to make the reservation
3. Verify: `Show me Alex Rivera's booking details`

**What to highlight:**
- Agent chains multiple tool calls automatically
- Creates guest + booking in one conversation
- Handles structured data creation from free-form text

---

## Scene 6: AI Chat — Analytics (30s)

**Goal:** Show analytics capabilities.

1. Type: `What's the occupancy rate and revenue summary for all properties in the last 30 days?`
2. Watch `booking_analytics` tool call
3. Agent responds with occupancy percentages and revenue breakdown

**What to highlight:**
- Business intelligence via natural language
- Revenue and occupancy calculations
- Data aggregated across properties

---

## Scene 7: AI Chat — Web Search (30s)

**Goal:** Show the Exa web search integration.

1. Type: `What's the weather forecast for Bali this weekend?`
2. Watch `web_search_exa` tool call
3. Agent responds with current weather info

**What to highlight:**
- Agent has access to live web data via Exa MCP
- Useful for guest concierge queries
- Seamlessly integrated alongside property tools

---

## Scene 8: AI Chat — HITL Confirmation (30s)

**Goal:** Show destructive action confirmation (Human-in-the-Loop).

1. Type: `Delete the guest Alex Rivera we just created`
2. A **confirmation card** appears asking to approve the deletion
3. Click **Approve** — agent executes the deletion
4. (Alternative: click **Cancel** to show the agent respects the decision)

**What to highlight:**
- Destructive actions require explicit user confirmation
- Clean confirmation UI with approve/cancel
- Agent handles both outcomes gracefully

---

## Scene 9: Dashboard — Properties (20s)

**Goal:** Show the property management dashboard.

1. Navigate to **Properties** in sidebar
2. Show the 5 seeded properties with details:
   - Le Ayu Villa Canggu ($129/night)
   - Pitu Village Escape ($86/night)
   - Da Vinci Villa by Nagisa ($350/night)
   - Umah Anyar Villas Ubud ($163/night)
   - Capung Asri Eco Resort ($122/night)
3. Click into a property to show details

**What to highlight:**
- Property cards with pricing
- Real Bali villa data
- Clean dashboard layout

---

## Scene 10: Dashboard — Bookings & Guests (20s)

**Goal:** Show booking and guest management views.

1. Navigate to **Bookings** — show the booking list with statuses
2. Filter by status (confirmed, checked_in, pending)
3. Navigate to **Guests** — show guest profiles with contact info

**What to highlight:**
- Multiple booking statuses visible
- Guest profiles with special requests and notes
- Data matches what the AI agent queried earlier

---

## Scene 11: Pricing Page (15s)

**Goal:** Show the SaaS pricing tiers.

1. Navigate to **Pricing** page
2. Show the three tiers:
   - **Free:** 1 property, 50 AI queries/month
   - **Pro ($29/mo):** 5 properties, 500 AI queries/month, notifications
   - **Business ($79/mo):** Unlimited everything, priority support

**What to highlight:**
- Clear tier differentiation
- Feature comparison
- CTA buttons for upgrade

---

## Scene 12: Stripe Checkout + Upgrade (30s)

**Goal:** Show the Stripe billing integration.

1. Click **Upgrade to Pro**
2. Stripe Checkout opens — use test card:
   - Card: `4242 4242 4242 4242`
   - Expiry: any future date
   - CVC: any 3 digits
3. Complete payment — redirected back to app
4. Navigate to **Billing** — show active subscription details
5. Show **Manage Subscription** (Stripe Customer Portal)

**What to highlight:**
- Full Stripe integration (Checkout + Portal)
- Subscription activated immediately via webhooks
- Plan limits updated in real-time

---

## Scene 13: Usage Limits in Action (20s)

**Goal:** Show plan gating enforcement.

1. (On free tier) Try to add a 2nd property — should get a **402 upgrade required** message
2. Or show the usage counter on the billing page (X/50 AI queries used)

**What to highlight:**
- Plan limits enforced server-side
- Helpful error messages with upgrade prompts
- Usage tracking per billing period

---

## Scene 14: Conversation History (15s)

**Goal:** Show conversation persistence.

1. Open sidebar — show list of past conversations
2. Click an old conversation — full history loads with tool calls
3. Start a new conversation

**What to highlight:**
- Conversations persist across sessions
- Full history including tool call/result cards
- Easy to start new or continue old conversations

---

## Recording Tips

- **Resolution:** 1920x1080 or 2560x1440
- **Browser:** Chrome (clean profile, no extensions visible)
- **Font size:** Zoom to 110-125% for readability
- **Pace:** Pause briefly after each action so viewers can follow
- **Narration:** Record voiceover separately or add captions in post
- **Highlights:** Use cursor effects or zoom-ins on tool call cards and streaming text
- **Total runtime target:** 5-6 minutes

---

## Troubleshooting During Recording

| Issue | Fix |
|-------|-----|
| Chat not streaming | Check backend logs: `./scripts/dev.sh logs backend` |
| OAuth redirect fails | Verify tunnel is open: `./scripts/dev.sh tunnel` |
| Stripe checkout 404 | Ensure Stripe test keys are set in `.env` |
| No seed data | Re-run: `docker compose exec backend python -m scripts.seed_data` |
| MCP tools timeout | Check MCP server: `./scripts/dev.sh logs mcp` |
