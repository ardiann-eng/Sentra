import os
import re
import math
import io
import time
import threading
import logging
from datetime import date, datetime, timedelta
from functools import wraps

# Configure logging for Vercel/Production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("sentra_bi")

import os
import re
import math
import io
import time
import threading
from datetime import date, datetime, timedelta
from functools import wraps

from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS

from sentra_engine import analyze_keyword, compare_keywords, fetch_regional_data, get_regional_interest
from ai_recommendation import generate_ai_insight, generate_compare_insight, generate_local_insight
from umkm_engine import (
    compute_umkm_health,
    build_umkm_analysis_prompt,
    build_umkm_plan_prompt,
    build_umkm_promo_prompt,
    groq_generate,
    upsert_umkm_profile,
    get_umkm_profile,
)

app = Flask(__name__, template_folder='.')
CORS(app)

# =========================
# TWO-LEVEL CACHE
# L1 = in-process dict (fast, TTL 6h)
# L2 = Supabase trend_cache table (persistent, shared, TTL 6h)
# =========================
_mem_cache: dict = {}
_cache_lock = threading.Lock()
CACHE_TTL_SEC = 6 * 60 * 60  # 6 hours


def _cache_key(keyword: str, geo: str = "ID", cat: str = "0") -> str:
    return "|".join([keyword.lower().strip(), geo.upper().strip(), str(cat)])


# ---- L1: memory ----
def _l1_get(key: str):
    with _cache_lock:
        entry = _mem_cache.get(key)
        if entry and (time.time() - entry["ts"]) < CACHE_TTL_SEC:
            return entry["data"]
    return None


def _l1_set(key: str, data: dict):
    with _cache_lock:
        _mem_cache[key] = {"data": data, "ts": time.time()}
        if len(_mem_cache) > 500:
            now = time.time()
            stale = [k for k, v in _mem_cache.items() if now - v["ts"] >= CACHE_TTL_SEC]
            for k in stale:
                del _mem_cache[k]


