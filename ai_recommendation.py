"""
Sentra BI v2.0 — AI Recommendation Engine (OpenRouter)
"""
import os
import requests

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_OPENROUTER_MODEL = "qwen/qwen3-next-80b-a3b-instruct:free"


def _extract_openrouter_text(resp_json: dict) -> str:
    choices = resp_json.get("choices") or []
    if not choices:
        return ""

    message = choices[0].get("message") or {}
    content = message.get("content")

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "\n".join([p for p in parts if p]).strip()

    return ""


def _generate_via_openrouter(prompt: str) -> tuple[str, int, str]:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return "", 0, "NO_KEY"

    response = requests.post(
        _OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": _OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": "You are an AI assistant for business insights."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 1024,
            "temperature": 0.4,
        },
        timeout=45,
    )

    if response.status_code != 200:
        return "", response.status_code, response.text[:300]

    text = _extract_openrouter_text(response.json())
    return text, 200, ""


def generate_ai_insight(data: dict) -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return "⚠ OPENROUTER_API_KEY belum dikonfigurasi."

    prompt = _build_prompt(data)

    try:
        text, status_code, err_detail = _generate_via_openrouter(prompt)
        if status_code != 200:
            print(f"[AI ERROR] OpenRouter API status {status_code}: {err_detail}")
            return f"⚠ OpenRouter AI error (HTTP {status_code}). Coba lagi nanti."

        if text:
            print(f"[AI] Berhasil: {_OPENROUTER_MODEL}")
            return text

        return "⚠ OpenRouter AI mengembalikan respons kosong. Coba lagi."

    except requests.exceptions.Timeout:
        print("[AI ERROR] OpenRouter API timeout (45s)")
        return "⚠ Gagal menghubungi OpenRouter AI (timeout). Coba lagi."
    except Exception as e:
        print(f"[AI ERROR] {type(e).__name__}: {e}")
        return "⚠ Gagal menghubungi OpenRouter AI. Coba lagi."


def generate_compare_insight(compare_data: dict) -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return "⚠ AI Insight tidak tersedia."

    prompt = _build_compare_prompt(compare_data)

    try:
        text, status_code, err_detail = _generate_via_openrouter(prompt)
        if status_code != 200:
            print(f"[AI COMPARE ERROR] OpenRouter API status {status_code}: {err_detail}")
            return "⚠ AI Compare Insight tidak tersedia saat ini."

        if text:
            return text

        return "⚠ AI Compare Insight tidak tersedia saat ini."

    except Exception as e:
        print(f"[AI COMPARE ERROR] {type(e).__name__}: {e}")
        return "⚠ AI Compare Insight tidak tersedia saat ini."


def generate_local_insight(keyword: str, regional_data: list) -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return "⚠ AI Local Insight tidak tersedia."

    if not regional_data:
        return "Tidak ada data regional yang cukup untuk dianalisis."

    prompt = _build_local_prompt(keyword, regional_data)

    try:
        text, status_code, err_detail = _generate_via_openrouter(prompt)
        if status_code != 200:
            print(f"[AI LOCAL ERROR] OpenRouter API status {status_code}: {err_detail}")
            return "Strategi lokal tidak dapat dimuat saat ini."

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
