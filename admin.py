import os
import math
import random
import time
import csv
import io
from datetime import datetime, date, timedelta
from functools import wraps
from flask import (
    Blueprint, request, jsonify, render_template,
    session, redirect, make_response
)

admin_bp = Blueprint("admin", __name__, template_folder="templates/admin")

SESSION_TIMEOUT_HOURS = 8


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect("/")
        login_time = session.get("admin_login_time", 0)
        if time.time() - login_time > SESSION_TIMEOUT_HOURS * 3600:
            session.clear()
            return redirect("/")
        return f(*args, **kwargs)
    return decorated


def _get_sb():
    """Get best available Supabase client: service > anon."""
    try:
        from app import get_supabase_service, get_supabase
        sb = get_supabase_service()
        if sb:
            return sb
        return get_supabase()
    except Exception:
        return None


def _get_email_map(sb) -> dict:
    """Fetch user email map {user_id: email} via admin API (paginated)."""
    email_map: dict = {}
    try:
        page = 1
        per_page = 1000  # Max allowed by Supabase
        while True:
            res = sb.auth.admin.list_users(page=page, per_page=per_page)
            users = getattr(res, "users", None) or (res if isinstance(res, list) else [])
            if not users:
                break
            for u in users:
                uid = str(getattr(u, "id", "") or "")
                email = getattr(u, "email", "") or ""
                if uid:
                    email_map[uid] = email
            # If fewer users than per_page were returned, we've hit the last page
            if len(users) < per_page:
                break
            page += 1
    except Exception:
        # Fallback: try without pagination params (older supabase-py versions)
        try:
            res = sb.auth.admin.list_users()
            users = getattr(res, "users", None) or (res if isinstance(res, list) else [])
            for u in users:
                uid = str(getattr(u, "id", "") or "")
                email = getattr(u, "email", "") or ""
                if uid:
                    email_map[uid] = email
        except Exception:
            pass
    return email_map


def _get_auth_full_map(sb) -> dict:
    """Returns {user_id: {'email': str, 'banned': bool}} via paginated admin API."""
    user_map: dict = {}
    try:
        page, per_page = 1, 1000
        while True:
            res = sb.auth.admin.list_users(page=page, per_page=per_page)
            users = getattr(res, "users", None) or (res if isinstance(res, list) else [])
            if not users:
                break
            for u in users:
                uid = str(getattr(u, "id", "") or "")
                if not uid:
                    continue
                email = getattr(u, "email", "") or ""
                banned_until = str(getattr(u, "banned_until", "") or "")
                is_banned = bool(banned_until and banned_until not in ("", "none", "null", "1970-01-01T00:00:00Z"))
                user_map[uid] = {"email": email, "banned": is_banned}
            if len(users) < per_page:
                break
            page += 1
    except Exception:
        try:
            res = sb.auth.admin.list_users()
            users = getattr(res, "users", None) or (res if isinstance(res, list) else [])
            for u in users:
                uid = str(getattr(u, "id", "") or "")
                if uid:
                    email = getattr(u, "email", "") or ""
                    user_map[uid] = {"email": email, "banned": False}
        except Exception:
            pass
    return user_map


def _is_guest(user_id: str) -> bool:
    return not user_id or user_id.startswith("guest_") or len(user_id) < 20


# ─── ML HELPERS ───────────────────────────────────────────────────────────

def _normalize(values: list) -> list:
    """Min-max normalization to [0, 1]."""
    if not values:
        return []
    mn, mx = min(values), max(values)
    rng = mx - mn or 1
    return [(v - mn) / rng for v in values]


