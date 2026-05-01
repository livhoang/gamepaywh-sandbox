# GamePay Webhook Sandbox

**Created by:** Liv D'Aquino 
**Date:** May 1, 2026  

A webhook simulation platform for in-game Bitcoin (SAT) payment events, with an AI integration assistant.

Built for game developers who want to test and debug webhook integrations without needing a live payment infrastructure.

---

## What it does

### Register
your webhook endpoint URL (or use the built-in test receiver)
### Fire 
simulated in-game payment events (rewards, tournament prizes, achievements, purchases, referrals)
### Inspect 
every delivery attempt in real time — status, HTTP response code, retry schedule
#### 🎯 Expandable Delivery Attempts
- **First successful delivery auto-expands** to show payload immediately
- **Click any delivery row** to expand/collapse and see the exact payload sent to that endpoint
- Visual chevron indicator (▼) shows expand/collapse state
- Smooth animations and hover effects
- Payload appears in context, right below the delivery details
#### 🎯 Smart Delivery Filtering
- **Successful deliveries shown by default** when there are multiple attempts
- Reduces clutter when some endpoints fail
- Toggle link to "Show all attempts" when you need to see failures
- Delivery count shows "X of Y" when filtered
### Debug
with an AI assistant that reads your live event and delivery logs and answers questions in plain language
### Test idempotency
by reusing the same key and confirming no duplicate delivery occurs
### Verify
HMAC-SHA256 signatures sent with every payload

---

## Quick Start

### 1. Clone and Set Up

```bash
git clone https://github.com/livhoang/gamepaywh-sandbox.git
cd gamepaywh-sandbox
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Open `.env` and add your OpenRouter API key:

```
OPENROUTER_API_KEY=your_key_here
```

Get a free key at [openrouter.ai/keys](https://openrouter.ai/keys). The AI assistant uses **GLM-4.5 Air (free tier)** — no cost at demo usage levels.

### 3. Run Locally

```bash
uvicorn main:app --reload
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

Interactive API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Running with Gunicorn

Gunicorn runs on **Mac and Linux only**. On Windows, use uvicorn directly.

```bash
# Mac / Linux — development
gunicorn main:app -w 2 -k uvicorn.workers.UvicornWorker --reload

# Production (Render, Railway, etc.)
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

`-w 4` sets 4 worker processes. A good rule of thumb: `(2 × CPU cores) + 1`.

---

## API Reference

### Endpoints

#### `POST /endpoints`
Register a webhook endpoint URL.

```json
{
  "url": "https://your-server.com/webhook",
  "description": "My game server (optional)"
}
```

**Response:** `201 Created`
```json
{
  "endpoint_id": "uuid",
  "url": "https://your-server.com/webhook",
  "description": "My game server",
  "registered_at": "2026-04-17T12:00:00",
  "active": true
}
```

---

#### `GET /endpoints`
List all registered endpoints.

**Response:** `200 OK`

---

#### `DELETE /endpoints/{endpoint_id}`
Deactivate an endpoint. It will no longer receive events.

**Response:** `200 OK`

---

#### `POST /events/trigger`
Fire a simulated gaming event. Delivery is asynchronous — the response returns immediately with `202 Accepted`.

```json
{
  "event_type": "player_reward_earned",
  "player_id": "player_001",
  "game_id": "game_001",
  "amount": 1000,
  "endpoint_id": "optional-uuid-to-target-one-endpoint",
  "idempotency_key": "optional-your-unique-key"
}
```

**Response:** `202 Accepted`

**Error responses:**
- `404 Not Found` — endpoint_id not found
- `409 Conflict` — idempotency_key already used (no delivery occurs)
- `422 Unprocessable Entity` — invalid event_type or inactive endpoint

Use `GET /events/{event_id}` to check delivery status after firing.

---

#### `GET /events`
List the 50 most recent events with delivery status.

**Response:** `200 OK`

---

#### `GET /events/{event_id}`
Full detail for one event: payload, idempotency key, status, and every delivery attempt.

**Response:** `200 OK`
```json
{
  "event": { ... },
  "deliveries": [
    {
      "delivery_id": "uuid",
      "endpoint_url": "https://...",
      "status": "delivered",
      "attempts": 1,
      "last_response_code": 200,
      "last_attempt_at": "2026-04-17T12:00:01"
    }
  ],
  "delivery_count": 1
}
```

---

#### `POST /test-receiver`
Built-in receiver. Register `http://localhost:8000/test-receiver` as your endpoint URL to capture payloads without needing an external server.

