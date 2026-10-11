# Manual production tests

Run these in **cmd** to check the live deployment by hand. `curl` ships with Windows.

## Setup (once per cmd window)

```cmd
cd /d "A:\VS CODE PROGRAM\agent-action-firewall\agent-action-firewall\backend"
for /f "tokens=1,* delims==" %a in ('findstr /b "DEMO_" .env.agent-keys.local') do set "%a=%b"
set API=https://agent-action-firewall-api.onrender.com
```

This loads both agent keys from `backend\.env.agent-keys.local` without printing them.

## 1. Backend is alive

```cmd
curl %API%/health
```

Expected: `{"status":"ok"}`. The first call after 15 idle minutes can take about a minute (Render free plan).

## 2. Real email is sent

Replace `you@gmail.com` with your own address.

```cmd
curl -X POST %API%/actions/request -H "X-API-Key: %DEMO_EMAIL_AGENT_KEY%" -H "Content-Type: application/json" -d "{\"action_type\":\"send_email\",\"payload\":{\"to\":\"you@gmail.com\",\"subject\":\"My manual test\",\"body\":\"Hello from the firewall\"}}"
```

Expected: `"decision":"allow"`, `"status":"executed"`, and the email arrives.

## 3. Small payment is allowed ($10)

Amounts are in cents (1000 = $10).

```cmd
curl -X POST %API%/actions/request -H "X-API-Key: %DEMO_PAYMENTS_AGENT_KEY%" -H "Content-Type: application/json" -d "{\"action_type\":\"make_payment\",\"payload\":{\"amount\":1000,\"currency\":\"usd\",\"description\":\"small test\"}}"
```

Expected: `"decision":"allow"`, `"status":"executed"`, an ID starting with `pi_`.

## 4. Big payment needs approval ($75)

```cmd
curl -X POST %API%/actions/request -H "X-API-Key: %DEMO_PAYMENTS_AGENT_KEY%" -H "Content-Type: application/json" -d "{\"action_type\":\"make_payment\",\"payload\":{\"amount\":7500,\"currency\":\"usd\",\"description\":\"big test\"}}"
```

Expected: `"decision":"needs_approval"`. Then open the dashboard, go to **Approvals**, and click **Approve**. The card should show it as executed.

## 5. Rate limit

Run the test 3 command four times within one minute.

Expected: the first 3 say `allow`; the 4th says `"decision":"deny"` with `"code":"rate_limited"`. It works again after a minute.

## 6. Bad agent key is rejected

```cmd
curl -X POST %API%/actions/request -H "X-API-Key: wrong-key" -H "Content-Type: application/json" -d "{\"action_type\":\"send_email\",\"payload\":{}}"
```

Expected: 401, nothing sent.

## 7. Wrong password is rejected

Sign in to the dashboard with a wrong password.

Expected: "Invalid username or password". More than 10 attempts in 5 minutes locks the login for a few minutes.

## Check the results

- **Agents** page: both demo agents listed, counts go up.
- **Audit** page: every test appears with its outcome.
- **Stripe** (dashboard.stripe.com, Test mode → Payments): the test payments. No real money moves.

## Troubleshooting

- Email fails with `invalid_grant`: the Gmail token expired (about every 7 days). Run `.venv\Scripts\python -m app.manage gmail-auth` and update `GMAIL_REFRESH_TOKEN` in Render.
- Dashboard says "Can't reach the firewall API": Render may be waking up (wait a minute), or `CORS_ORIGINS` in Render isn't `["https://agent-action-firewall.vercel.app"]`.
