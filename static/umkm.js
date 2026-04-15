// Sentra AI — UMKM Dashboard Shell (Vanilla + GSAP)
(function () {
  const LS_MODE_KEY = 'sentra_mode';
  const LS_ONBOARD_KEY = 'sentra_onboarding_done';

  const el = {
    onboardingOverlay: () => document.getElementById('onboarding-overlay'),
    onboardingModal: () => document.getElementById('onboarding-modal'),
    shell: () => document.getElementById('umkm-shell'),
    navItems: () => Array.from(document.querySelectorAll('.umkm-nav-item')),
    pages: () => Array.from(document.querySelectorAll('.umkm-page')),
    title: () => document.getElementById('umkm-title'),
    eyebrow: () => document.getElementById('umkm-eyebrow'),
  };

  const PAGE_META = {
    home: { title: 'Beranda Usaha', eyebrow: 'Dashboard UMKM' },
    'my-analysis': { title: 'Analisis Usaha Saya', eyebrow: 'Dashboard UMKM' },
    competitors: { title: 'Analisis Pesaing', eyebrow: 'Dashboard UMKM' },
    'business-plan': { title: 'Rencana Bisnis AI', eyebrow: 'Dashboard UMKM' },
    promo: { title: 'Strategi Promosi', eyebrow: 'Dashboard UMKM' },
    'local-trends': { title: 'Tren Pasar Lokal', eyebrow: 'Dashboard UMKM' },
    reports: { title: 'Laporan & PDF', eyebrow: 'Dashboard UMKM' },
    settings: { title: 'Pengaturan Usaha', eyebrow: 'Dashboard UMKM' },
  };

  function getUserId() {
    try {
      return (localStorage.getItem('sentra_uid') || '').trim();
    } catch (_) {
      return '';
    }
  }

  function withUserId(url) {
    const uid = getUserId();
    if (!uid) return url;
    const u = new URL(url, window.location.origin);
    u.searchParams.set('user_id', uid);
    return u.toString();
  }

  function lockScroll(on) {
    document.body.style.overflow = on ? 'hidden' : '';
    if (document.documentElement) document.documentElement.style.overflow = on ? 'hidden' : '';
  }

  function gsapIn(node) {
    if (typeof gsap === 'undefined' || !node) return;
    gsap.fromTo(node, { y: 12, opacity: 0 }, { y: 0, opacity: 1, duration: 0.5, ease: 'power3.out' });
  }

  function openOnboarding(force = false) {
    const done = localStorage.getItem(LS_ONBOARD_KEY) === '1';
    if (done && !force) return;
    const overlay = el.onboardingOverlay();
    const modal = el.onboardingModal();
    if (!overlay || !modal) return;
    overlay.classList.remove('hidden');
    lockScroll(true);
    if (typeof gsap !== 'undefined') {
      gsap.set(modal, { y: 18, opacity: 0, scale: 0.98, transformOrigin: 'center center' });
      gsap.to(modal, { y: 0, opacity: 1, scale: 1, duration: 0.55, ease: 'power3.out' });
    }
  }

  function closeOnboarding() {
    const overlay = el.onboardingOverlay();
    if (!overlay) return;
    overlay.classList.add('hidden');
    // only unlock if UMKM shell not open
    const shellOpen = !el.shell()?.classList.contains('hidden');
    if (!shellOpen) lockScroll(false);
  }

  function showUMKMShell(show) {
    const shell = el.shell();
    const stickyNav = document.getElementById('sticky-nav');
    const mainHeader = document.querySelector('header');
    if (!shell) return;
    if (show) {
      shell.classList.remove('hidden');
      if (stickyNav) stickyNav.classList.add('hidden');
      if (mainHeader && !mainHeader.classList.contains('umkm-topbar')) mainHeader.classList.add('hidden');
      lockScroll(true);
      gsapIn(shell);
    } else {
      shell.classList.add('hidden');
      if (stickyNav) stickyNav.classList.remove('hidden');
      if (mainHeader && !mainHeader.classList.contains('umkm-topbar')) mainHeader.classList.remove('hidden');
      lockScroll(false);
    }
  }

  function isMobile() {
    return window.matchMedia && window.matchMedia('(max-width: 980px)').matches;
  }

  function openMobileNav() {
    const shell = el.shell();
    const overlay = document.getElementById('umkm-side-overlay');
    if (!shell) return;
    shell.classList.add('mobile-nav-open');
    if (overlay) overlay.classList.remove('hidden');
  }

  function closeMobileNav() {
    const shell = el.shell();
    const overlay = document.getElementById('umkm-side-overlay');
    if (!shell) return;
    shell.classList.remove('mobile-nav-open');
    if (overlay) overlay.classList.add('hidden');
  }

  function toggleMobileNav() {
    const shell = el.shell();
    if (!shell) return;
    if (shell.classList.contains('mobile-nav-open')) closeMobileNav();
    else openMobileNav();
  }

  function setMode(mode) {
    localStorage.setItem(LS_MODE_KEY, mode);
    localStorage.setItem(LS_ONBOARD_KEY, '1');
    closeOnboarding();

    if (mode === 'umkm') {
      showUMKMShell(true);
      goTo('home');
      return;
    }
    showUMKMShell(false);
  }

  function selectMode(mode) {
    setMode(mode);
  }

  function goTo(pageId) {
    const meta = PAGE_META[pageId] || PAGE_META.home;
    el.navItems().forEach((btn) => btn.classList.toggle('active', btn.dataset.umkmPage === pageId));
    el.pages().forEach((p) => p.classList.toggle('active', p.dataset.umkmPage === pageId));
    if (el.title()) el.title().textContent = meta.title;
    if (el.eyebrow()) el.eyebrow().textContent = meta.eyebrow;

    const activePage = document.querySelector(`.umkm-page[data-umkm-page="${pageId}"]`);
    gsapIn(activePage);

    // lazily init local map when opening local-trends
    if (pageId === 'local-trends') {
      initUMKMLocalMap();
    }

    if (isMobile()) closeMobileNav();
  }

  // ---- Minimal local map (Leaflet) for UMKM page ----
  let _umkmMap = null;
  let _umkmLayer = null;

  const PROVINCE_COORDS = {
    "Aceh": [5.55, 95.32],
    "Sumatera Utara": [3.58, 98.67],
    "Sumatera Barat": [-0.95, 100.35],
    "Riau": [0.51, 101.45],
    "Kepulauan Riau": [1.08, 104.03],
    "Jambi": [-1.59, 103.61],
    "Sumatera Selatan": [-2.99, 104.76],
    "Bengkulu": [-3.79, 102.26],
    "Lampung": [-5.45, 105.27],
    "Kepulauan Bangka Belitung": [-2.13, 106.11],
    "Banten": [-6.12, 106.15],
    "DKI Jakarta": [-6.20, 106.85],
    "Jawa Barat": [-6.91, 107.61],
    "Jawa Tengah": [-6.97, 110.42],
    "DI Yogyakarta": [-7.80, 110.37],
    "Jawa Timur": [-7.25, 112.75],
    "Bali": [-8.65, 115.22],
    "Nusa Tenggara Barat": [-8.58, 116.10],
    "Nusa Tenggara Timur": [-10.17, 123.60],
    "Kalimantan Barat": [-0.03, 109.34],
    "Kalimantan Tengah": [-2.20, 113.92],
    "Kalimantan Selatan": [-3.32, 114.59],
    "Kalimantan Timur": [-0.50, 117.15],
    "Kalimantan Utara": [2.84, 117.36],
    "Sulawesi Utara": [1.49, 124.84],
    "Gorontalo": [0.54, 123.06],
    "Sulawesi Tengah": [-0.89, 119.87],
    "Sulawesi Barat": [-2.68, 118.89],
    "Sulawesi Selatan": [-5.14, 119.41],
    "Sulawesi Tenggara": [-3.99, 122.51],
    "Maluku": [-3.70, 128.17],
    "Maluku Utara": [0.79, 127.38],
    "Papua Barat": [-0.86, 134.06],
    "Papua Barat Daya": [-0.87, 131.25],
    "Papua": [-2.54, 140.72]
  };

  function getIntensityMeta(value) {
    const score = Math.max(0, Math.min(100, Number(value) || 0));
    if (score < 25) return { level: "Rendah", color: "#6B7280", fillOpacity: 0.45 };
    if (score < 50) return { level: "Sedang", color: "#FACC15", fillOpacity: 0.58 };
    if (score < 75) return { level: "Tinggi", color: "#F97316", fillOpacity: 0.66 };
    return { level: "Tertinggi", color: "#FDE047", fillOpacity: 0.78 };
  }

  function getRadius(score) {
    const safe = Math.max(0, Math.min(100, Number(score) || 0));
    return 9000 + safe * 1500;
  }

  function renderUMKMCircles(regional) {
    if (!_umkmMap || !_umkmLayer || typeof L === 'undefined') return;
    _umkmLayer.clearLayers();
    const rows = Array.isArray(regional) ? regional : [];

    const normalized = rows
      .map((r) => ({
        province: (r.province || r.name || '').toString().trim(),
        value: Math.max(0, Math.min(100, Number(r.value) || 0))
      }))
      .filter((r) => PROVINCE_COORDS[r.province]);

    const sorted = [...normalized].sort((a, b) => b.value - a.value);
    const ranking = new Map(sorted.map((it, idx) => [it.province, idx + 1]));

    normalized.forEach((it, idx) => {
      const meta = getIntensityMeta(it.value);
      const isPeak = it.value >= 75;
      const circle = L.circle(PROVINCE_COORDS[it.province], {
        radius: getRadius(it.value),
        color: meta.color,
        weight: isPeak ? 2.5 : 1.8,
        fillColor: meta.color,
        fillOpacity: meta.fillOpacity,
        className: isPeak ? "heat-circle peak" : "heat-circle"
      });

      circle.bindTooltip(
        `
          <div class="sentra-map-tooltip">
            <div class="sentra-map-tooltip-title">${it.province}</div>
            <div class="sentra-map-tooltip-row"><span>Skor Minat</span><strong>${it.value}%</strong></div>
            <div class="sentra-map-tooltip-row"><span>Ranking</span><strong>#${ranking.get(it.province)}</strong></div>
            <div class="sentra-map-tooltip-row"><span>Kategori</span><strong>${meta.level}</strong></div>
          </div>
        `,
        { sticky: true, direction: "top", offset: [0, -10], opacity: 1 }
      );

      circle.addTo(_umkmLayer);
      const el = circle.getElement && circle.getElement();
      if (el && typeof gsap !== "undefined") {
        gsap.set(el, { scale: 0.25, opacity: 0, transformOrigin: "center center" });
        gsap.to(el, { scale: 1, opacity: 1, duration: 0.5, delay: idx * 0.04, ease: "power3.out" });
      }
    });

    setTimeout(() => _umkmMap.invalidateSize(), 80);
  }

  function initUMKMLocalMap() {
    const mapEl = document.getElementById('umkm-local-map');
    if (!mapEl || typeof L === 'undefined') return;
    if (_umkmMap) {
      setTimeout(() => _umkmMap.invalidateSize(), 80);
      return;
    }

    _umkmMap = L.map('umkm-local-map', {
      zoomControl: true,
      attributionControl: false,
      scrollWheelZoom: false,
      tap: true
    }).setView([-2.4, 118], 5);

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', { maxZoom: 18, attribution: '&copy; CARTO' }).addTo(_umkmMap);
    _umkmLayer = L.layerGroup().addTo(_umkmMap);

    const loader = document.getElementById('umkm-map-loader');
    if (loader) loader.style.display = 'none';
    setTimeout(() => _umkmMap.invalidateSize(), 120);
  }

  function fillHomeFromAnalyze(payload) {
    const metrics = payload?.metrics || {};
    const hs = document.getElementById('umkm-health-score');
    const wo = document.getElementById('umkm-weekly-opportunity');
    const focus = document.getElementById('umkm-focus');
    if (hs) hs.textContent = (metrics.health_score ?? '—') + (metrics.health_score != null ? '/100' : '');
    if (wo) wo.textContent = metrics.weekly_opportunity || '—';
    if (focus) focus.textContent = metrics.focus || '—';

    const list = document.getElementById('umkm-reco-list');
    if (list) {
      const recos = [
        `Coba rapikan 1 paket best-seller: bikin nama paket + harga + isi yang jelas (biar orang nggak mikir lama).`,
        `Ambil 1 channel utama minggu ini (WA/IG/GoFood). Fokus konsisten 7 hari biar kelihatan hasilnya.`,
        `Naikkan repeat order: bikin promo “datang lagi” (voucher kecil / bonus topping / diskon 10%).`
      ];
      list.innerHTML = recos.map((t, i) => `
        <div class="umkm-list-item" style="align-items:center;">
          <div>
            <div class="umkm-list-title">Langkah ${i + 1}</div>
            <div class="umkm-list-sub">${t}</div>
          </div>
          <div class="umkm-rating">★</div>
        </div>
      `).join('');
    }

    // mini charts (simple, premium)
    try {
      if (typeof Chart !== 'undefined') {
        const mk = document.getElementById('umkm-mini-market');
        const sl = document.getElementById('umkm-mini-sales');
        const pr = document.getElementById('umkm-mini-promo');
        const series = [20, 28, 35, 42, 52, 60, 66].map((v) => v + (metrics.health_score ? (metrics.health_score - 55) / 6 : 0));
        const labels = ['S', 'S', 'R', 'K', 'J', 'S', 'M'];

        const mkChart = mk && new Chart(mk.getContext('2d'), {
          type: 'line',
          data: { labels, datasets: [{ data: series, borderColor: '#FACC15', backgroundColor: 'rgba(250,204,21,0.12)', tension: 0.35, fill: true, pointRadius: 0 }] },
          options: { plugins: { legend: { display: false } }, scales: { x: { display: false }, y: { display: false } } }
        });
        const slChart = sl && new Chart(sl.getContext('2d'), {
          type: 'bar',
          data: { labels, datasets: [{ data: series.map((v) => Math.max(4, v / 8)), backgroundColor: 'rgba(250,204,21,0.22)', borderColor: 'rgba(250,204,21,0.55)', borderWidth: 1, borderRadius: 8 }] },
          options: { plugins: { legend: { display: false } }, scales: { x: { display: false }, y: { display: false } } }
        });
        const prChart = pr && new Chart(pr.getContext('2d'), {
          type: 'line',
          data: { labels, datasets: [{ data: series.map((v, i) => Math.max(8, v / 2) - i * 2), borderColor: '#F97316', backgroundColor: 'rgba(249,115,22,0.10)', tension: 0.35, fill: true, pointRadius: 0 }] },
          options: { plugins: { legend: { display: false } }, scales: { x: { display: false }, y: { display: false } } }
        });
        // avoid lint unused
        void mkChart; void slChart; void prChart;
      }
    } catch (_) { /* ignore charts */ }
  }

  async function refreshLocalTrendsFromProfile(profile) {
    const keyword = (profile?.category || profile?.business_name || '').toString().trim();
    if (!keyword) return;
    try {
      const uid = getUserId();
      const res = await fetch('/api/analyze-local', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keyword, geo: 'ID', user_id: uid || undefined })
      });
      const data = await res.json();
      const regional = data?.regional_breakdown || data?.regional_data || [];
      renderUMKMCircles(regional);
    } catch (_) { /* silent */ }
  }

  // ---- API hooks (scaffold) ----
  async function loadProfile() {
    const out = document.getElementById('umkm-settings-output');
    if (out) out.textContent = 'Memuat profil...';
    try {
      const res = await fetch(withUserId('/api/umkm/profile'), { method: 'GET' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Gagal memuat profil');
      if (out) out.textContent = JSON.stringify(data.profile || {}, null, 2);

      // also reflect into home
      if (data.profile && Object.keys(data.profile).length > 0) {
        // attempt quick analyze refresh (non-blocking)
        submitProfileAndAnalyze({ ...data.profile, user_id: getUserId() });
        refreshLocalTrendsFromProfile(data.profile);
      }
    } catch (e) {
      if (out) out.textContent = String(e.message || e);
    }
  }

  async function runQuickCheck() {
    goTo('my-analysis');
    const form = document.getElementById('umkm-profile-form');
    if (form) {
      if (typeof gsap !== 'undefined') gsap.fromTo(form, { y: 8, opacity: 0.8 }, { y: 0, opacity: 1, duration: 0.35 });
    }
  }

  async function submitProfileAndAnalyze(payload) {
    const box = document.getElementById('umkm-analysis-output');
    const insight = document.getElementById('umkm-analysis-insight');
    if (box) box.style.display = 'block';
    if (insight) insight.textContent = 'Lagi aku cek pelan-pelan ya...';

    try {
      payload = { ...payload, user_id: getUserId() || payload.user_id };
      const res = await fetch('/api/umkm/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Gagal analisis');
      if (insight) insight.textContent = data.insight || 'Oke, analisis sudah selesai.';
      fillHomeFromAnalyze(data);
      if (data.profile) refreshLocalTrendsFromProfile(data.profile);
    } catch (e) {
      if (insight) insight.textContent = String(e.message || e);
    }
  }

  async function generatePlan() {
    const out = document.getElementById('umkm-plan-output');
    if (out) out.textContent = 'Menyusun rencana...';
    try {
      const res = await fetch('/api/umkm/plan', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_id: getUserId() }) });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Gagal membuat rencana');
      if (out) out.textContent = data.plan || '';
    } catch (e) {
      if (out) out.textContent = String(e.message || e);
    }
  }

  async function generatePromo() {
    const out = document.getElementById('umkm-promo-output');
    if (out) out.textContent = 'Nyari ide promosi yang pas...';
    try {
      const res = await fetch('/api/umkm/promo', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_id: getUserId() }) });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Gagal generate promo');
      if (out) out.textContent = data.promo || '';
    } catch (e) {
      if (out) out.textContent = String(e.message || e);
    }
  }

  async function findCompetitors() {
    const q = (document.getElementById('umkm-competitor-query')?.value || '').trim();
    const list = document.getElementById('umkm-competitor-list');
    if (list) list.innerHTML = '<div class="umkm-skeleton">Lagi cari pesaing di sekitar...</div>';
    try {
      const res = await fetch('/api/umkm/competitors', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q, user_id: getUserId() })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Gagal cari pesaing');
      const rows = data.results || [];
      if (!list) return;
      if (rows.length === 0) {
        list.innerHTML = '<div class="umkm-muted">Belum ketemu hasil. Coba kata kunci yang lebih umum ya.</div>';
        return;
      }
      list.innerHTML = rows.map((r) => `
        <div class="umkm-list-item">
          <div>
            <div class="umkm-list-title">${r.name || '—'}</div>
            <div class="umkm-list-sub">${r.address || ''}</div>
          </div>
          <div class="umkm-list-meta">
            <div class="umkm-rating">${r.rating ? `★ ${r.rating}` : '—'}</div>
            <div class="umkm-muted">${r.user_ratings_total ? `${r.user_ratings_total} ulasan` : ''}</div>
          </div>
        </div>
      `).join('');
    } catch (e) {
      if (list) list.innerHTML = `<div class="umkm-muted">${String(e.message || e)}</div>`;
    }
  }

  function downloadReport() {
    alert('PDF UMKM: segera. Setelah endpoint siap, tombol ini akan download report usaha.');
  }

  function resetMode() {
    localStorage.removeItem(LS_MODE_KEY);
    localStorage.removeItem(LS_ONBOARD_KEY);
    openOnboarding(true);
  }

  function wire() {
    // overlay click closes onboarding
    el.onboardingOverlay()?.addEventListener('click', () => closeOnboarding());

    // sidebar nav
    el.navItems().forEach((btn) => {
      btn.addEventListener('click', () => goTo(btn.dataset.umkmPage));
    });

    // close drawer on ESC
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeMobileNav();
    });

    // profile form
    const form = document.getElementById('umkm-profile-form');
    if (form) {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        const fd = new FormData(form);
        const payload = Object.fromEntries(fd.entries());
        submitProfileAndAnalyze(payload);
      });
    }
  }

  function boot() {
    wire();
    const mode = localStorage.getItem(LS_MODE_KEY);
    const done = localStorage.getItem(LS_ONBOARD_KEY) === '1';

    if (!done) {
      openOnboarding(false);
      return;
    }
    if (mode === 'umkm') {
      showUMKMShell(true);
      goTo('home');
      // eager load profile to populate home
      setTimeout(() => loadProfile(), 350);
    }
  }

  window.SentraUMKM = {
    openOnboarding,
    closeOnboarding,
    selectMode,
    goTo,
    loadProfile,
    runQuickCheck,
    generatePlan,
    generatePromo,
    findCompetitors,
    downloadReport,
    resetMode,
    toggleMobileNav,
    closeMobileNav
  };

  document.addEventListener('DOMContentLoaded', boot);
})();