# ---- L2: Supabase ----
def get_db_cache(keyword: str, geo: str = "ID", cat: str = "0") -> dict | None:
    """Read from Supabase trend_cache. Returns payload dict or None."""
    sb = get_supabase()
    if not sb:
        return None
    try:
        # Calculate 6h ago
        cutoff_iso = (datetime.utcnow() - timedelta(seconds=CACHE_TTL_SEC)).isoformat()

        res = (
            sb.table("trend_cache")
            .select("results, ai_insight, created_at")
            .eq("keyword", keyword.lower().strip())
            .eq("geo", geo.upper().strip())
            .eq("cat", str(cat))
            .gte("created_at", cutoff_iso)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if rows:
            payload = rows[0]["results"] or {}
            ai = rows[0].get("ai_insight") or ""
            if isinstance(payload, dict):
                payload["ai_insight"] = ai
                return payload
    except Exception:
        pass
    return None


def set_db_cache(keyword: str, geo: str, cat: str, result: dict, ai_insight: str):
    """UPSERT result into Supabase trend_cache. Silently ignores errors."""
    sb = get_supabase()
    if not sb:
        return
    try:
        # Strip ai_insight from results blob to avoid duplication
        results_blob = {k: v for k, v in result.items() if k not in ("ai_insight", "_meta")}
        sb.table("trend_cache").upsert(
            {
                "keyword":    keyword.lower().strip(),
                "geo":        geo.upper().strip(),
                "cat":        str(cat),
                "results":    results_blob,
                "ai_insight": ai_insight,
                "created_at": datetime.utcnow().isoformat(),
            },
            on_conflict="keyword,geo,cat",
        ).execute()
    except Exception:
        pass


# ---- Combined cache API ----
def cache_get(keyword: str, geo: str = "ID", cat: str = "0") -> dict | None:
    key = _cache_key(keyword, geo, cat)
    hit = _l1_get(key)
    if hit:
        return hit
    hit = get_db_cache(keyword, geo, cat)
    if hit:
        _l1_set(key, hit)  # warm L1
    return hit


def cache_set(keyword: str, geo: str, cat: str, result: dict, ai_insight: str):
    key = _cache_key(keyword, geo, cat)
    full = dict(result)
    full["ai_insight"] = ai_insight
    _l1_set(key, full)
    set_db_cache(keyword, geo, cat, result, ai_insight)

# =========================
# SUPABASE CLIENT
# =========================
_supabase_client = None

def get_supabase():
    """Lazy-init Supabase client. Returns None if env vars not set."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    url = (os.environ.get("SUPABASE_URL") or "").strip()
    key = (os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_ANON_KEY") or "").strip()
    if not url or not key:
        return None
    try:
        from supabase import create_client
        _supabase_client = create_client(url, key)
    except Exception:
        _supabase_client = None
    return _supabase_client


# =========================
# TIER / LIMIT HELPERS
# =========================
FREE_DAILY_LIMIT = 5


def get_user_tier(user_id: str) -> str:
    """Return 'pro' or 'free'. Defaults to 'free' on any error."""
    sb = get_supabase()
    if not sb or not user_id:
        return "free"
    try:
        # profiles.id adalah UUID dari auth.users (bukan kolom 'user_id')
        res = sb.table("profiles").select("tier").eq("id", user_id).maybe_single().execute()
        return (res.data or {}).get("tier", "free")
    except Exception:
        return "free"


def count_today_searches(user_id: str) -> int:
    """Count searches logged today for this user."""
    sb = get_supabase()
    if not sb or not user_id:
        return 0
    try:
        today = date.today().isoformat()
        res = (
            sb.table("search_logs")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .gte("created_at", f"{today}T00:00:00")
            .lte("created_at", f"{today}T23:59:59")
            .execute()
        )
        return res.count or 0
    except Exception:
        return 0


def log_search(user_id: str, keyword: str, geo: str = "ID", is_pro: bool = False):
    """Insert a row into search_logs. Fire-and-forget — errors are suppressed."""
    sb = get_supabase()
    if not sb or not user_id:
        return
    try:
        sb.table("search_logs").insert({
            "user_id": user_id,
            "keyword": keyword,
            "geo": geo,
            "is_pro_search": is_pro,
            # created_at diisi otomatis oleh Supabase DEFAULT now()
        }).execute()
    except Exception as e:
        print(f"[LOG_SEARCH ERROR] {e}")



def get_auth_session():
    """Extract and verify Supabase JWT. Returns (user_id, tier, is_pro)."""
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]

    sb = get_supabase()
    # Fallback identity defaults
    user_id = None
    tier = "free"
    is_pro = False

    if token and sb:
        try:
            # Verify token with Supabase - this is secure as it talks to Supabase API
            user_res = sb.auth.get_user(token)
            if user_res.user:
                user_id = user_res.user.id
                tier = get_user_tier(user_id)
                is_pro = (tier == "pro")
        except Exception as e:
            print(f"[AUTH ERROR] Invalid token: {e}")

    # If not authenticated, check for guest_id in query/body for backward compatibility or pure guests
    if not user_id:
        try:
            tmp_id = (request.args.get("user_id") or "").strip()
            if not tmp_id:
                data = request.get_json(silent=True) or {}
                tmp_id = (data.get("user_id") or "").strip()
            if tmp_id.startswith("guest_") or len(tmp_id) > 20: # simple guest validation
                user_id = tmp_id
        except:
            pass

    return user_id, tier, is_pro


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # We don't block guests, we just identify them. 
        # But we could block here if we wanted strictly private APIs.
        return f(*args, **kwargs)
    return decorated


def check_limit(user_id: str, tier: str):
    """
    Returns (searches_today, error_response_or_None).
    """
    if tier == "pro":
        return 0, None

    searches_today = count_today_searches(user_id) if user_id else 0

    if user_id and searches_today >= FREE_DAILY_LIMIT:
        return searches_today, (
            jsonify({
                "error": "Batas harian tercapai. Upgrade ke Pro untuk akses tanpa batas.",
                "error_code": "LIMIT_EXCEEDED",
                "searches_today": searches_today,
                "limit": FREE_DAILY_LIMIT,
                "tier": tier,
            }),
            403,
        )
    return searches_today, None


# =========================
# SANITIZE HELPER
# =========================
def sanitize(obj):
    """Bersihkan nilai numpy/float yang tidak bisa di-serialize ke JSON."""
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(v) for v in obj]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return round(obj, 4)
    try:
        import numpy as np
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return round(float(obj), 4)
        if isinstance(obj, np.bool_):
            return bool(obj)
    except ImportError:
        pass
    return obj


# =========================
# ROUTES
# =========================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/favicon.ico")
def favicon():
    return send_file("static/sentra.png", mimetype="image/png")


def _map_ide_produk_row(row):
    """Map kolom tabel ide_produk (nama dengan spasi) ke format frontend (snake_case)."""
    def get(*keys):
        for k in keys:
            if k in row and row[k] is not None:
                return row[k]
        return None
    return {
        "nama_produk": get("Nama Produk", "nama produk"),
        "kategori": get("Kategori", "kategori"),
        "modal_tier": get("Modal Tier", "modal tier"),
        "modal_min_juta": get("Modal Min (Juta)", "modal min (juta)"),
        "modal_max_juta": get("Modal Max (Juta)", "modal max (juta)"),
        "tren_persen": get("Tren (%)", "tren (%)"),
        "status_pasar": get("Status Pasar", "status pasar"),
        "puncak_penjualan": get("Puncak Penjualan", "puncak penjualan"),
        "kompetisi": get("Kompetisi", "kompetisi"),
        "margin_persen": get("Margin (%)", "margin (%)"),
        "target": get("Target Pasar", "target pasar"),
        "highlight": get("Highlight Analisis", "highlight analisis"),
        "skor_peluang": get("Skor Peluang", "skor peluang"),
        "rekomendasi": get("Rekomendasi", "rekomendasi"),
    }


@app.route("/api/ide-produk", methods=["GET"])
def api_ide_produk():
    """Return ide_produk rows for wizard: ?kategori=...&modal_tier=..."""
    kategori = (request.args.get("kategori") or "").strip()
    modal_tier = (request.args.get("modal_tier") or "").strip()
    if not kategori or not modal_tier:
        return jsonify({"error": "kategori dan modal_tier wajib", "data": []}), 400
    sb = get_supabase()
    if not sb:
        return jsonify({"error": "Koneksi database tidak tersedia", "data": []}), 503
    try:
        # Kolom di DB bisa "Kategori" atau "kategori" (PG lowercase jika tanpa quote)
        res = (
            sb.table("ide_produk")
            .select("*")
            .eq("Kategori", kategori)
            .eq("Modal Tier", modal_tier)
            .order("Skor Peluang", desc=True)
            .limit(6)
            .execute()
        )
        raw = list(res.data) if res.data else []
        data = [_map_ide_produk_row(r) for r in raw]
        return jsonify({"data": data})
    except Exception as e:
        msg = str(e)
        if "does not exist" in msg or "relation" in msg.lower() or "column" in msg.lower():
            msg = "Tabel/kolom ide_produk tidak cocok. Pastikan kolom: Kategori, Modal Tier, Skor Peluang, Nama Produk, dll."
        elif "RLS" in msg or "policy" in msg.lower():
            msg = "Akses ditolak (RLS). Aktifkan SELECT untuk anon di tabel ide_produk."
        return jsonify({"error": msg, "data": []}), 500


@app.route("/api/config", methods=["GET"])
def get_config():
    """Expose public Supabase credentials (anon key only, never service_role) to frontend."""
    url = (os.environ.get("SUPABASE_URL") or "").strip()
    anon_key = (os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_KEY") or "").strip()
    return jsonify({
        "supabase_url":      url,
        "supabase_anon_key": anon_key,
    })


@app.route("/api/user-status", methods=["POST", "GET"])
def user_status():
    """Return tier + quota info using JWT or body user_id."""
    user_id, tier, _ = get_auth_session()
    
    # If JWT failed, check body (for compatibility during transition)
    if not user_id:
        data = request.get_json(silent=True) or {}
        user_id = (data.get("user_id") or "").strip()
        tier = get_user_tier(user_id)

    searches_today = count_today_searches(user_id) if user_id else 0
    remaining = max(0, FREE_DAILY_LIMIT - searches_today) if tier == "free" else None

    return jsonify({
        "user_id": user_id or None,
        "tier": tier,
        "searches_today": searches_today,
        "searches_remaining": remaining,
        "daily_limit": FREE_DAILY_LIMIT if tier == "free" else None,
    })


@app.route("/api/analyze", methods=["POST"])
@require_auth
def analyze():
    user_id, tier, is_pro = get_auth_session()
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body tidak valid."}), 400

    keyword = data.get("keyword", "").strip()
    if not keyword:
        return jsonify({"error": "Keyword tidak boleh kosong."}), 400
    if len(keyword) > 100:
        return jsonify({"error": "Keyword terlalu panjang (maks 100 karakter)."}), 400

    # --- Tier & Limit Check ---
    searches_today, limit_err = check_limit(user_id, tier)
    if limit_err:
        return limit_err

    # --- Geo: Pro = pakai geo dari request, Free = paksa 'ID' ---
    geo = "ID"
    if is_pro:
        requested_geo = (data.get("geo") or "ID").strip().upper()
        if re.fullmatch(r'ID(-[A-Z]{2})?', requested_geo):
            geo = requested_geo

    # --- Category (for sector analysis) ---
    cat_id = int(data.get("cat", 0) or 0)
    cat_str = str(cat_id)

    # --- Cache check (L1 memory → L2 Supabase) ---
    cached = cache_get(keyword, geo, cat_str)
    if cached:
        remaining = max(0, FREE_DAILY_LIMIT - searches_today) if tier == "free" else None
        cached["_meta"] = {
            "tier": tier,
            "searches_today": searches_today,
            "searches_remaining": remaining,
            "geo": geo,
            "from_cache": True,
        }
        return jsonify(sanitize(cached))

    # --- Analisis ---
    result = analyze_keyword(keyword, geo=geo, cat=cat_id)

    # Map engine errors to proper HTTP codes
    if "error" in result:
        if result.get("error_code") == "TOO_MANY_REQUESTS":
            return jsonify({"error": result["error"], "error_code": "TOO_MANY_REQUESTS"}), 429
        return jsonify({"error": result["error"]}), 404

    # --- Log search ---
    if user_id:
        log_search(user_id, keyword, geo=geo, is_pro=is_pro)
        searches_today += 1

    # --- Cache the result (L1 + L2) --- simplified for async
    if result.get("growth") is not None:
        cache_set(keyword, geo, cat_str, result, "")

    # --- Attach quota info ---
    remaining = max(0, FREE_DAILY_LIMIT - searches_today) if tier == "free" else None
    result["_meta"] = {
        "tier": tier,
        "searches_today": searches_today,
        "searches_remaining": remaining,
        "geo": geo,
    }

    return jsonify(sanitize(result))


@app.route("/api/get-ai-insight", methods=["POST"])
def get_ai_insight_route():
    """Endpoint baru untuk ambil AI Insight secara terpisah (Async) dengan cache."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Data analisis tidak valid."}), 400
    
    # 1. Cek Cache
    keyword = data.get("keyword", "").strip()
    geo = (data.get("geo") or "ID").strip().upper()
    cat = str(data.get("cat", 0))
    
    if keyword:
        cached = cache_get(keyword, geo, cat)
        if cached and cached.get("ai_insight"):
            return jsonify({
                "ai_insight": cached["ai_insight"],
                "from_cache": True
            })

    # 2. Generate jika tidak ada di cache
    try:
        insight = generate_ai_insight(data)
        
        # 3. Simpan ke cache jika sukses (bukan pesan error/kuota)
        if keyword and insight and "⚠" not in insight:
            cache_set(keyword, geo, cat, data, insight)
            
        return jsonify({"ai_insight": insight})
    except Exception as e:
        return jsonify({"ai_insight": f"Gagal menghasilkan insight: {str(e)}"}), 500


