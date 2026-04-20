/**
 * Sentra AI — Account Settings Module
 * Module pattern: const AccSettings = (() => { ... })()
 *
 * Public API:
 *   toggleSidebar, closeSidebar, navTo,
 *   saveProfil, cancelProfil,
 *   saveBisnis, cancelBisnis,
 *   savePrefs,
 *   changePassword, checkPwStrength, togglePw,
 *   confirmDeleteBizData,
 *   logout
 */

const AccSettings = (() => {
  'use strict';

  // ─── State ───────────────────────────────────────────────
  let sb          = null;
  let _session    = null;
  let _data       = null;          // raw /api/account/me response
  let _avatarDataUrl = null;       // canvas-resized avatar (if changed)
  let _sidebarOpen   = true;
  const PREFS_KEY    = 'sentra_prefs';

  // ─── Init ─────────────────────────────────────────────────
  async function init() {
    _detectMobile();

    try {
      // 1. Fetch Supabase config from backend
      const cfgRes = await fetch('/api/config');
      const cfg    = await cfgRes.json();

      if (!cfg.supabase_url || !cfg.supabase_anon_key) {
        _fatalError('Konfigurasi Supabase tidak tersedia. Coba refresh halaman.');
        return;
      }

      sb = supabase.createClient(cfg.supabase_url, cfg.supabase_anon_key);

      // 2. Auth guard
      const { data: sessionData } = await sb.auth.getSession();
      _session = sessionData?.session;

      if (!_session?.access_token) {
        window.location.href = '/?auth=login&next=/pengaturan-akun';
        return;
      }

      // 3. Load data & render
      await loadData();
      loadPrefs();
      _bindAvatarInput();
      _bindCharCounters();
      _hideLoader();
      _animateIn();

    } catch (err) {
      console.error('[AccSettings] init error:', err);
      _fatalError('Gagal memuat halaman. Coba refresh.');
    }
  }

  function _detectMobile() {
    if (window.innerWidth < 768) {
      _sidebarOpen = false;
      _applySidebarState();
    }
  }

  function _hideLoader() {
    const loader = document.getElementById('page-loader');
    if (loader) loader.classList.add('hidden');
  }

  function _animateIn() {
    if (typeof gsap === 'undefined') return;
    gsap.from('#page-content > *', {
      opacity: 0,
      y: 16,
      duration: 0.4,
      stagger: 0.06,
      ease: 'power2.out',
      delay: 0.1,
    });
  }

  function _fatalError(msg) {
    const loader = document.getElementById('page-loader');
    if (loader) {
      loader.innerHTML = `<div style="text-align:center;padding:24px;">
        <p style="color:#EF4444;font-size:14px;margin-bottom:16px;">${msg}</p>
        <a href="/" style="color:#FACC15;font-size:13px;">← Kembali ke Dashboard</a>
      </div>`;
    }
  }

  // ─── Sidebar ──────────────────────────────────────────────
  function toggleSidebar() {
    _sidebarOpen = !_sidebarOpen;
    _applySidebarState();
  }

  function closeSidebar() {
    _sidebarOpen = false;
    _applySidebarState();
  }

  function _applySidebarState() {
    const sidebar  = document.getElementById('sidebar');
    const mainWrap = document.getElementById('main-wrap');
    const overlay  = document.getElementById('sidebar-overlay');
    const isMobile = window.innerWidth < 768;

    if (isMobile) {
      sidebar?.classList.toggle('mobile-open', _sidebarOpen);
      overlay?.classList.toggle('show', _sidebarOpen);
    } else {
      sidebar?.classList.toggle('collapsed', !_sidebarOpen);
      mainWrap?.classList.toggle('sidebar-hidden', !_sidebarOpen);
      overlay?.classList.remove('show');
    }
  }

  // ─── Nav (scroll to section) ──────────────────────────────
  function navTo(section) {
    const el = document.getElementById(`section-${section}`);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });

    // Update active nav item
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    const navEl = document.getElementById(`nav-${section}`);
    if (navEl) navEl.classList.add('active');

    if (window.innerWidth < 768) closeSidebar();
  }

  // ─── Data Loading ─────────────────────────────────────────
  async function loadData() {
    try {
      const res  = await fetch('/api/account/me', {
        headers: { 'Authorization': `Bearer ${_session.access_token}` }
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      _data = await res.json();
      _populateAll(_data);
    } catch (err) {
      console.error('[AccSettings] loadData error:', err);
      _toast('error', 'Gagal memuat data akun. Coba refresh.');
    }
  }

  function _populateAll(d) {
    if (!d) return;
    const auth    = d.auth    || {};
    const profile = d.profile || {};
    const umkm    = d.umkm   || {};

    // ── Profil ──
    _setVal('field-email',    auth.email    || profile.email || '');
    _setVal('field-nama',     profile.nama  || '');
    _setVal('field-fullname', profile.full_name || auth.email?.split('@')[0] || '');
    _setVal('field-phone',    profile.phone || auth.phone || '');

    // Avatar
    const initial = _getInitial(profile.nama || auth.email || '?');
    const avatarCircle = document.getElementById('avatar-circle');
    if (avatarCircle) {
      if (profile.avatar_url) {
        avatarCircle.innerHTML = `<img src="${profile.avatar_url}" alt="Avatar" />`;
      } else {
        avatarCircle.innerHTML = `<span style="font-size:28px;font-weight:800;">${initial}</span>`;
      }
    }

    // Topbar avatar
    const topbarAvatar = document.getElementById('topbar-avatar');
    if (topbarAvatar) {
      if (profile.avatar_url) {
        topbarAvatar.innerHTML = `<img src="${profile.avatar_url}" alt="" style="width:100%;height:100%;object-fit:cover;border-radius:50%;" />`;
      } else {
        topbarAvatar.innerHTML = `<span style="font-size:12px;font-weight:700;">${initial}</span>`;
      }
    }

    // ── Bisnis ──
    _setVal('field-biz-name',     umkm.business_name || '');
    _setVal('field-biz-cat',      umkm.category      || '');
    _setVal('field-biz-province', umkm.province      || '');
    _setVal('field-biz-city',     umkm.city          || '');
    _setVal('field-biz-desc',     umkm.business_description || '');
    _setVal('field-biz-rev',      umkm.avg_monthly_revenue  || '');
    _setVal('field-biz-margin',   umkm.margin_pct           || '');

    // ── Plan / Langganan ──
    const isPro  = d.is_pro;
    const tier   = d.tier || 'free';
    const planName  = document.getElementById('plan-name-display');
    const planBadge = document.getElementById('plan-badge');
    const planCTA   = document.getElementById('plan-cta-wrap');
    if (planName)  planName.textContent = tier.toUpperCase();
    if (planBadge) {
      planBadge.textContent = tier.toUpperCase();
      planBadge.className = `plan-badge ${tier}`;
    }
    if (planCTA && isPro) {
      planCTA.innerHTML = `<span style="color:var(--gold);font-size:13px;font-weight:600;">✦ Akun Pro Aktif</span>`;
    }

    // ── Login history ──
    const lastSignIn = auth.last_sign_in_at;
    if (lastSignIn) {
      const el = document.getElementById('last-login-time');
      if (el) {
        const d2 = new Date(lastSignIn);
        el.textContent = isNaN(d2) ? lastSignIn : d2.toLocaleString('id-ID', { dateStyle: 'medium', timeStyle: 'short' });
      }
    }

    // Device info
    const deviceEl = document.getElementById('last-login-device');
    if (deviceEl) {
      const ua = navigator.userAgent;
      let device = 'Browser Desktop';
      if (/Mobile|Android/.test(ua)) device = 'Perangkat Mobile';
      deviceEl.textContent = device + ' — Sesi Aktif Saat Ini';
    }

    // Update char counters
    _updateCharCounter('field-nama',     'cc-nama',  60);
    _updateCharCounter('field-biz-desc', 'cc-desc', 200);
  }

  // ─── Avatar ──────────────────────────────────────────────
  function _bindAvatarInput() {
    const input = document.getElementById('avatar-input');
    if (!input) return;
    input.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (!file) return;
      if (file.size > 5 * 1024 * 1024) {
        _toast('error', 'Ukuran file maks 5MB ya.');
        return;
      }
      const reader = new FileReader();
      reader.onload = (ev) => {
        const img = new Image();
        img.onload = () => {
          const canvas = document.createElement('canvas');
          canvas.width = canvas.height = 200;
          const ctx = canvas.getContext('2d');

          // Center-crop
          const size = Math.min(img.width, img.height);
          const sx   = (img.width  - size) / 2;
          const sy   = (img.height - size) / 2;
          ctx.drawImage(img, sx, sy, size, size, 0, 0, 200, 200);

          _avatarDataUrl = canvas.toDataURL('image/jpeg', 0.82);

          // Render preview
          const circle = document.getElementById('avatar-circle');
          if (circle) circle.innerHTML = `<img src="${_avatarDataUrl}" alt="Preview" style="width:100%;height:100%;object-fit:cover;" />`;
        };
        img.src = ev.target.result;
      };
      reader.readAsDataURL(file);
    });
  }

  // ─── Char Counters ───────────────────────────────────────
  function _bindCharCounters() {
    _bindCounter('field-nama',     'cc-nama',  60);
    _bindCounter('field-biz-desc', 'cc-desc', 200);
  }

  function _bindCounter(fieldId, counterId, max) {
    const field = document.getElementById(fieldId);
    const counter = document.getElementById(counterId);
    if (!field || !counter) return;
    field.addEventListener('input', () => {
      counter.textContent = field.value.length;
      counter.style.color = field.value.length >= max * 0.9 ? 'var(--danger)' : 'var(--text-faint)';
    });
  }

  function _updateCharCounter(fieldId, counterId, max) {
    const field   = document.getElementById(fieldId);
    const counter = document.getElementById(counterId);
    if (!field || !counter) return;
    counter.textContent = field.value.length;
  }

  // ─── Save Profil ─────────────────────────────────────────
  async function saveProfil() {
    const btn = document.getElementById('btn-save-profil');
    _setLoading(btn, true, 'Menyimpan...');

    const payload = {
      nama:      _getVal('field-nama'),
      full_name: _getVal('field-fullname'),
      phone:     _getVal('field-phone'),
    };

    if (_avatarDataUrl) payload.avatar_url = _avatarDataUrl;

    try {
      const res = await fetch('/api/account/update-profile', {
        method:  'POST',
        headers: {
          'Content-Type':  'application/json',
          'Authorization': `Bearer ${_session.access_token}`,
        },
        body: JSON.stringify(payload),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error || 'Gagal menyimpan profil.');
      _avatarDataUrl = null;
      _toast('success', 'Profil berhasil disimpan!');
    } catch (err) {
      _toast('error', err.message || 'Gagal menyimpan profil.');
    } finally {
      _setLoading(btn, false, '<i class="fa-solid fa-check"></i> Simpan Profil');
    }
  }

  function cancelProfil() {
    if (_data) _populateAll(_data);
    _avatarDataUrl = null;
  }

  // ─── Save Bisnis ─────────────────────────────────────────
  async function saveBisnis() {
    const btn = document.getElementById('btn-save-bisnis');
    _setLoading(btn, true, 'Menyimpan...');

    const payload = {
      business_name:        _getVal('field-biz-name'),
      category:             _getVal('field-biz-cat'),
      province:             _getVal('field-biz-province'),
      city:                 _getVal('field-biz-city'),
      business_description: _getVal('field-biz-desc'),
      avg_monthly_revenue:  _getNum('field-biz-rev'),
      margin_pct:           _getNum('field-biz-margin'),
    };

    try {
      const res = await fetch('/api/account/update-umkm', {
        method:  'POST',
        headers: {
          'Content-Type':  'application/json',
          'Authorization': `Bearer ${_session.access_token}`,
        },
        body: JSON.stringify(payload),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error || 'Gagal menyimpan data bisnis.');
      _toast('success', 'Data bisnis berhasil disimpan!');
    } catch (err) {
      _toast('error', err.message || 'Gagal menyimpan data bisnis.');
    } finally {
      _setLoading(btn, false, '<i class="fa-solid fa-check"></i> Simpan Data Bisnis');
    }
  }

  function cancelBisnis() {
    if (_data?.umkm) {
      const u = _data.umkm;
      _setVal('field-biz-name',     u.business_name || '');
      _setVal('field-biz-cat',      u.category      || '');
      _setVal('field-biz-province', u.province      || '');
      _setVal('field-biz-city',     u.city          || '');
      _setVal('field-biz-desc',     u.business_description || '');
      _setVal('field-biz-rev',      u.avg_monthly_revenue  || '');
      _setVal('field-biz-margin',   u.margin_pct           || '');
    }
  }

  // ─── Preferences ─────────────────────────────────────────
  function loadPrefs() {
    try {
      const saved = JSON.parse(localStorage.getItem(PREFS_KEY) || '{}');
      _setVal('pref-lang',         saved.lang         || 'id');
      _setVal('pref-theme',        saved.theme        || 'dark');
      _setCheck('pref-notif-trend',  Boolean(saved.notif_trend));
      _setCheck('pref-notif-email',  Boolean(saved.notif_email));
      _setCheck('pref-save-history', saved.save_history !== false);
    } catch (_) {}
  }

  function savePrefs() {
    const prefs = {
      lang:         _getVal('pref-lang'),
      theme:        _getVal('pref-theme'),
      notif_trend:  _getCheck('pref-notif-trend'),
      notif_email:  _getCheck('pref-notif-email'),
      save_history: _getCheck('pref-save-history'),
    };
    localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
    _toast('success', 'Preferensi disimpan ke perangkat ini!');
  }

  // ─── Password ─────────────────────────────────────────────
  function checkPwStrength(value) {
    const fill  = document.getElementById('pw-fill');
    const label = document.getElementById('pw-label');
    if (!fill || !label) return;

    let score = 0;
    if (value.length >= 8)  score++;
    if (/[A-Z]/.test(value)) score++;
    if (/[0-9]/.test(value)) score++;
    if (/[^A-Za-z0-9]/.test(value)) score++;

    const levels = [
      { pct: '0%',   color: 'transparent', text: 'Masukkan password baru',  tColor: 'var(--text-faint)' },
      { pct: '25%',  color: '#EF4444',     text: 'Sangat Lemah',            tColor: '#EF4444' },
      { pct: '50%',  color: '#F97316',     text: 'Lemah',                   tColor: '#F97316' },
      { pct: '75%',  color: '#EAB308',     text: 'Cukup Kuat',              tColor: '#EAB308' },
      { pct: '100%', color: '#22C55E',     text: 'Kuat ✓',                 tColor: '#22C55E' },
    ];

    const lvl = levels[value.length === 0 ? 0 : Math.min(score + 1, 4)];
    fill.style.width      = lvl.pct;
    fill.style.background = lvl.color;
    label.textContent     = lvl.text;
    label.style.color     = lvl.tColor;
  }

  function togglePw(fieldId, btn) {
    const field = document.getElementById(fieldId);
    if (!field) return;
    const isText = field.type === 'text';
    field.type = isText ? 'password' : 'text';
    const icon = btn.querySelector('i');
    if (icon) icon.className = `fa-regular ${isText ? 'fa-eye' : 'fa-eye-slash'}`;
  }

  async function changePassword() {
    const newPw     = _getVal('field-pw-new');
    const confirmPw = _getVal('field-pw-confirm');
    const btn       = document.getElementById('btn-change-pw');

    if (!newPw || newPw.length < 8) {
      _toast('error', 'Password minimal 8 karakter ya.');
      return;
    }
    if (newPw !== confirmPw) {
      _toast('error', 'Konfirmasi password tidak cocok.');
      return;
    }

    _setLoading(btn, true, 'Mengganti...');
    try {
      const { error } = await sb.auth.updateUser({ password: newPw });
      if (error) throw error;
      _setVal('field-pw-new', '');
      _setVal('field-pw-confirm', '');
      checkPwStrength('');
      _toast('success', 'Password berhasil diganti!');
    } catch (err) {
      _toast('error', err.message || 'Gagal mengganti password.');
    } finally {
      _setLoading(btn, false, '<i class="fa-solid fa-lock"></i> Ganti Password');
    }
  }

  // ─── Danger Zone ─────────────────────────────────────────
  function confirmDeleteBizData() {
    const confirmed = window.confirm(
      '⚠️ Hapus semua data bisnis kamu?\n\nTindakan ini TIDAK bisa dibatalkan. Data UMKM akan hilang permanen.\n\nLanjutkan?'
    );
    if (!confirmed) return;

    _deleteUmkm();
  }

  async function _deleteUmkm() {
    try {
      const res = await fetch('/api/account/delete-umkm', {
        method:  'POST',
        headers: { 'Authorization': `Bearer ${_session.access_token}` },
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error || 'Gagal menghapus data.');
      _toast('success', 'Data bisnis berhasil dihapus.');
      // Clear bisnis fields
      ['field-biz-name','field-biz-cat','field-biz-province','field-biz-city',
       'field-biz-desc','field-biz-rev','field-biz-margin'].forEach(id => _setVal(id, ''));
    } catch (err) {
      _toast('error', err.message || 'Gagal menghapus data bisnis.');
    }
  }

  // ─── Logout ──────────────────────────────────────────────
  async function logout() {
    const confirmed = window.confirm('Yakin mau keluar dari Sentra AI?');
    if (!confirmed) return;

    try {
      if (sb) {
        await Promise.race([
          sb.auth.signOut(),
          new Promise(resolve => setTimeout(resolve, 4000))
        ]);
      }
    } catch (_) {}

    // Wipe Supabase tokens
    try {
      Object.keys(localStorage)
        .filter(k => k.startsWith('sb-') || k.includes('supabase'))
        .forEach(k => localStorage.removeItem(k));
    } catch (_) {}

    window.location.href = '/';
  }

  // ─── Toast System ─────────────────────────────────────────
  function _toast(type, msg, durationMs = 3500) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const icon = type === 'success' ? 'fa-circle-check' : 'fa-circle-exclamation';
    const el   = document.createElement('div');
    el.className = `toast ${type}`;
    el.innerHTML = `
      <i class="fa-solid ${icon} toast-icon"></i>
      <span class="toast-msg">${msg}</span>
    `;
    container.appendChild(el);

    setTimeout(() => {
      el.style.opacity = '0';
      el.style.transition = 'opacity .3s';
      setTimeout(() => el.remove(), 350);
    }, durationMs);
  }

  // ─── DOM Helpers ──────────────────────────────────────────
  function _getVal(id) {
    return (document.getElementById(id)?.value || '').trim();
  }

  function _setVal(id, val) {
    const el = document.getElementById(id);
    if (el) el.value = val ?? '';
  }

  function _getNum(id) {
    const v = parseFloat(_getVal(id));
    return isNaN(v) ? null : v;
  }

  function _getCheck(id) {
    return Boolean(document.getElementById(id)?.checked);
  }

  function _setCheck(id, val) {
    const el = document.getElementById(id);
    if (el) el.checked = Boolean(val);
  }

  function _setLoading(btn, loading, htmlContent) {
    if (!btn) return;
    btn.disabled = loading;
    if (!loading) btn.innerHTML = htmlContent;
    else btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> &nbsp;';
  }

  function _getInitial(name) {
    return (name || '?').charAt(0).toUpperCase();
  }

  // ─── Auto-init ────────────────────────────────────────────
  window.addEventListener('DOMContentLoaded', init);

  // ─── Public API ───────────────────────────────────────────
  return {
    toggleSidebar,
    closeSidebar,
    navTo,
    saveProfil,
    cancelProfil,
    saveBisnis,
    cancelBisnis,
    savePrefs,
    changePassword,
    checkPwStrength,
    togglePw,
    confirmDeleteBizData,
    logout,
  };
})();
