"""
Sentra BI v2.0 — AI Recommendation Engine (google-genai SDK)
"""
import os
import time
from google import genai
from google.genai import types


def generate_ai_insight(data: dict) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "⚠ GEMINI_API_KEY belum dikonfigurasi."

    client = genai.Client(api_key=api_key)
    prompt = _build_prompt(data)

    models_to_try = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
    ]

    for model_name in models_to_try:
        for attempt in range(2):
            try:
                print(f"[AI] Mencoba: {model_name} (attempt {attempt+1})")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                text = response.text.strip()
                if text:
                    print(f"[AI] Berhasil: {model_name}")
                    return text
            except Exception as e:
                err = str(e)
                print(f"[AI ERROR] {model_name}: {type(e).__name__}: {e}")

                if "429" in err or "quota" in err.lower() or "ResourceExhausted" in type(e).__name__:
                    # Parse retry delay dari error message
                    retry_sec = 40
                    try:
                        import re
                        match = re.search(r'retry_delay\s*\{\s*seconds:\s*(\d+)', err)
                        if match:
                            retry_sec = int(match.group(1)) + 2
                    except Exception:
                        pass

                    if attempt == 0 and retry_sec <= 45:
                        print(f"[AI] Quota 429, tunggu {retry_sec}s lalu retry...")
                        time.sleep(retry_sec)
                        continue
                    else:
                        # Kuota model ini habis, coba model berikutnya
                        print(f"[AI] Skip ke model berikutnya (retry terlalu lama)")
                        break

                elif "404" in err or "not found" in err.lower():
                    # Model tidak tersedia, langsung skip
                    break

                elif attempt == 0:
                    time.sleep(2)
                    continue
                else:
                    break

    return "⚠ Kuota AI harian habis. Hasil analisis data di atas tetap akurat. Coba lagi besok atau upgrade ke Gemini API berbayar."


def generate_compare_insight(compare_data: dict) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "⚠ AI Insight tidak tersedia."

    client = genai.Client(api_key=api_key)
    prompt = _build_compare_prompt(compare_data)

    for model_name in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
        try:
            print(f"[AI COMPARE] Mencoba: {model_name}")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            text = response.text.strip()
            if text:
                return text
        except Exception as e:
            print(f"[AI COMPARE ERROR] {model_name}: {e}")
            if "429" in str(e):
                time.sleep(5)
            continue

    return "⚠ AI Compare Insight tidak tersedia saat ini."


def generate_local_insight(keyword: str, regional_data: list) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "⚠ AI Local Insight tidak tersedia."

    if not regional_data:
        return "Tidak ada data regional yang cukup untuk dianalisis."

    client = genai.Client(api_key=api_key)
    prompt = _build_local_prompt(keyword, regional_data)

    for model_name in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            return response.text.strip()
        except Exception as e:
            print(f"[AI LOCAL ERROR] {model_name}: {e}")
            if "429" in str(e):
                time.sleep(3)
            continue

    return "⚠ Strategi lokal tidak dapat dimuat saat ini."


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

    return f"""Kamu adalah konsultan bisnis yang membantu pemilik UMKM dan orang yang baru mau mulai usaha. Gaya bicaramu santai tapi tetap profesional.

Data analisis tren dari Sentra BI v2.0:

KEYWORD          : {data.get('keyword', 'N/A')}
Growth (7 hari)  : {growth_pct}
Momentum         : {momentum_str}
Volatilitas      : {volatility_pct}
Fase tren        : {data.get('lifecycle_stage', 'N/A')}
FOMO Index       : {fomo:.2f} — {fomo_label}
Saturasi         : {saturation:.1f} ({sat_label})
Tingkat risiko   : {data.get('risk_level', 'N/A')}
Market Pulse     : {data.get('market_pulse_score', 'N/A')}/100
Forecast 30 hr   : {forecast_str}
Musiman?         : {seasonality_str}
Entry Timing     : {timing_score}/100 — {timing_label}

Tulis analisis dalam Bahasa Indonesia dengan 3 bagian:

1. Kondisi Pasar Saat Ini
Ceritakan kondisi tren dalam 3-4 kalimat. Jelaskan apakah tren sedang panas, stabil, atau meredup. Singgung FOMO index dan apakah ini tren organik atau hype sesaat.

2. Peluang & Rekomendasi untuk UMKM  
Berikan 3 rekomendasi konkret yang bisa langsung dijalankan. Tiap rekomendasi 2-3 kalimat.

3. Kapan Harus Action?
Dalam 2-3 kalimat, jelaskan rekomendasi timing berdasarkan Entry Timing Score ({timing_score}/100).

Panjang total: 220-300 kata."""


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