def _euclidean(a: list, b: list) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _kmeans(points: list, k: int = 3, max_iter: int = 100, seed: int = 42) -> tuple:
    """K-Means++ clustering. Returns (labels, centroids)."""
    random.seed(seed)
    n = len(points)
    if n < k:
        return list(range(n)), points[:]

    # K-Means++ initialisation
    centroids = [points[random.randint(0, n - 1)]]
    for _ in range(k - 1):
        dists = [min(_euclidean(p, c) ** 2 for c in centroids) for p in points]
        total = sum(dists) or 1
        r, cum = random.random() * total, 0
        for i, d in enumerate(dists):
            cum += d
            if cum >= r:
                centroids.append(points[i])
                break
        else:
            centroids.append(points[-1])

    labels = [0] * n
    for _ in range(max_iter):
        new_labels = [min(range(k), key=lambda ci: _euclidean(p, centroids[ci])) for p in points]
        if new_labels == labels:
            break
        labels = new_labels
        dim = len(points[0])
        for ci in range(k):
            members = [points[i] for i, l in enumerate(labels) if l == ci]
            if members:
                centroids[ci] = [sum(m[d] for m in members) / len(members) for d in range(dim)]
    return labels, centroids


# NLP Rule-Based Intent Classifier
_INTENT_RULES: dict = {
    "Informational": [
        "apa", "pengertian", "adalah", "definisi", "artinya", "maksud",
        "mengenal", "tentang", "penjelasan", "cara", "tips", "langkah",
        "panduan", "tutorial", "bagaimana", "info", "jenis", "macam",
        "contoh", "daftar", "ceritakan", "jelaskan",
    ],
    "Analytical": [
        "analisis", "analisa", "margin", "laba", "profit", "untung",
        "strategi", "perbandingan", "bandingkan", "hitung", "kalkulasi",
        "estimasi", "proyeksi", "target", "optimasi", "efisiensi",
        "kinerja", "evaluasi", "rekomendasi", "prediksi", "tren",
        "statistik", "omzet", "revenue", "pendapatan", "biaya",
        "investasi", "modal", "roi", "break even",
    ],
    "Problem Solving": [
        "masalah", "gagal", "rugi", "sulit", "tidak bisa", "kenapa",
        "mengapa", "bangkrut", "sepi", "turun", "jelek", "buruk",
        "kurang", "lambat", "macet", "hutang", "pinjam", "tertipu",
        "komplain", "keluhan", "susah", "drop", "menurun", "mengatasi",
        "solusi untuk", "cara mengatasi",
    ],
}


