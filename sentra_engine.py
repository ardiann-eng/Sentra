import re
import time
import random
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from concurrent.futures import ThreadPoolExecutor
from pytrends.request import TrendReq
from pytrends.exceptions import TooManyRequestsError
try:
    from fake_useragent import UserAgent as _UA
    _UA_ENABLED = True
except Exception:
    _UA_ENABLED = False


# ── ScraperAPI proxy config ────────────────────────────────────────────────
_PROXY_URL = (
    "http://scraperapi:9d165dff5be59579040bc2333e85f07b"
    "@proxy-server.scraperapi.com:8001"
)
_PROXIES = {"http": _PROXY_URL, "https": _PROXY_URL}

_FALLBACK_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)


def _make_pytrends():
    api_key = "9d165dff5be59579040bc2333e85f07b"
    # Gunakan format standar ScraperAPI tanpa tambahan parameter di password
    proxy_url = f"http://scraperapi:{api_key}@proxy-server.scraperapi.com:8001"
    
    return TrendReq(
        hl='id-ID',
        tz=420,
        retries=2,
        backoff_factor=3,
        requests_args={
            'proxies': {'http': proxy_url, 'https': proxy_url},
            'timeout': 45, # Timeout internal lebih pendek dari Gunicorn
            'verify': False
        }
    )


def _jitter():
    """Random human-like delay between Trends requests (1-3 s)."""
    time.sleep(random.uniform(1.0, 3.0))


# =========================
# 1. FETCH DATA
# =========================

def fetch_trend_data(keyword, timeframe="today 3-m", geo="ID", cat=0):
    try:
        pytrends = _make_pytrends()
        _jitter()
        pytrends.build_payload([keyword], timeframe=timeframe, geo=geo, cat=cat)
        data = pytrends.interest_over_time()
    except TooManyRequestsError:
        raise
    except Exception as e:
        print(f"--- DEBUG fetch_trend_data ERROR ---: {e}")
        return None

    if data.empty:
        return None

    df = data[[keyword]].reset_index()
    df.columns = ["date", "interest"]
    return df


def fetch_trend_data_long(keyword, timeframe="today 12-m", geo="ID"):
    """Ambil data 12 bulan untuk keperluan seasonality & baseline."""
    try:
        pytrends = _make_pytrends()
        _jitter()
        pytrends.build_payload([keyword], timeframe=timeframe, geo=geo)
        data = pytrends.interest_over_time()
    except TooManyRequestsError:
        raise
    except Exception:
        return None

    if data.empty:
        return None

    df = data[[keyword]].reset_index()
    df.columns = ["date", "interest"]
    return df


def fetch_related_keywords(keyword):
    """Ambil keyword yang berkaitan untuk competitor density."""
    try:
        pytrends = _make_pytrends()
        _jitter()
        pytrends.build_payload([keyword], timeframe="today 3-m")
        related = pytrends.related_queries()
    except Exception:
        return []

    result = []
    try:
        top = related[keyword]["top"]
        if top is not None:
            result = top["query"].head(5).tolist()
    except Exception:
        pass

    return result


# =========================
# 1b. VALIDASI KEYWORD
# =========================

