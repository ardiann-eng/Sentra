// Sentra AI — UMKM Dashboard Shell (Vanilla + GSAP)
(function () {
  const LS_MODE_KEY = 'sentra_mode';
  const LS_ONBOARD_KEY = 'sentra_onboarding_done';
  const ONBOARDING_STEPS = {
    MODE: 'mode',
    UMKM: 'umkm'
  };

  const CATEGORY_OPTIONS = [
    { value: 'Kuliner & Minuman', label: 'Kuliner & Minuman', hint: 'Cafe, frozen food, bakery, minuman kemasan' },
    { value: 'Fashion', label: 'Fashion', hint: 'Pakaian, hijab, sepatu, aksesoris' },
    { value: 'Kecantikan & Perawatan', label: 'Kecantikan & Perawatan', hint: 'Skincare, kosmetik, body care, salon' },
    { value: 'Kerajinan & Dekorasi', label: 'Kerajinan & Dekorasi', hint: 'Souvenir, dekor rumah, handmade' },
    { value: 'Jasa', label: 'Jasa', hint: 'Laundry, desain, katering, servis, les' },
    { value: 'Rumah Tangga', label: 'Rumah Tangga', hint: 'Perabot, perlengkapan dapur, kebutuhan harian' },
    { value: 'Kesehatan', label: 'Kesehatan', hint: 'Herbal, alat kesehatan, kebutuhan wellness' },
    { value: 'Teknologi & Elektronik', label: 'Teknologi & Elektronik', hint: 'Aksesoris gadget, komputer, audio' },
    { value: 'Pertanian & Pangan', label: 'Pertanian & Pangan', hint: 'Hasil tani, olahan pangan, kebutuhan ternak' },
    { value: 'Lainnya', label: 'Lainnya', hint: 'Kategori usaha lain yang belum masuk daftar' }
  ];

  const PROVINCE_OPTIONS = [
    'Aceh', 'Sumatera Utara', 'Sumatera Barat', 'Riau', 'Jambi', 'Sumatera Selatan', 'Bengkulu', 'Lampung',
    'Kepulauan Bangka Belitung', 'Kepulauan Riau', 'DKI Jakarta', 'Jawa Barat', 'Jawa Tengah', 'DI Yogyakarta',
    'Jawa Timur', 'Banten', 'Bali', 'Nusa Tenggara Barat', 'Nusa Tenggara Timur', 'Kalimantan Barat',
    'Kalimantan Tengah', 'Kalimantan Selatan', 'Kalimantan Timur', 'Kalimantan Utara', 'Sulawesi Utara',
    'Sulawesi Tengah', 'Sulawesi Selatan', 'Sulawesi Tenggara', 'Gorontalo', 'Sulawesi Barat', 'Maluku',
    'Maluku Utara', 'Papua', 'Papua Barat', 'Papua Selatan', 'Papua Tengah', 'Papua Pegunungan', 'Papua Barat Daya'
  ].map((name) => ({ value: name, label: name, hint: 'Provinsi Indonesia' }));

  const PLATFORM_OPTIONS = [
    { value: 'WhatsApp', icon: 'fa-brands fa-whatsapp' },
    { value: 'Instagram', icon: 'fa-brands fa-instagram' },
    { value: 'TikTok Shop', icon: 'fa-brands fa-tiktok' },
    { value: 'Shopee', icon: 'fa-solid fa-bag-shopping' },
    { value: 'Tokopedia', icon: 'fa-solid fa-store' },
    { value: 'GoFood', icon: 'fa-solid fa-motorcycle' },
    { value: 'GrabFood', icon: 'fa-solid fa-bicycle' },
    { value: 'Website Sendiri', icon: 'fa-solid fa-globe' },
    { value: 'Offline / Toko Fisik', icon: 'fa-solid fa-shop' }
  ];

  const el = {
    onboardingOverlay: () => document.getElementById('onboarding-overlay'),
    onboardingModal: () => document.getElementById('onboarding-modal'),
    onboardingModeStep: () => document.getElementById('sentra-onboarding-mode-step'),
    onboardingUMKMStep: () => document.getElementById('sentra-onboarding-umkm-step'),
    onboardingForm: () => document.getElementById('umkm-onboarding-form'),
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

  const state = {
    onboardingStep: ONBOARDING_STEPS.MODE,
    selectedPlatforms: [],
    selects: [],
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

  function animateFormFocus(target) {
    if (typeof gsap === 'undefined' || !target) return;
    gsap.fromTo(target, { y: 0 }, { y: -2, duration: 0.18, yoyo: true, repeat: 1, ease: 'power2.out' });
  }

  function setOnboardingStep(step) {
    state.onboardingStep = step;
    const modeStep = el.onboardingModeStep();
    const umkmStep = el.onboardingUMKMStep();
    if (!modeStep || !umkmStep) return;

    const showUMKM = step === ONBOARDING_STEPS.UMKM;
    modeStep.classList.toggle('active', !showUMKM);
    umkmStep.classList.toggle('active', showUMKM);
    modeStep.setAttribute('aria-hidden', showUMKM ? 'true' : 'false');
    umkmStep.setAttribute('aria-hidden', showUMKM ? 'false' : 'true');

    const target = showUMKM ? umkmStep : modeStep;
    if (typeof gsap !== 'undefined') {
      gsap.fromTo(target, { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: 0.35, ease: 'power3.out' });
    }
  }

  function openOnboarding(force = false) {
    const done = localStorage.getItem(LS_ONBOARD_KEY) === '1';
    if (done && !force) return;
    const overlay = el.onboardingOverlay();
    const modal = el.onboardingModal();
    if (!overlay || !modal) return;
    overlay.classList.remove('hidden');
    lockScroll(true);
    setOnboardingStep(ONBOARDING_STEPS.MODE);
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

  function openUMKMOnboarding() {
    setOnboardingStep(ONBOARDING_STEPS.UMKM);
  }

  function openDashboard() {
    const done = localStorage.getItem(LS_ONBOARD_KEY) === '1';
    if (!done) {
      openOnboarding(true);
      openUMKMOnboarding();
    } else {
      showUMKMShell(true);
      goTo('home');
      setTimeout(() => loadProfile(), 300);
    }
  }

  function backToModeStep() {
    setOnboardingStep(ONBOARDING_STEPS.MODE);
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
    if (mode === 'umkm') {
      openUMKMOnboarding();
      return;
    }
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

  function fillDashboardFromProfile(profile) {
    if (!profile) return;
    const hs = document.getElementById('umkm-health-score');
    const wo = document.getElementById('umkm-weekly-opportunity');
    const focus = document.getElementById('umkm-focus');
    if (hs && hs.textContent === '—') hs.textContent = 'Mulai setup';
    if (wo) wo.textContent = profile.category || 'Kenali peluang pasar';
    if (focus) focus.textContent = profile.city || profile.province || 'Rapikan profil usaha';
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
      hydrateOnboardingForm(data.profile || {});

      // also reflect into home
      if (data.profile && Object.keys(data.profile).length > 0) {
        fillDashboardFromProfile(data.profile);
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
    resetOnboardingForm();
    openOnboarding(true);
  }

  function formatRupiahInput(value) {
    const digits = String(value || '').replace(/\D/g, '');
    if (!digits) return '';
    return new Intl.NumberFormat('id-ID').format(Number(digits));
  }

  function parseNumericInput(value) {
    const digits = String(value || '').replace(/\D/g, '');
    return digits ? Number(digits) : null;
  }

  function setFeedback(type, message) {
    const errorEl = document.getElementById('umkm-onboarding-error');
    const successEl = document.getElementById('umkm-onboarding-success');
    if (errorEl) {
      errorEl.textContent = type === 'error' ? message : '';
      errorEl.classList.toggle('hidden', type !== 'error');
    }
    if (successEl) {
      successEl.textContent = type === 'success' ? message : '';
      successEl.classList.toggle('hidden', type !== 'success');
    }
  }

  function setSubmitLoading(isLoading) {
    const btn = document.getElementById('umkm-onboarding-submit');
    const label = btn?.querySelector('.sentra-btn-label');
    const loader = btn?.querySelector('.sentra-btn-loader');
    if (!btn || !label || !loader) return;
    btn.disabled = isLoading;
    label.textContent = isLoading ? 'Menyimpan profil usaha...' : 'Simpan & Masuk ke Dashboard';
    loader.classList.toggle('hidden', !isLoading);
  }

  function updateDescriptionCount() {
    const textarea = document.getElementById('umkm-description');
    const counter = document.getElementById('umkm-description-count');
    if (!textarea || !counter) return;
    counter.textContent = `${textarea.value.length}/200`;
  }

  function renderPlatformChips(selected = []) {
    const wrap = document.getElementById('umkm-platform-chips');
    const hidden = document.getElementById('umkm-sales-platforms');
    if (!wrap || !hidden) return;
    state.selectedPlatforms = Array.isArray(selected) ? [...selected] : [];
    hidden.value = JSON.stringify(state.selectedPlatforms);

    wrap.innerHTML = PLATFORM_OPTIONS.map((platform) => {
      const active = state.selectedPlatforms.includes(platform.value);
      return `
        <button type="button" class="sentra-chip ${active ? 'is-active' : ''}" data-platform="${platform.value}">
          <i class="${platform.icon}"></i>
          <span>${platform.value}</span>
        </button>
      `;
    }).join('');

    wrap.querySelectorAll('[data-platform]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const value = btn.dataset.platform;
        if (!value) return;
        if (state.selectedPlatforms.includes(value)) {
          state.selectedPlatforms = state.selectedPlatforms.filter((item) => item !== value);
        } else {
          state.selectedPlatforms.push(value);
        }
        renderPlatformChips(state.selectedPlatforms);
      });
    });
  }

  function createSelect(root, options) {
    const hidden = root.querySelector('input[type="hidden"]');
    const trigger = root.querySelector('[data-select-trigger]');
    const valueEl = root.querySelector('[data-select-value]');
    const panel = root.querySelector('[data-select-panel]');
    const searchBox = root.querySelector('.sentra-select-search');
    const search = root.querySelector('[data-select-search]');
    const optionsWrap = root.querySelector('[data-select-options]');
    if (!hidden || !trigger || !valueEl || !panel || !searchBox || !search || !optionsWrap) return null;

    const selectState = {
      root,
      hidden,
      trigger,
      valueEl,
      panel,
      searchBox,
      search,
      optionsWrap,
      options,
      filtered: options,
      value: ''
    };

    function render(filteredOptions = selectState.filtered) {
      if (!filteredOptions.length) {
        optionsWrap.innerHTML = '<div class="sentra-select-empty">Belum ada hasil yang cocok.</div>';
        return;
      }
      optionsWrap.innerHTML = filteredOptions.map((opt) => {
        const selected = opt.value === selectState.value;
        return `
          <button type="button" class="sentra-select-option ${selected ? 'is-selected is-active' : ''}" data-value="${opt.value}">
            <span>
              ${opt.label}
              ${opt.hint ? `<small>${opt.hint}</small>` : ''}
            </span>
            <i class="fa-solid fa-check"></i>
          </button>
        `;
      }).join('');

      optionsWrap.querySelectorAll('[data-value]').forEach((btn) => {
        btn.addEventListener('click', () => {
          setValue(btn.dataset.value || '');
          close();
        });
      });
    }

    function setValue(value) {
      const match = selectState.options.find((opt) => opt.value === value);
      selectState.value = match?.value || '';
      hidden.value = selectState.value;
      valueEl.textContent = match?.label || trigger.dataset.placeholder || 'Pilih opsi';
      root.classList.toggle('has-value', Boolean(selectState.value));
      render(selectState.filtered);
    }

    function open() {
      state.selects.forEach((item) => item.close());
      root.classList.add('open');

      // Move panel to body to fully escape modal stacking context
      panel._origParent = panel.parentNode;
      panel._origNext = panel.nextSibling;
      document.body.appendChild(panel);

      panel.hidden = false;
      trigger.setAttribute('aria-expanded', 'true');

      const rect = trigger.getBoundingClientRect();
      const vh = window.innerHeight;
      const spaceBelow = vh - rect.bottom - 8;
      const spaceAbove = rect.top - 8;

      panel.style.position = 'fixed';
      panel.style.left = rect.left + 'px';
      panel.style.width = rect.width + 'px';
      panel.style.right = 'auto';
      panel.style.zIndex = '99900';

      // Open upward if not enough space below
      if (spaceBelow >= 180 || spaceBelow >= spaceAbove) {
        panel.style.top = (rect.bottom + 5) + 'px';
        panel.style.bottom = 'auto';
        optionsWrap.style.maxHeight = Math.max(80, Math.min(spaceBelow - 54, 240)) + 'px';
      } else {
        panel.style.bottom = (vh - rect.top + 5) + 'px';
        panel.style.top = 'auto';
        optionsWrap.style.maxHeight = Math.max(80, Math.min(spaceAbove - 54, 240)) + 'px';
      }

      render(selectState.filtered);
      // Don't auto-focus on mobile — keyboard pops up and shifts panel position
      if (window.innerWidth > 640) {
        setTimeout(() => search.focus(), 20);
      }
      if (typeof gsap !== 'undefined') {
        gsap.fromTo(panel, { y: -6, opacity: 0 }, { y: 0, opacity: 1, duration: 0.18, ease: 'power2.out' });
      }
    }

    function close() {
      root.classList.remove('open');
      panel.hidden = true;
      panel.style.cssText = '';
      optionsWrap.style.maxHeight = '';
      trigger.setAttribute('aria-expanded', 'false');
      search.value = '';
      selectState.filtered = selectState.options;
      // Restore panel to original DOM position
      if (panel._origParent) {
        panel._origParent.insertBefore(panel, panel._origNext || null);
        panel._origParent = null;
        panel._origNext = null;
      }
    }

    trigger.dataset.placeholder = valueEl.textContent;
    trigger.addEventListener('click', () => {
      if (root.classList.contains('open')) close();
      else open();
    });

    search.addEventListener('input', () => {
      const keyword = search.value.trim().toLowerCase();
      selectState.filtered = selectState.options.filter((opt) => {
        const haystack = `${opt.label} ${opt.hint || ''}`.toLowerCase();
        return haystack.includes(keyword);
      });
      render(selectState.filtered);
    });

    return { ...selectState, setValue, open, close, render };
  }

  function closeAllSelects(target) {
    state.selects.forEach((item) => {
      if (target && item.root.contains(target)) return;
      if (target && item.panel && item.panel.contains(target)) return;
      item.close();
    });
  }

  function hydrateOnboardingForm(profile) {
    const form = el.onboardingForm();
    if (!form || !profile) return;
    const setValue = (name, value) => {
      const input = form.querySelector(`[name="${name}"]`);
      if (input) input.value = value ?? '';
    };

    setValue('business_name', profile.business_name || '');
    setValue('city', profile.city || '');
    setValue('avg_monthly_revenue', profile.avg_monthly_revenue ? formatRupiahInput(profile.avg_monthly_revenue) : '');
    setValue('active_customers', profile.active_customers || '');
    setValue('business_description', profile.business_description || '');
    updateDescriptionCount();

    const categorySelect = state.selects.find((item) => item.root.dataset.select === 'category');
    const provinceSelect = state.selects.find((item) => item.root.dataset.select === 'province');
    if (categorySelect) categorySelect.setValue(profile.category || '');
    if (provinceSelect) provinceSelect.setValue(profile.province || '');

    let platforms = profile.sales_platforms || [];
    if (typeof platforms === 'string') {
      try {
        platforms = JSON.parse(platforms);
      } catch (_) {
        platforms = platforms.split(',').map((item) => item.trim()).filter(Boolean);
      }
    }
    renderPlatformChips(platforms);
  }

  function resetOnboardingForm() {
    const form = el.onboardingForm();
    form?.reset();
    state.selects.forEach((item) => item.setValue(''));
    renderPlatformChips([]);
    setFeedback('clear', '');
    updateDescriptionCount();
  }

  function collectOnboardingPayload() {
    const form = el.onboardingForm();
    if (!form) return null;
    const formData = new FormData(form);
    const payload = Object.fromEntries(formData.entries());
    payload.avg_monthly_revenue = parseNumericInput(payload.avg_monthly_revenue);
    payload.active_customers = payload.active_customers ? Number(payload.active_customers) : null;
    payload.sales_platforms = [...state.selectedPlatforms];
    payload.margin_pct = null;
    payload.target_customer = payload.active_customers
      ? `${payload.active_customers} pelanggan aktif`
      : 'Pemilik UMKM Indonesia';
    return payload;
  }

  function validateOnboarding(payload) {
    if (!payload.business_name?.trim()) return 'Nama usaha wajib diisi.';
    if (!payload.category?.trim()) return 'Kategori usaha wajib dipilih.';
    if (!payload.province?.trim()) return 'Provinsi wajib dipilih.';
    if (!payload.city?.trim()) return 'Kota / Kabupaten wajib diisi.';
    if ((payload.business_description || '').length > 200) return 'Deskripsi singkat maksimal 200 karakter.';
    return '';
  }

  async function submitUMKMOnboarding() {
    const payload = collectOnboardingPayload();
    if (!payload) return;
    const error = validateOnboarding(payload);
    if (error) {
      setFeedback('error', error);
      return;
    }

    setFeedback('clear', '');
    setSubmitLoading(true);
    try {
      const res = await fetch('/api/umkm/onboarding', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...payload, user_id: getUserId() })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Gagal menyimpan onboarding UMKM');

      setFeedback('success', 'Profil usaha kamu sudah tersimpan. Kita masuk ke dashboard, ya.');
      if (typeof gsap !== 'undefined') {
        gsap.to(el.onboardingModal(), {
          boxShadow: '0 0 0 rgba(0,0,0,0), 0 0 30px rgba(250,204,21,0.25)',
          duration: 0.28,
          yoyo: true,
          repeat: 1
        });
      }

      setTimeout(() => {
        setMode('umkm');
        showUMKMShell(true);
        goTo('home');
        fillDashboardFromProfile(data.profile || payload);
        submitProfileAndAnalyze({ ...(data.profile || payload), user_id: getUserId() });
      }, 650);
    } catch (e) {
      setFeedback('error', String(e.message || e));
    } finally {
      setSubmitLoading(false);
    }
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
      if (e.key === 'Escape') closeAllSelects();
    });

    document.addEventListener('click', (e) => closeAllSelects(e.target));
    document.addEventListener('scroll', () => closeAllSelects(), true);

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

    const onboardingForm = el.onboardingForm();
    if (onboardingForm) {
      onboardingForm.addEventListener('submit', (e) => {
        e.preventDefault();
        submitUMKMOnboarding();
      });

      onboardingForm.querySelectorAll('input, textarea').forEach((field) => {
        field.addEventListener('focus', () => animateFormFocus(field.closest('.sentra-field') || field));
      });
    }

    const revenue = document.getElementById('umkm-revenue');
    revenue?.addEventListener('input', () => {
      const cursorSafeValue = formatRupiahInput(revenue.value);
      revenue.value = cursorSafeValue;
    });

    document.getElementById('umkm-description')?.addEventListener('input', updateDescriptionCount);

    state.selects = Array.from(document.querySelectorAll('.sentra-select'))
      .map((root) => createSelect(root, root.dataset.select === 'province' ? PROVINCE_OPTIONS : CATEGORY_OPTIONS))
      .filter(Boolean);

    renderPlatformChips([]);
    updateDescriptionCount();
  }

  function boot() {
    wire();

    // Check for explicit redirect intent via URL param
    const urlParams = new URLSearchParams(window.location.search);
    const modeParam = urlParams.get('mode');

    // If ?mode=umkm-dashboard is set AND onboarding is already done → go straight to dashboard
    if (modeParam === 'umkm-dashboard' && localStorage.getItem(LS_ONBOARD_KEY) === '1') {
      // Clean the URL param so refresh doesn't keep re-triggering
      try {
        urlParams.delete('mode');
        const cleanUrl = urlParams.toString()
          ? `${window.location.pathname}?${urlParams.toString()}`
          : window.location.pathname;
        window.history.replaceState({}, '', cleanUrl);
      } catch (_) { /* silent */ }
      showUMKMShell(true);
      goTo('home');
      setTimeout(() => loadProfile(), 350);
      return;
    }

    const done = localStorage.getItem(LS_ONBOARD_KEY) === '1';
    const mode = localStorage.getItem(LS_MODE_KEY);

    // Not yet onboarded → always show mode-selection screen
    if (!done) {
      openOnboarding(false);
      return;
    }

    // Already chose UMKM mode AND came back deliberately (e.g. nav link or bookmark)
    if (mode === 'umkm' && modeParam === 'umkm-dashboard') {
      showUMKMShell(true);
      goTo('home');
      setTimeout(() => loadProfile(), 350);
      return;
    }

    // Default: already onboarded → stay on current page (analysis mode or no-op)
    // Do NOT auto-redirect; let user navigate intentionally.
  }

  window.SentraUMKM = {
    openOnboarding,
    openDashboard,
    closeOnboarding,
    openUMKMOnboarding,
    backToModeStep,
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