def _classify_intent(keyword: str) -> str:
    kw = keyword.lower()
    scores = {intent: sum(1 for w in words if w in kw)
              for intent, words in _INTENT_RULES.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "Informational"


def _safe_query(fn):
    sb = _get_sb()
    if not sb:
        return None, "Supabase tidak tersedia"
    try:
        return fn(sb), None
    except Exception as e:
        return None, str(e)


# ─── LOGOUT ─────────────────────────────────────────────────────────────────

@admin_bp.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ─── DASHBOARD ──────────────────────────────────────────────────────────────

@admin_bp.route("/")
@admin_required
def dashboard():
    return render_template("dashboard.html")


# ─── API: OVERVIEW ──────────────────────────────────────────────────────────

@admin_bp.route("/api/overview")
@admin_required
def api_overview():
    today = date.today().isoformat()
    month_start = date.today().replace(day=1).isoformat()

    def query(sb):
        # Use len(data) — count property unreliable with some supabase-py versions
        total_users = len(sb.table("profiles").select("id").execute().data or [])

        sl_all = sb.table("search_logs").select("id, created_at").execute().data or []
        searches_today = sum(1 for r in sl_all if (r.get("created_at") or "")[:10] == today)
        searches_month = sum(1 for r in sl_all if (r.get("created_at") or "")[:7] == today[:7])

        total_umkm = len(sb.table("umkm_profiles").select("user_id").execute().data or [])

        return {
            "total_users": total_users,
            "searches_today": searches_today,
            "searches_month": searches_month,
            "total_umkm": total_umkm,
        }

    data, err = _safe_query(query)
    if err:
        return jsonify({"total_users": 0, "searches_today": 0,
                        "searches_month": 0, "total_umkm": 0, "error": err})
    return jsonify(data)


@admin_bp.route("/api/debug")
@admin_required
def api_debug():
    """Cek koneksi dan raw data dari Supabase."""
    sb = _get_sb()
    if not sb:
        return jsonify({"error": "No Supabase client"})
    out = {}
    for tbl in ["profiles", "search_logs", "umkm_profiles"]:
        try:
            res = sb.table(tbl).select("*").limit(2).execute()
            sample = res.data or []
            out[tbl] = {
                "count_sample": len(sample),
                "columns": list(sample[0].keys()) if sample else [],
                "error": None
            }
        except Exception as e:
            out[tbl] = {"error": str(e)}
    return jsonify(out)


# ─── API: GROWTH ────────────────────────────────────────────────────────────

@admin_bp.route("/api/growth/users")
@admin_required
def api_growth_users():
    def query(sb):
        cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat()
        rows = (sb.table("profiles").select("created_at")
                .gte("created_at", cutoff).execute()).data or []
        counts: dict = {}
        for row in rows:
            d = row["created_at"][:10]
            counts[d] = counts.get(d, 0) + 1
        return [{"date": k, "count": v} for k, v in sorted(counts.items())]

    data, err = _safe_query(query)
    return jsonify(data or [])


@admin_bp.route("/api/growth/searches")
@admin_required
def api_growth_searches():
    def query(sb):
        cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat()
        rows = (sb.table("search_logs").select("created_at, user_id")
                .gte("created_at", cutoff).execute()).data or []
        counts: dict = {}
        for row in rows:
            d = row["created_at"][:10]
            counts[d] = counts.get(d, 0) + 1
        return [{"date": k, "count": v} for k, v in sorted(counts.items())]

    data, err = _safe_query(query)
    return jsonify(data or [])


# ─── API: TOP KEYWORDS ──────────────────────────────────────────────────────

@admin_bp.route("/api/top-keywords")
@admin_required
def api_top_keywords():
    def query(sb):
        rows = (sb.table("search_logs").select("keyword")
                .not_.is_("keyword", "null").execute()).data or []
        counts: dict = {}
        for row in rows:
            kw = (row.get("keyword") or "").strip().lower()
            if kw:
                counts[kw] = counts.get(kw, 0) + 1
        sorted_kw = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]
        return [{"keyword": k, "total": v} for k, v in sorted_kw]

    data, err = _safe_query(query)
    return jsonify(data or [])


# ─── API: SEARCH CATEGORY DISTRIBUTION ─────────────────────────────────────

@admin_bp.route("/api/search-categories")
@admin_required
def api_search_categories():
    CATEGORY_KEYWORDS = {
        "Fashion": ["baju", "fashion", "pakaian", "hijab", "sepatu", "kaos", "celana", "tas"],
        "Beauty": ["skincare", "kosmetik", "kecantikan", "serum", "lipstik", "moisturizer"],
        "F&B": ["makanan", "minuman", "kuliner", "kopi", "cafe", "restoran", "snack", "jajanan"],
        "Gadget": ["hp", "earbuds", "laptop", "elektronik", "gadget", "smartphone", "tablet"],
    }

    def query(sb):
        rows = (sb.table("search_logs").select("keyword")
                .not_.is_("keyword", "null").execute()).data or []
        dist = {cat: 0 for cat in CATEGORY_KEYWORDS}
        dist["Lainnya"] = 0
        for row in rows:
            kw = (row.get("keyword") or "").lower()
            matched = False
            for cat, kws in CATEGORY_KEYWORDS.items():
                if any(k in kw for k in kws):
                    dist[cat] += 1
                    matched = True
                    break
            if not matched:
                dist["Lainnya"] += 1
        return [{"category": k, "total": v} for k, v in dist.items() if v > 0]

    data, err = _safe_query(query)
    return jsonify(data or [])


