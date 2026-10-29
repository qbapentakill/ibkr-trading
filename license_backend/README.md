# License Verification Backend

Backend API do weryfikacji licencji trading bota. Darmowy hosting na Railway.app.

## 🚀 Quick Start

### 1. Setup Supabase (FREE)

1. Załóż konto: https://supabase.com
2. Utwórz nowy projekt (wybierz region blisko użytkowników)
3. Skopiuj:
   - Project URL: `https://xxxxx.supabase.co`
   - Anon key: `eyJhbGc...`
4. Otwórz SQL Editor i wklej zawartość `supabase_schema.sql`
5. Uruchom query (utworzy tabele)

### 2. Setup Stripe (FREE)

1. Załóż konto: https://stripe.com
2. Pobierz klucze z Dashboard → API keys:
   - Secret key: `sk_test_xxxxx`
3. Utwórz produkty:
   - Basic: $49/miesiąc
   - Pro: $99/miesiąc
   - Elite: $199/miesiąc
4. Skopiuj Price IDs (będzie potrzebne w Task #5)

### 3. Deploy na Railway.app (FREE)

1. Załóż konto: https://railway.app (login przez GitHub)
2. New Project → Deploy from GitHub repo
3. Wybierz folder `license_backend`
4. Dodaj Environment Variables:
   ```
   SUPABASE_URL=https://xxxxx.supabase.co
   SUPABASE_KEY=eyJhbGc...
   STRIPE_SECRET_KEY=sk_test_...
   STRIPE_WEBHOOK_SECRET=whsec_... (później)
   ```
5. Deploy!
6. Skopiuj URL: `https://your-app.up.railway.app`

### 4. Setup Stripe Webhook

1. Stripe Dashboard → Webhooks → Add endpoint
2. URL: `https://your-app.up.railway.app/webhook/stripe`
3. Events to send:
   - `checkout.session.completed`
   - `customer.subscription.deleted`
4. Skopiuj Signing secret: `whsec_xxxxx`
5. Dodaj do Railway env vars: `STRIPE_WEBHOOK_SECRET=whsec_xxxxx`

### 5. Setup Resend.io Email (FREE)

1. Załóż konto: https://resend.com
2. Verify domain (lub użyj resend.dev do testów)
3. Skopiuj API key: `re_xxxxx`
4. Dodaj do Railway env vars:
   ```
   RESEND_API_KEY=re_xxxxx
   FROM_EMAIL=noreply@your-domain.com
   FROM_NAME=Trading Bot
   ```
5. **Full guide:** Zobacz `EMAIL_SETUP.md`

## 🧪 Testowanie Local

```bash
# Install dependencies
pip install -r requirements.txt

# Stwórz .env file (skopiuj z .env.example)
cp .env.example .env
# Uzupełnij klucze API

# Uruchom serwer
uvicorn main:app --reload

# Test endpoint
curl http://localhost:8000/health

# Test verify (bez prawdziwego klucza - zwróci false)
curl -X POST http://localhost:8000/verify \
  -H "Content-Type: application/json" \
  -d '{"license_key": "TEST-1234-ABCD-5678"}'

# Test email sending
python test_email.py your-email@example.com
python test_email.py your-email@example.com renewal
python test_email.py your-email@example.com payment_failed
```

## 📧 Automated Emails

System automatycznie wysyła emaile przez Resend.io:

| Event | Email Type | When Sent |
|-------|-----------|-----------|
| Payment successful | License Key | Immediately after Stripe checkout |
| 7 days before expiry | Renewal Reminder | Requires cron job (see EMAIL_SETUP.md) |
| Payment failed | Payment Failed | When Stripe invoice fails |

**Email templates:** `email_service.py`
**Setup guide:** `EMAIL_SETUP.md`
**Test:** `python test_email.py your-email@example.com`

## 📊 Endpoints

### `GET /health`
Health check

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-09-15T12:00:00",
  "version": "1.0.0"
}
```

### `POST /verify`
Weryfikuje klucz licencyjny

**Request:**
```json
{
  "license_key": "ABC-123-XYZ-789",
  "bot_version": "1.0.0"
}
```

**Response (success):**
```json
{
  "valid": true,
  "tier": "pro",
  "expires_at": "2027-10-15T12:00:00Z",
  "enabled_agents": ["scalper", "trend_follower", "momentum_surfer", "breakout_hunter", "mean_reversion"],
  "message": "License valid"
}
```

**Response (invalid):**
```json
{
  "valid": false,
  "tier": null,
  "expires_at": null,
  "enabled_agents": null,
  "message": "Invalid license key"
}
```

### `POST /webhook/stripe`
Webhook Stripe (automatyczna generacja licencji po płatności)

### `GET /tiers`
Zwraca dostępne tiery (dla strony cennikowej)

**Response:**
```json
{
  "tiers": {
    "basic": {
      "price": 49,
      "agents": ["scalper", "trend_follower"],
      "description": "2 podstawowe boty"
    },
    "pro": {
      "price": 99,
      "agents": ["scalper", "trend_follower", "momentum_surfer", "breakout_hunter", "mean_reversion"],
      "description": "5 zaawansowanych botów"
    },
    "elite": {
      "price": 199,
      "agents": ["scalper", "trend_follower", "momentum_surfer", ...],
      "description": "Wszystkie 11 botów + auxiliary agents"
    }
  }
}
```

## 🔐 Bezpieczeństwo

- Klucze licencyjne są hashowane (SHA256) przed zapisem do DB
- Stripe webhooks weryfikowane przez signature
- HTTPS wymuszony przez Railway.app
- CORS skonfigurowany (zmień `allow_origins` w produkcji)

## 📈 Monitoring

Sprawdź logi na Railway:
```
https://railway.app/project/your-project/logs
```

Monitoruj usage Supabase:
```
https://supabase.com/dashboard/project/xxxxx/settings/usage
```

## 💰 Free Tier Limits

**Railway.app:**
- 500h execution time/miesiąc
- $5 credit/miesiąc (wystarczy na małe API)

**Supabase:**
- 500MB database
- 2GB bandwidth/miesiąc
- Unlimited API requests

**Wystarczy na ~100-200 aktywnych użytkowników.**

## 🐛 Troubleshooting

**"Webhook signature verification failed"**
- Sprawdź czy `STRIPE_WEBHOOK_SECRET` jest poprawny
- Użyj `stripe listen --forward-to localhost:8000/webhook/stripe` do testowania local

**"No data returned from Supabase"**
- Sprawdź czy tabela `licenses` istnieje
- Sprawdź RLS policies (może blokować zapytania)

**"Railway app crash"**
- Sprawdź logi: railway logs
- Sprawdź czy wszystkie env vars są ustawione
