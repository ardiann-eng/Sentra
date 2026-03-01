import re
import time
import random
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from concurrent.futures import ThreadPoolExecutor
from pytrends.request import TrendReq
from pytrends.exceptions import TooManyRequestsError

# --- CONFIGURATION ---
_ZENROWS_KEY = "a8f8f662b9b0d931d3801b0465097e626d3c5ae8"
_PROXY_URL = f"http://{_ZENROWS_KEY}_render_false:@proxy.zenrows.com:8001"
_PROXIES = {"http": _PROXY_URL, "https": _PROXY_URL}


def _make_pytrends():
    """Inisialisasi TrendReq dengan ZenRows Proxy."""
    return TrendReq(
        hl='id-ID',
        tz=420,
        retries=1,
        backoff_factor=1,
        requests_args={
            'proxies': _PROXIES,
            'timeout': 25,
            'verify': False
        }
    )


def _jitter():
    """Jeda minimal agar tidak terdeteksi bot."""
    time.sleep(random.uniform(1.0, 2.0))


# =========================
# 1. FETCH DATA
# =========================

def fetch_trend_data(keyword, timeframe="today 3-m", geo="ID", cat=0):
    """Ambil data tren 3 bulan (untuk metrik dasar)."""
    try:
        print(f"--- FETCH SHORT ---: {keyword} | {timeframe} | geo={geo}")
        pytrends = _make_pytrends()
        _jitter()
        pytrends.build_payload([keyword], timeframe=timeframe, geo=geo, cat=cat)
        data = pytrends.interest_over_time()

        if data is None or data.empty:
            print(f"--- DATA KOSONG ---: '{keyword}'")
            return None

        if data[keyword].sum() == 0:
            print(f"--- VOLUME NOL ---: '{keyword}'")
            return None

        df = data[[keyword]].reset_index()
        df.columns = ["date", "interest"]
        return df

    except TooManyRequestsError:
        print("--- ERROR 429 ---: Diblokir Google")
        raise
    except Exception as e:
        print(f"--- FETCH ERROR ---: {str(e)}")
        return None


def fetch_trend_data_long(keyword, timeframe="today 12-m", geo="ID", cat=0):
    """
    Ambil data tren 12 bulan — dipakai untuk seasonality detection
    dan sebagai sumber data utama yang dipotong untuk metrik 3 bulan.
    """
    try:
        print(f"--- FETCH LONG ---: {keyword} | {timeframe} | geo={geo}")
        pytrends = _make_pytrends()
        _jitter()
        pytrends.build_payload([keyword], timeframe=timeframe, geo=geo, cat=cat)
        data = pytrends.interest_over_time()

        if data is None or data.empty:
            print(f"--- DATA LONG KOSONG ---: '{keyword}'")
            return None

        if data[keyword].sum() == 0:
            print(f"--- VOLUME LONG NOL ---: '{keyword}'")
            return None

        df = data[[keyword]].reset_index()
        df.columns = ["date", "interest"]
        return df

    except TooManyRequestsError:
        print("--- ERROR 429 (long) ---: Diblokir Google")
        raise
    except Exception as e:
        print(f"--- FETCH LONG ERROR ---: {str(e)}")
        return None


# =========================
# 1b. VALIDASI KEYWORD
# =========================

def validate_keyword(keyword):
    """Validasi format keyword sebelum dikirim ke Google Trends."""
    cleaned = keyword.strip()
    if not cleaned:
        return {"valid": False, "error": "Keyword tidak boleh kosong."}
    alpha_chars = re.findall(r'[a-zA-Z]', cleaned)
    if len(alpha_chars) < 2:
        return {"valid": False, "error": "Keyword terlalu pendek atau tidak valid."}
    return {"valid": True}


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
    return round(float(np.mean(forecast)), 2)


# =========================
# 3. FITUR BARU v2.0
# =========================

def detect_peak(df, growth, momentum):
    values = df["interest"].values
    current = values[-1]
    peak_value = np.max(values)
    near_peak = current >= peak_value * 0.90
    momentum_weakening = momentum < 0.3
    growth_slowing = 0 < growth < 0.15
    return near_peak and (momentum_weakening or growth_slowing)


def compute_fomo_index(df):
    values = df["interest"].values
    if len(values) < 14:
        return 0.0
    short_term_avg = np.mean(values[-7:])
    long_term_avg = np.mean(values[:-7])
    if long_term_avg == 0:
        return 0.0
    ratio = short_term_avg / long_term_avg
    fomo = min((ratio - 1.0) / 1.0, 1.0)
    fomo = max(fomo, 0.0)
    return round(fomo, 3)