# ─── API: USERS ─────────────────────────────────────────────────────────────

@admin_bp.route("/api/users")
@admin_required
def api_users():
    page = max(1, int(request.args.get("page", 1)))
    search = request.args.get("search", "").strip().lower()
    tier_filter = request.args.get("tier", "all")
    per_page = 20

    def query(sb):
        q = sb.table("profiles").select("id, tier, created_at")
        if tier_filter != "all":
            q = q.eq("tier", tier_filter)
        profiles = q.order("created_at", desc=True).execute().data or []

        # Search counts per user (registered users only)
        sl_data = sb.table("search_logs").select("user_id").execute().data or []
        search_counts: dict = {}
        for row in sl_data:
            uid = str(row.get("user_id") or "")
            if not _is_guest(uid):
                search_counts[uid] = search_counts.get(uid, 0) + 1

        auth_map = _get_auth_full_map(sb)

        rows = []
        for p in profiles:
            pid = str(p["id"])
            auth_info = auth_map.get(pid, {"email": "", "banned": False})
            email = auth_info["email"]
            is_banned = auth_info["banned"]
            if search and search not in email.lower():
                continue
            rows.append({
                "id": pid,
                "email": email,
                "tier": p.get("tier", "free"),
                "created_at": p.get("created_at", ""),
                "total_searches": search_counts.get(pid, 0),
                "is_banned": is_banned,
            })

        total = len(rows)
        start = (page - 1) * per_page
        return {
            "users": rows[start:start + per_page],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": max(1, (total + per_page - 1) // per_page),
        }

    data, err = _safe_query(query)
    if err:
        return jsonify({"users": [], "total": 0, "page": 1, "pages": 1, "error": err})
    return jsonify(data)


@admin_bp.route("/api/users/<user_id>/searches")
@admin_required
def api_user_searches(user_id):
    def query(sb):
        return (sb.table("search_logs")
                .select("keyword, geo, created_at, is_pro_search")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(10).execute()).data or []

    data, err = _safe_query(query)
    return jsonify(data or [])


# ─── USER ACTIONS ─────────────────────────────────────────────────

@admin_bp.route("/api/users/all-emails", methods=["GET"])
@admin_required
def api_all_emails():
    """Returns a flat list of all registered user emails for BCC broadcasting."""
    sb = _get_sb()
    if not sb:
        return jsonify({"error": "Supabase tidak tersedia"}), 500
    try:
        auth_map = _get_auth_full_map(sb)
        emails = [info["email"] for info in auth_map.values() if info.get("email")]
        return jsonify({"emails": emails})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/api/users/<user_id>/tier", methods=["PATCH"])
@admin_required
def api_update_tier(user_id):
    data = request.get_json(silent=True) or {}
    new_tier = data.get("tier", "free")
    if new_tier not in ("free", "pro"):
        return jsonify({"error": "Invalid tier"}), 400

    def query(sb):
        sb.table("profiles").update({"tier": new_tier}).eq("id", user_id).execute()
        return {"ok": True, "tier": new_tier}

    result, err = _safe_query(query)
    if err:
        return jsonify({"error": err}), 500
    return jsonify(result)


@admin_bp.route("/api/users/<user_id>/ban", methods=["POST"])
@admin_required
def api_ban_user(user_id):
    data = request.get_json(silent=True) or {}
    action = data.get("action", "ban")  # "ban" or "unban"
    sb = _get_sb()
    if not sb:
        return jsonify({"error": "Supabase tidak tersedia"}), 500
    try:
        if action == "ban":
            sb.auth.admin.update_user_by_id(user_id, {"ban_duration": "876600h"})
        else:
            sb.auth.admin.update_user_by_id(user_id, {"ban_duration": "none"})
        return jsonify({"ok": True, "action": action})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/api/users/<user_id>", methods=["DELETE"])