def validate_keyword(keyword):
    """
    Validasi format keyword sebelum dikirim ke Google Trends.

    Menolak input yang:
    - Hanya berisi angka (misal '123456')
    - Hanya berisi simbol (misal '!!!??')
    - Berisi karakter berulang tidak wajar (misal 'aaaaa', 'ababab')
    - Terlalu pendek (kurang dari 2 karakter alfabet)

    Returns:
        dict dengan key 'valid' (bool) dan 'error' (str) jika tidak valid.
    """
    cleaned = keyword.strip()

    if not cleaned:
        return {"valid": False, "error": "Keyword tidak boleh kosong. Coba ketik nama produk seperti 'matcha' atau 'kopi susu'."}

    # Tolak jika hanya angka
    if re.fullmatch(r'[\d\s]+', cleaned):
        return {"valid": False, "error": "Keyword tidak boleh hanya berisi angka. Coba ketik nama produk, misal 'sepatu running' atau 'hijab premium'."}

    # Tolak jika hanya simbol/tanda baca
    if re.fullmatch(r'[^\w\s]+', cleaned):
        return {"valid": False, "error": "Keyword tidak valid — hanya berisi simbol. Coba ketik nama produk yang ingin kamu riset."}

    # Tolak karakter berulang (minimal 4x huruf yang sama berturut-turut)
    if re.search(r'(.)\1{3,}', cleaned):
        return {"valid": False, "error": "Keyword terlihat tidak wajar (huruf berulang). Pastikan kamu mengetik nama produk yang benar, misal 'brownies' atau 'skincare'."}

    # Tolak pola berulang pendek (misal 'ababab', 'xyzxyz')
    if len(cleaned) >= 4 and re.fullmatch(r'(.{1,3})\1{2,}', cleaned.replace(' ', '')):
        return {"valid": False, "error": "Keyword terlihat tidak wajar (pola berulang). Coba ketik nama produk yang sebenarnya."}

    # Minimal harus ada 2 huruf alfabet
    alpha_chars = re.findall(r'[a-zA-Z]', cleaned)
    if len(alpha_chars) < 2:
        return {"valid": False, "error": "Keyword terlalu pendek atau tidak mengandung huruf yang cukup. Coba ketik minimal 2 huruf, misal 'es kopi' atau 'tas kulit'."}

    return {"valid": True}


def check_keyword_exists(keyword):
    """
    Cek apakah keyword dikenali oleh Google menggunakan pytrends suggestions.

    Jika Google tidak memberikan saran sama sekali, kemungkinan besar
    keyword tersebut tidak relevan atau ketikan asal-asalan.

    Returns:
        dict dengan key 'exists' (bool) dan 'error' (str) jika tidak ditemukan.
    """
    try:
        pytrends = TrendReq()
        suggestions = pytrends.suggestions(keyword)

        if not suggestions or len(suggestions) == 0:
            return {
                "exists": False,
                "error": f"Google tidak mengenali keyword '{keyword}'. "
                         f"Pastikan ejaan sudah benar, atau coba keyword lain yang lebih umum."
            }

        return {"exists": True, "suggestions": suggestions}

    except Exception:
        # Jika suggestions API gagal, lanjutkan saja (jangan blokir user)
        return {"exists": True}


# =========================
# 2. METRICS DASAR
# =========================

def compute_growth(df):
    recent = df["interest"].iloc[-7:].mean()
    previous = df["interest"].iloc[-14:-7].mean()

    if previous == 0:
        return 0

    return (recent - previous) / previous


def compute_momentum(df):
    y = df["interest"].values
    x = np.arange(len(y)).reshape(-1, 1)

    model = LinearRegression().fit(x, y)
    return model.coef_[0]


def compute_volatility(df):
    mean = df["interest"].mean()
    if mean == 0:
        return 0
    return df["interest"].std() / mean


def detect_spike(df):
    mean = df["interest"].mean()
    std = df["interest"].std()
    last_value = df["interest"].iloc[-1]

    return last_value > mean + 2 * std


def compute_saturation(df, growth, momentum):
    momentum_norm = abs(momentum)

    if growth > 0 and momentum_norm < 0.1:
        return 0.8
    elif growth > 0 and momentum_norm < 0.2:
        return 0.6
    elif growth > 0:
        return 0.3
    else:
        return 0.2


def forecast_next_30_days(df):
    y = df["interest"].values
    x = np.arange(len(y)).reshape(-1, 1)

    model = LinearRegression().fit(x, y)

    future_x = np.arange(len(y), len(y) + 30).reshape(-1, 1)
    forecast = model.predict(future_x)

    avg_forecast = np.mean(forecast)

    return round(float(avg_forecast), 2)


# =========================
# 3. FITUR BARU v2.0
# =========================

