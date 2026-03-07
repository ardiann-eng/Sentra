"""
Sentra BI v2.0 — AI Recommendation Engine (Claude API / Anthropic)
"""
import os
import requests


def generate_ai_insight(data: dict) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "⚠ ANTHROPIC_API_KEY belum dikonfigurasi."

    prompt = _build_prompt(data)

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=45,
        )

        if response.status_code != 200:
            print(f"[AI ERROR] Claude API status {response.status_code}: {response.text[:300]}")
            return f"⚠ Claude AI error (HTTP {response.status_code}). Coba lagi nanti."

        text = response.json()["content"][0]["text"].strip()
        if text:
            print("[AI] Berhasil: claude-haiku-4-5-20251001")
            return text

        return "⚠ Claude AI mengembalikan respons kosong. Coba lagi."

    except requests.exceptions.Timeout:
        print("[AI ERROR] Claude API timeout (45s)")
        return "⚠ Gagal menghubungi Claude AI (timeout). Coba lagi."
    except Exception as e:
        print(f"[AI ERROR] {type(e).__name__}: {e}")
        return "⚠ Gagal menghubungi Claude AI. Coba lagi."


def generate_compare_insight(compare_data: dict) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "⚠ AI Insight tidak tersedia."

    prompt = _build_compare_prompt(compare_data)

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=45,
        )

        if response.status_code != 200:
            print(f"[AI COMPARE ERROR] Claude API status {response.status_code}: {response.text[:300]}")
            return "⚠ AI Compare Insight tidak tersedia saat ini."

        text = response.json()["content"][0]["text"].strip()
        if text:
            return text

        return "⚠ AI Compare Insight tidak tersedia saat ini."

    except Exception as e:
        print(f"[AI COMPARE ERROR] {type(e).__name__}: {e}")
        return "⚠ AI Compare Insight tidak tersedia saat ini."


def generate_local_insight(keyword: str, regional_data: list) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "⚠ AI Local Insight tidak tersedia."

    if not regional_data:
        return "Tidak ada data regional yang cukup untuk dianalisis."

    prompt = _build_local_prompt(keyword, regional_data)

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=45,
        )

        if response.status_code != 200:
            print(f"[AI LOCAL ERROR] Claude API status {response.status_code}: {response.text[:300]}")
            return "Strategi lokal tidak dapat dimuat saat ini."

        text = response.json()["content"][0]["text"].strip()
        if text:
            return text

        return "Strategi lokal tidak dapat dimuat saat ini."

    except Exception as e:
        print(f"[AI LOCAL ERROR] {type(e).__name__}: {e}")
        return "Strategi lokal tidak dapat dimuat saat ini."


def _format_seasonality(data: dict) -> str:
    if not data.get("is_seasonal"):
        return "Tidak terdeteksi pola musiman — tren berjalan sepanjang tahun."

    confidence = data.get("seasonal_confidence", 0)
    months = data.get("seasonal_peak_months", [])
    month_names = {
        1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
        5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
        9: "September", 10: "Oktober", 11: "November", 12: "Desember"
    }
    month_str = ", ".join([month_names.get(m, str(m)) for m in months])
    return f"Tren ini musiman (keyakinan {confidence*100:.0f}%). Puncak minat biasanya di bulan: {month_str}."