@admin_required
def api_delete_user(user_id):
    sb = _get_sb()
    if not sb:
        return jsonify({"error": "Supabase tidak tersedia"}), 500
    try:
        for tbl, col in [("search_logs", "user_id"), ("umkm_profiles", "user_id"), ("profiles", "id")]:
            try:
                sb.table(tbl).delete().eq(col, user_id).execute()
            except Exception:
                pass
        sb.auth.admin.delete_user(user_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── API: SEARCH LOGS ───────────────────────────────────────────────────────

@admin_bp.route("/api/searches")
@admin_required
def api_searches():
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    keyword_filter = request.args.get("keyword", "").strip().lower()

    def query(sb):
        q = (sb.table("search_logs")
             .select("id, user_id, keyword, geo, created_at, is_pro_search")
             .order("created_at", desc=True)
             .limit(200))
        if date_from:
            q = q.gte("created_at", date_from)
        if date_to:
            q = q.lte("created_at", date_to + "T23:59:59")
        rows = q.execute().data or []

        email_map = _get_email_map(sb)

        result = []
        for row in rows:
            kw = (row.get("keyword") or "").lower()
            if keyword_filter and keyword_filter not in kw:
                continue
            uid = str(row.get("user_id") or "")
            is_guest = _is_guest(uid)
            email = "Guest" if is_guest else email_map.get(uid, uid[:12] + "…")
            result.append({
                "id": row.get("id"),
                "email": email,
                "keyword": row.get("keyword", ""),
                "geo": row.get("geo", ""),
                "created_at": row.get("created_at", ""),
                "is_pro_search": row.get("is_pro_search", False),
                "is_guest": is_guest,
            })
        return result

    data, err = _safe_query(query)
    return jsonify(data or [])


@admin_bp.route("/api/searches/export")
@admin_required
def api_searches_export():
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    keyword_filter = request.args.get("keyword", "").strip().lower()

    def query(sb):
        q = (sb.table("search_logs")
             .select("id, user_id, keyword, geo, created_at, is_pro_search")
             .order("created_at", desc=True)
             .limit(5000))
        if date_from:
            q = q.gte("created_at", date_from)
        if date_to:
            q = q.lte("created_at", date_to + "T23:59:59")
        rows = q.execute().data or []

        email_map = _get_email_map(sb)

        result = []
        for row in rows:
            kw = (row.get("keyword") or "").lower()
            if keyword_filter and keyword_filter not in kw:
                continue
            uid = str(row.get("user_id") or "")
            email = "Guest" if _is_guest(uid) else email_map.get(uid, uid)
            result.append({
                "id": row.get("id"),
                "email": email,
                "keyword": row.get("keyword", ""),
                "geo": row.get("geo", ""),
                "created_at": row.get("created_at", ""),
                "is_pro_search": row.get("is_pro_search", False),
            })
        return result

    data, err = _safe_query(query)
    rows = data or []

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["id", "email", "keyword", "geo", "created_at", "is_pro_search"])
    writer.writeheader()
    writer.writerows(rows)

    resp = make_response(output.getvalue())
    resp.headers["Content-Type"] = "text/csv"
    resp.headers["Content-Disposition"] = "attachment; filename=search_logs.csv"
    return resp


# ─── API: UMKM ──────────────────────────────────────────────────────────────

@admin_bp.route("/api/umkm")
@admin_required
def api_umkm():
    def query(sb):
        rows = (sb.table("umkm_profiles")
                .select("user_id, business_name, category, city, province, avg_monthly_revenue, updated_at")
                .order("updated_at", desc=True)
                .execute()).data or []

        email_map = _get_email_map(sb)
        for row in rows:
            uid = str(row.get("user_id") or "")
            row["email"] = email_map.get(uid, "")
        return rows

    data, err = _safe_query(query)
    return jsonify(data or [])