def detect_peak(df, growth, momentum):
    """
    Deteksi apakah tren sedang berada di puncak (Peak).

    Peak terjadi ketika:
    - Interest saat ini berada di atau dekat nilai tertinggi historis
    - Tapi momentum mulai melemah atau berbalik arah
    - Growth masih positif tapi melambat

    Returns:
        bool: True jika tren terdeteksi sedang di fase Peak
    """
    values = df["interest"].values
    current = values[-1]
    peak_value = np.max(values)

    # Berada di 90% dari nilai tertinggi
    near_peak = current >= peak_value * 0.90

    # Momentum melemah (positif tapi kecil, atau mulai negatif)
    momentum_weakening = momentum < 0.3

    # Growth masih positif tapi kecil
    growth_slowing = 0 < growth < 0.15

    return near_peak and (momentum_weakening or growth_slowing)


def compute_fomo_index(df):
    """
    Hitung FOMO Index — seberapa besar lonjakan minat jangka pendek
    dibanding baseline jangka panjang.

    Nilai tinggi = minat melonjak tiba-tiba (bisa hype sesaat)
    Nilai rendah = pertumbuhan organik dan konsisten

    Returns:
        float: 0.0 – 1.0 (semakin tinggi = semakin FOMO)
    """
    values = df["interest"].values

    if len(values) < 14:
        return 0.0

    short_term_avg = np.mean(values[-7:])   # rata-rata 7 hari terakhir
    long_term_avg  = np.mean(values[:-7])   # rata-rata sebelumnya

    if long_term_avg == 0:
        return 0.0

    ratio = short_term_avg / long_term_avg

    # Clamp ke 0–1: ratio 2.0 (2x lipat) dianggap FOMO penuh
    fomo = min((ratio - 1.0) / 1.0, 1.0)
    fomo = max(fomo, 0.0)

    return round(fomo, 3)


def detect_seasonality(df_long):
    """
    Deteksi apakah tren bersifat musiman berdasarkan data 12 bulan.

    Metode: bandingkan standar deviasi antar bulan. Kalau pola interest
    berulang di bulan-bulan tertentu secara signifikan, itu seasonal.

    Returns:
        dict: {
            "is_seasonal": bool,
            "confidence": float (0–1),
            "peak_months": list[int]  — bulan dengan interest tertinggi
        }
    """
    if df_long is None or len(df_long) < 30:
        return {"is_seasonal": False, "confidence": 0.0, "peak_months": []}

    df_long = df_long.copy()
    df_long["month"] = pd.to_datetime(df_long["date"]).dt.month

    monthly_avg = df_long.groupby("month")["interest"].mean()

    if monthly_avg.std() == 0:
        return {"is_seasonal": False, "confidence": 0.0, "peak_months": []}

    # Koefisien variasi antar bulan
    cv = monthly_avg.std() / monthly_avg.mean()

    # CV > 0.25 mengindikasikan pola musiman yang signifikan
    is_seasonal = cv > 0.25
    confidence  = round(min(cv / 0.5, 1.0), 2)  # normalize ke 0–1

    # Bulan-bulan dengan interest di atas rata-rata + 0.5 std
    threshold   = monthly_avg.mean() + 0.5 * monthly_avg.std()
    peak_months = monthly_avg[monthly_avg >= threshold].index.tolist()

    return {
        "is_seasonal": is_seasonal,
        "confidence": confidence,
        "peak_months": peak_months
    }


def compute_forecast_confidence(df, volatility):
    """
    Hitung seberapa bisa dipercaya hasil forecast.

    Faktor yang menurunkan confidence:
    - Volatilitas tinggi (data zig-zag)
    - Data terlalu sedikit
    - R² regresi rendah

    Returns:
        float: 0.0 – 1.0 (semakin tinggi = forecast makin bisa dipercaya)
    """
    values = df["interest"].values

    if len(values) < 10:
        return 0.2

    # Hitung R² dari regresi linear
    x = np.arange(len(values)).reshape(-1, 1)
    y = values
    model = LinearRegression().fit(x, y)
    y_pred = model.predict(x)

    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)

    r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
    r2 = max(r2, 0)

    # Penalti volatilitas
    vol_penalty = min(volatility, 1.0)

    confidence = (0.6 * r2) + (0.4 * (1 - vol_penalty))
    return round(max(confidence, 0.05), 2)


