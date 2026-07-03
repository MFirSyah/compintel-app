-- =====================================================
-- COMPINTEL Database Schema
-- Sistem Analisis Pencocokan Produk Hybrid (TF-IDF + SBERT)
-- =====================================================

-- Drop existing tables (for clean migration)
DROP TABLE IF EXISTS produk_embeddings CASCADE;
DROP TABLE IF EXISTS upload_history CASCADE;
DROP TABLE IF EXISTS data_db_klik CASCADE;
DROP TABLE IF EXISTS data_kompetitor CASCADE;

-- =====================================================
-- Table: data_kompetitor
-- Data produk kompetitor (tokoh utama + kompetitor)
-- =====================================================
CREATE TABLE data_kompetitor (
    id SERIAL PRIMARY KEY,
    nama_produk VARCHAR(500) NOT NULL,
    nama_produk_clean VARCHAR(500),        -- Setelah text cleaning
    harga BIGINT NOT NULL,
    terjual_bln INTEGER DEFAULT 0,
    tanggal DATE NOT NULL,
    nama_toko VARCHAR(100) NOT NULL,
    status VARCHAR(20),                    -- 'READY' atau 'HABIS'
    brand VARCHAR(100),
    kategori VARCHAR(100),
    sku VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index untuk optimasi query
CREATE INDEX idx_kompetitor_toko ON data_kompetitor(nama_toko);
CREATE INDEX idx_kompetitor_tanggal ON data_kompetitor(tanggal);
CREATE INDEX idx_kompetitor_produk ON data_kompetitor(nama_produk);
CREATE INDEX idx_kompetitor_brand ON data_kompetitor(brand);
CREATE INDEX idx_kompetitor_sku ON data_kompetitor(sku);
CREATE INDEX idx_kompetitor_toko_tanggal ON data_kompetitor(nama_toko, tanggal);
CREATE INDEX idx_kompetitor_produk_toko ON data_kompetitor(nama_produk, nama_toko);

COMMENT ON TABLE data_kompetitor IS 'Data produk dari semua toko kompetitor';
COMMENT ON COLUMN data_kompetitor.nama_produk_clean IS 'Nama produk setelah preprocessing (lowercase, hapus special chars)';
COMMENT ON COLUMN data_kompetitor.status IS 'Status stok: READY (tersedia) atau HABIS (out of stock)';


-- =====================================================
-- Table: data_db_klik
-- Data produk DB KLIK (produk acuan/toko utama)
-- =====================================================
CREATE TABLE data_db_klik (
    id SERIAL PRIMARY KEY,
    nama_produk VARCHAR(500) NOT NULL,
    nama_produk_clean VARCHAR(500),
    harga BIGINT,
    terjual_bln INTEGER DEFAULT 0,
    tanggal DATE NOT NULL,
    brand VARCHAR(100),
    kategori VARCHAR(100),
    sku VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index untuk optimasi query
CREATE INDEX idx_dbklik_tanggal ON data_db_klik(tanggal);
CREATE INDEX idx_dbklik_sku ON data_db_klik(sku);
CREATE INDEX idx_dbklik_brand ON data_db_klik(brand);

COMMENT ON TABLE data_db_klik IS 'Data produk DB KLIK sebagai acuan harga utama';


-- =====================================================
-- Table: upload_history
-- Riwayat upload file CSV
-- =====================================================
CREATE TABLE upload_history (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    nama_toko VARCHAR(100) NOT NULL,
    tanggal_scraping DATE,
    status VARCHAR(20),                    -- 'READY' atau 'HABIS'
    row_count INTEGER DEFAULT 0,
    file_size BIGINT,
    status_upload VARCHAR(20) DEFAULT 'PENDING',  -- 'SUCCESS', 'FAILED', 'PENDING'
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index
CREATE INDEX idx_upload_history_created ON upload_history(created_at DESC);
CREATE INDEX idx_upload_history_toko ON upload_history(nama_toko);

COMMENT ON TABLE upload_history IS 'Log riwayat upload file CSV';
COMMENT ON COLUMN upload_history.status_upload IS 'Status proses upload: SUCCESS, FAILED, atau PENDING';


-- =====================================================
-- Table: produk_embeddings
-- Cache embeddings produk (TF-IDF & SBERT)
-- =====================================================
CREATE TABLE produk_embeddings (
    id SERIAL PRIMARY KEY,
    nama_produk VARCHAR(500) NOT NULL UNIQUE,
    embedding_tfidf TEXT,                  -- Serialized TF-IDF vector (JSON)
    embedding_sbert TEXT,                   -- Serialized SBERT vector (JSON)
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index
CREATE INDEX idx_embeddings_produk ON produk_embeddings(nama_produk);

COMMENT ON TABLE produk_embeddings IS 'Cache embeddings untuk optimasi performa matching';
COMMENT ON COLUMN produk_embeddings.embedding_tfidf IS 'Vector TF-IDF dalam format JSON array';
COMMENT ON COLUMN produk_embeddings.embedding_sbert IS 'Vector SBERT dalam format JSON array';


-- =====================================================
-- Sample Data (untuk testing)
-- =====================================================

-- Insert sample data DB KLIK
INSERT INTO data_db_klik (nama_produk, nama_produk_clean, harga, terjual_bln, tanggal, brand, kategori, sku) VALUES
('LOGITECH PEBBLE M350 WIRELESS MOUSE', 'logitech pebble m350 wireless mouse', 245000, 320, '2025-09-29', 'LOGITECH', 'MOUSE', 'LOGI-PEBBLE-M350'),
('LOGITECH G304 LIGHTSPEED WIRELESS GAMING MOUSE', 'logitech g304 lightspeed wireless gaming mouse', 389000, 180, '2025-09-29', 'LOGITECH', 'MOUSE', 'LOGI-G304-LIGHTSPEED'),
('WD GREEN SATA SSD 240GB', 'wd green sata ssd 240gb', 325000, 150, '2025-09-29', 'WD', 'SSD', 'WD-GREEN-SSD-240'),
('LG LED MONITOR 22MK600 22 INCH', 'lg led monitor 22mk600 22 inch', 1199000, 95, '2025-09-29', 'LG', 'MONITOR', 'LG-MONITOR-22MK600'),
('V-GEN DDR4 RESCUE 8GB 2666MHZ RAM', 'v-gen ddr4 rescue 8gb 2666mhz ram', 265000, 210, '2025-09-29', 'V-GEN', 'RAM', 'VGEN-RAM-D4-8GB'),
('TP-LINK WR840N WIRELESS N ROUTER 300MBPS', 'tp-link wr840n wireless n router 300mbps', 155000, 140, '2025-09-29', 'TP-LINK', 'NETWORKING', 'TPLINK-ROUTER-WR840N');

-- Insert sample data Kompetitor
INSERT INTO data_kompetitor (nama_produk, nama_produk_clean, harga, terjual_bln, tanggal, nama_toko, status, brand, kategori, sku) VALUES
-- JAYA PC (Agresif - harga murah)
('MOUSE LOGITECH M350 PEBBLE SLIM', 'mouse logitech m350 pebble slim', 229000, 287, '2025-09-29', 'JAYA PC', 'READY', 'LOGITECH', 'MOUSE', 'LOGI-PEBBLE-M350'),
('G304 LOGITECH LIGHTSPEED GAMING MOUSE WIRELESS', 'g304 logitech lightspeed gaming mouse wireless', 365000, 203, '2025-09-29', 'JAYA PC', 'READY', 'LOGITECH', 'MOUSE', 'LOGI-G304-LIGHTSPEED'),
('WD GREEN SSD 240 GB 2.5 SATA III', 'wd green ssd 240 gb 2.5 sata iii', 305000, 178, '2025-09-29', 'JAYA PC', 'READY', 'WD', 'SSD', 'WD-GREEN-SSD-240'),
('MONITOR LG 22MK600 22 INCH IPS FHD', 'monitor lg 22mk600 22 inch ips fhd', 1125000, 112, '2025-09-29', 'JAYA PC', 'READY', 'LG', 'MONITOR', 'LG-MONITOR-22MK600'),

-- TECH ISLAND
('LOGITECH SLIM WIRELESS MOUSE PEBBLE M350', 'logitech slim wireless mouse pebble m350', 239000, 245, '2025-09-29', 'TECH ISLAND', 'READY', 'LOGITECH', 'MOUSE', 'LOGI-PEBBLE-M350'),
('LOGITECH G304 LIGHTSPEED GAMING MOUSE HITAM PUTIH', 'logitech g304 lightspeed gaming mouse hitam putih', 379000, 156, '2025-09-29', 'TECH ISLAND', 'READY', 'LOGITECH', 'MOUSE', 'LOGI-G304-LIGHTSPEED'),
('WD SSD GREEN 240GB SATA INTERNAL', 'wd ssd green 240gb sata internal', 315000, 134, '2025-09-29', 'TECH ISLAND', 'READY', 'WD', 'SSD', 'WD-GREEN-SSD-240'),
('LG LED MONITOR 22MK600 IPS 22 INCH SLIM', 'lg led monitor 22mk600 ips 22 inch slim', 1159000, 88, '2025-09-29', 'TECH ISLAND', 'READY', 'LG', 'MONITOR', 'LG-MONITOR-22MK600'),

-- LOGITECH OFFICIAL (Harga premium)
('LOGITECH PEBBLE M350 WIRELESS MOUSE ORIGINAL', 'logitech pebble m350 wireless mouse original', 269000, 412, '2025-09-29', 'LOGITECH', 'READY', 'LOGITECH', 'MOUSE', 'LOGI-PEBBLE-M350'),
('G304 LIGHTSPEED GAMING MOUSE WIRELESS LOGITECH', 'g304 lightspeed gaming mouse wireless logitech', 425000, 287, '2025-09-29', 'LOGITECH', 'READY', 'LOGITECH', 'MOUSE', 'LOGI-G304-LIGHTSPEED'),

-- SURYA MITRA ONLINE
('LOGITECH PEBBLE M350 MOUSE BLUETOOTH ORIGINAL', 'logitech pebble m350 mouse bluetooth original', 242000, 198, '2025-09-29', 'SURYA MITRA ONLINE', 'READY', 'LOGITECH', 'MOUSE', 'LOGI-PEBBLE-M350'),
('LOGITECH G304 LIGHTSPEED MOUSE GAMING WIRELESS', 'logitech g304 lightspeed mouse gaming wireless', 372000, 145, '2025-09-29', 'SURYA MITRA ONLINE', 'HABIS', 'LOGITECH', 'MOUSE', 'LOGI-G304-LIGHTSPEED'),
('SSD WD GREEN 240GB SATA 3', 'ssd wd green 240gb sata 3', 309000, 167, '2025-09-29', 'SURYA MITRA ONLINE', 'READY', 'WD', 'SSD', 'WD-GREEN-SSD-240'),

-- IT SHOP
('LOGITECH PEBBLE M350 WIRELESS BLUETOOTH MOUSE SLIM', 'logitech pebble m350 wireless bluetooth mouse slim', 237000, 223, '2025-09-29', 'IT SHOP', 'READY', 'LOGITECH', 'MOUSE', 'LOGI-PEBBLE-M350'),
('LOGITECH G304 GAMING MOUSE LIGHTSPEED WIRELESS RESMI', 'logitech g304 gaming mouse lightspeed wireless resmi', 385000, 167, '2025-09-29', 'IT SHOP', 'READY', 'LOGITECH', 'MOUSE', 'LOGI-G304-LIGHTSPEED'),
('WD GREEN SATA SSD 240GB INTERNAL 2.5"', 'wd green sata ssd 240gb internal 2.5', 319000, 145, '2025-09-29', 'IT SHOP', 'READY', 'WD', 'SSD', 'WD-GREEN-SSD-240'),
('LG 22MK600M MONITOR LED IPS 22" FULL HD BORDERLESS', 'lg 22mk600m monitor led ips 22 full hd borderless', 1175000, 78, '2025-09-29', 'IT SHOP', 'READY', 'LG', 'MONITOR', 'LG-MONITOR-22MK600'),

-- ABDITAMA
('MOUSE PEBBLE M350 LOGITECH RESMI', 'mouse pebble m350 logitech resmi', 243000, 189, '2025-09-29', 'ABDITAMA', 'READY', 'LOGITECH', 'MOUSE', 'LOGI-PEBBLE-M350'),
('LOGITECH G304 LIGHTSPEED MOUSE GAMING WIRELESS', 'logitech g304 lightspeed mouse gaming wireless', 378000, 134, '2025-09-29', 'ABDITAMA', 'READY', 'LOGITECH', 'MOUSE', 'LOGI-G304-LIGHTSPEED'),
('WD GREEN SSD 240GB 2.5 SATA III', 'wd green ssd 240gb 2.5 sata iii', 312000, 123, '2025-09-29', 'ABDITAMA', 'READY', 'WD', 'SSD', 'WD-GREEN-SSD-240'),
('LG LED MONITOR 22MK600 22 INCH IPS BORDERLESS', 'lg led monitor 22mk600 22 inch ips borderless', 1165000, 67, '2025-09-29', 'ABDITAMA', 'READY', 'LG', 'MONITOR', 'LG-MONITOR-22MK600');

-- Insert sample upload history
INSERT INTO upload_history (filename, nama_toko, tanggal_scraping, status, row_count, file_size, status_upload) VALUES
('29-09-2025_DB KLIK_Ready.csv', 'DB KLIK', '2025-09-29', 'READY', 1976, 245678, 'SUCCESS'),
('29-09-2025_LOGITECH_Ready.csv', 'LOGITECH', '2025-09-29', 'READY', 845, 112345, 'SUCCESS'),
('29-09-2025_JAYA PC_Ready.csv', 'JAYA PC', '2025-09-29', 'READY', 923, 128456, 'SUCCESS'),
('29-09-2025_TECH ISLAND_Ready.csv', 'TECH ISLAND', '2025-09-29', 'READY', 756, 98234, 'SUCCESS'),
('29-09-2025_SURYA MITRA ONLINE_Habis.csv', 'SURYA MITRA ONLINE', '2025-09-29', 'HABIS', 234, 34567, 'SUCCESS');

-- =====================================================
-- Views untuk aggregasi data
-- =====================================================

-- View: Deduplicated produk per toko (latest date)
CREATE OR REPLACE VIEW v_produk_terbaru AS
SELECT DISTINCT ON (dk.nama_produk, dk.nama_toko)
    dk.id,
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
FROM data_kompetitor dk
ORDER BY dk.nama_produk, dk.nama_toko, dk.tanggal DESC;

COMMENT ON VIEW v_produk_terbaru IS 'Produk terbaru per toko (deduplicated berdasarkan tanggal terakhir)';


-- View: Statistik toko
CREATE OR REPLACE VIEW v_toko_stats AS
SELECT
    nama_toko,
    COUNT(*) as total_produk,
    COUNT(*) FILTER (WHERE status = 'READY') as produk_ready,
    COUNT(*) FILTER (WHERE status = 'HABIS') as produk_habis,
    ROUND(AVG(harga)::numeric, 0) as avg_harga,
    SUM(terjual_bln) as total_terjual
FROM data_kompetitor
GROUP BY nama_toko
ORDER BY total_produk DESC;

COMMENT ON VIEW v_toko_stats IS 'Statistik agregat per toko';


-- =====================================================
-- Functions
-- =====================================================

-- Function: Normalisasi nama produk
CREATE OR REPLACE FUNCTION fn_clean_product_name(text_input VARCHAR)
RETURNS VARCHAR AS $$
DECLARE
    result VARCHAR;
BEGIN
    -- Lowercase
    result := LOWER(text_input);
    -- Hapus karakter khusus
    result := regexp_replace(result, '[^a-z0-9\s]', ' ', 'g');
    -- Hapus spasi berlebih
    result := regexp_replace(result, '\s+', ' ', 'g');
    -- Trim
    result := TRIM(result);
    RETURN result;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fn_clean_product_name IS 'Normalisasi nama produk: lowercase, hapus special chars, trim spaces';


-- =====================================================
-- Grant permissions (adjust as needed)
-- =====================================================
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO compintel_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO compintel_app;