@admin_bp.route("/api/umkm/categories")
@admin_required
def api_umkm_categories():
    def query(sb):
        rows = (sb.table("umkm_profiles").select("category")
                .not_.is_("category", "null").execute()).data or []
        counts: dict = {}
        for row in rows:
            cat = (row.get("category") or "").strip()
            if cat:
                counts[cat] = counts.get(cat, 0) + 1
        return [{"category": k, "total": v} for k, v in
                sorted(counts.items(), key=lambda x: x[1], reverse=True)]

    data, err = _safe_query(query)
    return jsonify(data or [])


@admin_bp.route("/api/umkm/map")
@admin_required
def api_umkm_map():
    def query(sb):
        # UMKM grouped by province
        umkm_rows = (sb.table("umkm_profiles")
                     .select("province, user_id, business_name")
                     .not_.is_("province", "null").execute()).data or []

        umkm_by_prov: dict = {}
        user_by_prov: dict = {}
        for row in umkm_rows:
            prov = (row.get("province") or "").strip()
            if not prov:
                continue
            umkm_by_prov[prov] = umkm_by_prov.get(prov, 0) + 1
            # Count unique users per province
            uid = str(row.get("user_id") or "")
            if uid:
                if prov not in user_by_prov:
                    user_by_prov[prov] = set()
                user_by_prov[prov].add(uid)

        provinces = set(umkm_by_prov.keys())
        return [
            {
                "province": p,
                "users": len(user_by_prov.get(p, set())),
                "umkm": umkm_by_prov.get(p, 0),
            }
            for p in provinces
        ]

    data, err = _safe_query(query)
    return jsonify(data or [])


# ─── AI INSIGHTS ────────────────────────────────────────────────────

_TOKENS_FREE = 800    # avg tokens per free search
_TOKENS_PRO  = 4000   # avg tokens per pro search (includes AI analysis)
_COST_PER_1M = 0.60   # USD blended estimate (Groq free + OpenRouter)


@admin_bp.route("/api/ai/usage")
@admin_required
def api_ai_usage():
    """Daily estimated token & cost usage for last 30 days."""
    def query(sb):
        cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat()
        rows = (sb.table("search_logs")
                .select("created_at, is_pro_search")
                .gte("created_at", cutoff)
                .execute()).data or []

        daily: dict = {}
        for row in rows:
            d = (row.get("created_at") or "")[:10]
            if not d:
                continue
            if d not in daily:
                daily[d] = {"date": d, "free": 0, "pro": 0, "tokens": 0}
            is_pro = bool(row.get("is_pro_search"))
            tokens = _TOKENS_PRO if is_pro else _TOKENS_FREE
            daily[d]["pro" if is_pro else "free"] += 1
            daily[d]["tokens"] += tokens

        result = sorted(daily.values(), key=lambda x: x["date"])
        for r in result:
            r["cost_usd"] = round(r["tokens"] * _COST_PER_1M / 1_000_000, 5)
            r["total"] = r["free"] + r["pro"]

        total_tokens  = sum(r["tokens"] for r in result)
        total_cost    = round(sum(r["cost_usd"] for r in result), 4)
        total_searches = sum(r["total"] for r in result)
        pro_searches  = sum(r["pro"] for r in result)

        return {
            "daily": result,
            "total_tokens": total_tokens,
            "total_cost_usd": total_cost,
            "total_searches": total_searches,
            "pro_searches": pro_searches,
        }

    data, err = _safe_query(query)
    if err:
        return jsonify({"error": err}), 500
    return jsonify(data)