def _build_prompt(data: dict) -> str:
    growth_pct     = f"{(data.get('growth') or 0) * 100:.1f}%"
    volatility_pct = f"{(data.get('volatility') or 0) * 100:.1f}%"
    momentum       = data.get('momentum', 0) or 0
    momentum_str   = f"{abs(momentum):.3f} ({'naik' if momentum > 0 else 'turun'})"
    fomo           = data.get('fomo_index', 0) or 0
    fomo_label     = "tinggi (waspadai hype)" if fomo > 0.6 else "sedang" if fomo > 0.3 else "rendah (tren organik)"
    saturation     = data.get('saturation_index', 0) or 0
    sat_label      = "pasar jenuh" if saturation >= 0.7 else "persaingan mulai ketat" if saturation >= 0.4 else "pasar masih terbuka"
    fc_conf        = data.get('forecast_confidence', 0) or 0
    fc_label       = "tinggi" if fc_conf >= 0.7 else "sedang" if fc_conf >= 0.4 else "rendah"
    forecast_str   = f"{data.get('forecast_30d_avg', 'N/A')}/100 (keyakinan: {fc_label}, {fc_conf:.0%})"
    timing_score   = data.get('entry_timing_score', 'N/A')
    timing_label   = data.get('entry_timing_label', 'N/A')
    seasonality_str = _format_seasonality(data)

    return f"""Kamu adalah analis pasar senior Sentra BI. Tulis insight bisnis dalam Bahasa Indonesia — 
nada profesional, langsung ke poin, tanpa basa-basi pembuka.

═══ DATA PASAR: {data.get('keyword', 'N/A').upper()} ═══
Fase          : {data.get('lifecycle_stage', 'N/A')} | Risiko: {data.get('risk_level', 'N/A')}
Growth 7 hari : {growth_pct} | Momentum: {momentum_str}
Volatilitas   : {volatility_pct} | Market Pulse: {data.get('market_pulse_score', 'N/A')}/100
FOMO Index    : {fomo:.2f} ({fomo_label}) | Saturasi: {saturation:.1f} ({sat_label})
Entry Timing  : {timing_score}/100 — {timing_label}
Forecast 30hr : {forecast_str}
Musiman       : {seasonality_str}

Tulis analisis dengan TEPAT 3 bagian berikut:

**1. Kondisi Pasar**
3 kalimat. Baca data secara holistik — sebutkan fase, arah momentum, dan apakah 
permintaan ini organik atau hype sesaat berdasarkan FOMO Index.

**2. Rekomendasi Aksi**
Tepat 3 rekomendasi. Setiap rekomendasi: 1 kalimat aksi spesifik + 1 kalimat alasan 
dari data. Mulai tiap poin dengan kata kerja (Fokuskan, Manfaatkan, Hindari, dst).

**3. Timing & Keputusan**
2 kalimat. Berikan keputusan tegas: apakah sekarang waktu masuk, tunggu, atau hindari — 
berdasarkan Entry Timing Score {timing_score}/100 dan fase {data.get('lifecycle_stage', 'N/A')}.

ATURAN:
- Total 180-220 kata (lebih singkat = lebih baik)
- Tidak ada kalimat pembuka seperti "Berikut analisis saya..."
- Sebut angka spesifik dari data, bukan generik
- Gunakan format bold untuk heading tiap bagian"""


def _build_compare_prompt(compare_data: dict) -> str:
    a = compare_data["keyword_a"]
    b = compare_data["keyword_b"]
    c = compare_data["comparison"]

    def fmt_pct(v): return f"{(v or 0) * 100:.1f}%"
    def fmt_f(v): return f"{(v or 0):.3f}"

    return f"""Kamu adalah konsultan bisnis yang membantu UMKM membandingkan dua produk/tren.

Data perbandingan Sentra BI v2.0:

PRODUK A: {a.get('keyword', 'N/A')}
  Growth: {fmt_pct(a.get('growth'))} | Momentum: {fmt_f(a.get('momentum'))} | Market Pulse: {a.get('market_pulse_score', 0):.1f}/100
  Entry Timing: {a.get('entry_timing_score', 0):.1f}/100 | Risiko: {a.get('risk_level', 'N/A')}

PRODUK B: {b.get('keyword', 'N/A')}
  Growth: {fmt_pct(b.get('growth'))} | Momentum: {fmt_f(b.get('momentum'))} | Market Pulse: {b.get('market_pulse_score', 0):.1f}/100
  Entry Timing: {b.get('entry_timing_score', 0):.1f}/100 | Risiko: {b.get('risk_level', 'N/A')}

OVERALL WINNER: {c.get('winner_overall', '—')}

Tulis analisis perbandingan dalam Bahasa Indonesia dengan 3 bagian:
1. Perbandingan Kondisi Pasar (3-4 kalimat)
2. Produk Mana yang Lebih Layak Dipilih? (3-4 kalimat, tegas berpihak dengan alasan data)
3. Strategi untuk Keduanya (2-3 kalimat)

Panjang total: 220-300 kata."""


def _build_local_prompt(keyword: str, regional_data: list) -> str:
    sorted_data = sorted(regional_data, key=lambda x: x['value'], reverse=True)
    top_regions = sorted_data[:5]
    region_str = "\n".join([f"- {r['name']}: {r['value']}/100" for r in top_regions])

    return f"""Kamu adalah ahli strategi "Local Hero" untuk UMKM Indonesia.
Analisis data regional untuk kata kunci "{keyword}":

{region_str}

Dalam 1 paragraf singkat (maks 80 kata), berikan motivasi dan 1 strategi pemasaran spesifik untuk wilayah dengan minat tertinggi. Gaya bahasa santai, akrab, sebutkan nama daerahnya."""
