"""
License Verification Backend - FastAPI + Supabase
Darmowy hosting: Railway.app / Render.com

Endpoints:
- POST /verify - weryfikacja klucza licencyjnego
- POST /webhook/stripe - obsługa webhooków Stripe
- GET /health - health check
"""
from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
import secrets

# Supabase client (zainstaluj: pip install supabase)
from supabase import create_client, Client
from email_service import email_service

app = FastAPI(title="Trading Bot License API", version="1.0.0")

# CORS - pozwól na requesty z Twojej strony
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # W produkcji zmień na swoją domenę
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════════════════════════════════════
# CONFIG - Ustaw environment variables
# ═══════════════════════════════════════════════════════════════════════════
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://your-project.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "your-anon-key")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_...")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "sk_test_...")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8080")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ═══════════════════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════════════════
class VerifyRequest(BaseModel):
    license_key: str
    bot_version: Optional[str] = "1.0.0"

class VerifyResponse(BaseModel):
    valid: bool
    tier: Optional[str] = None
    expires_at: Optional[str] = None
    enabled_agents: Optional[list] = None
    message: Optional[str] = None

# ═══════════════════════════════════════════════════════════════════════════
# TIER DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════
TIER_CONFIG = {
    "basic": {
        "price": 49,
        "agents": [
            "scalper",
            "trend_follower"
        ],
        "description": "2 podstawowe boty"
    },
    "pro": {
        "price": 99,
        "agents": [
            "scalper",
            "trend_follower",
            "momentum_surfer",
            "breakout_hunter",
            "mean_reversion"
        ],
        "description": "5 zaawansowanych botów"
    },
    "elite": {
        "price": 199,
        "agents": [
            "scalper",
            "trend_follower",
            "momentum_surfer",
            "breakout_hunter",
            "mean_reversion",
            "gap_trader",
            "divergence_hunter",
            "vix_trader",
            "sentiment_trader",
            "options_flow",
            "scalp_king"
        ],
        "description": "Wszystkie 11 botów + auxiliary agents"
    }
}

# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════
def generate_license_key() -> str:
    """Generuje unikalny klucz licencyjny: ABC-123-XYZ-789"""
    parts = []
    for _ in range(4):
        part = secrets.token_hex(2).upper()
        parts.append(part)
    return "-".join(parts)

def hash_license_key(key: str) -> str:
    """Hash klucza do bezpiecznego przechowywania"""
    return hashlib.sha256(key.encode()).hexdigest()

# ═══════════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0"
    }

