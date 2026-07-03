-- =====================================================
-- COMPINTEL Database Schema for Supabase
-- Sistem Analisis Pencocokan Produk Hybrid (TF-IDF + SBERT)
-- =====================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- Table: public.profiles
-- User profile (extends auth.users)
-- =====================================================
CREATE TABLE public.profiles (
    id UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
    email TEXT,
    full_name TEXT,
    company_name TEXT,
    role TEXT DEFAULT 'user' CHECK (role IN ('admin', 'user', 'viewer')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- Table: public.data_kompetitor
-- Data produk kompetitor (tokoh utama + kompetitor)
-- =====================================================
CREATE TABLE public.data_kompetitor (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    nama_produk VARCHAR(500) NOT NULL,
    nama_produk_clean VARCHAR(500),
    harga BIGINT NOT NULL,
    terjual_bln INTEGER DEFAULT 0,
    tanggal DATE NOT NULL,
    nama_toko VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'READY',
    brand VARCHAR(100),
    kategori VARCHAR(100),
    sku VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index untuk optimasi query
CREATE INDEX idx_kompetitor_user ON public.data_kompetitor(user_id);
CREATE INDEX idx_kompetitor_toko ON public.data_kompetitor(nama_toko);
CREATE INDEX idx_kompetitor_tanggal ON public.data_kompetitor(tanggal);
CREATE INDEX idx_kompetitor_produk ON public.data_kompetitor(nama_produk);
CREATE INDEX idx_kompetitor_brand ON public.data_kompetitor(brand);
CREATE INDEX idx_kompetitor_sku ON public.data_kompetitor(sku);
CREATE INDEX idx_kompetitor_toko_tanggal ON public.data_kompetitor(nama_toko, tanggal);
CREATE INDEX idx_kompetitor_produk_toko ON public.data_kompetitor(nama_produk, nama_toko);

COMMENT ON TABLE public.data_kompetitor IS 'Data produk dari semua toko kompetitor';

-- =====================================================
-- Table: public.data_db_klik
-- Data produk DB KLIK (produk acuan/toko utama)
-- =====================================================
CREATE TABLE public.data_db_klik (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    nama_produk VARCHAR(500) NOT NULL,
    nama_produk_clean VARCHAR(500),
    harga BIGINT,
    terjual_bln INTEGER DEFAULT 0,
    tanggal DATE NOT NULL,
    brand VARCHAR(100),
    kategori VARCHAR(100),
    sku VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_dbklik_user ON public.data_db_klik(user_id);
CREATE INDEX idx_dbklik_tanggal ON public.data_db_klik(tanggal);
CREATE INDEX idx_dbklik_sku ON public.data_db_klik(sku);

COMMENT ON TABLE public.data_db_klik IS 'Data produk DB KLIK sebagai acuan harga utama';

-- =====================================================
-- Table: public.upload_history
-- Riwayat upload file CSV
-- =====================================================
CREATE TABLE public.upload_history (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    nama_toko VARCHAR(100) NOT NULL,
    tanggal_scraping DATE,
    status VARCHAR(20) DEFAULT 'READY',
    row_count INTEGER DEFAULT 0,
    file_size BIGINT,
    status_upload VARCHAR(20) DEFAULT 'SUCCESS',
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_upload_history_user ON public.upload_history(user_id);
CREATE INDEX idx_upload_history_created ON public.upload_history(created_at DESC);
CREATE INDEX idx_upload_history_toko ON public.upload_history(nama_toko);

COMMENT ON TABLE public.upload_history IS 'Log riwayat upload file CSV';

-- =====================================================
-- Table: public.produk_embeddings
-- Cache embeddings produk (TF-IDF & SBERT)
-- =====================================================
CREATE TABLE public.produk_embeddings (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    nama_produk VARCHAR(500) NOT NULL,
    embedding_tfidf TEXT,
    embedding_sbert TEXT,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, nama_produk)
);

CREATE INDEX idx_embeddings_user ON public.produk_embeddings(user_id);
CREATE INDEX idx_embeddings_produk ON public.produk_embeddings(nama_produk);

COMMENT ON TABLE public.produk_embeddings IS 'Cache embeddings untuk optimasi performa matching';

-- =====================================================
-- Table: public.user_settings
-- User preferences & settings
-- =====================================================
CREATE TABLE public.user_settings (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE UNIQUE,
    theme VARCHAR(10) DEFAULT 'dark' CHECK (theme IN ('dark', 'light')),
    default_threshold INTEGER DEFAULT 40,
    default_alpha FLOAT DEFAULT 0.5,
    notification_email BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- Row Level Security (RLS) Policies
-- =====================================================

-- Enable RLS on all tables
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.data_kompetitor ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.data_db_klik ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.upload_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.produk_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_settings ENABLE ROW LEVEL SECURITY;

-- Profiles: Users can only see/edit their own profile
CREATE POLICY "Users can view own profile" ON public.profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON public.profiles
    FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Users can insert own profile" ON public.profiles
    FOR INSERT WITH CHECK (auth.uid() = id);

-- Data Kompetitor: Users can only access their own data
CREATE POLICY "Users can view own competitor data" ON public.data_kompetitor
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own competitor data" ON public.data_kompetitor
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own competitor data" ON public.data_kompetitor
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own competitor data" ON public.data_kompetitor
    FOR DELETE USING (auth.uid() = user_id);

-- Data DB KLIK: Users can only access their own data
CREATE POLICY "Users can view own dbklik data" ON public.data_db_klik
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own dbklik data" ON public.data_db_klik
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own dbklik data" ON public.data_db_klik
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own dbklik data" ON public.data_db_klik
    FOR DELETE USING (auth.uid() = user_id);

-- Upload History: Users can only access their own history
CREATE POLICY "Users can view own upload history" ON public.upload_history
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own upload history" ON public.upload_history
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own upload history" ON public.upload_history
    FOR DELETE USING (auth.uid() = user_id);

-- Embeddings: Users can only access their own embeddings
CREATE POLICY "Users can view own embeddings" ON public.produk_embeddings
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own embeddings" ON public.produk_embeddings
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own embeddings" ON public.produk_embeddings
    FOR UPDATE USING (auth.uid() = user_id);

-- User Settings: Users can only access their own settings
CREATE POLICY "Users can view own settings" ON public.user_settings
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own settings" ON public.user_settings
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own settings" ON public.user_settings
    FOR UPDATE USING (auth.uid() = user_id);

-- =====================================================
-- Functions & Triggers
-- =====================================================

-- Function: Auto-create profile on user signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, full_name)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.email)
    );

    -- Create default settings
    INSERT INTO public.user_settings (user_id)
    VALUES (NEW.id);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger: Auto-create profile when user signs up
CREATE OR REPLACE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Function: Normalisasi nama produk
CREATE OR REPLACE FUNCTION fn_clean_product_name(text_input VARCHAR)
RETURNS VARCHAR AS $$
DECLARE
    result VARCHAR;
BEGIN
    result := LOWER(text_input);
    result := regexp_replace(result, '[^a-z0-9\s]', ' ', 'g');
    result := regexp_replace(result, '\s+', ' ', 'g');
    result := TRIM(result);
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- Views untuk aggregasi data
-- =====================================================

-- View: Deduplicated produk per toko (latest date)
CREATE OR REPLACE VIEW public.v_produk_terbaru AS
SELECT DISTINCT ON (dk.user_id, dk.nama_produk, dk.nama_toko)
    dk.id,
    dk.user_id,
    dk.nama_produk,
    dk.nama_produk_clean,
    dk.harga,
    dk.terjual_bln,
    dk.tanggal,
    dk.nama_toko,
    dk.status,
    dk.brand,
    dk.kategori,
    dk.sku
FROM public.data_kompetitor dk
ORDER BY dk.user_id, dk.nama_produk, dk.nama_toko, dk.tanggal DESC;

-- View: Statistik toko
CREATE OR REPLACE VIEW public.v_toko_stats AS
SELECT
    user_id,
    nama_toko,
    COUNT(*) as total_produk,
    COUNT(*) FILTER (WHERE status = 'READY') as produk_ready,
    COUNT(*) FILTER (WHERE status = 'HABIS') as produk_habis,
    ROUND(AVG(harga)::numeric, 0) as avg_harga,
    SUM(terjual_bln) as total_terjual
FROM public.data_kompetitor
GROUP BY user_id, nama_toko;

-- =====================================================
-- Storage Bucket untuk file uploads
-- =====================================================

-- Insert storage bucket (run in Supabase Dashboard or via API)
-- INSERT INTO storage.buckets (id, name, public) VALUES ('csv-uploads', 'csv-uploads', false);

-- =====================================================
-- Grant Permissions
-- =====================================================

GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO authenticated;
