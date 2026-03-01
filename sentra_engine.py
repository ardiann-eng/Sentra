import re
import time
import random
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from concurrent.futures import ThreadPoolExecutor
from pytrends.request import TrendReq
from pytrends.exceptions import TooManyRequestsError

# --- CONFIGURATION (OPTIMIZED FOR SPEED) ---
_ZENROWS_KEY = "a8f8f662b9b0d931d3801b0465097e626d3c5ae8"
# OPTIMIZED: ZenRows parameter format for faster connection (render=false)
_PROXY_URL = f"http://{_ZENROWS_KEY}_render_false:@proxy.zenrows.com:8001"
_PROXIES = {"http": _PROXY_URL, "https": _PROXY_URL}

def _make_pytrends():
    """Inisialisasi TrendReq dengan ZenRows Proxy yang dioptimasi."""
    return TrendReq(
        hl='id-ID',
        tz=420,
        retries=1, 
        backoff_factor=1,
        requests_args={
            'proxies': _PROXIES,
            'timeout': 20, # Reduced to 20s for faster failover/retries
            'verify': False
        }
    )

def _jitter():
    """Jeda minimal agar tidak terdeteksi bot (1-2 detik)."""
    time.sleep(random.uniform(1.0, 2.0))

# =========================
# 1. FETCH DATA (DENGAN DEBUG LOGS)
# =========================

def fetch_trend_data(keyword, timeframe="today 3-m", geo="ID", cat=0):
    try:
        print(f"--- DEBUG ZENROWS ---: Menghubungi Google untuk {keyword}")
        pytrends = _make_pytrends()
        _jitter()
        pytrends.build_payload([keyword], timeframe=timeframe, geo=geo, cat=cat)
        data = pytrends.interest_over_time()
        
        if data is None or data.empty:
            print(f"--- DEBUG SENTRA ---: Google memberikan data KOSONG untuk '{keyword}'")
            return None
        
        # Validasi jika data ada tapi volumenya 0 semua
        if data[keyword].sum() == 0:
            print(f"--- DEBUG SENTRA ---: Volume pencarian '{keyword}' terlalu rendah (0)")
            return None
        
        df = data[[keyword]].reset_index()
        df.columns = ["date", "interest"]
        return df
    except TooManyRequestsError:
        print("--- DEBUG SENTRA ---: ERROR 429 - Terdeteksi blokir oleh Google (Butuh Proxy)")
        raise
    except Exception as e:
        print(f"--- DEBUG SENTRA ERROR ---: {str(e)}")
        return None

# =========================
# 1b. VALIDASI KEYWORD
# =========================

def validate_keyword(keyword):
    """
    Validasi format keyword sebelum dikirim ke Google Trends.
    """
    cleaned = keyword.strip()

    if not cleaned:
        return {"valid": False, "error": "Keyword tidak boleh kosong."}

    # Minimal harus ada 2 huruf alfabet
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

    avg_forecast = np.mean(forecast)

    return round(float(avg_forecast), 2)


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
    long_term_avg  = np.mean(values[:-7])   

    if long_term_avg == 0:
        return 0.0

    ratio = short_term_avg / long_term_avg
    fomo = min((ratio - 1.0) / 1.0, 1.0)
    fomo = max(fomo, 0.0)

    return round(fomo, 3)


def detect_seasonality(df_long):
    if df_long is None or len(df_long) < 30:
        return {"is_seasonal": False, "confidence": 0.0, "peak_months": []}

    df_long = df_long.copy()
    df_long["month"] = pd.to_datetime(df_long["date"]).dt.month
    monthly_avg = df_long.groupby("month")["interest"].mean()

    if monthly_avg.std() == 0:
        return {"is_seasonal": False, "confidence": 0.0, "peak_months": []}

    cv = monthly_avg.std() / monthly_avg.mean()
    is_seasonal = cv > 0.25
    confidence  = round(min(cv / 0.5, 1.0), 2)  

    threshold   = monthly_avg.mean() + 0.5 * monthly_avg.std()
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
    stage_bonus = {"Emerging": +20, "Rising": +25, "Peak": -10, "Stable": +5, "Declining": -25}
    score += stage_bonus.get(lifecycle_stage, 0)

    if growth > 0.3: score += 15
    elif growth > 0.1: score += 8
    elif growth < -0.2: score -= 15

    if momentum > 0.5: score += 10
    elif momentum < -0.5: score -= 10

    if fomo_index > 0.7: score -= 15
    if saturation >= 0.7: score -= 12

    if current_avg > 0 and forecast_30d > current_avg * 1.1: score += 10
    
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
    if is_peak: return "Peak"
    if growth > 0.2 and momentum > 0: return "Rising"
    if growth < 0 and momentum < 0: return "Declining"
    if growth > 0: return "Emerging"
    return "Stable"