def detect_seasonality(df_long):
    if df_long is None or len(df_long) < 30:
        return {"is_seasonal": False, "confidence": 0.0, "peak_months": []}

    df_copy = df_long.copy()
    df_copy["month"] = pd.to_datetime(df_copy["date"]).dt.month
    monthly_avg = df_copy.groupby("month")["interest"].mean()

    if monthly_avg.std() == 0:
        return {"is_seasonal": False, "confidence": 0.0, "peak_months": []}

    cv = monthly_avg.std() / monthly_avg.mean()
    is_seasonal = cv > 0.25
    confidence = round(min(cv / 0.5, 1.0), 2)
    threshold = monthly_avg.mean() + 0.5 * monthly_avg.std()
    peak_months = monthly_avg[monthly_avg >= threshold].index.tolist()

    return {
        "is_seasonal": is_seasonal,
        "confidence": confidence,
        "peak_months": peak_months
    }


def compute_forecast_confidence(df, volatility):
    values = df["interest"].values
    if len(values) < 10:
        return 0.2

    x = np.arange(len(values)).reshape(-1, 1)
    y = values
    model = LinearRegression().fit(x, y)
    y_pred = model.predict(x)

    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)

    r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
    r2 = max(r2, 0)
    vol_penalty = min(volatility, 1.0)
    confidence = (0.6 * r2) + (0.4 * (1 - vol_penalty))
    return round(max(confidence, 0.05), 2)


def compute_entry_timing_score(lifecycle_stage, growth, momentum,
                                fomo_index, saturation, forecast_30d,
                                current_avg, risk_level):
    score = 50.0
    stage_bonus = {
        "Emerging": +20, "Rising": +25, "Peak": -10,
        "Stable": +5, "Declining": -25
    }
    score += stage_bonus.get(lifecycle_stage, 0)

    if growth > 0.3:     score += 15
    elif growth > 0.1:   score += 8
    elif growth < -0.2:  score -= 15
    elif growth < 0:     score -= 5

    if momentum > 0.5:   score += 10
    elif momentum > 0:   score += 5
    elif momentum < -0.5: score -= 10
    else:                score -= 3

    if fomo_index > 0.7:    score -= 15
    elif fomo_index > 0.4:  score -= 7

    if saturation >= 0.7:   score -= 12
    elif saturation >= 0.5: score -= 6

    if current_avg > 0 and forecast_30d > current_avg * 1.1:
        score += 10
    elif forecast_30d < current_avg * 0.9:
        score -= 8

    risk_penalty = {"High Risk": -10, "Medium Risk": -4, "Low Risk": 0}
    score += risk_penalty.get(risk_level, 0)

    return round(max(min(score, 100), 0), 1)


def entry_timing_label(score):
    if score >= 80: return "Waktu Terbaik"
    if score >= 60: return "Bagus, Mulai Persiapan"
    if score >= 40: return "Boleh Masuk, Waspada"
    if score >= 20: return "Tunggu Dulu"
    return "Hindari"


# =========================
# 4. CLASSIFICATION
# =========================

def classify_lifecycle(growth, momentum, is_peak):
    if is_peak:                        return "Peak"
    if growth > 0.2 and momentum > 0:  return "Rising"
    if growth < 0 and momentum < 0:    return "Declining"
    if growth > 0:                     return "Emerging"
    return "Stable"


def compute_risk(volatility, spike, fomo_index):
    if (volatility > 0.5 and spike) or fomo_index > 0.7: return "High Risk"
    if volatility > 0.3 or fomo_index > 0.4:             return "Medium Risk"
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
    score = (0.4 * growth_norm + 0.35 * momentum_norm + 0.25 * stability) * 100
    return round(score, 1)


# =========================
# 6. MASTER FUNCTION (FIXED)
# =========================

def analyze_keyword(keyword, geo="ID", cat=0):
    """
    Analisis lengkap satu keyword. Returns dict dengan semua metrik Sentra v2.0.
    """
    validation = validate_keyword(keyword)
    if not validation["valid"]:
        return {"error": validation["error"]}

    try:
        # Ambil data 12 bulan sekaligus (1 request proxy = lebih hemat & cepat)
        print(f"--- ANALYZE ---: '{keyword}' | geo={geo}")
        df_full = fetch_trend_data_long(keyword, geo=geo, cat=cat)

        if df_full is None or df_full.empty:
            return {
                "error": f"Data untuk '{keyword}' tidak ditemukan. "
                         "Coba keyword yang lebih umum atau cek koneksi proxy.",
                "error_code": "NO_DATA"
            }

        # Potong 90 hari terakhir untuk metrik dasar
        df = df_full.iloc[-90:].copy().reset_index(drop=True)

    except TooManyRequestsError:
        return {
            "error": "Google Trends sedang membatasi permintaan. Coba lagi dalam beberapa menit.",
            "error_code": "TOO_MANY_REQUESTS"
        }
    except Exception as e:
        print(f"--- ANALYZE ERROR ---: {str(e)}")
        return {"error": "Gagal memproses data tren.", "error_code": "ENGINE_ERROR"}

    # ── Metrik dasar ──
    growth     = compute_growth(df)
    momentum   = compute_momentum(df)
    volatility = compute_volatility(df)
    spike      = detect_spike(df)

    # ── Fitur v2.0 ──
    fomo_index    = compute_fomo_index(df)
    is_peak       = detect_peak(df, growth, momentum)
    seasonality   = detect_seasonality(df_full)   # pakai data penuh 12 bulan
    forecast_30   = forecast_next_30_days(df)
    fc_confidence = compute_forecast_confidence(df, volatility)
    saturation    = compute_saturation(df, growth, momentum)

    # ── Klasifikasi ──
    stage       = classify_lifecycle(growth, momentum, is_peak)
    risk        = compute_risk(volatility, spike, fomo_index)
    pulse_score = compute_market_pulse(growth, momentum, volatility)

    # ── Entry Timing ──
    current_avg  = float(df["interest"].iloc[-7:].mean())
    timing_score = compute_entry_timing_score(
        stage, growth, momentum, fomo_index,
        saturation, forecast_30, current_avg, risk
    )
    timing_lbl = entry_timing_label(timing_score)

    # ── Raw trend data untuk chart ──
    raw_trend = {
        "dates":  [str(d)[:10] for d in df["date"].tolist()],
        "values": [int(v) for v in df["interest"].tolist()],
    }

    return {
        # Identitas
        "keyword":              keyword,

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

        # Entry Timing
        "entry_timing_score":   timing_score,
        "entry_timing_label":   timing_lbl,

        # Raw trend untuk chart di frontend
        "raw_trend":            raw_trend,
    }


