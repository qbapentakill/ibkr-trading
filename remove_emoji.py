#!/usr/bin/env python3
"""Usuwa wszystkie emotki z pliku dashboard.py"""
import re

# Wczytaj plik
with open("panel/frontend/dashboard.py", "r", encoding="utf-8") as f:
    content = f.read()

# Regex dla emotek (Unicode ranges)
emoji_pattern = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emotikony
    "\U0001F300-\U0001F5FF"  # symbole i piktogramy
    "\U0001F680-\U0001F6FF"  # transport i symbole map
    "\U0001F1E0-\U0001F1FF"  # flagi (iOS)
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "\U0001F900-\U0001F9FF"  # emotki dodatkowe
    "\U0001FA70-\U0001FAFF"  # symbole rozszerzone A
    "\u2600-\u26FF"          # różne symbole
    "\u2700-\u27BF"          # dingbaty
    "]+",
    flags=re.UNICODE
)

# Usuń emotki
content_no_emoji = emoji_pattern.sub("", content)

# Zapisz
with open("panel/frontend/dashboard.py", "w", encoding="utf-8") as f:
    f.write(content_no_emoji)

print("✓ Emotki usunięte z dashboard.py")