def compute_entry_timing_score(lifecycle_stage, growth, momentum,
                                fomo_index, saturation, forecast_30d,
                                current_avg, risk_level):
    """
    Hitung Entry Timing Score — seberapa bagus timing untuk masuk sekarang.

    Skala 0–100:
    - 80–100 : Waktu terbaik untuk action
    - 60–79  : Timing bagus, mulai persiapan
    - 40–59  : Boleh masuk tapi hati-hati
    - 20–39  : Tunggu dulu, tren belum jelas
    - 0–19   : Hindari, risiko tinggi

    Returns:
        float: 0–100
    """
    score = 50.0  # baseline netral

    # --- Bonus dari lifecycle stage ---
    stage_bonus = {
        "Emerging": +20,
        "Rising":   +25,
        "Peak":     -10,
        "Stable":   +5,
        "Declining": -25,
    }
    score += stage_bonus.get(lifecycle_stage, 0)

    # --- Bonus dari growth ---
    if growth > 0.3:
        score += 15
    elif growth > 0.1:
        score += 8
    elif growth < -0.2:
        score -= 15
    elif growth < 0:
        score -= 5

    # --- Bonus dari momentum ---
    if momentum > 0.5:
        score += 10
    elif momentum > 0:
        score += 5
    elif momentum < -0.5:
        score -= 10
    else:
        score -= 3

    # --- Penalti FOMO tinggi (tren hype, bukan organik) ---
    if fomo_index > 0.7:
        score -= 15
    elif fomo_index > 0.4:
        score -= 7

    # --- Penalti saturasi tinggi ---
    if saturation >= 0.7:
        score -= 12
    elif saturation >= 0.5:
        score -= 6

    # --- Bonus dari forecast positif ---
    if current_avg > 0 and forecast_30d > current_avg * 1.1:
        score += 10
    elif forecast_30d < current_avg * 0.9:
        score -= 8

    # --- Penalti risk level ---
    risk_penalty = {"High Risk": -10, "Medium Risk": -4, "Low Risk": 0}
    score += risk_penalty.get(risk_level, 0)

    return round(max(min(score, 100), 0), 1)


def entry_timing_label(score):
    """Konversi Entry Timing Score ke label yang mudah dibaca."""
    if score >= 80:
        return "Waktu Terbaik"
    elif score >= 60:
        return "Bagus, Mulai Persiapan"
    elif score >= 40:
        return "Boleh Masuk, Waspada"
    elif score >= 20:
        return "Tunggu Dulu"
    else:
        return "Hindari"


# =========================
# 4. CLASSIFICATION
# =========================

def classify_lifecycle(growth, momentum, is_peak):
    """
    Klasifikasi lifecycle stage dengan tambahan deteksi Peak.
    """
    if is_peak:
        return "Peak"
    elif growth > 0.2 and momentum > 0:
        return "Rising"
    elif growth < 0 and momentum < 0:
        return "Declining"
    elif growth > 0:
        return "Emerging"
    else:
        return "Stable"


def compute_risk(volatility, spike, fomo_index):
    """Risk level dengan mempertimbangkan FOMO."""
    if (volatility > 0.5 and spike) or fomo_index > 0.7:
        return "High Risk"
    elif volatility > 0.3 or fomo_index > 0.4:
        return "Medium Risk"
    else:
        return "Low Risk"


# =========================
# 5. MARKET PULSE SCORE
# =========================

def compute_market_pulse(growth, momentum, volatility):
    growth_clamped = max(min(growth, 0.5), -0.5)
    growth_norm = (growth_clamped + 0.5)

    momentum_norm = (np.tanh(momentum) + 1) / 2

    vol_norm = min(volatility, 1)
    stability = 1 - vol_norm

    score = (
        0.4 * growth_norm +
        0.35 * momentum_norm +
        0.25 * stability
    ) * 100

    return round(score, 1)


# =========================
# 6. MASTER FUNCTION
# =========================