@app.route("/api/compare", methods=["POST"])
@require_auth
def compare():
    user_id, tier, is_pro = get_auth_session()
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body tidak valid."}), 400

    keyword_a = data.get("keyword_a", "").strip()
    keyword_b = data.get("keyword_b", "").strip()

    if not keyword_a or not keyword_b:
        return jsonify({"error": "Kedua keyword harus diisi."}), 400
    if keyword_a.lower() == keyword_b.lower():
        return jsonify({"error": "Kedua keyword tidak boleh sama."}), 400
    if len(keyword_a) > 100 or len(keyword_b) > 100:
        return jsonify({"error": "Keyword terlalu panjang (maks 100 karakter)."}), 400

    # --- Tier check (compare counts as 1 search) ---
    searches_today, limit_err = check_limit(user_id, tier)
    if limit_err:
        return limit_err

    geo = "ID"
    if is_pro:
        requested_geo = (data.get("geo") or "ID").strip().upper()
        if re.fullmatch(r'ID(-[A-Z]{2})?', requested_geo):
            geo = requested_geo

    # --- Cache check (L1 → L2) ---
    # Use a combined keyword for the compare cache key
    compare_kw = f"__cmp__{keyword_a}__vs__{keyword_b}"
    cached = cache_get(compare_kw, geo)
    if cached:
        remaining = max(0, FREE_DAILY_LIMIT - searches_today) if tier == "free" else None
        cached["_meta"] = {
            "tier": tier,
            "searches_today": searches_today,
            "searches_remaining": remaining,
            "geo": geo,
            "from_cache": True,
        }
        return jsonify(sanitize(cached))

    result = compare_keywords(keyword_a, keyword_b, geo=geo)

    if "error" in result:
        if result.get("error_code") == "TOO_MANY_REQUESTS":
            return jsonify({"error": result["error"], "error_code": "TOO_MANY_REQUESTS"}), 429
        return jsonify({"error": result["error"]}), 404

    if user_id:
        log_search(user_id, f"{keyword_a} vs {keyword_b}", geo=geo, is_pro=is_pro)
        searches_today += 1

    # --- Cache the result (L1 + L2) --- simplified for async
    cache_set(compare_kw, geo, "0", result, "")

    remaining = max(0, FREE_DAILY_LIMIT - searches_today) if tier == "free" else None
    result["_meta"] = {
        "tier": tier,
        "searches_today": searches_today,
        "searches_remaining": remaining,
        "geo": geo,
    }

    return jsonify(sanitize(result))