**Response:** `200 OK`

---

#### `GET /test-receiver/log`
View the last 20 payloads received by the built-in test receiver.

**Response:** `200 OK`

---

#### `POST /assistant`
Ask the AI assistant a question. It has live access to your event log, delivery log, and registered endpoints.

```json
{ "message": "Why did my webhook fail?" }
```

**Response:** `200 OK`
```json
{
  "role": "assistant",
  "content": "Looking at your delivery log...",
  "timestamp": "2026-04-17T12:00:05Z"
}
```

---

#### `GET /assistant/history`
Retrieve the full conversation history.

**Response:** `200 OK`

---

## HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200 OK` | Successful read or action |
| `201 Created` | Resource created (endpoint registration) |
| `202 Accepted` | Event accepted, delivery in progress |
| `404 Not Found` | Event or endpoint ID does not exist |
| `409 Conflict` | Idempotency key already used |
| `422 Unprocessable Entity` | Invalid input (bad event_type, inactive endpoint, etc.) |
| `500 Internal Server Error` | Unexpected server error |

---

## Event Types and Payloads

All events share these base fields:

```json
{
  "event_id": "uuid",
  "event_type": "player_reward_earned",
  "idempotency_key": "your-key-or-auto-generated",
  "game_id": "game_demo_001",
  "player_id": "player_001",
  "timestamp": "2026-04-17T12:00:00Z",
  "api_version": "2026-04"
}
```

---

### `player_reward_earned`
Player earns SAT for an in-game achievement.

```json
{
  "reward": {
    "type": "bitcoin_satoshis",
    "amount": 1000,
    "currency": "SAT",
    "reason": "level_completion",
    "level": 5
  }
}
```

---

### `tournament_prize_disbursed`
Player receives a prize payout for tournament placement.

```json
{
  "tournament_id": "tournament_abc123",
  "placement": 1,
  "prize": { "amount": 50000, "currency": "SAT" }
}
```

---

### `achievement_unlocked_payout`
Achievement badge unlocked with a SAT reward attached.

```json
{
  "achievement": {
    "id": "ach_speed_demon",
    "name": "Speed Demon",
    "description": "Complete level in under 60 seconds",
    "payout": { "amount": 500, "currency": "SAT" }
  }
}
```

---

### `in_game_purchase_completed`
In-game item purchase settled.

```json
{
  "purchase": {
    "item_id": "item_powerup_001",
    "item_name": "Turbo Boost Pack",
    "quantity": 1,
    "amount": 2500,
    "currency": "SAT"
  }
}
```

---

### `referral_bonus_credited`
Referral program bonus credited after a referred player registers.

```json
{
  "referral": {
    "referred_player_id": "player_xyz",
    "bonus": { "amount": 1000, "currency": "SAT" }
  }
}
```

---

## Retry Logic

When delivery to your endpoint fails (non-2xx response or connection error), GamePay retries automatically using exponential backoff:

| Attempt | Delay |
|---------|-------|
| 1 | Immediate |
| 2 | 5 seconds |
| 3 | 30 seconds |
| 4 | 2 minutes |
| 5 | 5 minutes → final |

After 5 failed attempts, the delivery is marked `failed`. No further retries occur.

**Delivery status values:**

| Status | Meaning |
|--------|---------|
| `pending` | Not yet attempted |
| `retrying` | Previous attempt failed, retry scheduled |
| `delivered` | At least one 2xx response received |
| `failed` | All 5 attempts exhausted with no 2xx |

Your endpoint should return a `2xx` status code promptly. If your handler takes too long, return `200` immediately and process the event asynchronously.

---

## Idempotency Keys

Every event carries an `idempotency_key` in the payload and in the `X-GamePay-Idempotency-Key` header.