def analyze_keyword(keyword, geo="ID", cat=0):
    """
    Analisis lengkap satu keyword.

    Args:
        keyword: kata kunci produk
        geo: kode wilayah Google Trends (default 'ID' = Indonesia nasional;
             Pro user bisa gunakan 'ID-JK', 'ID-JB', dst)

    Returns dict dengan semua metrik Sentra v2.0.
    """
    # — Validasi format keyword —
    validation = validate_keyword(keyword)
    if not validation["valid"]:
        return {"error": validation["error"]}

    # — Cek apakah keyword dikenali Google —
    existence = check_keyword_exists(keyword)
    if not existence.get("exists", True):
        return {"error": existence["error"]}

    # — Fetch data —
    try:
        df      = fetch_trend_data(keyword, geo=geo, cat=cat)
        df_long = fetch_trend_data_long(keyword, geo=geo)
    except TooManyRequestsError:
        return {
            "error": "Google Trends sedang ramai. Mohon tunggu 10-15 menit dan coba lagi.",
            "error_code": "TOO_MANY_REQUESTS",
        }

    if df is None:
        return {"error": "Data tidak ditemukan. Keyword ini tidak memiliki volume pencarian yang cukup di Google."}

    # — Cek jika semua interest bernilai 0 —
    if df["interest"].sum() == 0:
        return {"error": "Data tidak ditemukan. Keyword ini tidak memiliki volume pencarian yang cukup di Google."}

    # — Metrik dasar —
    growth     = compute_growth(df)
    momentum   = compute_momentum(df)
    volatility = compute_volatility(df)
    spike      = detect_spike(df)

    # — Fitur baru v2.0 —
    fomo_index  = compute_fomo_index(df)
    is_peak     = detect_peak(df, growth, momentum)
    seasonality = detect_seasonality(df_long)
    forecast_30 = forecast_next_30_days(df)
    fc_confidence = compute_forecast_confidence(df, volatility)
    saturation  = compute_saturation(df, growth, momentum)

    # — Klasifikasi —
    stage      = classify_lifecycle(growth, momentum, is_peak)
    risk       = compute_risk(volatility, spike, fomo_index)
    pulse_score = compute_market_pulse(growth, momentum, volatility)

    # — Entry Timing —
    current_avg = df["interest"].iloc[-7:].mean()
    timing_score = compute_entry_timing_score(
        stage, growth, momentum, fomo_index,
        saturation, forecast_30, current_avg, risk
    )
    timing_label = entry_timing_label(timing_score)

    return {
        # Identitas
        "keyword":  keyword,
        "geo":      geo,

        # Raw trend (untuk chart frontend)
        "raw_trend": {
            "dates":  [str(d.date())[:10] for d in df["date"]],
            "values": df["interest"].tolist(),
        },

        # Metrik dasar
        "growth":               round(float(growth), 3),
        "momentum":             round(float(momentum), 3),
        "volatility":           round(float(volatility), 3),

        # Klasifikasi
        "lifecycle_stage":      stage,
        "risk_level":           risk,
        "market_pulse_score":   pulse_score,

        # Saturasi & FOMO
        "saturation_index":     saturation,
        "fomo_index":           fomo_index,

        # Forecast
        "forecast_30d_avg":     forecast_30,
        "forecast_confidence":  fc_confidence,

        # Seasonality
        "is_seasonal":          seasonality["is_seasonal"],
        "seasonal_confidence":  seasonality["confidence"],
        "seasonal_peak_months": seasonality["peak_months"],

        # Entry Timing (output paling actionable)
        "entry_timing_score":   timing_score,
        "entry_timing_label":   timing_label,
    }


# =========================
# 7. BENCHMARKING / COMPARE
# =========================

