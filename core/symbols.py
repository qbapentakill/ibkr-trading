"""
Słownik symboli — skrót → pełna nazwa + kategoria.
Używany w panelu do wyświetlania pełnych nazw przy wyszukiwaniu.
"""

SYMBOL_NAMES: dict[str, tuple[str, str]] = {
    # format: "TICKER": ("Pełna nazwa", "kategoria")

    # ── Krypto ────────────────────────────────────────────────────────────────
    "BTC":   ("Bitcoin",              "crypto"),
    "ETH":   ("Ethereum",             "crypto"),
    "SOL":   ("Solana",               "crypto"),
    "BNB":   ("Binance Coin",         "crypto"),
    "XRP":   ("Ripple",               "crypto"),
    "ADA":   ("Cardano",              "crypto"),
    "AVAX":  ("Avalanche",            "crypto"),
    "DOT":   ("Polkadot",             "crypto"),
    "LINK":  ("Chainlink",            "crypto"),
    "UNI":   ("Uniswap",              "crypto"),
    "MATIC": ("Polygon",              "crypto"),
    "DOGE":  ("Dogecoin",             "crypto"),
    "SHIB":  ("Shiba Inu",            "crypto"),
    "LTC":   ("Litecoin",             "crypto"),
    "BCH":   ("Bitcoin Cash",         "crypto"),
    "ATOM":  ("Cosmos",               "crypto"),
    "NEAR":  ("NEAR Protocol",        "crypto"),
    "APT":   ("Aptos",                "crypto"),
    "ARB":   ("Arbitrum",             "crypto"),
    "OP":    ("Optimism",             "crypto"),
    "INJ":   ("Injective",            "crypto"),
    "TIA":   ("Celestia",             "crypto"),
    "PYTH":  ("Pyth Network",         "crypto"),
    "WIF":   ("dogwifhat",            "crypto"),
    "PEPE":  ("Pepe",                 "crypto"),
    "BONK":  ("Bonk",                 "crypto"),
    "TON":   ("Toncoin",              "crypto"),
    "SUI":   ("Sui",                  "crypto"),
    "SEI":   ("Sei",                  "crypto"),
    "JUP":   ("Jupiter",              "crypto"),
    "RNDR":  ("Render",               "crypto"),
    "FIL":   ("Filecoin",             "crypto"),
    "ICP":   ("Internet Computer",    "crypto"),
    "GRT":   ("The Graph",            "crypto"),
    "AAVE":  ("Aave",                 "crypto"),
    "MKR":   ("Maker",                "crypto"),
    "CRV":   ("Curve DAO",            "crypto"),
    "SNX":   ("Synthetix",            "crypto"),
    "LDO":   ("Lido DAO",             "crypto"),
    "FTM":   ("Fantom",               "crypto"),
    "ALGO":  ("Algorand",             "crypto"),
    "VET":   ("VeChain",              "crypto"),
    "XLM":   ("Stellar",              "crypto"),
    "HBAR":  ("Hedera",               "crypto"),
    "EOS":   ("EOS",                  "crypto"),
    "XTZ":   ("Tezos",                "crypto"),
    "SAND":  ("The Sandbox",          "crypto"),
    "MANA":  ("Decentraland",         "crypto"),
    "AXS":   ("Axie Infinity",        "crypto"),
    "THETA": ("Theta Network",        "crypto"),

    # ── Krypto ETF ────────────────────────────────────────────────────────────
    "IBIT":  ("iShares Bitcoin ETF",  "crypto_etf"),
    "FBTC":  ("Fidelity Bitcoin ETF", "crypto_etf"),
    "GBTC":  ("Grayscale Bitcoin",    "crypto_etf"),
    "BITO":  ("ProShares Bitcoin ETF","crypto_etf"),
    "ARKB":  ("ARK Bitcoin ETF",      "crypto_etf"),
    "EZBC":  ("Franklin Bitcoin ETF", "crypto_etf"),
    "MSTR":  ("MicroStrategy",        "crypto_etf"),
    "COIN":  ("Coinbase",             "crypto_etf"),

    # ── Mega-cap US ───────────────────────────────────────────────────────────
    "AAPL":  ("Apple",                "us_stock"),
    "MSFT":  ("Microsoft",            "us_stock"),
    "NVDA":  ("NVIDIA",               "us_stock"),
    "GOOGL": ("Alphabet (Google)",    "us_stock"),
    "AMZN":  ("Amazon",               "us_stock"),
    "META":  ("Meta Platforms",       "us_stock"),
    "TSLA":  ("Tesla",                "us_stock"),
    "NFLX":  ("Netflix",              "us_stock"),
    "AMD":   ("Advanced Micro Devices","us_stock"),
    "INTC":  ("Intel",                "us_stock"),
    "AVGO":  ("Broadcom",             "us_stock"),
    "QCOM":  ("Qualcomm",             "us_stock"),
    "ARM":   ("Arm Holdings",         "us_stock"),
    "TSM":   ("TSMC",                 "us_stock"),
    "ASML":  ("ASML Holding",         "us_stock"),
    "MU":    ("Micron Technology",    "us_stock"),
    "CRM":   ("Salesforce",           "us_stock"),
    "ORCL":  ("Oracle",               "us_stock"),
    "ADBE":  ("Adobe",                "us_stock"),
    "SNOW":  ("Snowflake",            "us_stock"),
    "PLTR":  ("Palantir",             "us_stock"),
    "UBER":  ("Uber",                 "us_stock"),
    "JPM":   ("JPMorgan Chase",       "us_stock"),
    "BAC":   ("Bank of America",      "us_stock"),
    "GS":    ("Goldman Sachs",        "us_stock"),
    "V":     ("Visa",                 "us_stock"),
    "MA":    ("Mastercard",           "us_stock"),
    "PYPL":  ("PayPal",               "us_stock"),
    "JNJ":   ("Johnson & Johnson",    "us_stock"),
    "PFE":   ("Pfizer",               "us_stock"),
    "MRNA":  ("Moderna",              "us_stock"),
    "LLY":   ("Eli Lilly",            "us_stock"),
    "XOM":   ("ExxonMobil",           "us_stock"),
    "CVX":   ("Chevron",              "us_stock"),
    "WMT":   ("Walmart",              "us_stock"),
    "COST":  ("Costco",               "us_stock"),
    "MCD":   ("McDonald's",           "us_stock"),
    "DIS":   ("Disney",               "us_stock"),
    "BA":    ("Boeing",               "us_stock"),
    "HOOD":  ("Robinhood",            "us_stock"),
    "RIVN":  ("Rivian",               "us_stock"),
    "SOFI":  ("SoFi Technologies",    "us_stock"),
    "RBLX":  ("Roblox",               "us_stock"),
    "SNAP":  ("Snap",                 "us_stock"),
    "RDDT":  ("Reddit",               "us_stock"),
    "ABNB":  ("Airbnb",               "us_stock"),
    "DASH":  ("DoorDash",             "us_stock"),

    # ── ETF ───────────────────────────────────────────────────────────────────
    "SPY":   ("SPDR S&P 500 ETF",     "etf"),
    "QQQ":   ("Invesco Nasdaq 100",   "etf"),
    "IWM":   ("iShares Russell 2000", "etf"),
    "DIA":   ("SPDR Dow Jones ETF",   "etf"),
    "VTI":   ("Vanguard Total Market","etf"),
    "VOO":   ("Vanguard S&P 500",     "etf"),
    "TQQQ":  ("ProShares UltraPro QQQ","etf"),
    "SQQQ":  ("ProShares UltraShort QQQ","etf"),
    "SOXL":  ("Direxion Semi Bull 3x","etf"),
    "GLD":   ("SPDR Gold Shares",     "etf"),
    "SLV":   ("iShares Silver Trust", "etf"),

    # ── Polska GPW ────────────────────────────────────────────────────────────
    "ARLN":  ("Arlen SA",             "pl_stock"),
    "PKN":   ("PKN Orlen",            "pl_stock"),
    "PKO":   ("PKO Bank Polski",      "pl_stock"),
    "PZU":   ("PZU SA",               "pl_stock"),
    "CDR":   ("CD Projekt",           "pl_stock"),
    "ALE":   ("Allegro",              "pl_stock"),
    "DNP":   ("Dino Polska",          "pl_stock"),
    "KGH":   ("KGHM",                 "pl_stock"),
    "JSW":   ("Jastrzębska Spółka Węglowa","pl_stock"),
    "LPP":   ("LPP SA",               "pl_stock"),
    "CCC":   ("CCC SA",               "pl_stock"),
    "MBK":   ("mBank",                "pl_stock"),
    "PEO":   ("Bank Pekao",           "pl_stock"),
    "ING":   ("ING Bank Śląski",      "pl_stock"),
    "SPL":   ("Santander Bank Polska","pl_stock"),
    "OPL":   ("Orange Polska",        "pl_stock"),
    "PGN":   ("PGNiG",                "pl_stock"),
    "TPE":   ("Tauron",               "pl_stock"),
    "ENA":   ("Enea",                 "pl_stock"),
    "PGE":   ("PGE",                  "pl_stock"),
    "LTS":   ("Lotos",                "pl_stock"),
    "MRC":   ("Mercator Medical",     "pl_stock"),
    "PCO":   ("Polen Capital",        "pl_stock"),
    "AMC":   ("AmRest",               "pl_stock"),
    "ACP":   ("Asseco Poland",        "pl_stock"),

    # ── Wielka Brytania LSE ───────────────────────────────────────────────────
    "HSBA":  ("HSBC Holdings",        "uk_stock"),
    "BP":    ("BP plc",               "uk_stock"),
    "SHEL":  ("Shell plc",            "uk_stock"),
    "GSK":   ("GSK plc",              "uk_stock"),
    "AZN":   ("AstraZeneca",          "uk_stock"),
    "ULVR":  ("Unilever",             "uk_stock"),
    "RIO":   ("Rio Tinto",            "uk_stock"),
    "AAL":   ("Anglo American",       "uk_stock"),
    "BARC":  ("Barclays",             "uk_stock"),
    "LLOY":  ("Lloyds Banking",       "uk_stock"),
    "NWG":   ("NatWest Group",        "uk_stock"),
    "VOD":   ("Vodafone",             "uk_stock"),
    "BT":    ("BT Group",             "uk_stock"),
    "IAG":   ("IAG (British Airways)","uk_stock"),
    "RR":    ("Rolls-Royce",          "uk_stock"),
    "BAE":   ("BAE Systems",          "uk_stock"),
    "REL":   ("RELX",                 "uk_stock"),
    "DGE":   ("Diageo",               "uk_stock"),
    "CPG":   ("Compass Group",        "uk_stock"),
    "EXPN":  ("Experian",             "uk_stock"),
    "LSE":   ("London Stock Exchange","uk_stock"),
    "LGEN":  ("Legal & General",      "uk_stock"),
    "PRU":   ("Prudential",           "uk_stock"),
    "STAN":  ("Standard Chartered",   "uk_stock"),
    "ABF":   ("Associated British Foods","uk_stock"),
}

CATEGORY_LABELS = {
    "crypto":     "₿ Krypto",
    "crypto_etf": "₿ Krypto ETF",
    "us_stock":   "🇺🇸 Akcje US",
    "etf":        "📊 ETF",
    "pl_stock":   "🇵🇱 Polska GPW",
    "uk_stock":   "🇬🇧 Wielka Brytania LSE",
}


def get_full_name(ticker: str) -> str:
    """Zwraca pełną nazwę dla tickera, np. BTC → Bitcoin."""
    entry = SYMBOL_NAMES.get(ticker.upper())
    return entry[0] if entry else ticker


def get_display(ticker: str) -> str:
    """Zwraca 'TICKER — Pełna nazwa' dla selectbox."""
    name = get_full_name(ticker)
    return f"{ticker} — {name}" if name != ticker else ticker


def search_symbols(query: str, category: str | None = None) -> list[str]:
    """Wyszukuje tickery po nazwie lub tickerze."""
    q = query.strip().upper()
    results = []
    for ticker, (name, cat) in SYMBOL_NAMES.items():
        if category and cat != category:
            continue
        if q in ticker or q in name.upper():
            results.append(ticker)
    return results[:30]
