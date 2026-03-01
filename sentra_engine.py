import re
import time
import random
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from serpapi import GoogleSearch
from dateutil import parser as dateutil_parser

import os
import urllib3
urllib3.disable_warnings()


# -----------------------------------------
# CONFIGURATION
# -----------------------------------------
_FETCH_HARD_TIMEOUT = 60   # detik

# SerpApi key - set env var SERPAPI_KEY di Railway Dashboard untuk override
_SERPAPI_KEY = os.environ.get(
    "SERPAPI_KEY",
    "b23db169b613630723c51a6d01a08225dbf19320b42c031167813baf77531aff"
)


def _jitter():
    """Jeda kecil antar request."""
    time.sleep(random.uniform(0.5, 1.5))

# ─────────────────────────────────────────
# HARD TIMEOUT WRAPPER
# ─────────────────────────────────────────

def _run_with_timeout(fn, *args, timeout=_FETCH_HARD_TIMEOUT, **kwargs):
    """
    Jalankan fn di thread terpisah dengan hard timeout.
    HANYA berfungsi dengan gunicorn sync workers (bukan gevent).
    railway.json harus pakai: --worker-class sync
    """
    with ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(fn, *args, **kwargs)
        try:
            return future.result(timeout=timeout)
        except FuturesTimeoutError:
            raise TimeoutError(
                f"Google Trends tidak merespons setelah {timeout}s."
            )


# ─────────────────────────────────────────
# 1. FETCH DATA
# ─────────────────────────────────────────

def _fetch_inner(keyword, timeframe, geo, cat):
    """
    Fetch data Google Trends via SerpApi.
    Mengembalikan DataFrame dengan kolom: date (datetime), interest (int).
    """
    print(f"[FETCH] '{keyword}' | {timeframe} | geo={geo}")
    _jitter()

    params = {
        "engine":     "google_trends",
        "q":          keyword,
        "date":       timeframe,
        "geo":        geo,
        "cat":        str(cat),
        "data_type":  "TIMESERIES",
        "hl":         "id",
        "tz":         "-420",
        "api_key":    _SERPAPI_KEY,
    }

    try:
        results = GoogleSearch(params).get_dict()
    except Exception as e:
        print(f"[FETCH ERROR] SerpApi exception: {e}")
        return None

    if "error" in results:
        print(f"[FETCH ERROR] SerpApi error: {results['error']}")
        return None

    timeline = (
        results.get("interest_over_time", {})
               .get("timeline_data", [])
    )
    if not timeline:
        print(f"[FETCH] Data kosong untuk '{keyword}'")
        return None

    rows = []
    for item in timeline:
        try:
            # Setiap item: { "date": "Jan 5 – 11, 2025", "values": [{"query":"...","value":72,"extracted_value":72}] }
            date_str = item.get("date", "")
            val = item["values"][0]["extracted_value"]
            rows.append({"date": dateutil_parser.parse(date_str, fuzzy=True), "interest": int(val)})
        except (KeyError, IndexError, ValueError):
            continue

    if not rows:
        print(f"[FETCH] Gagal parse timeline untuk '{keyword}'")
        return None

    df = pd.DataFrame(rows)
    if df["interest"].sum() == 0:
        print(f"[FETCH] Volume nol untuk '{keyword}'")
        return None

    return df


def fetch_trend_data_long(keyword, timeframe="today 12-m", geo="ID", cat=0):
    """Ambil data 12 bulan dengan hard timeout."""
    try:
        return _run_with_timeout(
            _fetch_inner, keyword, timeframe, geo, cat,
            timeout=_FETCH_HARD_TIMEOUT
        )
    except TimeoutError:
        raise
    except Exception as e:
        print(f"[FETCH ERROR] {type(e).__name__}: {e}")
        return None


def fetch_trend_data(keyword, timeframe="today 3-m", geo="ID", cat=0):
    """Ambil data 3 bulan dengan hard timeout."""
    return fetch_trend_data_long(keyword, timeframe=timeframe, geo=geo, cat=cat)


def fetch_regional_data(keyword, geo="ID"):
    """
    Fetch regional interest (GEO_MAP) via SerpApi.
    Mengembalikan list berisi {name, value}.
    """
    def _fetch():
        print(f"[FETCH REGIONAL] '{keyword}' | geo={geo}")
        _jitter()
        params = {
            "engine":     "google_trends",
            "q":          keyword,
            "geo":        geo,
            "data_type":  "GEO_MAP",
            "hl":         "id",
            "api_key":    _SERPAPI_KEY,
        }
        try:
            results = GoogleSearch(params).get_dict()
            if "error" in results: return []
            regions = results.get("interest_by_region", [])
            return [
                {"name": r["name"], "value": int(r.get("extracted_value", 0))} 
                for r in regions if "name" in r
            ]
        except Exception as e:
            print(f"[FETCH REGIONAL ERROR] {e}")
            return []

    try:
        return _run_with_timeout(_fetch, timeout=_FETCH_HARD_TIMEOUT)
    except Exception:
        return []


