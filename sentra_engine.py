import re
import time
import random
import requests
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pytrends.request import TrendReq
from pytrends.exceptions import TooManyRequestsError

# ─────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────
_ZENROWS_KEY = "a8f8f662b9b0d931d3801b0465097e626d3c5ae8"
_PROXY_URL   = f"http://{_ZENROWS_KEY}_render_false:@proxy.zenrows.com:8001"
_PROXIES     = {"http": _PROXY_URL, "https": _PROXY_URL}

# Hard timeout untuk satu request proxy ke Google Trends
# Frontend timeout = 90s, gunicorn = 120s → set 55s supaya ada ruang error handling
_FETCH_HARD_TIMEOUT = 55  # detik


def _make_pytrends():
    """
    Buat TrendReq dengan session yang sudah dikonfigurasi timeout.
    Cara ini memastikan timeout benar-benar dihormati oleh requests session internal pytrends.
    """
    session = requests.Session()
    session.proxies.update(_PROXIES)
    session.verify = False
    # Mount adapter dengan timeout di level adapter
    adapter = requests.adapters.HTTPAdapter(max_retries=1)
    session.mount("http://",  adapter)
    session.mount("https://", adapter)

    pt = TrendReq(
        hl='id-ID',
        tz=420,
        retries=1,
        backoff_factor=0.5,
        requests_args={
            'proxies': _PROXIES,
            'timeout': (10, 30),  # (connect_timeout, read_timeout)
            'verify':  False,
        }
    )
    return pt


def _jitter():
    """Jeda kecil agar tidak langsung diblokir Google."""
    time.sleep(random.uniform(0.5, 1.5))


# ─────────────────────────────────────────
# HARD TIMEOUT WRAPPER
# ─────────────────────────────────────────

def _run_with_timeout(fn, *args, timeout=_FETCH_HARD_TIMEOUT, **kwargs):
    """
    Jalankan fn(*args, **kwargs) di thread terpisah dengan hard timeout.
    Jika tidak selesai dalam `timeout` detik, raise TimeoutError.

    Ini solusi utama untuk mencegah gunicorn WORKER TIMEOUT:
    proxy ZenRows kadang hang tanpa response → thread dibiarkan mati,
    worker utama langsung return error daripada ikut hang.
    """
    with ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(fn, *args, **kwargs)
        try:
            return future.result(timeout=timeout)
        except FuturesTimeoutError:
            raise TimeoutError(
                f"Request ke Google Trends timeout setelah {timeout}s. "
                "Proxy ZenRows tidak merespons."
            )


# ─────────────────────────────────────────
# 1. FETCH DATA
# ─────────────────────────────────────────

def _fetch_long_inner(keyword, timeframe, geo, cat):
    """Inner function — dijalankan di thread dengan hard timeout."""
    print(f"[FETCH] '{keyword}' | {timeframe} | geo={geo} | cat={cat}")
    pt = _make_pytrends()
    _jitter()
    pt.build_payload([keyword], timeframe=timeframe, geo=geo, cat=cat)
    data = pt.interest_over_time()

    if data is None or data.empty:
        print(f"[FETCH] Data kosong untuk '{keyword}'")
        return None

    if data[keyword].sum() == 0:
        print(f"[FETCH] Volume nol untuk '{keyword}'")
        return None

    df = data[[keyword]].reset_index()
    df.columns = ["date", "interest"]
    return df


def fetch_trend_data_long(keyword, timeframe="today 12-m", geo="ID", cat=0):
    """
    Ambil data 12 bulan dari Google Trends via ZenRows proxy.
    Dibungkus hard timeout sehingga tidak pernah hang > _FETCH_HARD_TIMEOUT detik.
    """
    try:
        return _run_with_timeout(
            _fetch_long_inner, keyword, timeframe, geo, cat,
            timeout=_FETCH_HARD_TIMEOUT
        )
    except TimeoutError as e:
        print(f"[TIMEOUT] {e}")
        raise  # biarkan analyze_keyword tangkap
    except TooManyRequestsError:
        print("[429] Google Trends membatasi request")
        raise
    except Exception as e:
        print(f"[FETCH ERROR] {type(e).__name__}: {e}")
        return None