**Purpose:** Guarantee your handler processes each event exactly once, even if GamePay delivers the same event multiple times due to network failures or retries.

**How to use it:**

```python
# Python — store processed keys in your database
processed_keys = set()  # use a real DB in production

@app.post("/webhook")
async def receive_webhook(request: Request):
    payload = await request.json()
    key = payload.get("idempotency_key")

    if key in processed_keys:
        return {"status": "already_processed"}  # return 200, ignore

    processed_keys.add(key)
    # ... process the event
    return {"status": "ok"}
```

**Testing idempotency in the sandbox:**

1. Fire an event and note the `idempotency_key` from the response.
2. Fire the same event again using that key in the `idempotency_key` field.
3. The sandbox returns `409 Conflict` — no second delivery occurs.

---

## Webhook Signature Verification

Every delivery includes an `X-GamePay-Signature` header containing an HMAC-SHA256 signature of the raw request body.

Format: `sha256=<hex_digest>`

**Always verify this signature** before processing an event to ensure it came from GamePay and was not tampered with.

The signing secret is set in your `.env` file as `WEBHOOK_SECRET`.

### Python

```python
import hmac
import hashlib

def verify_signature(payload_bytes: bytes, signature_header: str, secret: str) -> bool:
    expected = "sha256=" + hmac.new(
        secret.encode(),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)

# In your webhook handler:
@app.post("/webhook")
async def receive_webhook(request: Request):
    payload_bytes = await request.body()
    sig = request.headers.get("X-GamePay-Signature", "")

    if not verify_signature(payload_bytes, sig, "your_secret"):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = json.loads(payload_bytes)
    # ... process
```

### Node.js

```javascript
const crypto = require('crypto');

function verifySignature(payloadBuffer, signatureHeader, secret) {
  const expected = 'sha256=' + crypto
    .createHmac('sha256', secret)
    .update(payloadBuffer)
    .digest('hex');
  return crypto.timingSafeEqual(
    Buffer.from(expected),
    Buffer.from(signatureHeader)
  );
}

// Express handler:
app.post('/webhook', express.raw({ type: 'application/json' }), (req, res) => {
  const sig = req.headers['x-gamepay-signature'];
  if (!verifySignature(req.body, sig, process.env.WEBHOOK_SECRET)) {
    return res.status(401).send('Invalid signature');
  }
  const payload = JSON.parse(req.body);
  // ... process
  res.json({ received: true });
});
```

### Go

```go
import (
    "crypto/hmac"
    "crypto/sha256"
    "encoding/hex"
    "fmt"
)

func verifySignature(body []byte, sigHeader, secret string) bool {
    mac := hmac.New(sha256.New, []byte(secret))
    mac.Write(body)
    expected := "sha256=" + hex.EncodeToString(mac.Sum(nil))
    return hmac.Equal([]byte(expected), []byte(sigHeader))
}
```

**Important:** Always use a constant-time comparison function (`hmac.compare_digest`, `crypto.timingSafeEqual`) rather than `==` to prevent timing attacks.

---

## Production Security Best Practices

### WEBHOOK_SECRET Configuration

**Development (default):**
The sandbox ships with a default secret for local testing. This is fine for development.

**Production (CRITICAL):**
You **MUST** set a cryptographically secure random secret:

```bash
# Generate a secure 32-byte hex secret
openssl rand -hex 32

# Example output:
# a8f2e4c93b7d4f1a9e6c2d5b8a1f3c7e9d4b6f8a2c5e1d3f7b9a4c6e8d1f5a3b
```

**On Railway:**
1. Go to your web service → Variables
2. Add: `WEBHOOK_SECRET=your_generated_secret_here`
3. Redeploy

**Security checklist:**
- ✅ Secret is at least 32 bytes (64 hex characters)
- ✅ Secret is randomly generated, not a password or phrase
- ✅ Secret is stored in environment variables, never in code
- ✅ Secret is different between staging and production
- ✅ Secret is rotated periodically (document rotation process)
- ✅ All webhook receivers verify signatures using this secret

**What happens if you don't change the default secret:**
- Attackers can forge webhook requests
- Your game could credit fake rewards
- Real money loss

---

## UI Features

### Endpoint Selection

