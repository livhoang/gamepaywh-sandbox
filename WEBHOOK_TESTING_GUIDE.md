# Webhook Testing Guide: Free Alternatives

This guide covers the two most popular free webhook testing services you can use with the GamePay Dev Sandbox.

---

## Option 1: RequestBin.com (Recommended for Simplicity)

**Best for:** Quick testing, viewing payloads, no account required

### Setup Instructions

#### 1. Create a New Bin

1. Go to [https://requestbin.com](https://requestbin.com)
2. Click **"Create a Request Bin"** or **"Create a public bin"**
3. You'll be redirected to your unique bin URL (e.g., `https://requestbin.com/r/en12345abcde`)

**Note:** No account needed! The bin is created instantly.

#### 2. Copy Your Endpoint URL

- Your endpoint URL will be displayed at the top of the page
- Format: `https://requestbin.com/r/YOUR_BIN_ID`
- This URL is public and accessible for **48 hours** (free tier)

#### 3. Register the Endpoint in GamePay

1. In the GamePay Dev Sandbox, go to the **Endpoints** tab
2. Click **"Register New Endpoint"**
3. Paste your RequestBin URL
4. Add a description (e.g., "RequestBin Test - Player Rewards")
5. Click **"Register"**

#### 4. Trigger an Event

1. Go to the **Events** tab in GamePay
2. Select an event type (e.g., `player_reward_earned`)
3. Select your RequestBin endpoint
4. Click **"Fire Event"**

#### 5. View the Webhook Payload

1. Go back to your RequestBin tab in your browser
2. **Refresh the page** (RequestBin doesn't auto-update)
3. You should see the POST request with:
   - Request headers (including `Content-Type`, `User-Agent`, etc.)
   - Full JSON payload
   - Timestamp

### RequestBin Features

✅ **Pros:**
- No account required
- Instant setup (< 30 seconds)
- Clean, simple interface
- Shows request headers, body, and query params
- Public bins valid for 48 hours
- Supports up to 50 requests per bin (free tier)

❌ **Cons:**
- No custom URLs without Pro plan
- Bins expire after 48 hours
- No webhook response customization
- Must manually refresh to see new requests

### Pro Tips for RequestBin

- **Bookmark your bin URL** if you're doing extended testing
- **Create multiple bins** for different event types to keep testing organized
- **Use the search/filter** if you have many requests in one bin
- For production testing, consider the Pro plan ($8/month) for private bins and custom domains

---

## Option 2: Pipedream.com (Recommended for Advanced Testing)

**Best for:** Custom logic, workflow automation, detailed inspection, long-term testing

### Setup Instructions

#### 1. Create a Free Account

1. Go to [https://pipedream.com](https://pipedream.com)
2. Click **"Sign Up"** (free forever plan available)
3. Sign up with:
   - Google account (fastest)
   - GitHub account
   - Email + password

#### 2. Create a New Workflow

1. After signing in, click **"New Workflow"** or **"+"** in the top right
2. Select **"HTTP / Webhook"** as the trigger
3. Choose **"HTTP API Requests"** from the dropdown
4. You'll see your unique endpoint URL immediately

#### 3. Copy Your Endpoint URL

- Format: `https://[random-id].m.pipedream.net`
- Example: `https://en12abc34def56.m.pipedream.net`
- This URL is permanent and won't expire (as long as the workflow exists)

#### 4. Configure the Workflow (Optional but Powerful)

By default, Pipedream just receives and logs requests. You can add custom logic:

1. Click **"+"** below the HTTP trigger step
2. Add a **Code** step (Node.js or Python)
3. Access the webhook payload with `event.body`

**Example: Log specific fields**
```javascript
// Node.js code step
export default defineComponent({
  async run({ steps, $ }) {
    const payload = steps.trigger.event.body;
    
    // Extract and log specific data
    console.log("Event Type:", payload.event_type);
    console.log("Player ID:", payload.player_id);
    console.log("Amount:", payload.reward?.amount || payload.prize?.amount);
    
    // Return formatted data
    return {
      received_at: new Date().toISOString(),
      event_summary: `${payload.event_type} for ${payload.player_id}`,
      amount: payload.reward?.amount || payload.prize?.amount
    };
  }
})
```

**Example: Send data to Slack/Discord/Email**
1. Click **"+"** after your code step
2. Search for "Slack", "Discord", or "Email"
3. Connect your account and configure the message template

#### 5. Register the Endpoint in GamePay

1. Copy your Pipedream workflow URL
2. In GamePay Dev Sandbox, go to **Endpoints** tab
3. Click **"Register New Endpoint"**
4. Paste your Pipedream URL
5. Add description (e.g., "Pipedream - Production Test")
6. Click **"Register"**

#### 6. Trigger an Event

1. Go to **Events** tab in GamePay
2. Select event type
3. Select your Pipedream endpoint
4. Click **"Fire Event"**

#### 7. View the Webhook in Pipedream

1. Go back to your Pipedream workflow tab
2. Click **"Select Event"** in the HTTP trigger section
3. Select the most recent request from the dropdown
4. You'll see:
   - Full request headers
   - JSON body (formatted and searchable)
   - Query parameters
   - IP address and timestamp

**Auto-refresh:** Pipedream updates in real-time - no manual refresh needed!

### Pipedream Features

✅ **Pros:**
- Free forever plan (100,000 invocations/month)
- Permanent URLs (don't expire)
- Real-time event viewer (auto-updates)
- Add custom logic (Node.js, Python, Go, Bash)
- Built-in integrations (Slack, Discord, Email, 1000+ apps)
- Event history saved for 30 days
- Beautiful JSON inspector
- Can return custom responses to GamePay
- Export/share workflows

❌ **Cons:**
- Requires account creation
- More complex interface (steeper learning curve)
- Overkill for simple "view payload" use cases

### Advanced Pipedream Use Cases

#### 1. Custom Response Codes

By default, Pipedream returns `200 OK`. You can customize:

```javascript
// Return custom status code
export default defineComponent({
  async run({ steps, $ }) {
    await $.respond({
      status: 201,
      headers: { "X-Custom-Header": "GamePay-Test" },
      body: { received: true, timestamp: new Date().toISOString() }
    });
  }
})
```

#### 2. Validate Webhook Signatures (Future Enhancement)

When GamePay adds webhook signatures, you can verify them:

```javascript
// Validate signature (pseudocode)
const crypto = require('crypto');

export default defineComponent({
  async run({ steps, $ }) {
    const signature = steps.trigger.event.headers['x-gamepay-signature'];
    const payload = JSON.stringify(steps.trigger.event.body);
    const secret = process.env.WEBHOOK_SECRET; // Store in Pipedream environment
    
    const expectedSignature = crypto
      .createHmac('sha256', secret)
      .update(payload)
      .digest('hex');
    
    if (signature !== expectedSignature) {
      console.log("⚠️ Invalid signature!");
      await $.respond({ status: 401 });
      return;
    }
    
    console.log("✅ Valid signature");
    // Process webhook...
  }
})
```

#### 3. Store Webhooks in Database

Connect Pipedream to:
- **Supabase** (PostgreSQL)
- **Google Sheets**
- **Airtable**
- **MongoDB**

Example: Store to Google Sheets
1. Add a **Google Sheets** action step
2. Select **"Add Row"**
3. Map fields:
   - Column A: `steps.trigger.event.body.event_type`
   - Column B: `steps.trigger.event.body.player_id`
   - Column C: `steps.trigger.event.body.timestamp`

### Pro Tips for Pipedream

- **Use environment variables** for secrets (Settings → Environment)
- **Enable workflow notifications** to get alerts on errors
- **Export workflows** as JSON for version control
- **Create separate workflows** for different environments (dev, staging, prod)
- **Use the event selector** to replay old events during testing

---

## Quick Comparison

| Feature | RequestBin | Pipedream |
|---------|-----------|-----------|
| **Setup Time** | < 30 seconds | 2-3 minutes |
| **Account Required** | No | Yes (free) |
| **URL Expiration** | 48 hours | Never |
| **Custom Logic** | No | Yes (Node.js, Python) |
| **Integrations** | No | 1000+ apps |
| **Free Tier Limits** | 50 requests/bin | 100k/month |
| **Real-time Updates** | No (manual refresh) | Yes |
| **Best For** | Quick tests | Production testing |

---

## Production Considerations

When moving to production, you'll replace these test endpoints with your actual application endpoints. Here's what you need:

### Your Production Endpoint Requirements

1. **HTTPS required** - GamePay will only send to secure endpoints
2. **Must return 2xx status code** within 5 seconds
3. **Should handle retries** - GamePay retries failed deliveries
4. **Should validate signatures** (when GamePay implements this)
5. **Should be idempotent** - same event may be delivered multiple times

### Recommended Production Setup

```javascript
// Example Express.js endpoint (Node.js)
const express = require('express');
const app = express();

app.post('/webhooks/gamepay', express.json(), async (req, res) => {
  // 1. Validate signature (when available)
  // const signature = req.headers['x-gamepay-signature'];
  // if (!isValidSignature(req.body, signature)) {
  //   return res.status(401).json({ error: 'Invalid signature' });
  // }
  
  // 2. Check idempotency
  const { idempotency_key } = req.body;
  const alreadyProcessed = await db.checkIdempotency(idempotency_key);
  if (alreadyProcessed) {
    return res.status(200).json({ message: 'Already processed' });
  }
  
  // 3. Respond quickly (don't process synchronously)
  res.status(200).json({ received: true });
  
  // 4. Process asynchronously
  await processWebhookAsync(req.body);
});

app.listen(3000);
```

---

## Troubleshooting

### RequestBin Issues

**"No requests showing"**
- Make sure you clicked "Fire Event" in GamePay
- Refresh the RequestBin page manually
- Check if the endpoint is registered and active in GamePay
- Verify the URL is correct (copy-paste error?)

**"Bin expired"**
- RequestBin bins expire after 48 hours
- Create a new bin and register the new URL

### Pipedream Issues

**"Event not appearing"**
- Click "Select Event" in the HTTP trigger
- Make sure the workflow is not paused (check top right corner)
- Check the GamePay event detail view for delivery status

**"Workflow execution failed"**
- Check the error message in Pipedream's event inspector
- Verify your code syntax if you added custom steps
- Check Pipedream's status page: [status.pipedream.com](https://status.pipedream.com)

**"Rate limit exceeded"**
- Free tier: 100,000 invocations/month
- If exceeded, upgrade to Pro or wait until next month

---

## Next Steps

1. **Test all event types** - Make sure your endpoint handles all 5 GamePay event types
2. **Test error scenarios** - Simulate failures (return 500 error in Pipedream)
3. **Test retries** - See how GamePay handles retry logic
4. **Build your production endpoint** - Use the patterns from this guide
5. **Set up monitoring** - Use Pipedream notifications or your own alerting

---

## Additional Free Alternatives (Honorable Mentions)

- **webhook.site** - Similar to RequestBin, custom URLs with account
- **beeceptor.com** - 100 requests/day free, good for API mocking
- **hookbin.com** - Simple, lightweight alternative to RequestBin
- **ngrok.com** - For testing localhost endpoints (tunneling)

---

**Need help?** Check the GamePay Dev Sandbox README or the built-in AI assistant for troubleshooting tips.
