"""
Skrypt do manualnego tworzenia test licencji (dla Ciebie do testowania)

Usage:
    python create_test_license.py --tier pro --email test@example.com --days 30
"""
import os
import secrets
import hashlib
from datetime import datetime, timedelta
from supabase import create_client
from dotenv import load_dotenv
import argparse

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def generate_license_key() -> str:
    """Generuje klucz: ABC-123-XYZ-789"""
    parts = []
    for _ in range(4):
        part = secrets.token_hex(2).upper()
        parts.append(part)
    return "-".join(parts)

def hash_license_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()

def create_license(tier: str, email: str, days: int = 30):
    """Tworzy nową licencję w Supabase"""
    license_key = generate_license_key()
    key_hash = hash_license_key(license_key)
    expires_at = datetime.utcnow() + timedelta(days=days)
    
    try:
        response = supabase.table("licenses").insert({
            "key_hash": key_hash,
            "tier": tier,
            "customer_email": email,
            "active": True,
            "expires_at": expires_at.isoformat(),
            "created_at": datetime.utcnow().isoformat(),
            "verification_count": 0,
            "notes": "Test license - manually created"
        }).execute()
        
        print("✓ Licencja utworzona!")
        print(f"  Klucz: {license_key}")
        print(f"  Tier: {tier}")
        print(f"  Email: {email}")
        print(f"  Wygasa: {expires_at.strftime('%Y-%m-%d %H:%M')}")
        print(f"\n  Test command:")
        print(f'  curl -X POST http://localhost:8000/verify -H "Content-Type: application/json" -d \'{{"license_key": "{license_key}"}}\'')
        
        return license_key
        
    except Exception as e:
        print(f"❌ Błąd: {e}")
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create test license")
    parser.add_argument("--tier", choices=["basic", "pro", "elite"], default="pro", help="License tier")
    parser.add_argument("--email", default="test@example.com", help="Customer email")
    parser.add_argument("--days", type=int, default=30, help="Valid for N days")
    
    args = parser.parse_args()
    
    create_license(args.tier, args.email, args.days)