# ─────────────────────────────────────────
# 1b. VALIDASI KEYWORD
# ─────────────────────────────────────────

def validate_keyword(keyword):
    cleaned = keyword.strip()
    if not cleaned:
        return {"valid": False, "error": "Keyword tidak boleh kosong."}
    if len(re.findall(r'[a-zA-Z\u00C0-\u024F\u0400-\u04FF]', cleaned)) < 2:
        return {"valid": False, "error": "Keyword terlalu pendek atau tidak valid."}
    return {"valid": True}


# ─────────────────────────────────────────
# 2. METRICS DASAR
# ─────────────────────────────────────────

def compute_growth(df):
    recent   = df["interest"].iloc[-7:].mean()
    previous = df["interest"].iloc[-14:-7].mean()
    if previous == 0:
        return 0.0
    return float((recent - previous) / previous)


def compute_momentum(df):
    y = df["interest"].values.astype(float)
    x = np.arange(len(y)).reshape(-1, 1)
    return float(LinearRegression().fit(x, y).coef_[0])


def compute_volatility(df):
    mean = df["interest"].mean()
    if mean == 0:
        return 0.0
    return float(df["interest"].std() / mean)


def detect_spike(df):
    mean = df["interest"].mean()
    std  = df["interest"].std()
    return bool(df["interest"].iloc[-1] > mean + 2 * std)


def compute_saturation(df, growth, momentum):
    m = abs(momentum)
    if growth > 0 and m < 0.1: return 0.8
    if growth > 0 and m < 0.2: return 0.6
    if growth > 0:              return 0.3
    return 0.2


def forecast_next_30_days(df):
    y      = df["interest"].values.astype(float)
    x      = np.arange(len(y)).reshape(-1, 1)
    model  = LinearRegression().fit(x, y)
    future = np.arange(len(y), len(y) + 30).reshape(-1, 1)
    return round(float(np.mean(model.predict(future))), 2)


# ─────────────────────────────────────────
# 3. FITUR v2.0
# ─────────────────────────────────────────

def detect_peak(df, growth, momentum):
    vals    = df["interest"].values
    current = float(vals[-1])
    peak    = float(np.max(vals))
    return (current >= peak * 0.90) and (momentum < 0.3 or (0 < growth < 0.15))


def compute_fomo_index(df):
    vals = df["interest"].values.astype(float)
    if len(vals) < 14:
        return 0.0
    short = np.mean(vals[-7:])
    long_ = np.mean(vals[:-7])
    if long_ == 0:
        return 0.0
    return round(float(max(0.0, min((short / long_ - 1.0), 1.0))), 3)


def detect_seasonality(df_long):
    if df_long is None or len(df_long) < 30:
        return {"is_seasonal": False, "confidence": 0.0, "peak_months": []}
    df_copy = df_long.copy()
    df_copy["month"] = pd.to_datetime(df_copy["date"]).dt.month
    monthly = df_copy.groupby("month")["interest"].mean()
    if monthly.std() == 0:
        return {"is_seasonal": False, "confidence": 0.0, "peak_months": []}
    cv         = float(monthly.std() / monthly.mean())
    confidence = round(min(cv / 0.5, 1.0), 2)
    threshold  = monthly.mean() + 0.5 * monthly.std()
    return {
        "is_seasonal":  cv > 0.25,
        "confidence":   confidence,
        "peak_months":  [int(m) for m in monthly[monthly >= threshold].index.tolist()],
    }


def compute_forecast_confidence(df, volatility):
    vals = df["interest"].values.astype(float)
    if len(vals) < 10:
        return 0.2
    x      = np.arange(len(vals)).reshape(-1, 1)
    model  = LinearRegression().fit(x, vals)
    pred   = model.predict(x)
    ss_res = float(np.sum((vals - pred) ** 2))
    ss_tot = float(np.sum((vals - np.mean(vals)) ** 2))
    r2     = max(0.0, 1.0 - ss_res / ss_tot) if ss_tot != 0 else 0.0
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
    m = float((np.tanh(momentum) + 1) / 2)
    s = 1.0 - min(volatility, 1.0)
    return round((0.4 * g + 0.35 * m + 0.25 * s) * 100, 1)


# ─────────────────────────────────────────
# 6. MASTER FUNCTION
# ─────────────────────────────────────────