def fetch_comparison_trend(keyword_a, keyword_b, timeframe="today 3-m", geo="ID"):
    """
    Fetch interest over time untuk kedua keyword dalam SATU request pytrends.
    """
    try:
        pytrends = TrendReq()
        pytrends.build_payload([keyword_a, keyword_b], timeframe=timeframe, geo=geo)
        data = pytrends.interest_over_time()

        if data.empty:
            return None

        df = data[[keyword_a, keyword_b]].reset_index()

        return {
            "dates":    [d.strftime("%Y-%m-%d") for d in df["date"]],
            "values_a": df[keyword_a].tolist(),
            "values_b": df[keyword_b].tolist(),
        }
    except Exception:
        return None


def compute_comparison_metrics(result_a, result_b):
    """
    Bandingkan metrik kedua keyword dan tentukan pemenang per-metrik.

    Returns:
        dict berisi winner per-metrik dan summary.
    """
    def pick_winner(val_a, val_b, keyword_a, keyword_b, higher_is_better=True):
        if val_a is None or val_b is None:
            return "—"
        if higher_is_better:
            return keyword_a if val_a > val_b else keyword_b if val_b > val_a else "Seri"
        else:
            return keyword_a if val_a < val_b else keyword_b if val_b < val_a else "Seri"

    kw_a = result_a["keyword"]
    kw_b = result_b["keyword"]

    comparison = {
        "winner_growth":      pick_winner(result_a["growth"],             result_b["growth"],             kw_a, kw_b, True),
        "winner_momentum":    pick_winner(result_a["momentum"],           result_b["momentum"],           kw_a, kw_b, True),
        "winner_stability":   pick_winner(result_a["volatility"],         result_b["volatility"],         kw_a, kw_b, False),  # lower volatility = better
        "winner_pulse":       pick_winner(result_a["market_pulse_score"], result_b["market_pulse_score"], kw_a, kw_b, True),
        "winner_timing":      pick_winner(result_a["entry_timing_score"], result_b["entry_timing_score"], kw_a, kw_b, True),
        "winner_fomo":        pick_winner(result_a["fomo_index"],         result_b["fomo_index"],         kw_a, kw_b, False),  # lower FOMO = more organic
        "winner_saturation":  pick_winner(result_a["saturation_index"],   result_b["saturation_index"],   kw_a, kw_b, False),  # lower = more open market
    }

    # Overall winner — berdasarkan bobot market pulse + entry timing
    score_a = (result_a.get("market_pulse_score") or 0) * 0.4 + (result_a.get("entry_timing_score") or 0) * 0.6
    score_b = (result_b.get("market_pulse_score") or 0) * 0.4 + (result_b.get("entry_timing_score") or 0) * 0.6

    if score_a > score_b:
        comparison["winner_overall"] = kw_a
    elif score_b > score_a:
        comparison["winner_overall"] = kw_b
    else:
        comparison["winner_overall"] = "Seri"

    comparison["score_a"] = round(score_a, 1)
    comparison["score_b"] = round(score_b, 1)

    return comparison



def compare_keywords(keyword_a, keyword_b, geo="ID"):
    """
    Master function untuk benchmarking dua keyword.
    """
    # — Validasi kedua keyword sebelum analisis paralel —
    for kw in [keyword_a, keyword_b]:
        val = validate_keyword(kw)
        if not val["valid"]:
            return {"error": f"Keyword '{kw}': {val['error']}"}

    # Paralel: analisis kedua keyword + fetch trend komparasi
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_a     = executor.submit(analyze_keyword, keyword_a, geo)
        future_b     = executor.submit(analyze_keyword, keyword_b, geo)
        future_trend = executor.submit(fetch_comparison_trend, keyword_a, keyword_b, "today 3-m", geo)

        result_a    = future_a.result()
        result_b    = future_b.result()
        trend_data  = future_trend.result()

    # Cek error
    if "error" in result_a:
        return {"error": f"Keyword '{keyword_a}': {result_a['error']}"}
    if "error" in result_b:
        return {"error": f"Keyword '{keyword_b}': {result_b['error']}"}

    # Hitung perbandingan
    comparison = compute_comparison_metrics(result_a, result_b)

    return {
        "keyword_a":  result_a,
        "keyword_b":  result_b,
        "comparison": comparison,
        "trend_data": trend_data,
    }
