#!/usr/bin/env python3
"""Generuje hash hasła do panelu sterowania."""
import bcrypt

password = input("Wprowadź nowe hasło panelu: ").strip()
if not password:
    print("❌ Hasło nie może być puste")
    exit(1)

hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
print("\n✅ Hash hasła (skopiuj do .env):\n")
print(hashed)
print("\n💾 Ustaw w .env:")
print(f"PANEL_PASSWORD_HASH={hashed}")