# =========================
# 7. BENCHMARKING / COMPARE
# =========================

def fetch_comparison_trend(keyword_a, keyword_b, timeframe="today 3-m", geo="ID"):
    try:
        pytrends = _make_pytrends()
        _jitter()
        pytrends.build_payload([keyword_a, keyword_b], timeframe=timeframe, geo=geo)
        data = pytrends.interest_over_time()
        if data is None or data.empty:
            return None
        df = data[[keyword_a, keyword_b]].reset_index()
        return {
            "dates":    [d.strftime("%Y-%m-%d") for d in df["date"]],
            "values_a": df[keyword_a].tolist(),
            "values_b": df[keyword_b].tolist(),
        }
    except Exception as e:
        print(f"--- COMPARE TREND ERROR ---: {str(e)}")
        return None


def compute_comparison_metrics(result_a, result_b):
    def pick_winner(val_a, val_b, kw_a, kw_b, higher_better=True):
        if val_a is None or val_b is None: return "—"
        if higher_better:
            return kw_a if val_a > val_b else kw_b if val_b > val_a else "Seri"
        return kw_a if val_a < val_b else kw_b if val_b < val_a else "Seri"

    kw_a, kw_b = result_a["keyword"], result_b["keyword"]
    comparison = {
        "winner_growth":     pick_winner(result_a["growth"],              result_b["growth"],              kw_a, kw_b),
        "winner_momentum":   pick_winner(result_a["momentum"],            result_b["momentum"],            kw_a, kw_b),
        "winner_stability":  pick_winner(result_a["volatility"],          result_b["volatility"],          kw_a, kw_b, False),
        "winner_pulse":      pick_winner(result_a["market_pulse_score"],  result_b["market_pulse_score"],  kw_a, kw_b),
        "winner_timing":     pick_winner(result_a["entry_timing_score"],  result_b["entry_timing_score"],  kw_a, kw_b),
        "winner_fomo":       pick_winner(result_a["fomo_index"],          result_b["fomo_index"],          kw_a, kw_b, False),
        "winner_saturation": pick_winner(result_a["saturation_index"],    result_b["saturation_index"],    kw_a, kw_b, False),
    }

    score_a = (result_a.get("market_pulse_score") or 0) * 0.4 + (result_a.get("entry_timing_score") or 0) * 0.6
    score_b = (result_b.get("market_pulse_score") or 0) * 0.4 + (result_b.get("entry_timing_score") or 0) * 0.6
    comparison["winner_overall"] = kw_a if score_a > score_b else kw_b if score_b > score_a else "Seri"
    comparison["score_a"] = round(score_a, 1)
    comparison["score_b"] = round(score_b, 1)
    return comparison


def compare_keywords(keyword_a, keyword_b, geo="ID"):
    for kw in [keyword_a, keyword_b]:
        val = validate_keyword(kw)
        if not val["valid"]:
            return {"error": f"Keyword '{kw}': {val['error']}"}

    with ThreadPoolExecutor(max_workers=3) as executor:
        f_a = executor.submit(analyze_keyword, keyword_a, geo)
        f_b = executor.submit(analyze_keyword, keyword_b, geo)
        f_t = executor.submit(fetch_comparison_trend, keyword_a, keyword_b, "today 3-m", geo)
        r_a = f_a.result()
        r_b = f_b.result()
        t_d = f_t.result()

    if "error" in r_a:
        return {"error": f"Keyword '{keyword_a}': {r_a['error']}", "error_code": r_a.get("error_code")}
    if "error" in r_b:
        return {"error": f"Keyword '{keyword_b}': {r_b['error']}", "error_code": r_b.get("error_code")}

    return {
        "keyword_a":  r_a,
        "keyword_b":  r_b,
        "comparison": compute_comparison_metrics(r_a, r_b),
        "trend_data": t_d,
    }