def compute_risk(volatility, spike, fomo_index):
    if (volatility > 0.5 and spike) or fomo_index > 0.7: return "High Risk"
    if volatility > 0.3 or fomo_index > 0.4: return "Medium Risk"
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
# 6. MASTER FUNCTION
# =========================

# --- Di dalam sentra_engine.py ---

def analyze_keyword(keyword, geo="ID", cat=0):
    validation = validate_keyword(keyword)
    if not validation["valid"]: return {"error": validation["error"]}

    try:
        # LANGKAH KRUSIAL: Hanya satu kali panggil proxy untuk efisiensi RAM/Waktu
        print(f"--- DEBUG ZENROWS ---: Menghubungi Google (Full Data) untuk {keyword}")
        df_full = fetch_trend_data_long(keyword, geo=geo) 
        
        if df_full is None or df_full.empty:
            return {"error": "Data tidak ditemukan atau IP diblokir."}

        # Potong data di memori untuk keperluan metrik 3 bulan terakhir
        df = df_full.iloc[-90:].copy() 
        
    except Exception as e:
        print(f"Error proses data: {e}")
        return {"error": "Gagal memproses data tren."}

    # Gunakan 'df' untuk metrik dasar dan 'df_full' untuk seasonality
    growth     = compute_growth(df)
    momentum   = compute_momentum(df)
    volatility = compute_volatility(df)


# =========================
# 7. BENCHMARKING / COMPARE
# =========================

def fetch_comparison_trend(keyword_a, keyword_b, timeframe="today 3-m", geo="ID"):
    try:
        pytrends = _make_pytrends()
        pytrends.build_payload([keyword_a, keyword_b], timeframe=timeframe, geo=geo)
        data = pytrends.interest_over_time()
        if data.empty: return None
        df = data[[keyword_a, keyword_b]].reset_index()
        return {
            "dates": [d.strftime("%Y-%m-%d") for d in df["date"]],
            "values_a": df[keyword_a].tolist(),
            "values_b": df[keyword_b].tolist()
        }
    except Exception: return None


def compute_comparison_metrics(result_a, result_b):
    def pick_winner(val_a, val_b, kw_a, kw_b, higher_better=True):
        if val_a is None or val_b is None: return "—"
        if higher_better: return kw_a if val_a > val_b else kw_b if val_b > val_a else "Seri"
        return kw_a if val_a < val_b else kw_b if val_b < val_a else "Seri"

    kw_a, kw_b = result_a["keyword"], result_b["keyword"]
    comparison = {
        "winner_growth":      pick_winner(result_a["growth"], result_b["growth"], kw_a, kw_b),
        "winner_momentum":    pick_winner(result_a["momentum"], result_b["momentum"], kw_a, kw_b),
        "winner_stability":   pick_winner(result_a["volatility"], result_b["volatility"], kw_a, kw_b, False),
        "winner_pulse":       pick_winner(result_a["market_pulse_score"], result_b["market_pulse_score"], kw_a, kw_b),
        "winner_timing":      pick_winner(result_a["entry_timing_score"], result_b["entry_timing_score"], kw_a, kw_b),
        "winner_fomo":        pick_winner(result_a["fomo_index"], result_b["fomo_index"], kw_a, kw_b, False),
        "winner_saturation":  pick_winner(result_a["saturation_index"],   result_b["saturation_index"],   kw_a, kw_b, False),
    }

    score_a = (result_a.get("market_pulse_score") or 0) * 0.4 + (result_a.get("entry_timing_score") or 0) * 0.6
    score_b = (result_b.get("market_pulse_score") or 0) * 0.4 + (result_b.get("entry_timing_score") or 0) * 0.6
    comparison["winner_overall"] = kw_a if score_a > score_b else kw_b if score_b > score_a else "Seri"
    comparison["score_a"], comparison["score_b"] = round(score_a, 1), round(score_b, 1)
    return comparison


def compare_keywords(keyword_a, keyword_b, geo="ID"):
    for kw in [keyword_a, keyword_b]:
        val = validate_keyword(kw)
        if not val["valid"]: return {"error": f"Keyword '{kw}': {val['error']}"}

    with ThreadPoolExecutor(max_workers=3) as executor:
        f_a = executor.submit(analyze_keyword, keyword_a, geo)
        f_b = executor.submit(analyze_keyword, keyword_b, geo)
        f_t = executor.submit(fetch_comparison_trend, keyword_a, keyword_b, "today 3-m", geo)
        r_a, r_b, t_d = f_a.result(), f_b.result(), f_t.result()

    if "error" in r_a: return {"error": f"Keyword '{keyword_a}': {r_a['error']}"}
    if "error" in r_b: return {"error": f"Keyword '{keyword_b}': {r_b['error']}"}
    return {"keyword_a": r_a, "keyword_b": r_b, "comparison": compute_comparison_metrics(r_a, r_b), "trend_data": t_d}