The sandbox allows you to control which endpoints receive each event:

**Fire to All Endpoints (default):**
- "Fire to all" checkbox is checked by default
- Event is sent to every active registered endpoint simultaneously

**Fire to Specific Endpoints:**
1. Uncheck "Fire to all"
2. Check only the endpoints you want to target
3. Fire event → only selected endpoints receive it

**Use cases:**
- Testing one endpoint while leaving others registered
- Debugging specific integrations
- Simulating production routing logic

### Event Inspection

When you click an event in the Event Feed, the detail panel shows:
- Full event payload with syntax highlighting
- **Delivery Attempts** section with clear endpoint identification:
  - Target endpoint URL (prominent display)
  - Status badge (delivered/failed/retrying/pending)
  - HTTP response code (color-coded)
  - Retry schedule and timestamps
  - Left border color matches delivery status

#### 🎯 Expandable Delivery Attempts
- **Click any delivery row** to expand and see the exact payload sent to that endpoint
- Visual chevron indicator (▼) shows expand/collapse state
- Smooth animations and hover effects
- Payload appears in context, right below the delivery details

#### 🎯 Smart Delivery Filtering
- **Successful deliveries shown by default** when there are multiple attempts
- Reduces clutter when some endpoints fail
- Toggle link to "Show all attempts" when you need to see failures
- Delivery count shows "X of Y" when filtered

Each delivery is tracked independently, making it easy to see which endpoints succeeded and which failed.

---

If you do not have an external server, use the built-in receiver:

1. Click **"Use Built-in Receiver"** in the left panel — it fills in `http://localhost:8000/test-receiver` automatically.
2. Click **Register**.
3. Fire any event.
4. Switch to the **Built-in Receiver** tab in the middle panel to see the captured payload.

The built-in receiver always returns `200 OK`, so events will show as `delivered` immediately.

---

## Testing with Custom Endpoints Locally

**What "registering an endpoint" means:**

When you register an endpoint, you're telling the sandbox **WHERE to send webhooks TO** (the destination URL). This is NOT creating a new endpoint ON the sandbox — it's telling the sandbox about YOUR server that will receive webhooks.

**The flow:**
```
You register: http://your-server.com/webhook
     ↓
Sandbox fires an event
     ↓
Sandbox POSTs payload to http://your-server.com/webhook
     ↓
Your server receives it and returns 200 OK
     ↓
Sandbox marks delivery as "delivered"
```

**What works locally:**
- ✅ `http://localhost:8000/test-receiver` (the built-in receiver - always works)
- ✅ `http://localhost:5000/webhook` (if you run a second server on port 5000)
- ✅ `https://webhook.site/xyz123` (external webhook testing service)
- ✅ `https://abc123.ngrok.io/webhook` (ngrok tunnel to your localhost)

