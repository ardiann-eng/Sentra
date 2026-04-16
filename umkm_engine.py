"""
Sentra AI — UMKM Engine

Tujuan:
- Simpan/muat profil UMKM (Supabase)
- Hitung ringkasan indikator usaha (lightweight)
- Generate output AI (Groq llama-3.3-70b-versatile) dengan tone hangat UMKM

Catatan:
- Engine ini tidak mengubah logic Sentra keyword analysis yang sudah ada.
- Semua fungsi aman dipanggil meski Supabase belum dikonfigurasi (akan fallback).
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from ai_recommendation import _generate_via_groq  # reuse client + model config


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _safe_num(v: Any) -> float | None:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except Exception:
        return None


def compute_umkm_health(profile: dict) -> dict:
    """
    Simple heuristic scoring (0-100) for UMKM dashboard.
    Input profile keys (optional):
      - avg_monthly_revenue (float)
      - margin_pct (float)
      - category (str)
      - location (str)
    """
    rev = _safe_num(profile.get("avg_monthly_revenue"))
    margin = _safe_num(profile.get("margin_pct"))

    # baseline
    score = 55.0
    focus = "Kerapihan Operasional"

    if rev is not None:
        if rev >= 50_000_000:
            score += 12
        elif rev >= 15_000_000:
            score += 6
        elif rev <= 3_000_000:
            score -= 6

    if margin is not None:
        if margin >= 45:
            score += 10
            focus = "Skalakan Penjualan"
        elif margin >= 30:
            score += 5
            focus = "Perkuat Repeat Order"
        elif margin <= 15:
            score -= 10
            focus = "Rapikan Harga & Biaya"

    score = max(0, min(100, score))
    weekly_opportunity = "Naikkan repeat order +1 level"
    if score >= 75:
        weekly_opportunity = "Gas promo di wilayah paling panas"
    elif score <= 45:
        weekly_opportunity = "Fokus perbaiki margin & paket hemat"

    return {
        "health_score": round(score),
        "weekly_opportunity": weekly_opportunity,
        "focus": focus,
    }


def build_umkm_analysis_prompt(profile: dict, metrics: dict) -> str:
    name = (profile.get("business_name") or "Usahamu").strip()
    category = (profile.get("category") or "produk/jasa").strip()
    location = (profile.get("location") or "lokasi kamu").strip()
    rev = profile.get("avg_monthly_revenue") or "—"
    margin = profile.get("margin_pct") or "—"
    target = profile.get("target_customer") or "—"

    return f"""Kamu adalah asisten bisnis Sentra AI untuk pemilik UMKM Indonesia.
Gaya bahasa: hangat, suportif, praktis, tidak kaku, seperti teman yang bantu.

KONTEKS USAHA
- Nama usaha: {name}
- Kategori: {category}
- Lokasi: {location}
- Omzet/bulan: {rev}
- Margin (%): {margin}
- Target pembeli: {target}

RINGKASAN INDIKATOR
- Skor kesehatan usaha: {metrics.get('health_score')}/100
- Fokus utama: {metrics.get('focus')}
- Peluang minggu ini: {metrics.get('weekly_opportunity')}

TULIS output dengan format:
1) Ringkasan (2-3 kalimat)
2) 3 langkah cepat (bullet, masing-masing 1-2 kalimat, actionable)
3) Kesalahan yang paling sering bikin seret (2 poin singkat)

Batasi 220-300 kata. Jangan ada kalimat pembuka seperti "Berikut analisis...".
"""


def build_umkm_plan_prompt(profile: dict, metrics: dict) -> str:
    name = (profile.get("business_name") or "Usahamu").strip()
    category = (profile.get("category") or "produk/jasa").strip()
    location = (profile.get("location") or "lokasi kamu").strip()

    return f"""Kamu adalah mentor UMKM Sentra AI.
Tugas: susun rencana bisnis yang realistis, bertahap, dan gampang dieksekusi.
Nada: hangat dan praktis.

Usaha: {name} ({category}) di {location}
Skor kesehatan: {metrics.get('health_score')}/100
Fokus utama: {metrics.get('focus')}

Buat rencana 14 hari (2 minggu) dengan struktur:
- Minggu 1 (3-5 langkah)
- Minggu 2 (3-5 langkah)
- Checklist harian sederhana (5 item)

Setiap langkah harus spesifik (contoh: "buat 2 paket bundling", "set WA broadcast 1x", dll).
"""


def build_umkm_promo_prompt(profile: dict) -> str:
    name = (profile.get("business_name") or "Usahamu").strip()
    category = (profile.get("category") or "produk/jasa").strip()
    location = (profile.get("location") or "lokasi kamu").strip()

    return f"""Kamu adalah copywriter UMKM yang bantu pemilik usaha bikin promosi yang laris.
Nada: santai, hangat, Indonesia sehari-hari, tidak lebay.

Usaha: {name}
Kategori: {category}
Lokasi: {location}

Buat:
1) 5 ide promo (judul + mekanisme singkat)
2) 5 caption IG/WA (masing-masing 2-3 kalimat + CTA)
3) 10 hook konten (1 baris)
"""


def groq_generate(prompt: str) -> str:
    text, status, err = _generate_via_groq(prompt)
    if status != 200 or not text:
        return "⚠ Lagi ada kendala memuat AI. Coba lagi ya."
    return text.strip()


def upsert_umkm_profile(sb, user_id: str, profile: dict) -> dict:
    location = (
        profile.get("location")
        or ", ".join(
            [p for p in [(profile.get("city") or "").strip(), (profile.get("province") or "").strip()] if p]
        )
    )
    sales_platforms = profile.get("sales_platforms")
    if isinstance(sales_platforms, str):
        sales_platforms = [p.strip() for p in sales_platforms.split(",") if p.strip()]

    payload = {
        "user_id": user_id,
        "business_name": (profile.get("business_name") or "").strip(),
        "category": (profile.get("category") or "").strip(),
        "location": (location or "").strip(),
        "avg_monthly_revenue": _safe_num(profile.get("avg_monthly_revenue")),
        "margin_pct": _safe_num(profile.get("margin_pct")),
        "target_customer": (profile.get("target_customer") or "").strip(),
        "province": (profile.get("province") or "").strip(),
        "city": (profile.get("city") or "").strip(),
        "active_customers": _safe_num(profile.get("active_customers")),
        "sales_platforms": sales_platforms or [],
        "business_description": (profile.get("business_description") or "").strip(),
        "updated_at": _now_iso(),
    }

    try:
        res = sb.table("umkm_profiles").upsert(payload, on_conflict="user_id").execute()
        rows = res.data or []
        return rows[0] if rows else payload
    except Exception:
        # Backward-compatible retry if the table has not been migrated with new onboarding columns yet.
        legacy_payload = {
            "user_id": payload["user_id"],
            "business_name": payload["business_name"],
            "category": payload["category"],
            "location": payload["location"],
            "avg_monthly_revenue": payload["avg_monthly_revenue"],
            "margin_pct": payload["margin_pct"],
            "target_customer": payload["target_customer"],
            "updated_at": payload["updated_at"],
        }
        res = sb.table("umkm_profiles").upsert(legacy_payload, on_conflict="user_id").execute()
        rows = res.data or []
        merged = rows[0] if rows else legacy_payload
        return {**payload, **merged}


def get_umkm_profile(sb, user_id: str) -> dict | None:
    res = sb.table("umkm_profiles").select("*").eq("user_id", user_id).maybe_single().execute()
    return res.data

