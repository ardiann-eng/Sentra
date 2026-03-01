"""
Sentra Business Intelligence System v2.0
AI Recommendation Engine menggunakan Google Gemini API
"""

import os
from google import genai


def _is_quota_error(e: Exception) -> bool:
    """Deteksi apakah error adalah quota/rate limit Gemini."""
    msg = str(e).lower()
    return any(k in msg for k in [
        "429", "quota", "resource_exhausted", "rate_limit",
        "too many requests", "retry_after"
    ])


def generate_ai_insight(data: dict) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "⚠ AI Insight tidak tersedia — GEMINI_API_KEY belum dikonfigurasi."

    prompt = _build_prompt(data)

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text.strip()

    except Exception as e:
        if _is_quota_error(e):
            return (
                "⚠ Kuota AI sedang penuh. Data tren di atas tetap akurat — "
                "insight teks akan tersedia kembali dalam beberapa jam. "
                "Upgrade ke Gemini API berbayar untuk akses tak terbatas."
            )
        return f"⚠ AI Insight sementara tidak tersedia. Data analisis di atas tetap bisa digunakan."


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
    conf_pct  = f"{confidence * 100:.0f}%"
    return f"Tren ini musiman (keyakinan {conf_pct}). Puncak minat biasanya di bulan: {month_str}."


def _build_prompt(data: dict) -> str:
    growth_pct     = f"{(data.get('growth') or 0) * 100:.1f}%"
    volatility_pct = f"{(data.get('volatility') or 0) * 100:.1f}%"
    momentum       = data.get('momentum', 0) or 0
    momentum_str   = f"{abs(momentum):.3f} ({'naik' if momentum > 0 else 'turun'})"

    fomo           = data.get('fomo_index', 0) or 0
    fomo_label     = "tinggi (waspadai hype)" if fomo > 0.6 else \
                     "sedang" if fomo > 0.3 else "rendah (tren organik)"
    fomo_str       = f"{fomo:.2f} — {fomo_label}"

    saturation     = data.get('saturation_index', 0) or 0
    sat_label      = "pasar jenuh" if saturation >= 0.7 else \
                     "persaingan mulai ketat" if saturation >= 0.4 else \
                     "pasar masih terbuka"
    sat_str        = f"{saturation:.1f} ({sat_label})"

    fc_conf        = data.get('forecast_confidence', 0) or 0
    fc_label       = "tinggi" if fc_conf >= 0.7 else \
                     "sedang" if fc_conf >= 0.4 else "rendah"
    forecast_str   = f"{data.get('forecast_30d_avg', 'N/A')}/100 " \
                     f"(keyakinan forecast: {fc_label}, {fc_conf:.0%})"

    timing_score   = data.get('entry_timing_score', 'N/A')
    timing_label   = data.get('entry_timing_label', 'N/A')
    timing_str     = f"{timing_score}/100 — {timing_label}"

    seasonality_str = _format_seasonality(data)

    prompt = f"""Kamu adalah konsultan bisnis yang membantu pemilik UMKM dan orang yang baru mau mulai usaha. Gaya bicaramu santai tapi tetap profesional — seperti teman yang paham bisnis dan mau kasih saran jujur berdasarkan data.

Berikut data lengkap analisis tren dari sistem Sentra BI v2.0:

KEYWORD          : {data.get('keyword', 'N/A')}
─────────────────────────────────────────
KONDISI TREN
  Growth (7 hari) : {growth_pct}
  Momentum        : {momentum_str}
  Volatilitas     : {volatility_pct}
  Fase tren       : {data.get('lifecycle_stage', 'N/A')}
  FOMO Index      : {fomo_str}

PASAR
  Saturasi        : {sat_str}
  Tingkat risiko  : {data.get('risk_level', 'N/A')}
  Market Pulse    : {data.get('market_pulse_score', 'N/A')}/100

PREDIKSI
  Forecast 30 hr  : {forecast_str}
  Musiman?        : {seasonality_str}

KEPUTUSAN
  Entry Timing    : {timing_str}
─────────────────────────────────────────

Tulis analisis dalam Bahasa Indonesia dengan 3 bagian berikut. Gaya penulisan mengalir seperti orang berbicara — tidak kaku, tidak pakai bullet bertumpuk, hindari jargon teknis yang membingungkan orang awam.

1. Kondisi Pasar Saat Ini
Ceritakan kondisi tren ini dalam 3-4 kalimat. Jelaskan apakah tren sedang panas, stabil, atau meredup. Singgung FOMO index — apakah ini tren yang organik atau sekadar hype sesaat. Kalau tren musiman, sebut kapan waktu terbaiknya.

2. Peluang & Rekomendasi untuk UMKM
Berikan 3 rekomendasi konkret yang bisa langsung dijalankan. Tiap rekomendasi 2-3 kalimat: jelaskan apa yang harus dilakukan dan kenapa masuk akal berdasarkan data. Pertimbangkan tingkat saturasi dan risiko — apakah masih ada ruang untuk pemain baru, dan apa yang bisa dilakukan untuk unggul dari pesaing.

3. Kapan Harus Action?
Dalam 2-3 kalimat, jelaskan rekomendasi timing berdasarkan Entry Timing Score. Apakah ini momen untuk langsung tancap gas, perlu persiapan dulu, atau sebaiknya pantau dulu beberapa minggu. Sebutkan angka Entry Timing Score-nya dan artinya dengan bahasa yang mudah dipahami orang awam.

Panjang total jawaban antara 220-300 kata. Cukup untuk pengambilan keputusan, tidak berlebihan."""

    return prompt