def _fetch_short_inner(keyword, timeframe, geo, cat):
    """Inner function untuk fetch 3 bulan."""
    print(f"[FETCH SHORT] '{keyword}' | {timeframe} | geo={geo}")
    pt = _make_pytrends()
    _jitter()
    pt.build_payload([keyword], timeframe=timeframe, geo=geo, cat=cat)
    data = pt.interest_over_time()

    if data is None or data.empty:
        return None
    if data[keyword].sum() == 0:
        return None

    df = data[[keyword]].reset_index()
    df.columns = ["date", "interest"]
    return df


def fetch_trend_data(keyword, timeframe="today 3-m", geo="ID", cat=0):
    """Ambil data 3 bulan dengan hard timeout."""
    try:
        return _run_with_timeout(
            _fetch_short_inner, keyword, timeframe, geo, cat,
            timeout=_FETCH_HARD_TIMEOUT
        )
    except TimeoutError as e:
        print(f"[TIMEOUT SHORT] {e}")
        raise
    except TooManyRequestsError:
        raise
    except Exception as e:
        print(f"[FETCH SHORT ERROR] {type(e).__name__}: {e}")
        return None


# ─────────────────────────────────────────
# 1b. VALIDASI KEYWORD
# ─────────────────────────────────────────

def validate_keyword(keyword):
    cleaned = keyword.strip()
    if not cleaned:
        return {"valid": False, "error": "Keyword tidak boleh kosong."}
    if len(re.findall(r'[a-zA-Z]', cleaned)) < 2:
        return {"valid": False, "error": "Keyword terlalu pendek atau tidak valid."}
    return {"valid": True}


# ─────────────────────────────────────────
# 2. METRICS DASAR
# ─────────────────────────────────────────

def compute_growth(df):
    recent   = df["interest"].iloc[-7:].mean()
    previous = df["interest"].iloc[-14:-7].mean()
    if previous == 0:
        return 0
    return (recent - previous) / previous


def compute_momentum(df):
    y = df["interest"].values
    x = np.arange(len(y)).reshape(-1, 1)
    return LinearRegression().fit(x, y).coef_[0]


def compute_volatility(df):
    mean = df["interest"].mean()
    if mean == 0:
        return 0
    return df["interest"].std() / mean


def detect_spike(df):
    mean = df["interest"].mean()
    std  = df["interest"].std()
    return df["interest"].iloc[-1] > mean + 2 * std


def compute_saturation(df, growth, momentum):
    m = abs(momentum)
    if growth > 0 and m < 0.1: return 0.8
    if growth > 0 and m < 0.2: return 0.6
    if growth > 0:              return 0.3
    return 0.2


def forecast_next_30_days(df):
    y       = df["interest"].values
    x       = np.arange(len(y)).reshape(-1, 1)
    model   = LinearRegression().fit(x, y)
    future  = np.arange(len(y), len(y) + 30).reshape(-1, 1)
    return round(float(np.mean(model.predict(future))), 2)


# ─────────────────────────────────────────
# 3. FITUR v2.0
# ─────────────────────────────────────────

def detect_peak(df, growth, momentum):
    vals    = df["interest"].values
    current = vals[-1]
    peak    = np.max(vals)
    return (current >= peak * 0.90) and (momentum < 0.3 or (0 < growth < 0.15))


def compute_fomo_index(df):
    vals = df["interest"].values
    if len(vals) < 14:
        return 0.0
    short = np.mean(vals[-7:])
    long_ = np.mean(vals[:-7])
    if long_ == 0:
        return 0.0
    return round(max(0.0, min((short / long_ - 1.0) / 1.0, 1.0)), 3)


