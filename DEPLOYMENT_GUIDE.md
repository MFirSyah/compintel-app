# DEPLOYMENT GUIDE - COMPINTEL Online

Panduan deploy COMPINTEL ke production dengan **Supabase** dan **Vercel/Railway**.

---

## 🗄️ Langkah 1: Setup Supabase

### 1.1 Buat Project Supabase

1. Buka [supabase.com](https://supabase.com)
2. Klik **"New Project"**
3. Isi detail:
   - **Name**: `compintel`
   - **Database Password**: (generate secure password)
   - **Region**: Southeast Asia (Singapore)
4. Tunggu project dibuat (~2 menit)

### 1.2 Dapatkan Credentials

Di Supabase Dashboard → **Settings** → **API**:

```
SUPABASE_URL = https://xxxxx.supabase.co
SUPABASE_ANON_KEY = eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_KEY = eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 1.3 Setup Database Schema

1. Buka **SQL Editor** di Supabase Dashboard
2. Copy-paste isi file: `backend/migrations/002_supabase_schema.sql`
3. Klik **Run** untuk execute

### 1.4 Setup Storage (untuk upload CSV)

1. Di Supabase Dashboard → **Storage** → **New bucket**
2. Nama: `csv-uploads`
3. Public: **No** (private, authenticated only)
4. Add policy untuk authenticated users upload/download

---

## 🚀 Langkah 2: Deploy Backend (Railway)

### 2.1 Persiapan

1. Buat akun di [railway.app](https://railway.app)
2. Connect GitHub repo

### 2.2 Setup Railway Project

```bash
# Clone repo
git clone https://github.com/yourusername/compintel.git
cd compintel/backend

# Install dependencies locally untuk test
pip install -r requirements.txt
```

### 2.3 Configure Railway

1. **New Railway Project** → **Deploy from GitHub repo**
2. Pilih repo `compintel`
3. Set root directory: `backend`
4. Add Environment Variables:

```env
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_KEY=your-service-key
DATABASE_URL=postgresql://postgres:password@db.xxxxx.supabase.co:5432/postgres
HOST=0.0.0.0
PORT=8000
```

5. **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### 2.4 Deploy

1. Klik **Deploy** → Railway auto-detect Python
2. Tunggu build (~3-5 menit)
3. Dapatkan URL: `https://compintel.up.railway.app`

---

## 🌐 Langkah 3: Deploy Frontend (Vercel)

### 3.1 Persiapan

1. Buat akun di [vercel.com](https://vercel.com)
2. Install Vercel CLI:

```bash
npm install -g vercel
```

### 3.2 Update Frontend Config

Edit `index.html`, cari bagian Supabase config:

```javascript
// Replace dengan credentials Anda
const SUPABASE_URL = 'https://xxxxx.supabase.co';
const SUPABASE_ANON_KEY = 'your-anon-key';
```

### 3.3 Deploy

```bash
# Masuk ke folder project
cd compintel

# Login Vercel
vercel login

# Deploy (follow prompts)
vercel

# Untuk production
vercel --prod
```

### 3.4 Set Environment Variables (Optional)

Di Vercel Dashboard → **Settings** → **Environment Variables`:

```env
VITE_SUPABASE_URL=https://xxxxx.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
VITE_API_URL=https://compintel.up.railway.app
```

---

## 🔐 Langkah 4: Configure Supabase Auth

### 4.1 Setup Email Templates

Di Supabase Dashboard → **Authentication** → **Email Templates**:

```html
<!-- Confirm Signup -->
<h2>Verifikasi Email COMPINTEL</h2>
<p>Klik link berikut untuk verifikasi email Anda:</p>
<a href="{{ .ConfirmationURL }}">Verifikasi Email</a>
```

### 4.2 Configure Redirect URLs

Di **Authentication** → **URL Configuration**:

```
Site URL: https://compintel.vercel.app
Redirect URLs:
- https://compintel.vercel.app/auth/callback
- http://localhost:3000 (development)
```

### 4.3 Enable Providers (Optional)

Di **Authentication** → **Providers**:
- Google (optional)
- GitHub (optional)

---

## 📱 Langkah 5: Custom Domain (Optional)

### Railway Backend
1. Railway Dashboard → **Settings** → **Networking**
2. Add custom domain: `api.compintel.com`

### Vercel Frontend
1. Vercel Dashboard → **Domains**
2. Add: `compintel.com` atau `app.compintel.com`

---

## 🧪 Langkah 6: Testing

### Test Auth Flow
1. Buka app URL
2. Klik **Daftar**
3. Isi form → check email
4. Klik link verifikasi
5. Login

### Test Upload
1. Login
2. Buka **Pusat Data**
3. Drag file CSV (format: `dd-mm-yyyy_Toko_Ready.csv`)
4. Preview → Konfirmasi

### Test Matching
1. Buka **Smart Matching**
2. Ketik: "Logitech G304"
3. Klik **Analisa AI**
4. Lihat hasil

---

## 🔧 Troubleshooting

### CORS Error
Pastikan backend CORS allow origin:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://compintel.vercel.app"],  # Specific origin
    ...
)
```

### Auth Session Expired
Tambahkan di frontend:
```javascript
supabaseClient.auth.onAuthStateChange((event, session) => {
    if (event === 'SIGNED_IN') {
        // Refresh token
    }
});
```

### Database Connection Failed
Check environment variable `DATABASE_URL` di Railway

---

## 💰 Estimasi Biaya

| Service | Plan | Monthly |
|---------|------|---------|
| Supabase | Free Tier | $0 |
| Railway | Starter | $5 (100h compute) |
| Vercel | Hobby | $0 |
| Domain | .com | ~$10/tahun |

**Total: ~$5/bulan** (untuk development/small scale)

---

## 📊 Arsitektur Final

```
┌─────────────────────────────────────────────────────────────┐
│                      USER BROWSER                            │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    VERCEL (Frontend)                        │
│                   Static Hosting + CDN                       │
│              https://compintel.vercel.app                    │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
┌─────────────────┐ ┌──────────────┐ ┌──────────────────┐
│   SUPABASE      │ │   RAILWAY    │ │   USER DATA      │
│   - Auth        │ │  (Backend)   │ │   - CSV Files    │
│   - Database    │ │  FastAPI     │ │   - Embeddings   │
│   - Storage     │ │  + ML        │ │                  │
└─────────────────┘ └──────────────┘ └──────────────────┘
```

---

## 📝 Checklist Deployment

- [ ] Buat project Supabase
- [ ] Setup database schema
- [ ] Configure storage bucket
- [ ] Setup auth email templates
- [ ] Deploy backend ke Railway
- [ ] Deploy frontend ke Vercel
- [ ] Test login/signup
- [ ] Test CSV upload
- [ ] Test matching
- [ ] Configure custom domain (optional)
- [ ] Setup monitoring (optional)

---

## 🆘 Support

Jika ada pertanyaan:
1. Check [Supabase Docs](https://supabase.com/docs)
2. Check [Railway Docs](https://docs.railway.app)
3. Check [Vercel Docs](https://vercel.com/docs)