def generate_compare_insight(compare_data: dict) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "⚠ AI Insight tidak tersedia — GEMINI_API_KEY belum dikonfigurasi."

    prompt = _build_compare_prompt(compare_data)

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text.strip()

    except Exception as e:
        if _is_quota_error(e):
            return (
                "⚠ Kuota AI sedang penuh. Hasil perbandingan di atas tetap akurat — "
                "insight teks akan tersedia kembali dalam beberapa jam."
            )
        return "⚠ AI Insight sementara tidak tersedia. Hasil perbandingan di atas tetap bisa digunakan."


def _build_compare_prompt(compare_data: dict) -> str:
    a = compare_data["keyword_a"]
    b = compare_data["keyword_b"]
    c = compare_data["comparison"]

    def fmt_pct(v): return f"{(v or 0) * 100:.1f}%"
    def fmt_f(v): return f"{(v or 0):.3f}"
    def fmt_s(v): return f"{(v or 0):.1f}"

    prompt = f"""Kamu adalah konsultan bisnis yang membantu pemilik UMKM membandingkan dua produk/tren. Gaya bicaramu santai tapi profesional — seperti teman yang paham bisnis dan mau kasih saran jujur.

Berikut data perbandingan dari Sentra BI v2.0:

═══════════════════════════════════════════
PRODUK A: {a.get('keyword', 'N/A')}
───────────────────────────────────────────
  Growth 7 hari  : {fmt_pct(a.get('growth'))}
  Momentum       : {fmt_f(a.get('momentum'))} ({'naik' if (a.get('momentum') or 0) > 0 else 'turun'})
  Volatilitas    : {fmt_pct(a.get('volatility'))}
  Fase tren      : {a.get('lifecycle_stage', 'N/A')}
  Market Pulse   : {fmt_s(a.get('market_pulse_score'))}/100
  Entry Timing   : {fmt_s(a.get('entry_timing_score'))}/100 — {a.get('entry_timing_label', 'N/A')}
  FOMO Index     : {fmt_f(a.get('fomo_index'))}
  Saturasi       : {fmt_s(a.get('saturation_index'))}
  Risiko         : {a.get('risk_level', 'N/A')}

═══════════════════════════════════════════
PRODUK B: {b.get('keyword', 'N/A')}
───────────────────────────────────────────
  Growth 7 hari  : {fmt_pct(b.get('growth'))}
  Momentum       : {fmt_f(b.get('momentum'))} ({'naik' if (b.get('momentum') or 0) > 0 else 'turun'})
  Volatilitas    : {fmt_pct(b.get('volatility'))}
  Fase tren      : {b.get('lifecycle_stage', 'N/A')}
  Market Pulse   : {fmt_s(b.get('market_pulse_score'))}/100
  Entry Timing   : {fmt_s(b.get('entry_timing_score'))}/100 — {b.get('entry_timing_label', 'N/A')}
  FOMO Index     : {fmt_f(b.get('fomo_index'))}
  Saturasi       : {fmt_s(b.get('saturation_index'))}
  Risiko         : {b.get('risk_level', 'N/A')}

═══════════════════════════════════════════
PEMENANG PER METRIK
───────────────────────────────────────────
  Growth terbaik   : {c.get('winner_growth', '—')}
  Momentum terbaik : {c.get('winner_momentum', '—')}
  Paling stabil    : {c.get('winner_stability', '—')}
  Market Pulse     : {c.get('winner_pulse', '—')}
  Entry Timing     : {c.get('winner_timing', '—')}
  FOMO terendah    : {c.get('winner_fomo', '—')}
  Saturasi terendah: {c.get('winner_saturation', '—')}
  OVERALL WINNER   : {c.get('winner_overall', '—')}
═══════════════════════════════════════════

Tulis analisis perbandingan dalam Bahasa Indonesia dengan 3 bagian berikut. Gaya penulisan mengalir, santai tapi tetap berdasarkan data:

1. Perbandingan Kondisi Pasar
Bandingkan kondisi tren kedua produk secara head-to-head dalam 3-4 kalimat. Jelaskan mana yang sedang lebih 'panas', mana yang lebih stabil, dan bagaimana posisi keduanya di pasar. Singgung perbedaan fase lifecycle dan tingkat risiko.

2. Produk Mana yang Lebih Layak Dipilih?
Berikan rekomendasi tegas — produk mana yang lebih layak dipilih SAAT INI dan jelaskan kenapa dalam 3-4 kalimat. Pertimbangkan Entry Timing Score, Market Pulse, tingkat saturasi, dan risiko. Jangan ragu untuk berpihak, tapi tetap dukung dengan data.

3. Strategi untuk Keduanya
Dalam 2-3 kalimat, berikan tips jika user ingin menjual atau memanfaatkan kedua produk sekaligus. Apakah bisa dikombinasikan? Produk mana yang jadi prioritas utama vs produk pelengkap?

Panjang total jawaban antara 220-300 kata. Langsung to the point, tidak berlebihan."""

    return prompt