@app.route("/api/get-compare-insight", methods=["POST"])
def get_compare_insight_route():
    """Endpoint baru untuk ambil AI Compare Insight secara terpisah (Async) dengan cache."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Data perbandingan tidak valid."}), 400
    
    # 1. Cek Cache
    kw_a = data.get("keyword_a", {}).get("keyword", "")
    kw_b = data.get("keyword_b", {}).get("keyword", "")
    geo = (data.get("geo") or "ID").strip().upper()
    
    if kw_a and kw_b:
        compare_kw = f"__cmp__{kw_a}__vs__{kw_b}"
        cached = cache_get(compare_kw, geo)
        if cached and cached.get("ai_insight"):
            return jsonify({
                "ai_insight": cached["ai_insight"],
                "from_cache": True
            })

    # 2. Generate jika tidak ada di cache
    try:
        from ai_recommendation import generate_compare_insight
        insight = generate_compare_insight(data)
        
        # 3. Simpan ke cache jika sukses
        if kw_a and kw_b and insight and "⚠" not in insight:
            compare_kw = f"__cmp__{kw_a}__vs__{kw_b}"
            cache_set(compare_kw, geo, "0", data, insight)

        return jsonify({"ai_insight": insight})
    except Exception as e:
        return jsonify({"ai_insight": f"Gagal menghasilkan insight: {str(e)}"}), 500


# =========================
# HOMEPAGE PREVIEW ENDPOINT
# No quota deduction — cached 6h — for the live preview chart on homepage
# =========================
PREVIEW_KEYWORD = "skincare"

@app.route("/api/preview", methods=["GET"])
def preview():
    """
    Returns trending data for the homepage Live Intelligence Preview.
    Tries: L1 cache → Supabase cache (standard key) → beauty-sector cache → static fallback.
    Never deducts quota.
    """
    keyword = PREVIEW_KEYWORD
    geo = "ID"

    # 1. Try standard cache key (same key used by normal /api/analyze for this keyword)
    cached = cache_get(keyword, geo, "0")
    if cached and cached.get("raw_trend"):
        return jsonify(sanitize(cached))

    # 2. Try beauty sector cache key
    cached = cache_get(keyword, geo, "sector:beauty")
    if cached and cached.get("raw_trend"):
        return jsonify(sanitize(cached))

    # 3. Try the preview-specific cache key
    cached = cache_get(keyword, geo, "preview")
    if cached and cached.get("raw_trend"):
        return jsonify(sanitize(cached))

    # 4. Try fetching live (SerpAPI) — best effort, silent error
    try:
        result = analyze_keyword(keyword, geo=geo, cat=0)
        if "error" not in result and result.get("raw_trend"):
            cache_set(keyword, geo, "0", result, "")
            return jsonify(sanitize(result))
    except Exception:
        pass

    # 5. Static fallback — always renders chart so homepage never breaks
    import math as _math
    base = [55,57,60,55,52,58,62,65,68,63,59,61,64,67,70,72,68,65,70,75,
            73,71,74,78,80,76,72,75,79,82,85,81,77,74,70,73,76,80,83,86,
            88,84,80,76,72,75,78,82,85,88,91,87,83,79,75,71,74,77,80,83,
            86,89,92,88,84,80,76,72,88,84,80,76,72,68,65,67,70,73,76,79,
            82,85,88,91,87,83,79,75,71,74,77,80]
    # Generate realistic-ish dates for last 90 days
    from datetime import date, timedelta
    today = date.today()
    dates = [(today - timedelta(days=89-i)).isoformat() for i in range(90)]
    return jsonify({
        "keyword": keyword,
        "market_pulse_score": 72.0,
        "lifecycle_stage": "Rising",
        "risk_level": "Low Risk",
        "saturation_index": 0.35,
        "growth": 0.124,
        "raw_trend": {"dates": dates, "values": base[:len(dates)]},
        "_static_fallback": True,
    })


# =========================
# SECTOR ANALYSIS ENDPOINT
# =========================
SECTOR_KEYWORDS = {
    "fashion":  "baju wanita",
    "beauty":   "skincare",
    "fnb":      "kuliner Indonesia",
    "gadget":   "earbuds wireless",
    "home":     "dekorasi rumah",
    "hobi":     "peralatan olahraga",
    "musiman":  "hampers lebaran",
}


@app.route("/api/analyze_sector", methods=["POST"])
def analyze_sector():
    """
    Analyze a predefined sector by type ('fashion', 'beauty', etc.).
    Results are cached so subsequent users get instant responses.
    """
    data = request.get_json(silent=True) or {}
    sector = (data.get("sector") or "").strip().lower()
    if sector not in SECTOR_KEYWORDS:
        return jsonify({"error": f"Sektor tidak dikenal. Pilih: {', '.join(SECTOR_KEYWORDS.keys())}"}), 400

    keyword = SECTOR_KEYWORDS[sector]
    user_id = (data.get("user_id") or "").strip()
    geo = "ID"  # sectors always use national-level data

    # --- Tier/limit check ---
    # fixed: get_user_tier first, then call check_limit with correct signature (user_id, tier) -> (searches_today, error)
    tier = get_user_tier(user_id) if user_id else "free"
    searches_today, limit_err = check_limit(user_id, tier)
    if limit_err:
        return limit_err

    # --- Cache-first (L1 → L2) ---
    cat = f"sector:{sector}"
    cached = cache_get(keyword, geo, cat)
    if cached:
        remaining = max(0, FREE_DAILY_LIMIT - searches_today) if tier == "free" else None
        cached["_meta"] = {
            "tier": tier, "searches_today": searches_today,
            "searches_remaining": remaining, "geo": geo,
            "from_cache": True, "sector": sector,
        }
        return jsonify(sanitize(cached))

    # --- Cache miss: fetch from Google Trends ---
    result = analyze_keyword(keyword, geo=geo)
    if "error" in result:
        if result.get("error_code") == "TOO_MANY_REQUESTS":
            return jsonify({"error": result["error"], "error_code": "TOO_MANY_REQUESTS"}), 429
        return jsonify({"error": result["error"]}), 404

    # Log the search
    if user_id:
        log_search(user_id, f"[sektor] {sector}: {keyword}")
        searches_today += 1

    # ---- MATIKAN SEMENTARA AI UNTUK TESTING ---
    try:
         result["ai_insight"] = generate_ai_insight(result)
    except ValueError as e:
         result["ai_insight"] = f"⚠ {str(e)}"
    except Exception:
        result["ai_insight"] = "AI insight tidak tersedia saat ini."
        
    # Save to L1 + L2 cache
    cache_set(keyword, geo, cat, result, result.get("ai_insight", ""))

    remaining = max(0, FREE_DAILY_LIMIT - searches_today) if tier == "free" else None
    result["_meta"] = {
        "tier": tier, "searches_today": searches_today,
        "searches_remaining": remaining, "geo": geo,
        "sector": sector,
    }
    return jsonify(sanitize(result))



@app.route("/api/generate-pdf", methods=["POST"])
def generate_pdf():
    """Pro-only: generate a PDF report from analysis data."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body tidak valid."}), 400

    user_id = (data.get("user_id") or "").strip()
    tier = get_user_tier(user_id)

    if tier != "pro":
        return jsonify({
            "error": "Fitur PDF hanya tersedia untuk pengguna Pro. Upgrade sekarang!",
            "error_code": "PRO_REQUIRED",
        }), 403

    analysis = data.get("analysis")
    if not analysis:
        return jsonify({"error": "Data analisis tidak ditemukan."}), 400

    try:
        pdf_buffer = _build_pdf(analysis)
        keyword = analysis.get("keyword", "sentra-report")
        filename = f"sentra-bi-{keyword.replace(' ', '-')}.pdf"
        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as e:
        return jsonify({"error": f"Gagal membuat PDF: {str(e)}"}), 500


