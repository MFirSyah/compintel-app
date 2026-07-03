# Rencana Implementasi: Redesain UI COMPINTEL & Integrasi Fitur Berdasarkan Panduan Desain Premium

Proyek ini bertujuan untuk memperbarui antarmuka pengguna (UI) dari aplikasi **COMPINTEL** (Sistem Analisis Pencocokan Produk Hybrid) agar mengadopsi estetika premium dari **Sobat AI** (Dark Mode, Glassmorphism, Space-tech vibe) sesuai dengan panduan di [gaya_ui.md](file:///D:/TUGAS%20KULIAH/SEMESTER%208/TUGAS%20AKHIR/APP/gaya_ui.md), serta mengimplementasikan seluruh fitur yang dijelaskan dalam [BRIEF_SKRIPSI_MU_FIRMAN (1).md](file:///D:/TUGAS%20KULIAH/SEMESTER%208/TUGAS%20AKHIR/APP/BRIEF_SKRIPSI_MU_FIRMAN%20(1).md).

---

## User Review Required

> [!IMPORTANT]
> **Desain Premium Dark Mode & Glassmorphism:**
> Aplikasi akan diubah secara radikal menjadi tema gelap bernuansa luar angkasa dengan latar belakang gelap pekat (`#0b0f19`), efek kaca transparan, dan aksen neon berpendar. Ini akan sepenuhnya menggantikan tampilan UI putih/slate standar saat ini.

> [!TIP]
> **Mode Offline / Mock Integrasi:**
> Untuk memastikan aplikasi web ini dapat berjalan langsung dan diuji secara interaktif (bahkan tanpa backend FastAPI yang berjalan di localhost), kami akan menambahkan mesin simulasi pencocokan produk leksikal (TF-IDF sederhana) di sisi klien (Javascript) sebagai fallback pintar. Jika backend FastAPI terhubung, sistem akan otomatis menggunakan API backend.

---

## Proposed Changes

Kami akan memperbarui file [index.html](file:///D:/TUGAS%20KULIAH/SEMESTER%208/TUGAS%20AKHIR/APP/index.html) dengan modifikasi sebagai berikut:

### 1. Gaya & Desain Sistem (`gaya_ui.md`)
* **Warna & Latar Belakang:** Menambahkan variabel CSS HSL kustom dan efek pendaran ambient (`Top-Left Glow`, `Top-Right Glow`, `Bottom-Center Glow`).
* **Tipografi:** Memuat font `'Outfit'` (untuk judul) dan `'Inter'` (untuk bodi/metrik) dari Google Fonts.
* **Glassmorphism:** Membuat kartu dengan efek blur kaca (`backdrop-filter: blur(20px)`), garis tepi transparan, dan bayangan dalam.
* **Animasi Mikro:**
  * Status koneksi dengan dot hijau berdenyut (*pulse*).
  * Efek melayang (*hover translateY* & glow) pada kartu dan tombol.
  * Efek membesar pegas elastis (*scale-up wizard*) saat perpindahan halaman.
  * Animasi melayang naik-turun lambat untuk emoji jam pasir (`⏳`).
* **Locked Cognitive Overlay:** Menerapkan panel terkunci opasitas 22% dengan pemberitahuan dinamis untuk visualisasi data jika data tidak mencukupi.

### 2. Fitur Aplikasi (`BRIEF_SKRIPSI_MU_FIRMAN (1).md`)
* **Manajemen & Preview Upload CSV:**
  * Peningkatan area Drag & Drop dengan umpan balik visual berpendar.
  * Pembaca file lokal (FileReader) untuk menampilkan **Preview Data** (tabel data) dan validasi kolom wajib (`NAMA`, `HARGA`, `TERJUAL/BLN`) sebelum data diunggah.
  * Tampilan kemajuan (*progress bar*) upload yang mulus.
  * Riwayat upload file terakhir.
* **Pencocokan Produk Cerdas (Smart Matching):**
  * Slider minimal kemiripan dan input harga acuan yang responsif.
  * Penambahan status perbandingan harga ("Lebih Murah" bernuansa hijau pendar, "Lebih Mahal" merah coral, "Setara" amber).
  * Penyaringan daftar toko pencarian.
  * Kolom pilihan (*checkbox*) pada setiap baris hasil pencarian untuk memilih produk yang akan dianalisis secara mendalam.
* **Deduplikasi vs Riwayat Lengkap:**
  * Di halaman tabel utama, data disajikan dalam format ter-deduplikasi (tanggal terbaru per toko).
  * Di halaman analisis detail, seluruh riwayat tanggal akan dimuat.
* **Halaman Analisis Detail (Time Series):**
  * Halaman/Tab baru khusus untuk menampilkan analisis tren produk terpilih.
  * Visualisasi grafik tren harga (Line Chart) dan perbandingan total penjualan (Bar Chart) menggunakan Chart.js yang diintegrasikan dengan tema gelap.
  * Tabel data historis lengkap beserta perhitungan selisih perubahan harga ($\Delta\%$).

---

## Verification Plan

### Automated/Manual Verification
1. **Verifikasi Tampilan UI:**
   * Buka halaman di web browser untuk memastikan font, pendaran ambient, glassmorphism, dan skema warna gelap berjalan dengan sempurna.
   * Uji responsivitas navigasi sidebar dan efek transisi antar tab.
2. **Uji Fitur Upload & Preview:**
   * Coba seret file CSV (baik yang valid maupun tidak valid) ke area drop.
   * Pastikan validasi berjalan (penamaan file, kecocokan header) dan tabel preview data muncul sebelum tombol konfirmasi ditekan.
3. **Uji Smart Matching & Checkbox:**
   * Cari produk (menggunakan data mock jika server lokal mati) dan ubah slider threshold.
   * Beri tanda centang pada beberapa produk hasil pencarian dan pastikan tombol "Analisis Produk Terpilih" aktif.
4. **Uji Grafik Analisis Detail:**
   * Pindah ke tab analisis detail untuk produk terpilih, periksa kelancaran rendering grafik garis tren harga dan grafik batang penjualan.
   * Uji ekspor laporan CSV dari hasil analisis detail.
