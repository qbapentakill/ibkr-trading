-- Supabase SQL Schema dla License System
-- Uruchom to w Supabase Dashboard → SQL Editor

-- Tabela licenses
CREATE TABLE IF NOT EXISTS licenses (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    key_hash TEXT UNIQUE NOT NULL,  -- SHA256 hash klucza (bezpieczeństwo)
    license_key_plain TEXT,  -- Plain key for 24h (for email delivery), then deleted
    tier TEXT NOT NULL CHECK (tier IN ('basic', 'pro', 'elite')),
    customer_email TEXT NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_verified_at TIMESTAMPTZ,
    verification_count INTEGER DEFAULT 0,
    stripe_session_id TEXT,
    stripe_customer_id TEXT,
    notes TEXT
);

-- Indeksy dla szybkiego wyszukiwania
CREATE INDEX IF NOT EXISTS idx_licenses_key_hash ON licenses(key_hash);
CREATE INDEX IF NOT EXISTS idx_licenses_email ON licenses(customer_email);
CREATE INDEX IF NOT EXISTS idx_licenses_active ON licenses(active);

-- Tabela verification_logs (opcjonalna - do monitoringu)
CREATE TABLE IF NOT EXISTS verification_logs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    license_id UUID REFERENCES licenses(id),
    verified_at TIMESTAMPTZ DEFAULT NOW(),
    bot_version TEXT,
    ip_address TEXT,
    success BOOLEAN
);

-- Index dla logs
CREATE INDEX IF NOT EXISTS idx_verification_logs_license ON verification_logs(license_id);
CREATE INDEX IF NOT EXISTS idx_verification_logs_verified_at ON verification_logs(verified_at);

-- Row Level Security (RLS) - zabezpieczenie danych
ALTER TABLE licenses ENABLE ROW LEVEL SECURITY;
ALTER TABLE verification_logs ENABLE ROW LEVEL SECURITY;

-- Policy: API może czytać wszystko (używamy service_role key w backendzie)
-- W produkcji: użyj anon key + bardziej restrykcyjne policies

COMMENT ON TABLE licenses IS 'License keys dla trading bot SaaS';
COMMENT ON TABLE verification_logs IS 'Historia weryfikacji licencji (monitoring)';
