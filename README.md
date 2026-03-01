# Sentra BI v2.0

> **Business Intelligence berbasis Google Trends & Gemini AI untuk UMKM Indonesia**

Sentra BI menganalisis tren minat pasar secara real-time menggunakan data Google Trends, melengkapinya dengan metrik bisnis (Growth, Momentum, FOMO Index, Entry Timing Score), dan menghasilkan rekomendasi AI dari Gemini.

---

## ✨ Fitur Utama

| Fitur | Free | Pro |
|---|:---:|:---:|
| Analisis keyword (5/hari) | ✅ | ✅ ∞ |
| Mode Perbandingan (A vs B) | ✅ | ✅ |
| Growth, Momentum, Volatilitas | ✅ | ✅ |
| Market Pulse Score | ✅ | ✅ |
| Entry Timing Score (ring chart) | ✅ | ✅ |
| FOMO Index & Saturasi Pasar | ✅ | ✅ |
| Forecast 30 Hari | ✅ | ✅ |
| Pola Musiman | ✅ | ✅ |
| AI Insight — 3 Card (Gemini) | ✅ | ✅ |
| Sektor Dashboard (7 sektor) | ✅ | ✅ |
| Lokasi per-Provinsi | ❌ | ✅ |
| Download Laporan PDF | ❌ | ✅ |

---

## 🏗️ Arsitektur

```
index.html          → Single-page frontend (vanilla JS + Chart.js)
app.py              → Flask API server (Railway)
sentra_engine.py    → Google Trends fetcher + semua kalkulasi metrik
ai_recommendation.py→ Gemini AI prompt builder & parser
```

### Alur Request (2-Stage Async)
```
User click "Analisis"
    │
    ├── Stage 1 → POST /api/analyze  ──→ sentra_engine → Google Trends (via ScraperAPI)
    │              ↳ render grafik & metrik segera (< 15 detik ideal)
    │
    └── Stage 2 → POST /api/get-ai-insight ──→ Gemini AI
                   ↳ render AI cards (skeleton shimmer saat loading)
```

---

## 🚀 Setup Lokal

### 1. Clone & Install
```bash
git clone https://github.com/ardiann-eng/Sentra.git
cd Sentra
pip install -r requirements.txt
```

### 2. Buat file `.env`
```env
GEMINI_API_KEY=your_gemini_api_key
SCRAPERAPI_KEY=your_scraperapi_key
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=your_supabase_anon_key
```

### 3. Jalankan
```bash
python app.py
# Buka http://localhost:5000
```

---

## 🌐 Deploy ke Railway

1. Push ke GitHub
2. Buat project baru di [railway.app](https://railway.app) → Connect repo
3. Tambahkan Environment Variables:
   - `GEMINI_API_KEY`
   - `SCRAPERAPI_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
4. Railway otomatis deploy menggunakan `railway.json`

**Start command** (dari `railway.json`):
```
gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --worker-class sync --timeout 75
```

---

## 🔑 Environment Variables

| Variable | Wajib | Keterangan |
|---|:---:|---|
| `GEMINI_API_KEY` | ✅ | Google Gemini AI — [aistudio.google.com](https://aistudio.google.com) |
| `SCRAPERAPI_KEY` | ✅ | Proxy untuk Google Trends — [scraperapi.com](https://www.scraperapi.com) (1000 req/bln gratis) |
| `SUPABASE_URL` | ⚠️ | Database cache & user data — opsional tapi disarankan |
| `SUPABASE_KEY` | ⚠️ | Supabase anon/service key |

> Tanpa `SCRAPERAPI_KEY`, fetch langsung ke Google Trends (kemungkinan besar 429 di Railway).

---

## 📊 Metrik yang Dihitung

| Metrik | Deskripsi |
|---|---|
| **Growth** | Perubahan minat 7 hari terakhir vs 7 hari sebelumnya |
| **Momentum** | Slope regresi linear tren (arah naik/turun) |
| **Volatilitas** | Koefisien variasi — seberapa stabil tren |
| **Market Pulse Score** | Skor kesehatan pasar gabungan (0–100) |
| **FOMO Index** | Short-term vs long-term ratio — deteksi hype sesaat |
| **Saturasi Pasar** | Perkiraan kepadatan pesaing |
| **Entry Timing Score** | Skor waktu terbaik masuk pasar (0–100) |
| **Forecast 30 Hari** | Prediksi minat berbasis linear regression |
| **Pola Musiman** | Deteksi bulan-bulan dengan minat tertinggi |

---

## 🗄️ Supabase Schema

```sql
-- Cache hasil analisis (TTL 6 jam)
CREATE TABLE trend_cache (
    id         SERIAL PRIMARY KEY,
    keyword    TEXT NOT NULL,
    geo        TEXT NOT NULL DEFAULT 'ID',
    cat        TEXT NOT NULL DEFAULT '0',
    results    JSONB,
    ai_insight TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (keyword, geo, cat)
);

-- Log pencarian per user (untuk freemium limit)
CREATE TABLE search_logs (
    id         SERIAL PRIMARY KEY,
    user_id    TEXT NOT NULL,
    keyword    TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Profil user (tier: 'free' | 'pro')
CREATE TABLE profiles (
    user_id TEXT PRIMARY KEY,
    tier    TEXT DEFAULT 'free'
);
```

---

## 📁 Struktur File

```
Sentra2/
├── app.py              # Flask server, endpoints, cache, freemium logic
├── sentra_engine.py    # Core: Google Trends fetch + semua kalkulasi metrik
├── ai_recommendation.py# Gemini AI prompt generation & response parsing
├── index.html          # Frontend SPA (HTML + CSS + JS)
├── requirements.txt    # Python dependencies
├── railway.json        # Railway deploy config
└── .env                # Local env vars (jangan di-commit!)
```

---

## 📡 API Endpoints

| Method | Endpoint | Deskripsi |
|---|---|---|
| `POST` | `/api/analyze` | Analisis satu keyword (data tren + metrik) |
| `POST` | `/api/get-ai-insight` | AI insight untuk hasil analisis (async) |
| `POST` | `/api/compare` | Bandingkan dua keyword |
| `POST` | `/api/get-compare-insight` | AI insight untuk hasil perbandingan (async) |
| `POST` | `/api/analyze_sector` | Analisis sektor (preset keyword) |
| `POST` | `/api/user-status` | Cek kuota & tier user |
| `POST` | `/api/generate-pdf` | Generate laporan PDF (Pro only) |
| `GET`  | `/api/health` | Health check |

---

## 🛡️ Freemium System

- **Guest ID** dibuat otomatis di `localStorage` saat pertama kali visit
- Setiap request mengirim `user_id` ke backend
- Backend mencatat `search_logs` & membatasi **5 analisis/hari** untuk Free tier
- Upgrade ke Pro membuka: analisis tak terbatas, lokasi provinsi, PDF download

---

## ⚙️ Tech Stack

- **Backend:** Python 3.12, Flask, Gunicorn + Gevent
- **Data Source:** Google Trends (via `pytrends` + ScraperAPI proxy)
- **AI:** Google Gemini (`google-genai`)
- **Database/Cache:** Supabase (PostgreSQL)
- **Frontend:** Vanilla HTML/CSS/JS, Chart.js
- **Hosting:** Railway
- **PDF:** ReportLab

---

*Sentra BI v2.0 — Powered by Google Trends & Gemini AI*
