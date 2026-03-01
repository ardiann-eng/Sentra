"""
Sentra BI v2.0 — Flask Web Server untuk Railway
"""

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

from sentra_engine import analyze_keyword, compare_keywords
from ai_recommendation import generate_ai_insight, generate_compare_insight

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
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
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
        res = sb.table("profiles").select("tier").eq("user_id", user_id).single().execute()
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


def log_search(user_id: str, keyword: str):
    """Insert a row into search_logs. Fire-and-forget — errors are suppressed."""
    sb = get_supabase()
    if not sb or not user_id:
        return
    try:
        sb.table("search_logs").insert({
            "user_id": user_id,
            "keyword": keyword,
            "created_at": datetime.utcnow().isoformat(),
        }).execute()
    except Exception:
        pass


def check_limit(user_id: str):
    """
    Returns (tier, searches_today, error_response_or_None).
    If limit exceeded, returns a 403 JSON response tuple.
    """
    tier = get_user_tier(user_id)
    searches_today = count_today_searches(user_id) if user_id else 0

    if user_id and tier == "free" and searches_today >= FREE_DAILY_LIMIT:
        return tier, searches_today, (
            jsonify({
                "error": "Batas harian tercapai. Upgrade ke Pro untuk akses tanpa batas.",
                "error_code": "LIMIT_EXCEEDED",
                "searches_today": searches_today,
                "limit": FREE_DAILY_LIMIT,
                "tier": tier,
            }),
            403,
        )
    return tier, searches_today, None


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


@app.route("/api/user-status", methods=["POST"])
def user_status():
    """Return tier + quota info for the requesting user."""
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
def analyze():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body tidak valid."}), 400

    keyword = data.get("keyword", "").strip()
    if not keyword:
        return jsonify({"error": "Keyword tidak boleh kosong."}), 400
    if len(keyword) > 100:
        return jsonify({"error": "Keyword terlalu panjang (maks 100 karakter)."}), 400

    user_id = (data.get("user_id") or "").strip()

    # --- Tier check & limit ---
    tier, searches_today, limit_err = check_limit(user_id)
    if limit_err:
        return limit_err

    # --- Geo: Pro = pakai geo dari request, Free = paksa 'ID' ---
    geo = "ID"
    if tier == "pro":
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
        log_search(user_id, keyword)
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
    """Endpoint baru untuk ambil AI Insight secara terpisah (Async)."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Data analisis tidak valid."}), 400
    
    try:
        insight = generate_ai_insight(data)
        return jsonify({"ai_insight": insight})
    except Exception as e:
        return jsonify({"ai_insight": f"Gagal menghasilkan insight: {str(e)}"}), 500


@app.route("/api/compare", methods=["POST"])
def compare():
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

    user_id = (data.get("user_id") or "").strip()

    # --- Tier check (compare counts as 1 search) ---
    tier, searches_today, limit_err = check_limit(user_id)
    if limit_err:
        return limit_err

    geo = "ID"
    if tier == "pro":
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
        log_search(user_id, f"{keyword_a} vs {keyword_b}")
        searches_today += 1

    if user_id:
        log_search(user_id, f"{keyword_a} vs {keyword_b}")
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
    """Endpoint baru untuk ambil AI Compare Insight secara terpisah (Async)."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Data perbandingan tidak valid."}), 400
    
    try:
        from ai_recommendation import generate_compare_insight
        insight = generate_compare_insight(data)
        return jsonify({"ai_insight": insight})
    except Exception as e:
        return jsonify({"ai_insight": f"Gagal menghasilkan insight: {str(e)}"}), 500


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
    tier, searches_today, limit_err = check_limit(user_id)
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
    story.append(Paragraph("Sentra BI v2.0 — Powered by Google Trends & Gemini AI", label_style))

    doc.build(story)
    buf.seek(0)
    return buf


@app.route("/api/health")
def health():
    sb_ok = get_supabase() is not None
    return jsonify({"status": "ok", "version": "2.0", "supabase": sb_ok})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
