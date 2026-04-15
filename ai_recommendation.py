"""
Sentra BI v2.0 — AI Recommendation Engine (Groq Llama 3.3)
"""
import os
from groq import Groq

_GROQ_MODELS = [
    "llama-3.1-8b-instant",       # Super cepat & hemat (Primary)
    "llama-3.3-70b-versatile",    # Lebih pintar tapi berat (Secondary)
    "mixtral-8x7b-32768"          # Alternatif jika semua penuh
]

def _generate_via_groq(prompt: str) -> tuple[str, int, str, str]:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return "", 0, "NO_KEY", ""

    client = Groq(api_key=api_key)
    last_err = ""

    for model_name in _GROQ_MODELS:
        try:
            completion = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are an AI assistant for business insights for Indonesian SMEs (UMKM)."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7, 
                max_tokens=600,    # Dipersempit agar hemat token dan lebih tajam jawabannya
                top_p=1,
                stream=False
            )
            
            text = completion.choices[0].message.content or ""
            return text.strip(), 200, "", model_name
            
        except Exception as e:
            err_str = str(e)
            last_err = err_str
            print(f"[AI FALLBACK] Model {model_name} failed: {err_str[:100]}...")
            
            # Kalau kena rate limit (429), lompati ke model yang lebih ringan
            if '429' in err_str or 'rate_limit' in err_str.lower():
                continue
            else:
                # Kalau error lain (misal API key salah, 401), langung berhenti
                return "", 500, err_str, model_name

    # Kalau semua model sudah dicoba dan tidak ada yang berhasil
    return "", 500, f"Semua AI sedang sibuk (Rate Limit). Coba lagi nanti. Detail: {last_err[:100]}...", ""


def _format_friendly_error(err_detail: str) -> str:
    err_lower = err_detail.lower()
    if "429" in err_lower or "rate_limit" in err_lower:
        return "Aduh, otaknya Sentra AI lagi agak sibuk menangani banyak permintaan nih. Coba klik lagi tombolnya dalam 1-2 menit ya, Kak!"
    if "api_key" in err_lower or "auth" in err_lower:
        return "Satelit Sentra kehilangan koneksi kunci rahasia. Hubungi tim teknis ya!"
    return f"Ada sedikit gangguan teknis: {err_detail[:60]}... Coba lagi ya!"

def generate_ai_insight(data: dict) -> str:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return "⚠ Konfigurasi AI belum lengkap. Hubungi Admin."

    prompt = _build_prompt(data)

    try:
        text, status_code, err_detail, used_model = _generate_via_groq(prompt)
        if status_code != 200:
            return _format_friendly_error(err_detail)

        if text:
            print(f"[AI] Berhasil: {used_model}")
            return text

        return "⚠ Groq AI mengembalikan respons kosong. Coba lagi."

    except Exception as e:
        print(f"[AI ERROR] {type(e).__name__}: {e}")
        return "⚠ Gagal menghubungi Groq AI. Coba lagi."


def generate_compare_insight(compare_data: dict) -> str:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return "⚠ AI Insight tidak tersedia."

    prompt = _build_compare_prompt(compare_data)

    try:
        text, status_code, err_detail, used_model = _generate_via_groq(prompt)
        if status_code != 200:
            return "⚠ Maaf, analisis pembanding belum bisa dimuat karena server sedang padat. Coba beberapa saat lagi."

        if text:
            return text

        return "⚠ AI Compare Insight tidak tersedia saat ini."

    except Exception as e:
        print(f"[AI COMPARE ERROR] {type(e).__name__}: {e}")
        return "⚠ AI Compare Insight tidak tersedia saat ini."


def generate_local_insight(keyword: str, regional_data: list) -> str:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return "⚠ AI Local Insight tidak tersedia."

    if not regional_data:
        return "Tidak ada data regional yang cukup untuk dianalisis."

    prompt = _build_local_prompt(keyword, regional_data)

    try:
        text, status_code, err_detail, used_model = _generate_via_groq(prompt)
        if status_code != 200:
            return "Strategi lokal lagi istirahat sebentar. Coba klik lagi nanti ya."

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

    return f"""Kamu adalah mentor dan asisten bisnis UMKM yang ramah dari Sentra AI. Tulis insight bisnis dalam Bahasa Indonesia sehari-hari yang mudah dipahami oleh pengusaha kecil (UMKM) — nada hangat, suportif, praktis, dan seperti teman yang memberi saran bisnis. Jangan terlalu kaku atau formal.

═══ DATA PASAR: {data.get('keyword', 'N/A').upper()} ═══
Fase          : {data.get('lifecycle_stage', 'N/A')} | Risiko: {data.get('risk_level', 'N/A')}
Growth 7 hari : {growth_pct} | Momentum: {momentum_str}
Volatilitas   : {volatility_pct} | Market Pulse: {data.get('market_pulse_score', 'N/A')}/100
FOMO Index    : {fomo:.2f} ({fomo_label}) | Saturasi: {saturation:.1f} ({sat_label})
Entry Timing  : {timing_score}/100 — {timing_label}
Forecast 30hr : {forecast_str}
Musiman       : {seasonality_str}

Tulis analisis menjadi TEPAT 3 bagian bernomor.

1. Tulis 3 kalimat santai tentang kondisi pasar saat ini (fase, apakah hype sesaat, risikonya).
2. Tulis 3 ide aksi praktis yang bisa langsung dicoba oleh UMKM (gabungkan dalam satu paragraf, jangan pakai bullet poin/list).
3. Tulis 2 kalimat tegas tapi suportif tentang apakah sekarang waktu yang pas buat mulai jualan/masuk pasar ini (berdasarkan Entry Timing Score).

ATURAN SANGAT PENTING:
- DILARANG KERAS menggunakan format markdown seperti bold (**), asterisk (*), atau tanda pagar (#). Jangan ada bintang-bintang di teks.
- DILARANG menuliskan judul/heading seperti "Kondisi Pasar" atau "Rekomendasi Aksi".
- Awali tiap bagian HANYA dengan angka dan titik (misal: "1. Pasar lagi bagus nih..."), lalu pisahkan tiap nomor dengan spasi baris baru (enter).
- Panjang total maksimal 200 kata. Gunakan kalimat pendek yang nyaman dibaca."""


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