def detect_seasonality(df_long):
    if df_long is None or len(df_long) < 30:
        return {"is_seasonal": False, "confidence": 0.0, "peak_months": []}
    df_copy = df_long.copy()
    df_copy["month"] = pd.to_datetime(df_copy["date"]).dt.month
    monthly = df_copy.groupby("month")["interest"].mean()
    if monthly.std() == 0:
        return {"is_seasonal": False, "confidence": 0.0, "peak_months": []}
    cv         = monthly.std() / monthly.mean()
    confidence = round(min(cv / 0.5, 1.0), 2)
    threshold  = monthly.mean() + 0.5 * monthly.std()
    return {
        "is_seasonal":  cv > 0.25,
        "confidence":   confidence,
        "peak_months":  monthly[monthly >= threshold].index.tolist(),
    }


def compute_forecast_confidence(df, volatility):
    vals = df["interest"].values
    if len(vals) < 10:
        return 0.2
    x     = np.arange(len(vals)).reshape(-1, 1)
    model = LinearRegression().fit(x, vals)
    pred  = model.predict(x)
    ss_res = np.sum((vals - pred) ** 2)
    ss_tot = np.sum((vals - np.mean(vals)) ** 2)
    r2    = max(0, 1 - ss_res / ss_tot) if ss_tot != 0 else 0
    return round(max(0.6 * r2 + 0.4 * (1 - min(volatility, 1.0)), 0.05), 2)


def compute_entry_timing_score(lifecycle_stage, growth, momentum,
                                fomo_index, saturation, forecast_30d,
                                current_avg, risk_level):
    score = 50.0
    score += {"Emerging": +20, "Rising": +25, "Peak": -10,
              "Stable": +5, "Declining": -25}.get(lifecycle_stage, 0)

    if   growth >  0.3: score += 15
    elif growth >  0.1: score += 8
    elif growth < -0.2: score -= 15
    elif growth <  0:   score -= 5

    if   momentum >  0.5: score += 10
    elif momentum >  0:   score += 5
    elif momentum < -0.5: score -= 10
    else:                 score -= 3

    if   fomo_index > 0.7: score -= 15
    elif fomo_index > 0.4: score -= 7

    if   saturation >= 0.7: score -= 12
    elif saturation >= 0.5: score -= 6

    if current_avg > 0:
        if   forecast_30d > current_avg * 1.1: score += 10
        elif forecast_30d < current_avg * 0.9: score -= 8

    score += {"High Risk": -10, "Medium Risk": -4, "Low Risk": 0}.get(risk_level, 0)
    return round(max(min(score, 100), 0), 1)


def entry_timing_label(score):
    if score >= 80: return "Waktu Terbaik"
    if score >= 60: return "Bagus, Mulai Persiapan"
    if score >= 40: return "Boleh Masuk, Waspada"
    if score >= 20: return "Tunggu Dulu"
    return "Hindari"


# ─────────────────────────────────────────
# 4. CLASSIFICATION
# ─────────────────────────────────────────

def classify_lifecycle(growth, momentum, is_peak):
    if is_peak:                        return "Peak"
    if growth > 0.2 and momentum > 0:  return "Rising"
    if growth < 0   and momentum < 0:  return "Declining"
    if growth > 0:                     return "Emerging"
    return "Stable"


def compute_risk(volatility, spike, fomo_index):
    if (volatility > 0.5 and spike) or fomo_index > 0.7: return "High Risk"
    if volatility > 0.3 or fomo_index > 0.4:             return "Medium Risk"
    return "Low Risk"


# ─────────────────────────────────────────
# 5. MARKET PULSE SCORE
# ─────────────────────────────────────────

def compute_market_pulse(growth, momentum, volatility):
    g = (max(min(growth, 0.5), -0.5) + 0.5)
    m = (np.tanh(momentum) + 1) / 2
    s = 1 - min(volatility, 1)
    return round((0.4 * g + 0.35 * m + 0.25 * s) * 100, 1)


