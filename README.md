# Sentra AI

> **Business Intelligence berbasis Google Trends & Claude AI untuk UMKM Indonesia**

Sentra AI menganalisis tren minat pasar secara real-time menggunakan data Google Trends, melengkapinya dengan metrik bisnis (Growth, Momentum, FOMO Index, Entry Timing Score), dan menghasilkan rekomendasi strategis dari Claude AI (Anthropic).

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
| AI Insight — 3 Card (Claude AI) | ✅ | ✅ |
| Radar Peluang Sektor (7 sektor) | ✅ | ✅ |
| Berita Terkini per Keyword | ✅ | ✅ |
| Animated Typing Placeholder | ✅ | ✅ |
| Lokasi per-Provinsi | ✅ | ✅ |
| Analisis Regional & Lokal | ✅ | ✅ |
| Download Laporan PDF | ❌ | ✅ |

---

## 🏗️ Arsitektur

```
index.html           → Single-page frontend (vanilla JS + Chart.js + GSAP)
app.py               → Flask API server (Railway)
sentra_engine.py     → Google Trends fetcher + semua kalkulasi metrik
ai_recommendation.py → Claude AI prompt builder & parser
sector_static_data.py→ Data statis 7 sektor (market size, YoY growth, subsectors)
```

### Alur Request (2-Stage Async)
```
User ketik keyword → klik "Analisis"
    │
    ├── Stage 1 → POST /api/analyze ──→ sentra_engine → Google Trends (via ScraperAPI)
    │              ↳ render grafik & metrik segera (< 15 detik ideal)
    │
    └── Stage 2 → POST /api/get-ai-insight ──→ Claude AI (Anthropic)
                   ↳ render AI cards (skeleton shimmer saat loading)
```

### Two-Level Cache
```
Request masuk
    │
    ├── L1: In-process dict (RAM) — TTL 6 jam
    │       ↳ hit → return langsung (< 1ms)
    │
    └── L2: Supabase trend_cache (PostgreSQL) — TTL 6 jam
            ↳ hit → warm L1 → return
            ↳ miss → fetch Google Trends → simpan L1 + L2
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
ANTHROPIC_API_KEY=your_claude_api_key
SCRAPERAPI_KEY=your_scraperapi_key
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=your_supabase_service_role_key
SUPABASE_ANON_KEY=your_supabase_anon_key
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
   - `ANTHROPIC_API_KEY`
   - `SCRAPERAPI_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `SUPABASE_ANON_KEY`
4. Railway otomatis deploy menggunakan `railway.json`

**Start command** (dari `railway.json`):
```
gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --worker-class sync --timeout 75
```

---

## 🔑 Environment Variables

