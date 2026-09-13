---
name: Webhook Handler Generator
description: Draft secure webhook receiver endpoints complete with cryptographic signature verification (Stripe, GitHub, Midtrans).
metadata:
  source: skills/webhook-handler-generator/webhook-handler-generator.md
---

# Webhook Handler Generator

## Prerequisites & Dependencies
- Node.js 18+ with npm or pnpm
- Mandatory packages: `npm i express webhook-receiver` or `npm i stripe`, `npm i @octokit/webhooks` for GitHub
- Access to webhook signing secrets: Stripe `webhook secret`, GitHub `webhook secret`, Midtrans `server key hash`
- Optional: `npm i crypto` (built-in Node.js, no install needed), `npm i helm` for deployment testing
- A secure endpoint URL (HTTPS recommended) and a tunneling tool for local development: `ngrok` or `cloudflared`

## Execution Steps
1. Identify the webhook source: Stripe, GitHub, Midtrans, or custom; each has a different signing mechanism
2. Retrieve the webhook signing secret/key from your provider's dashboard and store it as an environment variable (`WEBHOOK_SECRET`, `STRIPE_WEBHOOK_SECRET`, `GITHUB_WEBHOOK_SECRET`)
3. Set up the receiver endpoint using Express (or your preferred framework): `POST /webhook/:source`
4. Implement signature verification:
   - **Stripe**: `stripe.webhooks.constructEvent(rawBody, signature, webhookSecret)` – verifies `Temporal-Signature` header
   - **GitHub**: `@octokit/webhooks` – validates `X-Hub-Signature-256` using the secret
   - **Midtrans**: hash the `notification_id` and `status_code` with SHA-512 using the server key
5. Parse the verified event payload: extract the relevant data (payment intent, issue number, order ID)
6. Process the business logic: update database, trigger email/SMS, fulfill order, return `200 OK` promptly (within 10s)
7. Idempotency: store received event IDs and skip reprocessing if already handled; return `200 OK` to acknowledge
8. Error handling: return `400` for verification failures, `500` for processing errors; avoid infinite retries

```javascript
// Example: Secure Stripe webhook handler with Express
const express = require('express');
const stripe = require('stripe')(process.env.STRIPE_SECRET_KEY);
const endpointRouter = express.Router();

endpointRouter.post(
  '/stripe',
  express.raw({ type: 'application/json' }),
  (request, response) => {
    const sig = request.headers['stripe-signature'];
    let event;

    try {
      event = stripe.webhooks.constructEvent(
        request.body,
        sig,
        process.env.STRIPE_WEBHOOK_SECRET
      );
    } catch (err) {
      console.warn(`⚠️  Webhook signature verification failed: ${err.message}`);
      return response.status(400).send(`Webhook Error: ${err.message}`);
    }

    // Handle the event
    switch (event.type) {
      case 'payment_intent.succeeded':
        const paymentIntent = event.data.object;
        // TODO: fulfill order, update DB, send confirmation email
        console.log(`💳 PaymentIntent ${paymentIntent.id} succeeded`);
        break;
      case 'payment_intent.payment_failed':
        console.log(`❌ PaymentIntent ${event.data.object.id} failed`);
        break;
      default:
        console.log(`✅ Unhandled event type: ${event.type}`);
    }

    // Respond 200 OK to acknowledge receipt (idempotent)
    response.json({ received: true });
  }
);

module.exports = endpointRouter;
```

```bash
# Local development with ngrok
ngrok http 4000   # expose local port 4000 to https://<sub>.ngrok.io

# Set webhook URL in Stripe dashboard
# https://<sub>.ngrok.io/webhook/stripe

# Verify locally (optional)
stripe listen --forward-to http://localhost:4000/webhook/stripe
```

```bash
npm i express stripe
```