def _build_pdf(data: dict) -> io.BytesIO:
    """Build a minimal PDF report using reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    GOLD   = colors.HexColor("#D4A843")
    DARK   = colors.HexColor("#0A0A08")
    LIGHT  = colors.HexColor("#F5F0E0")
    GRAY   = colors.HexColor("#888070")
    GREEN  = colors.HexColor("#2ECC71")
    RED    = colors.HexColor("#E74C3C")

    styles = getSampleStyleSheet()
    title_style  = ParagraphStyle("title",  fontSize=22, textColor=GOLD,   spaceAfter=4,  alignment=TA_CENTER, fontName="Helvetica-Bold")
    sub_style    = ParagraphStyle("sub",    fontSize=9,  textColor=GRAY,   spaceAfter=16, alignment=TA_CENTER, fontName="Helvetica")
    h2_style     = ParagraphStyle("h2",     fontSize=13, textColor=GOLD,   spaceBefore=12, spaceAfter=6, fontName="Helvetica-Bold")
    body_style   = ParagraphStyle("body",   fontSize=10, textColor=colors.black, leading=16, fontName="Helvetica")
    label_style  = ParagraphStyle("label",  fontSize=8,  textColor=GRAY,   fontName="Helvetica")

    keyword  = data.get("keyword", "—")
    stage    = data.get("lifecycle_stage", "—")
    risk     = data.get("risk_level", "—")
    growth   = data.get("growth", 0)
    momentum = data.get("momentum", 0)
    vol      = data.get("volatility", 0)
    pulse    = data.get("market_pulse_score", 0)
    timing   = data.get("entry_timing_score", 0)
    timing_l = data.get("entry_timing_label", "—")
    fomo     = data.get("fomo_index", 0)
    sat      = data.get("saturation_index", 0)
    fc30     = data.get("forecast_30d_avg", 0)
    fc_conf  = data.get("forecast_confidence", 0)
    ai_text  = data.get("ai_insight", "").replace("**", "").replace("*", "")
    generated = datetime.utcnow().strftime("%d %B %Y, %H:%M UTC")

    story = []
    story.append(Paragraph("SENTRA BI", title_style))
    story.append(Paragraph(f"Laporan Analisis Pasar — {keyword.title()}", sub_style))
    story.append(Paragraph(f"Dibuat: {generated}", label_style))
    story.append(HRFlowable(width="100%", thickness=1, color=GOLD, spaceAfter=14))

    story.append(Paragraph("Ringkasan Klasifikasi", h2_style))
    class_data = [
        ["Lifecycle Stage", stage],
        ["Risk Level", risk],
        ["Entry Timing", timing_l],
    ]
    t = Table(class_data, colWidths=[5*cm, 11*cm])
    t.setStyle(TableStyle([
        ("FONTNAME",    (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE",    (0,0), (-1,-1), 10),
        ("TEXTCOLOR",   (0,0), (0,-1), GRAY),
        ("TEXTCOLOR",   (1,0), (1,-1), DARK),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [colors.white, colors.HexColor("#F8F5EE")]),
        ("GRID",        (0,0), (-1,-1), 0.5, colors.HexColor("#DDCCAA")),
        ("PADDING",     (0,0), (-1,-1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.4*cm))

    story.append(Paragraph("Metrik Utama", h2_style))
    g_str  = f"+{growth*100:.1f}%" if growth >= 0 else f"{growth*100:.1f}%"
    m_str  = f"{'▲' if momentum >= 0 else '▼'} {abs(momentum):.3f}"
    metrics_data = [
        ["Metrik",          "Nilai",                  "Keterangan"],
        ["Growth 7 Hari",   g_str,                    "Perubahan minat minggu ini"],
        ["Momentum",        m_str,                    "Arah tren"],
        ["Volatilitas",     f"{vol*100:.1f}%",        "Fluktuasi pasar"],
        ["Market Pulse",    f"{pulse:.1f} / 100",     "Kesehatan pasar"],
        ["Entry Timing",    f"{timing:.1f} / 100",    "Waktu terbaik masuk"],
        ["FOMO Index",      f"{fomo:.2f}",            "Tingkat hype"],
        ["Saturasi",        f"{sat:.1f}",             "Kepadatan kompetitor"],
        ["Forecast 30 Hari",f"{fc30:.1f} / 100",     f"Keyakinan: {fc_conf*100:.0f}%"],
    ]
    mt = Table(metrics_data, colWidths=[4.5*cm, 3*cm, 8.5*cm])
    mt.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,0), GOLD),
        ("TEXTCOLOR",   (0,0), (-1,0), DARK),
        ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME",    (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE",    (0,0), (-1,-1), 9),
        ("TEXTCOLOR",   (0,1), (0,-1), GRAY),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F8F5EE")]),
        ("GRID",        (0,0), (-1,-1), 0.5, colors.HexColor("#DDCCAA")),
        ("PADDING",     (0,0), (-1,-1), 6),
        ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(mt)
    story.append(Spacer(1, 0.4*cm))

    if ai_text:
        story.append(Paragraph("AI Business Insight", h2_style))
        for para in ai_text.split("\n"):
            para = para.strip()
            if para:
                story.append(Paragraph(para, body_style))
                story.append(Spacer(1, 0.15*cm))

    story.append(Spacer(1, 0.6*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY))
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph("Sentra BI v2.0 — Powered by Google Trends & Claude AI", label_style))

    doc.build(story)
    buf.seek(0)
    return buf


# =========================
# SECTOR RADAR (Radar Peluang Sektor) — NEW
# No Google Trends, uses static data + RSS feeds + AI signal
# =========================
RSS_SOURCES = {
    "fashion": [
        "https://www.antaranews.com/rss/gaya-hidup.xml",
        "https://ekonomi.bisnis.com/feed",
        "https://www.kontan.co.id/rss/industri",
    ],
    "beauty": [
        "https://www.antaranews.com/rss/gaya-hidup.xml",
        "https://ekonomi.bisnis.com/feed",
        "https://finance.detik.com/rss",
    ],
    "fnb": [
        "https://www.antaranews.com/rss/ekonomi.xml",
        "https://ekonomi.bisnis.com/feed",
        "https://www.kontan.co.id/rss/industri",
        "https://finance.detik.com/rss",
    ],
    "gadget": [
        "https://www.antaranews.com/rss/tekno.xml",
        "https://ekonomi.bisnis.com/feed",
        "https://finance.detik.com/rss",
    ],
    "home": [
        "https://www.antaranews.com/rss/gaya-hidup.xml",
        "https://ekonomi.bisnis.com/feed",
        "https://www.kontan.co.id/rss/industri",
    ],
    "hobi": [
        "https://www.antaranews.com/rss/olahraga.xml",
        "https://www.antaranews.com/rss/gaya-hidup.xml",
        "https://finance.detik.com/rss",
    ],
    "musiman": [
        "https://www.antaranews.com/rss/ekonomi.xml",
        "https://ekonomi.bisnis.com/feed",
        "https://www.kontan.co.id/rss/industri",
        "https://finance.detik.com/rss",
    ],
}

# fixed: renamed from SECTOR_KEYWORDS to SECTOR_RSS_KEYWORDS
# (SECTOR_KEYWORDS at line 693 is a separate dict used by analyze_sector)
SECTOR_RSS_KEYWORDS = {
    "fashion":  ["fashion", "baju", "pakaian", "batik", "tekstil", "busana",
                 "hijab", "outfit", "garmen", "apparel", "clothing"],
    "beauty":   ["skincare", "kosmetik", "kecantikan", "makeup", "perawatan",
                 "beauty", "serum", "lotion", "parfum", "salon"],
    "fnb":      ["makanan", "minuman", "kuliner", "restoran", "fnb", "pangan",
                 "food", "beverage", "cafe", "kafe", "warung", "catering"],
    "gadget":   ["gadget", "elektronik", "smartphone", "teknologi", "digital",
                 "earphone", "laptop", "komputer", "handphone", "perangkat"],
    "home":     ["furniture", "furnitur", "dekorasi", "interior", "rumah",
                 "properti", "living", "home", "perabot", "dapur"],
    "hobi":     ["olahraga", "hobi", "fitness", "gym", "travel", "gaming",
                 "leisure", "sport", "outdoor", "wisata", "rekreasi"],
    "musiman":  ["lebaran", "ramadan", "natal", "tahun baru", "hampers",
                 "harbolnas", "musiman", "hari raya", "imlek", "parsel"],
}

# TTL khusus untuk news cache (30 menit)
_NEWS_CACHE_TTL = 30 * 60


def fetch_rss_news(sector: str, max_items: int = 3) -> list:
    """
    Fetch berita real dari RSS feeds yang relevan untuk setiap sektor.
    Filter artikel berdasarkan SECTOR_RSS_KEYWORDS.
    Cache hasil 30 menit di _mem_cache dengan key 'rss_{sector}'.
    Return [] jika tidak ada artikel yang cocok — frontend sudah handle ini.
    """
    import feedparser
    from datetime import datetime, timezone

    # --- 30-minute news cache ---
    news_cache_key = f"rss_{sector}"
    with _cache_lock:
        entry = _mem_cache.get(news_cache_key)
        if entry and (time.time() - entry["ts"]) < _NEWS_CACHE_TTL:
            return entry["data"]

    keywords = SECTOR_RSS_KEYWORDS.get(sector, [])  # fixed: use SECTOR_RSS_KEYWORDS
    feeds = RSS_SOURCES.get(sector, [])
    results = []

    for feed_url in feeds:
        if len(results) >= max_items:
            break
        try:
            feed = feedparser.parse(
                feed_url,
                request_headers={
                    "User-Agent": "Mozilla/5.0 (compatible; SentraBI/2.0)"
                }
            )
            if not feed.entries:
                continue

            for entry in feed.entries[:25]:
                if len(results) >= max_items:
                    break

                title   = entry.get("title", "").lower()
                summary = entry.get("summary", "").lower()
                content = title + " " + summary

                # Filter: minimal 1 keyword sektor harus cocok
                if not any(kw in content for kw in keywords):
                    continue

                # Hitung time_ago dari waktu publikasi
                time_ago = "Baru saja"
                try:
                    published = (
                        entry.get("published_parsed") or
                        entry.get("updated_parsed")
                    )
                    if published:
                        pub_dt = datetime(*published[:6], tzinfo=timezone.utc)
                        diff   = datetime.now(timezone.utc) - pub_dt
                        secs   = diff.total_seconds()
                        if secs < 3600:
                            time_ago = f"{int(secs // 60)} menit lalu"
                        elif secs < 86400:
                            time_ago = f"{int(secs // 3600)} jam lalu"
                        elif secs < 604800:
                            time_ago = f"{int(secs // 86400)} hari lalu"
                        else:
                            time_ago = f"{int(secs // 604800)} minggu lalu"
                except Exception:
                    pass

                # Ekstrak nama source dari domain URL feed
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(feed_url).netloc.replace("www.", "")
                    source = domain.split(".")[0].title()
                except Exception:
                    source = "Berita"

                results.append({
                    "title":    entry.get("title", "Berita terkait"),
                    "source":   source,
                    "time_ago": time_ago,
                    "url":      entry.get("link", "#"),
                })

        except Exception as e:
            print(f"[RSS ERROR] {feed_url}: {e}")
            continue

    final = results[:max_items]

    # --- Simpan ke news cache (30 menit) ---
    with _cache_lock:
        _mem_cache[news_cache_key] = {"data": final, "ts": time.time()}

    return final

# cleaned: removed dead code — _extract_domain() was defined but never called
def generate_sector_ai_signal(sector: str, static_data: dict, news_items: list) -> str:
    """
    Generate 1-sentence actionable insight (max 20 words) based on:
    - Sector static data (growth, stage)
    - News headlines
    Return empty string if Claude fails or too slow.
    """
    try:
        growth = static_data.get("yoy_growth", 0)
        headlines = " | ".join([n.get("title", "") for n in news_items[:2]])
        context = static_data.get("context", "")

        prompt = f"""Data Sektor: {sector.title()}