# ─────────────────────────────────────────
# 6. MASTER FUNCTION
# ─────────────────────────────────────────

def analyze_keyword(keyword, geo="ID", cat=0):
    """
    Analisis lengkap satu keyword. Returns dict dengan semua metrik Sentra v2.0.

    Error handling:
    - TimeoutError  → proxy ZenRows hang → return error_code TIMEOUT
    - TooManyRequestsError → 429 Google → return error_code TOO_MANY_REQUESTS
    - No data       → keyword tidak ada di Google Trends → return error_code NO_DATA
    """
    val = validate_keyword(keyword)
    if not val["valid"]:
        return {"error": val["error"]}

    print(f"[ANALYZE] '{keyword}' | geo={geo} | cat={cat}")

    try:
        # Satu request untuk data 12 bulan (lebih hemat vs 2 request)
        df_full = fetch_trend_data_long(keyword, geo=geo, cat=cat)

    except TimeoutError:
        return {
            "error": (
                "Koneksi ke Google Trends timeout. "
                "Server proxy sedang lambat, coba lagi dalam 1-2 menit."
            ),
            "error_code": "TIMEOUT",
        }
    except TooManyRequestsError:
        return {
            "error": "Google Trends membatasi permintaan. Coba lagi dalam beberapa menit.",
            "error_code": "TOO_MANY_REQUESTS",
        }
    except Exception as e:
        print(f"[ANALYZE ERROR] {type(e).__name__}: {e}")
        return {"error": "Gagal memproses data tren.", "error_code": "ENGINE_ERROR"}

    if df_full is None or df_full.empty:
        return {
            "error": (
                f"Data untuk '{keyword}' tidak ditemukan di Google Trends. "
                "Coba keyword yang lebih umum atau berbahasa Indonesia."
            ),
            "error_code": "NO_DATA",
        }

    # Potong 90 hari terakhir untuk metrik dasar
    df = df_full.iloc[-90:].copy().reset_index(drop=True)

    # ── Metrik ──
    growth     = compute_growth(df)
    momentum   = compute_momentum(df)
    volatility = compute_volatility(df)
    spike      = detect_spike(df)
    fomo_index = compute_fomo_index(df)
    is_peak    = detect_peak(df, growth, momentum)
    seasonality   = detect_seasonality(df_full)
    forecast_30   = forecast_next_30_days(df)
    fc_confidence = compute_forecast_confidence(df, volatility)
    saturation    = compute_saturation(df, growth, momentum)

    stage       = classify_lifecycle(growth, momentum, is_peak)
    risk        = compute_risk(volatility, spike, fomo_index)
    pulse_score = compute_market_pulse(growth, momentum, volatility)
    current_avg = float(df["interest"].iloc[-7:].mean())
    timing_score = compute_entry_timing_score(
        stage, growth, momentum, fomo_index,
        saturation, forecast_30, current_avg, risk
    )
    timing_lbl = entry_timing_label(timing_score)

    # Raw trend untuk chart
    raw_trend = {
        "dates":  [str(d)[:10] for d in df["date"].tolist()],
        "values": [int(v) for v in df["interest"].tolist()],
    }

    return {
        "keyword":               keyword,
        "growth":                round(float(growth), 3),
        "momentum":              round(float(momentum), 3),
        "volatility":            round(float(volatility), 3),
        "lifecycle_stage":       stage,
        "risk_level":            risk,
        "market_pulse_score":    pulse_score,
        "saturation_index":      saturation,
        "fomo_index":            fomo_index,
        "forecast_30d_avg":      forecast_30,
        "forecast_confidence":   fc_confidence,
        "is_seasonal":           seasonality["is_seasonal"],
        "seasonal_confidence":   seasonality["confidence"],
        "seasonal_peak_months":  seasonality["peak_months"],
        "entry_timing_score":    timing_score,
        "entry_timing_label":    timing_lbl,
        "raw_trend":             raw_trend,
    }


