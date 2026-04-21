import os
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
    """Import get_supabase_service from app context."""
    try:
        from app import get_supabase_service
        return get_supabase_service()
    except Exception:
        return None


def _safe_query(fn):
    """Run fn(sb) and return (data, error). Never raises."""
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
        total_users = (sb.table("profiles").select("id", count="exact")
                       .execute()).count or 0
        searches_today = (sb.table("search_logs").select("id", count="exact")
                          .gte("created_at", today).execute()).count or 0
        searches_month = (sb.table("search_logs").select("id", count="exact")
                          .gte("created_at", month_start).execute()).count or 0
        total_umkm = (sb.table("umkm_profiles").select("id", count="exact")
                      .execute()).count or 0
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
        rows = (sb.table("search_logs").select("created_at")
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
        # Fetch profiles with tier
        q = sb.table("profiles").select("id, tier, created_at")
        if tier_filter != "all":
            q = q.eq("tier", tier_filter)
        profiles_res = q.execute()
        profiles = profiles_res.data or []

        # Fetch all search log counts per user
        sl_res = sb.table("search_logs").select("user_id").execute()
        sl_data = sl_res.data or []
        search_counts: dict = {}
        for row in sl_data:
            uid = str(row.get("user_id") or "")
            search_counts[uid] = search_counts.get(uid, 0) + 1

        # Try to get emails via admin list_users
        email_map: dict = {}
        try:
            users_res = sb.auth.admin.list_users()
            for u in (users_res or []):
                email_map[str(u.id)] = u.email or ""
        except Exception:
            pass

        rows = []
        for p in profiles:
            pid = str(p["id"])
            email = email_map.get(pid, "")
            if search and search not in email.lower():
                continue
            rows.append({
                "id": pid,
                "email": email,
                "tier": p.get("tier", "free"),
                "created_at": p.get("created_at", ""),
                "total_searches": search_counts.get(pid, 0),
            })

        rows.sort(key=lambda x: x["created_at"], reverse=True)
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
        rows = (sb.table("search_logs").select("keyword, geo, created_at, is_pro_search")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(10).execute()).data or []
        return rows

    data, err = _safe_query(query)
    return jsonify(data or [])


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
             .limit(100))
        if date_from:
            q = q.gte("created_at", date_from)
        if date_to:
            q = q.lte("created_at", date_to + "T23:59:59")
        rows = q.execute().data or []

        # Get emails
        email_map: dict = {}
        try:
            users_res = sb.auth.admin.list_users()
            for u in (users_res or []):
                email_map[str(u.id)] = u.email or ""
        except Exception:
            pass

        result = []
        for row in rows:
            kw = (row.get("keyword") or "").lower()
            if keyword_filter and keyword_filter not in kw:
                continue
            uid = str(row.get("user_id") or "")
            result.append({
                "id": row.get("id"),
                "email": email_map.get(uid, uid[:8] + "…" if uid else ""),
                "keyword": row.get("keyword", ""),
                "geo": row.get("geo", ""),
                "created_at": row.get("created_at", ""),
                "is_pro_search": row.get("is_pro_search", False),
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

        email_map: dict = {}
        try:
            users_res = sb.auth.admin.list_users()
            for u in (users_res or []):
                email_map[str(u.id)] = u.email or ""
        except Exception:
            pass

        result = []
        for row in rows:
            kw = (row.get("keyword") or "").lower()
            if keyword_filter and keyword_filter not in kw:
                continue
            uid = str(row.get("user_id") or "")
            result.append({
                "id": row.get("id"),
                "email": email_map.get(uid, uid),
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
                .select("id, user_id, business_name, category, city, province, monthly_revenue, updated_at")
                .order("updated_at", desc=True)
                .execute()).data or []

        email_map: dict = {}
        try:
            users_res = sb.auth.admin.list_users()
            for u in (users_res or []):
                email_map[str(u.id)] = u.email or ""
        except Exception:
            pass

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
        # User distribution by province (from profiles)
        profile_rows = (sb.table("profiles").select("id").execute()).data or []
        total_users = len(profile_rows)

        # UMKM by province
        umkm_rows = (sb.table("umkm_profiles").select("province")
                     .not_.is_("province", "null").execute()).data or []
        umkm_by_prov: dict = {}
        for row in umkm_rows:
            prov = (row.get("province") or "").strip()
            if prov:
                umkm_by_prov[prov] = umkm_by_prov.get(prov, 0) + 1

        # User province distribution (approximate — from umkm_profiles since profiles don't have province)
        user_by_prov: dict = {}
        all_umkm_full = (sb.table("umkm_profiles").select("province, user_id")
                         .not_.is_("province", "null").execute()).data or []
        for row in all_umkm_full:
            prov = (row.get("province") or "").strip()
            if prov:
                user_by_prov[prov] = user_by_prov.get(prov, 0) + 1

        provinces = set(list(umkm_by_prov.keys()) + list(user_by_prov.keys()))
        return [
            {
                "province": p,
                "users": user_by_prov.get(p, 0),
                "umkm": umkm_by_prov.get(p, 0),
            }
            for p in provinces
        ]

    data, err = _safe_query(query)
    return jsonify(data or [])


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

    cache_count = cache_info()

    # Count DB cache entries
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
        "l1_cache_entries": cache_count,
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
