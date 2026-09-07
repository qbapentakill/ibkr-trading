#!/usr/bin/env python3
"""
Szybki test komunikacji z IBKR.

Testy:
  1. Połączenie z IBKR (TWS/IB Gateway)
  2. Pobieranie danych rynkowych
  3. Weryfikacja konta papierowego
  4. Stan MarketDataService

Użycie:
    python scripts/quick_test.py
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import Settings
from core.ibkr_connector import IBKRConnector
from core.logger import logger
from services.market_data import MarketDataService


async def test_connection():
    """Test IBKR connection."""
    print("\n" + "="*60)
    print("🔌 TEST 1: Połączenie z IBKR")
    print("="*60)
    
    settings = Settings()
    connector = IBKRConnector(settings)
    
    try:
        await connector.connect()
        print(f"✅ Połączono z {settings.ibkr_host}:{settings.ibkr_port}")
        
        # Check if connected
        if not connector.ib.isConnected():
            print("❌ IBKRConnector nie podłączony!")
            return False
            
        print("✅ IBKRConnector actywny")
        return connector
    except Exception as e:
        print(f"❌ Błąd połączenia: {e}")
        print("\n💡 Upewnij się że:")
        print("   - TWS lub IB Gateway jest uruchomiony")
        print("   - Zalogowany na konto papierowe")
        print("   - API enabled w ustawieniach")
        return None


async def test_market_data(connector):
    """Test market data service."""
    print("\n" + "="*60)
    print("📊 TEST 2: Pobieranie danych rynkowych")
    print("="*60)
    
    try:
        mds = MarketDataService(connector)
        
        # Request data for SPY (najczęściej dostępny)
        print("📡 Pobieranie 5-minutowych danych dla SPY...")
        df = await mds.get_ohlcv("SPY", bar_size="5 mins", duration="1 D")
        
        if df is None or df.empty:
            print("❌ Brak danych. Sprawdź:")
            print("   - Symbol jest poprawny (SPY, QQQ, ES, etc.)")
            print("   - Sesja giełdy jest otwarta")
            print("   - Subskrypcja danych w IBKR")
            return False
        
        print(f"✅ Pobrano {len(df)} świec")
        print(f"\nOstatnia świeca:")
        print(df.tail(1).to_string())
        
        # Test indicators
        print(f"\n🔄 Obliczanie wskaźników...")
        ema_9 = mds.calculate_ema(df, period=9)
        rsi = mds.calculate_rsi(df, period=14)
        bb = mds.calculate_bollinger_bands(df, period=20, std_dev=2)
        
        if ema_9 is not None and rsi is not None and bb is not None:
            print(f"✅ Wskaźniki obliczone:")
            print(f"   EMA(9): {ema_9.iloc[-1]:.2f}")
            print(f"   RSI(14): {rsi.iloc[-1]:.2f}")
            print(f"   BB Upper: {bb['upper'].iloc[-1]:.2f}")
            print(f"   BB Lower: {bb['lower'].iloc[-1]:.2f}")
        else:
            print("❌ Błąd obliczania wskaźników")
            return False
            
        return True
    except Exception as e:
        print(f"❌ Błąd: {e}")
        return False


async def test_account():
    """Test account info."""
    print("\n" + "="*60)
    print("💰 TEST 3: Informacje o koncie")
    print("="*60)
    
    settings = Settings()
    connector = IBKRConnector(settings)
    
    try:
        await connector.connect()
        
        # Get account values
        account_values = connector.get_account_values()
        if not account_values:
            print("❌ Brak danych konta")
            return False
        
        print("✅ Dane konta:")
        for key, value in list(account_values.items())[:10]:
            print(f"   {key}: {value}")
        
        # Check paper trading
        if "paper" in str(account_values).lower():
            print("\n✅ Konto papierowe (Paper Trading) - BEZPIECZNE!")
        else:
            print("\n⚠️  Sprawdź czy to konto papierowe lub demo")
        
        return True
    except Exception as e:
        print(f"❌ Błąd: {e}")
        return False


async def test_config():
    """Test configuration."""
    print("\n" + "="*60)
    print("⚙️  TEST 4: Konfiguracja")
    print("="*60)
    
    try:
        settings = Settings()
        
        print("✅ Konfiguracja załadowana z .env:")
        print(f"   IBKR Host: {settings.ibkr_host}")
        print(f"   IBKR Port: {settings.ibkr_port}")
        print(f"   Real Mode: {settings.real_mode} {'🔴 NIEBEZPIECZNE!' if settings.real_mode else '🟢 Paper Trading'}")
        print(f"   Max Daily Loss: ${settings.max_daily_loss_usd}")
        print(f"   Max Drawdown: {settings.max_drawdown_pct}%")
        print(f"   Total Capital: ${settings.total_capital_usd}")
        
        if settings.real_mode:
            print("\n🚨 UWAGA: REAL_MODE=true - System będzie handlować na rzeczywistym koncie!")
        
        return True
    except Exception as e:
        print(f"❌ Błąd konfiguracji: {e}")
        print("   Sprawdź .env - czy wszystkie wymagane pola są ustawione?")
        return False


async def main():
    """Run all tests."""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*58 + "║")
    print("║" + "  🚀 IBKR Trading System - Quick Test".center(58) + "║")
    print("║" + " "*58 + "║")
    print("╚" + "="*58 + "╝")
    
    results = {}
    
    # Test 4: Config
    results['config'] = await test_config()
    
    # Test 1: Connection
    connector = await test_connection()
    results['connection'] = connector is not None
    
    if connector:
        # Test 2: Market Data
        results['market_data'] = await test_market_data(connector)
        
        # Test 3: Account
        results['account'] = await test_account()
        
        await connector.disconnect()
    
    # Summary
    print("\n" + "="*60)
    print("📋 PODSUMOWANIE")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {test_name:20} {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "="*60)
    if all_passed:
        print("✅ Wszystkie testy przeszły! System gotowy do uruchomienia.")
        print("\n🚀 Uruchom:")
        print("   1. python main.py")
        print("   2. streamlit run panel/frontend/dashboard.py")
    else:
        print("❌ Niektóre testy nie przeszły. Sprawdź komunikaty powyżej.")
    print("="*60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