@admin_bp.route("/api/ai/empty-searches")
@admin_required
def api_empty_searches():
    """Keywords searched only once in last 30 days (potential poor-result indicators)."""
    def query(sb):
        cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat()
        rows = (sb.table("search_logs")
                .select("keyword, user_id, is_pro_search, created_at")
                .gte("created_at", cutoff)
                .not_.is_("keyword", "null")
                .execute()).data or []

        stats: dict = {}
        for row in rows:
            kw = (row.get("keyword") or "").strip().lower()
            if not kw or len(kw) < 2:
                continue
            uid = str(row.get("user_id") or "")
            if kw not in stats:
                stats[kw] = {"keyword": kw, "count": 0, "users": set(), "is_pro": 0, "last_seen": ""}
            stats[kw]["count"] += 1
            stats[kw]["users"].add(uid)
            if row.get("is_pro_search"):
                stats[kw]["is_pro"] += 1
            d = (row.get("created_at") or "")[:10]
            if d > stats[kw]["last_seen"]:
                stats[kw]["last_seen"] = d

        one_timers = [
            {"keyword": kw, "count": s["count"], "unique_users": len(s["users"]),
             "is_pro": s["is_pro"], "last_seen": s["last_seen"]}
            for kw, s in stats.items() if s["count"] == 1
        ]
        one_timers.sort(key=lambda x: x["last_seen"], reverse=True)

        return {
            "one_timers": one_timers[:50],
            "one_timer_count": len(one_timers),
            "total_unique_keywords": len(stats),
            "searched_once_pct": round(len(one_timers) / len(stats) * 100, 1) if stats else 0,
        }

    data, err = _safe_query(query)
    if err:
        return jsonify({"error": err}), 500
    return jsonify(data)


# ─── ML ANALYTICS ENDPOINTS ──────────────────────────────────────────────────

@admin_bp.route("/api/ml/umkm-clusters")
@admin_required
def api_ml_umkm_clusters():
    """K-Means (k=3) clustering on UMKM profiles via pure-Python implementation."""
    def query(sb):
        rows = (sb.table("umkm_profiles")
                .select("user_id, business_name, category, avg_monthly_revenue, margin_pct, active_customers, city, province")
                .execute()).data or []

        # Keep only rows with at least revenue data
        rows = [r for r in rows if r.get("avg_monthly_revenue") is not None]

        if len(rows) < 3:
            return {"clusters": [], "total": len(rows),
                    "error": "Data UMKM belum cukup (minimal 3 profil dengan data omzet)"}

        revenues  = [float(r.get("avg_monthly_revenue") or 0) for r in rows]
        margins   = [float(r.get("margin_pct") or 0)          for r in rows]
        customers = [float(r.get("active_customers") or 0)    for r in rows]

        rev_n  = _normalize(revenues)
        mar_n  = _normalize(margins)
        cust_n = _normalize(customers)

        points = [[rev_n[i], mar_n[i], cust_n[i]] for i in range(len(rows))]
        k = min(3, len(rows))
        labels, centroids = _kmeans(points, k=k)

        # Determine cluster order by avg revenue (label nicely: A=highest)
        cluster_avgs = []
        for ci in range(k):
            idxs = [i for i, l in enumerate(labels) if l == ci]
            avg_rev = sum(revenues[i] for i in idxs) / len(idxs) if idxs else 0
            cluster_avgs.append((ci, avg_rev))
        order = [ci for ci, _ in sorted(cluster_avgs, key=lambda x: -x[1])]
        rank = {ci: pos for pos, ci in enumerate(order)}  # original ci -> rank 0/1/2

        NAMES   = ["A", "B", "C"]
        COLORS  = ["rgba(212,168,67,0.7)", "rgba(59,130,246,0.7)", "rgba(34,197,94,0.7)"]
        PROFILES = ["High Performer", "Berkembang", "Perlu Perhatian"]
        P_COLORS = ["#4ade80", "#fbbf24", "#fca5a5"]

        clusters = [{"name": NAMES[pos], "color": COLORS[pos],
                     "profile": PROFILES[pos], "profile_color": P_COLORS[pos],
                     "members": []} for pos in range(k)]

        for i, row in enumerate(rows):
            pos = rank[labels[i]]
            r_size = max(5, min(18, int(cust_n[i] * 13) + 5))
            clusters[pos]["members"].append({
                "label": (row.get("business_name") or row.get("category") or "")[:22],
                "category": row.get("category", ""),
                "city": row.get("city", ""),
                "avg_monthly_revenue": revenues[i],
                "margin_pct": margins[i],
                "active_customers": int(customers[i]),
                "x": round(rev_n[i], 4),
                "y": round(mar_n[i], 4),
                "r": r_size,
            })

        for cl in clusters:
            m = cl["members"]
            cl["count"] = len(m)
            cl["avg_revenue"] = round(sum(x["avg_monthly_revenue"] for x in m) / len(m), 0) if m else 0
            cl["avg_margin"]  = round(sum(x["margin_pct"]          for x in m) / len(m), 1) if m else 0
            cl["avg_customers"] = round(sum(x["active_customers"]  for x in m) / len(m), 0) if m else 0

        return {"clusters": clusters, "total": len(rows), "k": k}

    data, err = _safe_query(query)
    if err:
        return jsonify({"error": err}), 500
    return jsonify(data)