# ─────────────────────────────────────────
# 7. BENCHMARKING / COMPARE
# ─────────────────────────────────────────

def _fetch_comparison_inner(keyword_a, keyword_b, timeframe, geo):
    pt = _make_pytrends()
    _jitter()
    pt.build_payload([keyword_a, keyword_b], timeframe=timeframe, geo=geo)
    data = pt.interest_over_time()
    if data is None or data.empty:
        return None
    df = data[[keyword_a, keyword_b]].reset_index()
    return {
        "dates":    [d.strftime("%Y-%m-%d") for d in df["date"]],
        "values_a": df[keyword_a].tolist(),
        "values_b": df[keyword_b].tolist(),
    }


def fetch_comparison_trend(keyword_a, keyword_b, timeframe="today 3-m", geo="ID"):
    try:
        return _run_with_timeout(
            _fetch_comparison_inner, keyword_a, keyword_b, timeframe, geo,
            timeout=_FETCH_HARD_TIMEOUT
        )
    except Exception as e:
        print(f"[COMPARE TREND ERROR] {e}")
        return None


def compute_comparison_metrics(result_a, result_b):
    def pick(va, vb, ka, kb, hi=True):
        if va is None or vb is None: return "—"
        if hi:  return ka if va > vb else kb if vb > va else "Seri"
        return ka if va < vb else kb if vb < va else "Seri"

    ka, kb = result_a["keyword"], result_b["keyword"]
    c = {
        "winner_growth":     pick(result_a["growth"],             result_b["growth"],             ka, kb),
        "winner_momentum":   pick(result_a["momentum"],           result_b["momentum"],           ka, kb),
        "winner_stability":  pick(result_a["volatility"],         result_b["volatility"],         ka, kb, False),
        "winner_pulse":      pick(result_a["market_pulse_score"], result_b["market_pulse_score"], ka, kb),
        "winner_timing":     pick(result_a["entry_timing_score"], result_b["entry_timing_score"], ka, kb),
        "winner_fomo":       pick(result_a["fomo_index"],         result_b["fomo_index"],         ka, kb, False),
        "winner_saturation": pick(result_a["saturation_index"],   result_b["saturation_index"],   ka, kb, False),
    }
    sa = (result_a.get("market_pulse_score") or 0) * 0.4 + (result_a.get("entry_timing_score") or 0) * 0.6
    sb = (result_b.get("market_pulse_score") or 0) * 0.4 + (result_b.get("entry_timing_score") or 0) * 0.6
    c["winner_overall"] = ka if sa > sb else kb if sb > sa else "Seri"
    c["score_a"] = round(sa, 1)
    c["score_b"] = round(sb, 1)
    return c


def compare_keywords(keyword_a, keyword_b, geo="ID"):
    for kw in [keyword_a, keyword_b]:
        v = validate_keyword(kw)
        if not v["valid"]:
            return {"error": f"Keyword '{kw}': {v['error']}"}

    with ThreadPoolExecutor(max_workers=3) as ex:
        fa = ex.submit(analyze_keyword, keyword_a, geo)
        fb = ex.submit(analyze_keyword, keyword_b, geo)
        ft = ex.submit(fetch_comparison_trend, keyword_a, keyword_b, "today 3-m", geo)
        ra, rb, td = fa.result(), fb.result(), ft.result()

    if "error" in ra:
        return {"error": f"Keyword '{keyword_a}': {ra['error']}", "error_code": ra.get("error_code")}
    if "error" in rb:
        return {"error": f"Keyword '{keyword_b}': {rb['error']}", "error_code": rb.get("error_code")}

    return {
        "keyword_a":  ra,
        "keyword_b":  rb,
        "comparison": compute_comparison_metrics(ra, rb),
        "trend_data": td,
    }