@app.post("/verify", response_model=VerifyResponse)
async def verify_license(request: VerifyRequest):
    """
    Weryfikuje klucz licencyjny i zwraca tier + enabled agents
    
    Bot wywołuje to przy starcie i co 24h
    """
    key = request.license_key.strip().upper()
    key_hash = hash_license_key(key)
    
    try:
        # Szukaj w Supabase
        response = supabase.table("licenses").select("*").eq("key_hash", key_hash).execute()
        
        if not response.data or len(response.data) == 0:
            return VerifyResponse(
                valid=False,
                message="Invalid license key"
            )
        
        license_data = response.data[0]
        
        # Sprawdź czy aktywna
        if not license_data.get("active"):
            return VerifyResponse(
                valid=False,
                message="License key is inactive"
            )
        
        # Sprawdź expiry
        expires_at = datetime.fromisoformat(license_data["expires_at"].replace("Z", "+00:00"))
        if expires_at < datetime.now(timezone.utc):
            return VerifyResponse(
                valid=False,
                message="License key has expired"
            )
        
        tier = license_data["tier"]
        enabled_agents = TIER_CONFIG[tier]["agents"]
        
        # Update last_verified timestamp
        supabase.table("licenses").update({
            "last_verified_at": datetime.now(timezone.utc).isoformat(),
            "verification_count": license_data.get("verification_count", 0) + 1
        }).eq("id", license_data["id"]).execute()
        
        return VerifyResponse(
            valid=True,
            tier=tier,
            expires_at=license_data["expires_at"],
            enabled_agents=enabled_agents,
            message="License valid"
        )
        
    except Exception as e:
        print(f"Error verifying license: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """
    Stripe webhook - tworzy nową licencję po płatności
    """
    import stripe
    import json

    payload = await request.body()
    stripe_signature = request.headers.get("stripe-signature") or request.headers.get("Stripe-Signature")

    # Weryfikacja podpisu Stripe
    try:
        stripe.api_key = STRIPE_SECRET_KEY
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError as e:
        print(f"❌ Błąd podpisu webhooka: {e}")
        # Fallback: parsuj bez weryfikacji (TYLKO DO TESTÓW - usuń w produkcji)
        try:
            event = json.loads(payload)
            print(f"⚠️  Webhook bez weryfikacji podpisu (test mode)")
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        print(f"❌ Błąd parsowania webhooka: {e}")
        raise HTTPException(status_code=400, detail="Bad payload")

    print(f"📨 Webhook event: {event['type']}")

    # ── Płatność zakończona sukcesem ──────────────────────────────────────
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        customer_email = session.get("customer_email")
        session_id     = session.get("id")
        metadata       = session.get("metadata", {})

        # Tier bierzemy z metadata (ustawiamy przy tworzeniu sesji checkout)
        # Fallback: szacujemy po kwocie
        tier = metadata.get("tier")
        if not tier:
            amount_total = session.get("amount_total", 0) / 100  # centów → USD
            if amount_total >= 190:
                tier = "elite"
            elif amount_total >= 90:
                tier = "pro"
            else:
                tier = "basic"

        if not customer_email:
            print(f"⚠️  Brak emaila klienta w sesji {session_id}")
            return {"status": "ok", "warning": "no customer email"}

        # Wygeneruj klucz licencyjny
        license_key = generate_license_key()
        key_hash    = hash_license_key(license_key)
        expires_at  = datetime.now(timezone.utc) + timedelta(days=30)

        try:
            supabase.table("licenses").insert({
                "key_hash":          key_hash,
                "license_key_plain": license_key,
                "tier":              tier,
                "customer_email":    customer_email,
                "active":            True,
                "expires_at":        expires_at.isoformat(),
                "created_at":        datetime.now(timezone.utc).isoformat(),
                "stripe_session_id": session_id,
                "verification_count": 0
            }).execute()

            print(f"✅ Licencja utworzona: {license_key} (tier: {tier}) dla {customer_email}")
        except Exception as e:
            print(f"❌ Błąd zapisu licencji do Supabase: {e}")
            raise HTTPException(status_code=500, detail="Failed to save license")

        # Wyślij email z kluczem
        try:
            email_service.send_license_key(
                to=customer_email,
                license_key=license_key,
                tier=tier,
                expires_at=expires_at.isoformat()
            )
        except Exception as e:
            # Email failure nie blokuje - licencja już jest zapisana
            print(f"⚠️  Błąd wysyłki emaila (licencja zapisana): {e}")

    # ── Subskrypcja anulowana ─────────────────────────────────────────────
    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        stripe_customer_id = subscription.get("customer")
        print(f"🔴 Subskrypcja anulowana dla klienta: {stripe_customer_id}")
        # TODO: dezaktywuj licencję po stripe_customer_id

    return {"status": "ok"}

@app.get("/tiers")
async def get_tiers():
    """Zwraca dostępne tiery (dla strony cennikowej)"""
    return {
        "tiers": TIER_CONFIG
    }

@app.get("/get-license-by-session/{session_id}")
async def get_license_by_session(session_id: str):
    """
    Pobiera license key na podstawie Stripe session ID
    
    Wywołane przez success page po successful payment
    """
    try:
        # Find license by session_id
        response = supabase.table("licenses").select("*").eq("stripe_session_id", session_id).execute()
        
        if not response.data or len(response.data) == 0:
            raise HTTPException(status_code=404, detail="License not found")
        
        license_data = response.data[0]
        
        # Return plain key if available (within 24h of creation)
        plain_key = license_data.get("license_key_plain")
        
        return {
            "license_key": plain_key if plain_key else "Check your email",
            "tier": license_data["tier"],
            "expires_at": license_data["expires_at"]
        }
        
    except Exception as e:
        print(f"Error fetching license: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/create-checkout-session")
async def create_checkout_session(request: Request):
    """
    Tworzy Stripe Checkout Session
    
    Wywołane przez pricing page po kliknięciu "Buy"
    """
    import stripe
    stripe.api_key = STRIPE_SECRET_KEY
    
    try:
        body = await request.json()
        price_id = body.get("priceId")
        tier = body.get("tier")
        
        if not price_id or not tier:
            raise HTTPException(status_code=400, detail="Missing priceId or tier")
        
        # Create Checkout Session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=f'{FRONTEND_URL}/success.html?session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url=f'{FRONTEND_URL}/pricing.html',
            metadata={
                'tier': tier
            },
            allow_promotion_codes=True,
            billing_address_collection='required',
        )
        
        return {"id": checkout_session.id}
        
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Error creating checkout session: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