| Variable | Wajib | Keterangan |
|---|:---:|---|
| `ANTHROPIC_API_KEY` | ✅ | Claude AI (Anthropic) — [console.anthropic.com](https://console.anthropic.com) |
| `SCRAPERAPI_KEY` | ✅ | Proxy untuk Google Trends — [scraperapi.com](https://www.scraperapi.com) (1000 req/bln gratis) |
| `SUPABASE_URL` | ⚠️ | Database cache & user data — opsional tapi disarankan |
| `SUPABASE_KEY` | ⚠️ | Supabase service role key (untuk server-side operations) |
| `SUPABASE_ANON_KEY` | ⚠️ | Supabase anon key (dikirim ke frontend via `/api/config`) |

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
    id             SERIAL PRIMARY KEY,
    user_id        TEXT NOT NULL,
    keyword        TEXT,
    geo            TEXT DEFAULT 'ID',
    is_pro_search  BOOLEAN DEFAULT FALSE,
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Profil user (tier: 'free' | 'pro')
CREATE TABLE profiles (
    id      UUID PRIMARY KEY REFERENCES auth.users(id),
    tier    TEXT DEFAULT 'free'
);
```

---

## 📁 Struktur File

```
Sentra/
├── app.py                → Flask server, endpoints, cache, freemium logic
├── sentra_engine.py      → Core: Google Trends fetch + semua kalkulasi metrik
├── ai_recommendation.py  → Claude AI prompt generation & response parsing
├── sector_static_data.py → Data statis 7 sektor untuk Radar Peluang
├── index.html            → Frontend SPA (HTML + CSS + JS)
├── requirements.txt      → Python dependencies
├── railway.json          → Railway deploy config
├── static/
│   ├── sentra.png        → Favicon / logo
│   └── Sentra_AI_Whitepaper.pdf
└── .env                  → Local env vars (jangan di-commit!)
```

---

## 📡 API Endpoints

| Method | Endpoint | Deskripsi |
|---|---|---|
| `POST` | `/api/analyze` | Analisis satu keyword (data tren + metrik) |
| `POST` | `/api/get-ai-insight` | AI insight untuk hasil analisis (async, cached) |
| `POST` | `/api/compare` | Bandingkan dua keyword |
| `POST` | `/api/get-compare-insight` | AI insight untuk hasil perbandingan (async, cached) |
| `POST` | `/api/analyze-local` | Analisis minat per-provinsi + AI strategi lokal |
| `POST` | `/api/sector-radar` | Data Radar Peluang Sektor (static + RSS news + AI signal) |
| `POST` | `/api/keyword-news` | Berita terkini dari Google News RSS per keyword |
| `GET`  | `/api/ide-produk` | Rekomendasi ide produk UMKM (wizard) |
| `GET`  | `/api/preview` | Data preview homepage (cached, tanpa kuota) |
| `POST` | `/api/user-status` | Cek kuota & tier user |
| `GET`  | `/api/config` | Expose Supabase anon key ke frontend |
| `POST` | `/api/generate-pdf` | Generate laporan PDF (Pro only) |
| `GET`  | `/api/health` | Health check |

---

## 🛡️ Freemium & Auth System

- **Autentikasi** via Supabase Auth (JWT Bearer token)
- **Guest ID** dibuat otomatis di `localStorage` sebagai fallback untuk user yang belum login
- Setiap request mengirim JWT atau `user_id` ke backend
- Backend mencatat `search_logs` & membatasi **5 analisis/hari** untuk Free tier
- Upgrade ke Pro membuka: analisis tak terbatas, lokasi per-provinsi, PDF download

---

## 🔭 Radar Peluang Sektor

Dashboard 7 sektor UMKM Indonesia dengan data real-time:

| Sektor | Keyword Representatif |
|---|---|
| 👗 Fashion | baju wanita |
| 💄 Beauty | skincare |
| 🍜 F&B | kuliner Indonesia |
| 📱 Gadget | earbuds wireless |
| 🏠 Home & Living | dekorasi rumah |
| 🎯 Hobi & Lifestyle | peralatan olahraga |
| 🎁 Musiman | hampers lebaran |

Setiap kartu sektor menampilkan:
- Market size & YoY growth (dari `sector_static_data.py`)
- Berita terkini dari RSS feeds (Antara, Bisnis, Kontan, Detik) — cache 30 menit
- AI Signal 1 kalimat dari Claude AI
- Sparkline chart (mock data visual)

---

## ⚙️ Tech Stack

| Layer | Teknologi |
|---|---|
| **Backend** | Python 3.12, Flask, Gunicorn + Gevent |
| **Data Source** | Google Trends via `pytrends` + ScraperAPI proxy |
| **AI** | Claude Haiku (`claude-haiku-4-5-20251001`) via Anthropic API |
| **Database/Cache** | Supabase (PostgreSQL) — L2 cache + auth + user data |
| **In-Memory Cache** | Python dict (L1, TTL 6h) |
| **News** | Google News RSS + feedparser (per keyword), RSS feeds per sektor |
| **Frontend** | Vanilla HTML/CSS/JS, Chart.js, GSAP 3 |
| **PDF** | ReportLab |
| **Hosting** | Railway |

---

## 🎨 Frontend Highlights

- **Animated Typing Placeholder** — placeholder input berganti otomatis dengan efek mengetik/menghapus (8 contoh keyword, berhenti saat fokus)
- **Live Intelligence Preview** — chart tren real-time di homepage (keyword: skincare)
- **Skeleton Shimmer** — loading state untuk AI cards & berita
- **Radar Peluang** — floating panel per sektor dengan data live
- **Freemium Gate** — modal upgrade Pro dengan animasi GSAP
- **Supabase Auth** — login/register modal terintegrasi

---

*Sentra AI — Powered by Google Trends & Claude AI (Anthropic)*