**What fails locally:**
- ❌ `my-endpoint` (not a valid URL)
- ❌ `http://my-endpoint` (DNS doesn't resolve)
- ❌ `http://fake-server.com/webhook` (server doesn't exist)

### Quick Test with a Second Server

The project includes `simple_webhook_receiver.py` — a Flask server for testing:

```bash
# Terminal 1: Run the sandbox
cd gamepaywh-sandbox
uvicorn main:app --reload

# Terminal 2: Run the test receiver
pip install flask  # if not installed
python simple_webhook_receiver.py
```

Then in the sandbox:
1. Register `http://localhost:5000/webhook`
2. Fire an event
3. Terminal 2 shows the received payload

**On Railway:** Same behavior — you can register ANY URL, but delivery only succeeds if that URL exists and returns 200 OK.

---

## Webhook Testing with Free Services

See **`WEBHOOK_TESTING_GUIDE.md`** for detailed instructions on:

### RequestBin.com (Recommended for Quick Tests)
- ✅ No account required
- ✅ Instant setup (< 30 seconds)
- ✅ Clean interface
- ❌ 48-hour expiration

### Pipedream.com (Recommended for Advanced Use)
- ✅ Permanent URLs
- ✅ Custom logic (Node.js, Python)
- ✅ 1000+ integrations
- ✅ Real-time updates
- ❌ Requires free account

**Quick setup for RequestBin:**
1. Go to https://requestbin.com
2. Click "Create a Request Bin"
3. Copy the URL
4. Register it in GamePay Endpoints tab
5. Fire an event
6. Refresh RequestBin to see the payload

---

## Deploying to Railway (free tier with PostgreSQL)

Railway provides $5 free credit per month (≈500 hours) and native PostgreSQL support. **This is the recommended deployment method** for a persistent demo.

### Step 1: Push to GitHub

```bash
git init
git add .
git commit -m "GamePay webhook sandbox"
git remote add origin https://github.com/livhoang/gamepaywh-sandbox.git
git push -u origin main
```

### Step 2: Deploy to Railway

1. Go to [railway.app](https://railway.app) and sign in with GitHub
2. Click **New Project** → **Deploy from GitHub repo**
3. Select your `gamepaywh-sandbox` repository
4. Railway auto-detects the Python app and deploys it

### Step 3: Add PostgreSQL Database

1. In your Railway project, click **+ New** → **Database** → **Add PostgreSQL**
2. Railway automatically:
   - Creates a PostgreSQL instance
   - Generates a `DATABASE_URL` environment variable
   - Links it to your web service

Your app will automatically use PostgreSQL instead of SQLite (detected via `DATABASE_URL`).

### Step 4: Add Environment Variables

In your web service settings → **Variables** tab, add:

```
OPENROUTER_API_KEY=your_openrouter_key_here
WEBHOOK_SECRET=your_random_secret_here
```

**Generate a secure webhook secret:**
```bash
openssl rand -hex 32
```

Railway already set `DATABASE_URL` — do not modify it.

### Step 5: Get Your Public URL

1. In your web service settings → **Settings** tab
2. Click **Generate Domain** under Public Networking
3. You'll get a URL like: `https://gamepaywh-sandbox-production.up.railway.app`

### Done!

Open your Railway URL. The sandbox is live with persistent PostgreSQL storage.

**Free tier limits:**
- $5 credit/month (≈500 hours if app runs 24/7)
- After credit exhausted, service sleeps until next month
- PostgreSQL data persists (unlike Render free tier)

**To check database:**
1. In Railway, click your PostgreSQL service
2. Click **Data** tab → view tables
3. Or click **Connect** → get psql connection string

---

### Alternative: Render or Fly.io

**Render** (less recommended): Free tier has no persistent disk — database resets on each deploy. Use Railway instead for persistence.

**Fly.io** (advanced): Requires Docker knowledge. Better for production, overkill for a demo.

---

## Project Structure

```
gamepaywh-sandbox/
├── main.py                         # FastAPI app — all routes
├── models.py                       # Data models, PostgreSQL/SQLite setup, payload builders
├── webhook_sender.py               # Delivery engine — retry logic, HMAC signing
├── ai_assistant.py                 # AI integration - OpenRouter GLM-4.5 Air
├── static/
│   └── index.html                  # Full frontend — single file
├── requirements.txt                # Dependencies
├── Procfile                        # For Railway / Heroku deployment
├── .env.example                    # Environment variable template
├── .gitignore
├── WEBHOOK_TESTING_GUIDE.md        # RequestBin & Pipedream guide
├── CHANGELOG_MODIFICATIONS.md      # Detailed change log
└── README.md                       # This file
```

**Database:** Uses PostgreSQL (asyncpg) when `DATABASE_URL` is set (Railway), otherwise SQLite (aiosqlite) for local dev. No code changes needed — auto-detects.

---

## Browser Compatibility

**Tested on:**
- Chrome 120+ ✅
- Firefox 121+ ✅
- Safari 17+ ✅
- Edge 120+ ✅

**Requirements:**
- Modern browser with ES6+ support
- CSS flexbox support
- CSS transitions support

**Note:** IE11 is not supported (uses modern JavaScript).

---

## AI Model

The assistant uses **GLM-4.5 Air** via OpenRouter (`z-ai/glm-4.5-air:free`).

- 106B total / 12B active parameters (Mixture-of-Experts)
- Purpose-built for agentic applications
- 131K context window
- Supports tool use and function calling
- Free tier on OpenRouter — no cost for demo usage

The assistant runs in **non-thinking mode** (`reasoning: {enabled: false}`) for fast response times. Switch to thinking mode by setting `"enabled": true` in `ai_assistant.py` if you want deeper reasoning at the cost of latency.

---

## Good questions to ask the assistant

- "Why did my last webhook fail?"
- "Show me the full payload schema for `tournament_prize_disbursed`"
- "How do I verify the signature in Node.js?"
- "What events should I handle if I want to reward players for purchases and referrals?"
- "What is the idempotency key and why do I need it?"
- "My endpoint returned a 500 — how many more retries will happen?"
- "Show me a Python handler that processes `player_reward_earned` correctly"

---

## Production Deployment Notes

When deploying to production:

### Environment Variables

```bash
DATABASE_URL=postgresql://...  # Auto-set by Railway
OPENROUTER_API_KEY=your_key    # Required for AI assistant  
WEBHOOK_SECRET=random_hex_32   # For HMAC signature generation
```

### Webhook Security

See **Webhook Signature Verification** section above for complete signature validation examples.

### HTTPS Required

GamePay webhooks require HTTPS in production. Use:
- **Heroku** (free tier with auto SSL)
- **Railway** (free tier with auto SSL)
- **Render** (free tier with auto SSL)
- **Fly.io** (free tier with auto SSL)

---

## Known Issues / Limitations

### Current Limitations

1. **No authentication** - Anyone with the URL can access the sandbox
2. **UI shows only 50 most recent events** - Older events exist in database but not displayed
3. **Single-instance deployment** - Not designed for horizontal scaling

### These are expected for a dev sandbox

The focus is on demonstrating webhook delivery mechanics, not production robustness.

---

## Troubleshooting

### Delivery not expanding on click

**Symptoms:** Click delivery row, nothing happens

**Solutions:**
1. Check browser console for JavaScript errors
2. Hard refresh (Ctrl+Shift+R / Cmd+Shift+R)
3. Clear browser cache
4. Try a different browser

### Filter link not appearing

**Symptoms:** All deliveries showing, no "Show all" link

**Expected behavior:** This is correct if:
- All deliveries succeeded (nothing to filter)
- All deliveries failed (show everything)
- Only one delivery total

Filter only shows when there's a mix of success/failure.

### Test receiver not working

**Symptoms:** Deliveries to test receiver fail

**Solutions:**
1. Ensure `simple_webhook_receiver.py` is running
2. Check it's on port 8001: `http://localhost:8001/webhook`
3. Verify endpoint URL in Endpoints tab matches
4. Check terminal for errors

### RequestBin not receiving webhooks

**Symptoms:** Event shows delivered, but RequestBin empty

**Solutions:**
1. **Refresh** the RequestBin page (not auto-updating)
2. Check the URL matches exactly (copy-paste from RequestBin)
3. Verify the event was fired to that endpoint
4. Check if bin expired (48-hour limit)

---

## Development Notes

### Running Tests

```bash
# No automated tests in this sandbox
# Manual testing recommended (see Test Scenarios above)
```

### Code Style

- **Frontend:** Vanilla JavaScript (no frameworks)
- **Backend:** FastAPI with async/await
- **Formatting:** 2-space indents (HTML/JS), 4-space (Python)
- **Comments:** Inline for complex logic only

### Contributing

If extending this project:
1. Follow existing code style
2. Test on Chrome, Firefox, Safari
3. Update CHANGELOG_MODIFICATIONS.md
4. Document new features in README


---

## License

MIT

---

## Support

For questions about the modifications:
- See CHANGELOG_MODIFICATIONS.md for technical details
- See WEBHOOK_TESTING_GUIDE.md for webhook setup
- Check browser console for JavaScript errors
- Review the Test Scenarios section above

---

## Next Steps

1. ✅ **Test locally** - Follow Quick Start above
2. ✅ **Test Webhooks** - Follow Test Scenarios
3. ✅ **Set up RequestBin** - See WEBHOOK_TESTING_GUIDE.md
4. ✅ **Review code changes** - See CHANGELOG_MODIFICATIONS.md
5. 🚀 **Deploy** - See Production Deployment Notes