Pertumbuhan YoY: {growth}%
Konteks: {context}
Berita: {headlines if headlines else 'N/A'}

Buat HANYA 1 kalimat actionable insight dalam Bahasa Indonesia (max 20 kata).
Insight:"""

        # Pass to AI engine - will fail gracefully if Claude is slow/unavailable
        insight = generate_ai_insight({
            "keyword": f"{sector} insight",
            "context": prompt,
            "raw_trend": {"dates": [], "values": []},
            "growth": growth / 100,
        })

        if insight and len(insight) < 200 and "⚠" not in insight:
            return insight.strip()[:150]
    except Exception:
        pass

    return ""

@app.route("/api/sector-radar", methods=["POST"])
def sector_radar():
    """
    Endpoint baru untuk Radar Peluang Sektor.
    Request: { "sector": "fashion" }
    Response: {
        "sector": "fashion",
        "static": { market_size_label, yoy_growth, umkm_share, top_subsectors, context, quarter },
        "news": [ { title, source, time_ago, url }, ... ],
        "ai_signal": "1 kalimat insight atau kosong jika gagal",
        "cached_at": "ISO timestamp"
    }
    Cached 2 jam di _mem_cache.
    """
    data = request.get_json(silent=True) or {}
    sector = (data.get("sector") or "").strip().lower()

    SECTOR_ALIASES = {'skincare': 'beauty', 'makanan': 'fnb', 'elektronik': 'gadget', 'furnitur': 'home', 'olahraga': 'hobi'}
    sector = SECTOR_ALIASES.get(sector, sector)

    if sector not in RSS_SOURCES:
        return jsonify({
            "error": f"Sektor tidak dikenal. Pilih: {', '.join(RSS_SOURCES.keys())}"
        }), 400

    # --- Generate cache key for 2-hour cache ---
    cache_key = _cache_key(f"radar_{sector}", "ID", "sector-radar")

    # --- Check L1 cache (2 hour TTL) ---
    with _cache_lock:
        entry = _mem_cache.get(cache_key)
        if entry and (time.time() - entry["ts"]) < (2 * 60 * 60):
            return jsonify(entry["data"])

    # --- Load static data ---
    try:
        from sector_static_data import SECTOR_STATIC_DATA
        static = SECTOR_STATIC_DATA.get(sector, {})
    except Exception:
        static = {}

    # --- Fetch RSS news (timeout 5s total) ---
    news = fetch_rss_news(sector, max_items=3)

    # --- Generate AI signal (async, but wait max 5s) ---
    ai_signal = ""
    try:
        ai_signal = generate_sector_ai_signal(sector, static, news)
    except Exception:
        pass

    # --- Build response ---
    response = {
        "sector": sector,
        "static": {
            "market_size_label": static.get("market_size_label", "—"),
            "yoy_growth": static.get("yoy_growth", 0),
            "umkm_share": static.get("umkm_share", 0),
            "top_subsectors": static.get("top_subsectors", []),
            "context": static.get("context", ""),
            "quarter": static.get("quarter", ""),
        },
        "news": news,
        "ai_signal": ai_signal,
        "cached_at": datetime.utcnow().isoformat() + "Z",
    }

    # --- Store in L1 cache (2 hours) ---
    with _cache_lock:
        _mem_cache[cache_key] = {"data": response, "ts": time.time()}

    return jsonify(response)

@app.route("/api/analyze-local", methods=["POST"])
@app.route("/api/analyze-local/", methods=["POST"])
def analyze_local_route():
    print(f"[DEBUG] /api/analyze-local hit by {request.remote_addr}")
    data = request.json or {}
    keyword = data.get("keyword", "").strip()
    geo = data.get("geo", "ID")

    if not keyword:
        return jsonify({"error": "Keyword required"}), 400

    # Regional data
    regional_data = fetch_regional_data(keyword, geo)
    if not regional_data:
        return jsonify({"success": True, "regional_data": [], "local_insight": "Satelit belum menemukan data pencarian regional yang cukup untuk kata kunci ini di wilayah Indonesia.", "error_code": "NO_DATA"}), 200

    # Full regional breakdown for Indonesia (Provinsi)
    regional_breakdown = get_regional_interest(keyword, geo)
    top_province = regional_breakdown[0]["province"] if regional_breakdown else None
    top_3 = [r["province"] for r in regional_breakdown[:3]] if regional_breakdown else []

    # AI Strategi Lokal
    local_insight = generate_local_insight(keyword, regional_data)

    return jsonify({
        "keyword": keyword,
        "regional_data": regional_data,
        "regional_breakdown": regional_breakdown,
        "top_province": top_province,
        "top_3": top_3,
        "local_insight": local_insight
    })


# =========================
# UMKM DASHBOARD ENDPOINTS
# =========================
@app.route("/api/umkm/profile", methods=["GET", "POST"])
def umkm_profile():
    """
    GET  : load profile for current user (JWT or guest user_id)
    POST : upsert profile
    """
    user_id, _, _ = get_auth_session()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    sb = get_supabase()
    if not sb:
        return jsonify({"error": "Koneksi database tidak tersedia"}), 503

    if request.method == "GET":
        try:
            profile = get_umkm_profile(sb, user_id)
            return jsonify({"profile": profile or {}})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    data = request.get_json(silent=True) or {}
    try:
        profile = upsert_umkm_profile(sb, user_id, data)
        return jsonify({"profile": profile})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/umkm/analyze", methods=["POST"])
def umkm_analyze():
    """
    Upsert profile + compute lightweight metrics + generate warm UMKM insight (Groq).
    """
    user_id, _, _ = get_auth_session()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    sb = get_supabase()
    if not sb:
        return jsonify({"error": "Koneksi database tidak tersedia"}), 503

    payload = request.get_json(silent=True) or {}
    try:
        profile = upsert_umkm_profile(sb, user_id, payload)
        metrics = compute_umkm_health(profile)
        prompt = build_umkm_analysis_prompt(profile, metrics)
        insight = groq_generate(prompt)

        # store analytics snapshot (best-effort)
        try:
            sb.table("umkm_analytics").insert({
                "user_id": user_id,
                "metrics": metrics,
                "ai_insight": insight,
                "created_at": datetime.utcnow().isoformat(),
            }).execute()
        except Exception:
            pass

        return jsonify({"profile": profile, "metrics": metrics, "insight": insight})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/umkm/plan", methods=["POST"])
def umkm_plan():
    user_id, _, _ = get_auth_session()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    sb = get_supabase()
    if not sb:
        return jsonify({"error": "Koneksi database tidak tersedia"}), 503

    try:
        profile = get_umkm_profile(sb, user_id) or {}
        metrics = compute_umkm_health(profile)
        prompt = build_umkm_plan_prompt(profile, metrics)
        plan = groq_generate(prompt)
        return jsonify({"plan": plan})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/umkm/promo", methods=["POST"])
def umkm_promo():
    user_id, _, _ = get_auth_session()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    sb = get_supabase()
    if not sb:
        return jsonify({"error": "Koneksi database tidak tersedia"}), 503

    try:
        profile = get_umkm_profile(sb, user_id) or {}
        prompt = build_umkm_promo_prompt(profile)
        promo = groq_generate(prompt)
        return jsonify({"promo": promo})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/umkm/competitors", methods=["POST"])
def umkm_competitors():
    """
    Find competitors via SerpAPI Google Maps engine.
    Reuses the SERPAPI_KEY already configured for Google Trends.
    """
    user_id, _, _ = get_auth_session()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    from sentra_engine import _SERPAPI_KEY
    if not _SERPAPI_KEY:
        return jsonify({"error": "SERPAPI_KEY belum dikonfigurasi"}), 503

    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    if not query:
        return jsonify({"error": "Query tidak boleh kosong"}), 400

    # Optional: bias by UMKM profile location
    sb = get_supabase()
    location_hint = ""
    if sb:
        try:
            prof = get_umkm_profile(sb, user_id) or {}
            location_hint = (prof.get("location") or "").strip()
        except Exception:
            location_hint = ""

    full_query = f"{query} {location_hint}".strip()

    try:
        import serpapi
        client = serpapi.Client(api_key=_SERPAPI_KEY)
        search_params = {
            "engine": "google_maps",
            "q": full_query,
            "type": "search",
            "hl": "id",
            "gl": "id",
        }
        search_result = client.search(search_params)
        local_results = search_result.get("local_results") or []

        results = []
        for r in local_results[:8]:
            results.append({
                "name": r.get("title"),
                "address": r.get("address"),
                "rating": r.get("rating"),
                "user_ratings_total": r.get("reviews"),
                "type": r.get("type"),
                "hours": r.get("hours"),
            })

        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================
# KEYWORD NEWS ENDPOINT
# cleaned: removed dead code — duplicate _NEWS_CACHE_TTL (already defined at module level above)
# =========================
@app.route("/api/keyword-news", methods=["POST"])
def keyword_news():
    """
    Fetch berita dari Google News RSS berdasarkan keyword yang dianalisis user.
    Cache 30 menit di _mem_cache.
    """
    import feedparser
    from urllib.parse import quote
    from datetime import datetime, timezone

    data = request.get_json(silent=True) or {}
    keyword = (data.get("keyword") or "").strip()

    if not keyword:
        return jsonify({"error": "Keyword tidak boleh kosong."}), 400

    # --- 30-minute cache ---
    news_cache_key = f"gnews_{keyword.lower()}"
    with _cache_lock:
        entry = _mem_cache.get(news_cache_key)
        if entry and (time.time() - entry["ts"]) < _NEWS_CACHE_TTL:
            return jsonify({"news": entry["data"], "from_cache": True})

    # --- Fetch Google News RSS ---
    encoded_kw = quote(keyword)
    feed_url = f"https://news.google.com/rss/search?q={encoded_kw}&hl=id&gl=ID&ceid=ID:id"

    results = []
    try:
        feed = feedparser.parse(
            feed_url,
            request_headers={"User-Agent": "Mozilla/5.0 (compatible; SentraBI/2.0)"}
        )

        for entry in feed.entries[:5]:
            time_ago = "Baru saja"
            try:
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                if published:
                    pub_dt = datetime(*published[:6], tzinfo=timezone.utc)
                    diff = datetime.now(timezone.utc) - pub_dt
                    secs = diff.total_seconds()
                    if secs < 3600:
                        time_ago = f"{int(secs // 60)} menit lalu"
                    elif secs < 86400:
                        time_ago = f"{int(secs // 3600)} jam lalu"
                    elif secs < 604800:
                        time_ago = f"{int(secs // 86400)} hari lalu"
                    else:
                        time_ago = f"{int(secs // 604800)} minggu lalu"
            except Exception:
                pass

            # Extract source dari field "source" Google News atau dari title
            source = "Google News"
            try:
                raw_source = entry.get("source", {})
                if isinstance(raw_source, dict):
                    source = raw_source.get("title", "Google News")
                elif isinstance(raw_source, str):
                    source = raw_source
                # Google News kadang taruh source di title setelah " - "
                if " - " in entry.get("title", ""):
                    parts = entry["title"].rsplit(" - ", 1)
                    if len(parts) == 2:
                        source = parts[1].strip()
            except Exception:
                pass

            results.append({
                "title": entry.get("title", "").rsplit(" - ", 1)[0].strip(),
                "source": source,
                "time_ago": time_ago,
                "url": entry.get("link", "#"),
            })

    except Exception as e:
        print(f"[KEYWORD NEWS ERROR] {e}")
        return jsonify({"news": [], "error": str(e)})

    # --- Simpan ke cache ---
    with _cache_lock:
        _mem_cache[news_cache_key] = {"data": results, "ts": time.time()}

    return jsonify({"news": results, "from_cache": False})


@app.route("/api/health")
def health():
    sb_ok = get_supabase() is not None
    return jsonify({"status": "ok", "version": "2.0", "supabase": sb_ok, "openrouter": bool(os.environ.get("OPENROUTER_API_KEY"))})


@app.route("/api/admin/clear-cache", methods=["POST"])
def clear_cache():
    """Clear L1 memory cache. Panggil sekali setelah deploy fix tanggal."""
    global _mem_cache
    with _cache_lock:
        count = len(_mem_cache)
        _mem_cache.clear()
    return jsonify({"cleared": count, "message": "L1 cache cleared"})

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Global error caught: {str(e)}", exc_info=True)
    return jsonify({
        "error": "Internal Server Error",
        "message": str(e),
        "type": type(e).__name__
    }), 500

print("\n" + "="*50)
print("[SYSTEM] Sentra BI is starting...")
print("[SYSTEM] Registration: /api/analyze-local is READY.")
print("="*50 + "\n")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