@admin_bp.route("/api/ml/search-intents")
@admin_required
def api_ml_search_intents():
    """Rule-based NLP intent classification on search_logs (last 30 days)."""
    def query(sb):
        cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat()
        rows = (sb.table("search_logs")
                .select("keyword, is_pro_search, created_at")
                .gte("created_at", cutoff)
                .not_.is_("keyword", "null")
                .execute()).data or []

        counts   = {i: 0 for i in _INTENT_RULES}
        kw_seen  = {i: {} for i in _INTENT_RULES}

        for row in rows:
            kw = (row.get("keyword") or "").strip()
            if not kw:
                continue
            intent = _classify_intent(kw)
            counts[intent] += 1
            kw_seen[intent][kw] = kw_seen[intent].get(kw, 0) + 1

        total = sum(counts.values()) or 1
        intents = sorted(
            [{"intent": k, "count": v, "pct": round(v / total * 100, 1)} for k, v in counts.items()],
            key=lambda x: -x["count"]
        )
        top_by_intent = {
            intent: [{"keyword": kw, "count": c}
                     for kw, c in sorted(kw_seen[intent].items(), key=lambda x: -x[1])[:6]]
            for intent in _INTENT_RULES
        }
        return {"intents": intents, "top_by_intent": top_by_intent, "total_classified": total}

    data, err = _safe_query(query)
    if err:
        return jsonify({"error": err}), 500
    return jsonify(data)


# ─── API: SYSTEM HEALTH ─────────────────────────────────────────────────────

@admin_bp.route("/api/system")
@admin_required
def api_system():
    sb = _get_sb()
    supabase_ok = False
    if sb:
        try:
            sb.table("profiles").select("id").limit(1).execute()
            supabase_ok = True
        except Exception:
            pass

    def cache_info():
        try:
            from app import _mem_cache
            return len(_mem_cache)
        except Exception:
            return 0

    db_cache_count = 0
    db_cache_today = 0
    if sb:
        try:
            db_cache_count = sb.table("trend_cache").select("id", count="exact").execute().count or 0
            today_str = date.today().isoformat()
            db_cache_today = (sb.table("trend_cache").select("id", count="exact")
                              .gte("created_at", today_str).execute()).count or 0
        except Exception:
            pass

    return jsonify({
        "supabase": supabase_ok,
        "serpapi": bool(os.environ.get("SERPAPI_KEY") or os.environ.get("SERP_API_KEY")),
        "groq": bool(os.environ.get("GROQ_API_KEY")),
        "openrouter": bool(os.environ.get("OPENROUTER_API_KEY")),
        "l1_cache_entries": cache_info(),
        "db_cache_total": db_cache_count,
        "db_cache_today": db_cache_today,
    })


@admin_bp.route("/api/clear-cache", methods=["POST"])
@admin_required
def api_clear_cache():
    try:
        from app import _mem_cache, _cache_lock
        with _cache_lock:
            count = len(_mem_cache)
            _mem_cache.clear()
        return jsonify({"success": True, "cleared": count})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