def analyze_keyword(keyword, geo="ID", cat=0):
    val = validate_keyword(keyword)
    if not val["valid"]:
        return {"error": val["error"]}

    print(f"[ANALYZE] '{keyword}' | geo={geo} | cat={cat}")

    try:
        df_full = fetch_trend_data_long(keyword, geo=geo, cat=cat)
    except TimeoutError:
        return {
            "error": "SerpApi tidak merespons. Coba lagi dalam 1-2 menit.",
            "error_code": "TIMEOUT",
        }
    except Exception as e:
        print(f"[ANALYZE ERROR] {type(e).__name__}: {e}")
        return {"error": "Gagal memproses data tren.", "error_code": "ENGINE_ERROR"}

    if df_full is None or df_full.empty:
        return {
            "error": (
                f"Data untuk '{keyword}' tidak ditemukan. "
                "Coba keyword yang lebih umum atau berbahasa Indonesia."
            ),
            "error_code": "NO_DATA",
        }

    df = df_full.iloc[-90:].copy().reset_index(drop=True)

    growth        = compute_growth(df)
    momentum      = compute_momentum(df)
    volatility    = compute_volatility(df)
    spike         = detect_spike(df)
    fomo_index    = compute_fomo_index(df)
    is_peak       = detect_peak(df, growth, momentum)
    seasonality   = detect_seasonality(df_full)
    forecast_30   = forecast_next_30_days(df)
    fc_confidence = compute_forecast_confidence(df, volatility)
    saturation    = compute_saturation(df, growth, momentum)

    stage        = classify_lifecycle(growth, momentum, is_peak)
    risk         = compute_risk(volatility, spike, fomo_index)
    pulse_score  = compute_market_pulse(growth, momentum, volatility)
    current_avg  = float(df["interest"].iloc[-7:].mean())
    timing_score = compute_entry_timing_score(
        stage, growth, momentum, fomo_index,
        saturation, forecast_30, current_avg, risk
    )
    timing_lbl = entry_timing_label(timing_score)

    raw_trend = {
        "dates":  [str(d)[:10] for d in df["date"].tolist()],
        "values": [int(v) for v in df["interest"].tolist()],
    }

    return {
        "keyword":              keyword,
        "growth":               round(growth, 3),
        "momentum":             round(momentum, 3),
        "volatility":           round(volatility, 3),
        "lifecycle_stage":      stage,
        "risk_level":           risk,
        "market_pulse_score":   pulse_score,
        "saturation_index":     saturation,
        "fomo_index":           fomo_index,
        "forecast_30d_avg":     forecast_30,
        "forecast_confidence":  fc_confidence,
        "is_seasonal":          seasonality["is_seasonal"],
        "seasonal_confidence":  seasonality["confidence"],
        "seasonal_peak_months": seasonality["peak_months"],
        "entry_timing_score":   timing_score,
        "entry_timing_label":   timing_lbl,
        "raw_trend":            raw_trend,
    }


# ─────────────────────────────────────────
# 7. BENCHMARKING / COMPARE
# ─────────────────────────────────────────

def _fetch_comparison_inner(keyword_a, keyword_b, timeframe, geo):
    """
    Fetch data perbandingan 2 keyword via SerpApi (satu call, lebih efisien).
    Mengembalikan dict: {dates, values_a, values_b}.
    """
    _jitter()
    params = {
        "engine":    "google_trends",
        "q":         f"{keyword_a},{keyword_b}",
        "date":      timeframe,
        "geo":       geo,
        "data_type": "TIMESERIES",
        "hl":        "id",
        "tz":        "-420",
        "api_key":   _SERPAPI_KEY,
    }

    try:
        results = GoogleSearch(params).get_dict()
    except Exception as e:
        print(f"[COMPARE FETCH ERROR] SerpApi exception: {e}")
        return None

    if "error" in results:
        print(f"[COMPARE FETCH ERROR] SerpApi error: {results['error']}")
        return None

    timeline = (
        results.get("interest_over_time", {})
               .get("timeline_data", [])
    )
    if not timeline:
        return None

    dates, vals_a, vals_b = [], [], []
    for item in timeline:
        try:
            dates.append(item["date"][:10])  # ambil tanggal awal periode
            # SerpApi mengembalikan values[] berurutan sesuai q= (koma-separated)
            vals_a.append(int(item["values"][0]["extracted_value"]))
            vals_b.append(int(item["values"][1]["extracted_value"]))
        except (KeyError, IndexError, ValueError):
            continue

    if not dates:
        return None

    return {"dates": dates, "values_a": vals_a, "values_b": vals_b}


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

    # Sequential (bukan parallel) untuk menghindari rate limit Google
    ra = analyze_keyword(keyword_a, geo)
    if "error" in ra:
        return {"error": f"Keyword '{keyword_a}': {ra['error']}", "error_code": ra.get("error_code")}

    time.sleep(random.uniform(2.0, 4.0))  # jeda antar request

    rb = analyze_keyword(keyword_b, geo)
    if "error" in rb:
        return {"error": f"Keyword '{keyword_b}': {rb['error']}", "error_code": rb.get("error_code")}

    time.sleep(random.uniform(1.5, 2.5))

    td = fetch_comparison_trend(keyword_a, keyword_b, "today 3-m", geo)

    return {
        "keyword_a":  ra,
        "keyword_b":  rb,
        "comparison": compute_comparison_metrics(ra, rb),
        "trend_data": td,
    }
