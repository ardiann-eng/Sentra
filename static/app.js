// Sentra AI - Main Application Script
// --- EMERGENCY VISIBILITY FALLBACK (3s) ---
// If splash-screen or animations get stuck on Vercel/Production
setTimeout(() => {
  const splash = document.getElementById('splash-screen');
  const isSplashVisible = splash &&
    splash.style.display !== 'none' &&
    !splash.classList.contains('hidden') &&
    parseFloat(getComputedStyle(splash).opacity) > 0;

  if (isSplashVisible || true) {
    if (splash) {
      splash.style.transition = 'opacity 0.5s ease';
      splash.style.opacity = '0';
      setTimeout(() => { splash.style.display = 'none'; }, 500);
    }
    document.body.style.overflow = 'auto';

    const allTargets = [
      'section', 'header', '.hero', '.howto-section',
      '.radar-section', '.radar-section-modern', '.wp-section',
      '#market-snapshot', '.snapshot-section', '.pricing-section',
      '#testimoni-section', '#sector-dashboard',
      '#radar-grid-modern', '.radar-card-premium'
    ].join(', ');

    document.querySelectorAll(allTargets).forEach(el => {
      el.style.opacity = '1';
      el.style.visibility = 'visible';
      el.style.transform = 'none';
      el.style.filter = 'none';
    });
  }
}, 4000);

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agt', 'Sep', 'Okt', 'Nov', 'Des'];
const STEPS = [
  'Memindai sinyal pasar...',
  'Membaca 12 bulan data historis...',
  'Mendeteksi fase & arah tren...',
  'Mengukur kepadatan persaingan...',
  'Membangun proyeksi 30 hari ke depan...',
  'Menyusun rekomendasi bisnis...',
  'Menyempurnakan hasil analisis...'
];
const COMPARE_STEPS = [
  'Memindai dua pasar sekaligus...',
  'Membaca pasar produk pertama...',
  'Membaca pasar produk kedua...',
  'Membandingkan 9 metrik utama...',
  'Membangun grafik perbandingan...',
  'Menyusun rekomendasi...',
  'Hampir selesai...'
];

let stepTimer = null;
let compareMode = false;
function unlockScroll() {
  document.body.style.removeProperty('overflow');
  document.body.style.removeProperty('overflow-y');
  document.body.style.removeProperty('overflow-x');
  if (document.documentElement) {
    document.documentElement.style.removeProperty('overflow');
    document.documentElement.style.removeProperty('overflow-y');
  }
}
let trendChart = null;
let regionalChart = null;

if (!localStorage.getItem('sentra_uid')) {
  const guestId = 'guest_' + Math.random().toString(36).substr(2, 9) + Date.now().toString(36);
  localStorage.setItem('sentra_uid', guestId);
}

const userState = {
  userId: localStorage.getItem('sentra_uid'),
  token: null,
  tier: 'free',
  searchesToday: 0,
  remaining: 5,
};
let sb = null;
let authMode = 'login';
let currentUser = null;
let currentProfile = null;
let selectedKategori = null;
let selectedModalTier = null;
let lastAnalysisResult = null;
let _aiInsightGenerated = false;
let lastCompareData = null;
let lastAnalysisData = null;

function getAuthHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  if (userState.token) {
    headers['Authorization'] = `Bearer ${userState.token}`;
  }
  return headers;
}

const loadingTexts = [
  "Sentra Initializing...",
  "Loading Market Data...",
  "Syncing Real-Time Signals...",
  "Calibrating Forecast Engine...",
  "Scanning Business Opportunities...",
  "System Ready..."
];

const SPLASH_TARGETS = 'header, .hero';
gsap.set(SPLASH_TARGETS, { opacity: 0, y: 30 });

function startSplashScreen() {
  const textEl = document.getElementById('splash-text');
  let textIdx = 0;
  const textInterval = setInterval(() => {
    if (textEl) {
      textEl.textContent = loadingTexts[textIdx];
      textIdx = (textIdx + 1) % loadingTexts.length;
    }
  }, 600);

  setTimeout(() => {
    clearInterval(textInterval);

    const tl = gsap.timeline({
      onComplete: () => {
        const splashEl = document.getElementById('splash-screen');
        if (splashEl) splashEl.remove();
        document.body.style.overflowY = 'auto';
        gsap.set(SPLASH_TARGETS, { clearProps: 'all' });
        document.querySelectorAll(
          'header, .hero, .howto-section, .radar-section, .radar-section-modern, ' +
          '.wp-section, .social-proof-section, #market-snapshot, .snapshot-section, ' +
          '.pricing-section, #sector-dashboard, ' +
          '#testimoni-section'
        ).forEach(el => {
          el.style.opacity = '1';
          el.style.transform = 'none';
          el.style.visibility = 'visible';
          el.style.filter = 'none';
          el.style.willChange = 'auto';
        });

        document.querySelectorAll('#radar-grid-modern, .radar-card-premium').forEach(el => {
          el.style.opacity = '1';
          el.style.transform = 'none';
          el.style.visibility = 'visible';
        });
      }
    });

    tl.to('#splash-screen', { duration: 0.8, opacity: 0, ease: 'power2.inOut' });
    tl.to(SPLASH_TARGETS, { duration: 0.8, opacity: 1, y: 0, stagger: 0.1, ease: 'power2.out' }, "-=0.5");
  }, 1200);
}

startSplashScreen();

/*  USER STATUS / QUOTA  */

async function fetchUserStatus() {

  try {

    const res = await fetch('/api/user-status', {

      method: 'POST',

      headers: getAuthHeaders(),

      body: JSON.stringify({ user_id: userState.userId || '' }),

    });

    if (!res.ok) return;

    const d = await res.json();

    userState.tier = d.tier || 'free';

    userState.searchesToday = d.searches_today || 0;

    userState.remaining = d.searches_remaining;

    updateQuotaUI();

  } catch (_) { /* silent fail */ }

}

function updateQuotaUI(meta) {

  if (meta) {

    userState.tier = meta.tier || userState.tier;

    userState.searchesToday = meta.searches_today ?? userState.searchesToday;

    userState.remaining = meta.searches_remaining ?? userState.remaining;

  }

  const isPro = userState.tier === 'pro';

  // Status bar — show for both tiers but hide quota details for Pro

  const statusBar = document.getElementById('status-bar');

  const text = document.getElementById('quota-text');

  const dots = document.getElementById('quota-dots');

  const upgradeBtn = document.getElementById('quota-upgrade-btn');

  if (statusBar) statusBar.classList.remove('hidden');

  if (!isPro && text) {

    const used = userState.searchesToday || 0;

    const rem = Math.max(0, 5 - used);

    text.textContent = `Riset tersisa hari ini: ${rem}/5`;

    dots.innerHTML = '';

    for (let i = 0; i < 5; i++) {

      const d = document.createElement('div');

      d.className = 'quota-dot' + (i >= rem ? ' used' : '');

      dots.appendChild(d);

    }

    if (upgradeBtn) upgradeBtn.style.display = '';

  } else if (isPro && text) {

    text.textContent = 'Pro — Akses Penuh';

    dots.innerHTML = '';

    if (upgradeBtn) upgradeBtn.style.display = 'none';

  }

  // Geo dropdown — unlock for Pro

  const geoSelect = document.getElementById('geo-select');

  const geoLock = document.getElementById('geo-lock');

  if (geoSelect) geoSelect.disabled = !isPro;

  if (geoLock) geoLock.style.display = isPro ? 'none' : '';

  // PDF button — unlock for Pro

  const pdfBtn = document.getElementById('pdf-btn');

  if (pdfBtn) {

    pdfBtn.disabled = !isPro;

    pdfBtn.innerHTML = isPro

      ? 'Download Laporan PDF'

      : '<span class="lock-icon"></span>Download Laporan PDF';

  }

}

/*  SUPABASE AUTH CORE  */

async function initSupabase() {

  try {

    const res = await fetch('/api/config');

    const config = await res.json();

    if (!config.supabase_url) return;

    sb = supabase.createClient(config.supabase_url, config.supabase_anon_key);

    await initAuth();

  } catch (e) { /* silent */ }

}

async function initAuth() {

  if (!sb) return;

  const { data: { session } } = await sb.auth.getSession();

  if (session && session.user) {

    currentUser = session.user;

    userState.userId = session.user.id;

    userState.token = session.access_token;

    await loadProfile(currentUser.id);

    updateNavAuth();

    fetchUserStatus();

  }

  sb.auth.onAuthStateChange(async (event, session) => {

    if (event === 'SIGNED_IN' && session) {

      currentUser = session.user;

      userState.userId = session.user.id;

      userState.token = session.access_token;

      await loadProfile(currentUser.id);

      updateNavAuth();

      fetchUserStatus();

    }

    if (event === 'SIGNED_OUT') {

      currentUser = null;

      currentProfile = null;

      userState.userId = localStorage.getItem('sentra_uid');

      userState.token = null;

      updateNavAuth();

    }

  });

}

async function loadProfile(userId) {

  if (!sb) return;

  try {

    const { data } = await sb

      .from('profiles')

      .select('*')

      .eq('id', userId)

      .single();

    currentProfile = data;

  } catch (e) { currentProfile = null; }

}

function updateNavAuth() {

  const headerContainer = document.getElementById('auth-header-action');

  const stickyContainer = document.getElementById('sticky-nav-auth');

  if (!currentUser) {

    const loginBtn = '<button class="auth-nav-login" onclick="openAuthModal(\'login\')">Masuk</button>';

    if (headerContainer) headerContainer.innerHTML = loginBtn;

    if (stickyContainer) stickyContainer.innerHTML = loginBtn;

    return;

  }

  const initial = _getInitial();

  const plan = (currentProfile && currentProfile.plan === 'pro') ? 'pro' : 'free';

  const planLabel = plan === 'pro' ? 'PRO' : 'FREE';

  const profileBtn = '<button id="auth-profile-btn" class="auth-profile-btn" onclick="event.stopPropagation(); openProfileDropdown()">' +

    '<span class="auth-avatar">' + initial + '</span>' +

    '<span class="auth-plan-badge ' + plan + '">' + planLabel + '</span>' +

    '</button>';

  if (headerContainer) headerContainer.innerHTML = profileBtn;

  if (stickyContainer) stickyContainer.innerHTML = profileBtn;

  // Add for UMKM dashboard topbar if exists
  const umkmAuth = document.getElementById('umkm-auth-action');
  if (umkmAuth) umkmAuth.innerHTML = profileBtn;
}

function _getInitial() {

  if (currentProfile && currentProfile.nama) return currentProfile.nama[0].toUpperCase();

  if (currentUser && currentUser.email) return currentUser.email[0].toUpperCase();

  return '?';

}

/*  AUTH MODAL RENDERING  */

const AUTH_REMEMBER_KEY = 'sentra_remember_me';
const AUTH_REMEMBER_EMAIL_KEY = 'sentra_remember_email';
let authView = 'login';

function getRememberedAuth() {
  try {
    return {
      enabled: localStorage.getItem(AUTH_REMEMBER_KEY) === '1',
      email: localStorage.getItem(AUTH_REMEMBER_EMAIL_KEY) || ''
    };
  } catch (e) {
    return { enabled: false, email: '' };
  }
}

function persistRememberMe(email, enabled) {
  try {
    if (enabled) {
      localStorage.setItem(AUTH_REMEMBER_KEY, '1');
      localStorage.setItem(AUTH_REMEMBER_EMAIL_KEY, email || '');
    } else {
      localStorage.removeItem(AUTH_REMEMBER_KEY);
      localStorage.removeItem(AUTH_REMEMBER_EMAIL_KEY);
    }
  } catch (e) { /* silent */ }
}

function getPasswordStrengthMeta(password) {
  const value = password || '';
  let score = 0;
  if (value.length >= 8) score += 1;
  if (/[A-Z]/.test(value)) score += 1;
  if (/[a-z]/.test(value)) score += 1;
  if (/\d/.test(value)) score += 1;
  if (/[^A-Za-z0-9]/.test(value)) score += 1;

  if (!value) return { score: 0, label: 'Belum diisi', tone: 'muted' };
  if (score <= 2) return { score, label: 'Masih lemah', tone: 'weak' };
  if (score <= 4) return { score, label: 'Cukup aman', tone: 'medium' };
  return { score, label: 'Kuat', tone: 'strong' };
}

function validateAuthInput(kind, value) {
  const email = (value || '').trim();
  if (kind === 'email') {
    if (!email) return 'Email wajib diisi.';
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return 'Format email belum valid.';
    return '';
  }
  if (kind === 'password-login') {
    if (!(value || '').trim()) return 'Password wajib diisi.';
    return '';
  }
  if (kind === 'password-signup') {
    if (!(value || '').trim()) return 'Password wajib diisi.';
    if ((value || '').length < 8) return 'Minimal 8 karakter.';
    if (!/[A-Za-z]/.test(value || '') || !/\d/.test(value || '')) return 'Gunakan kombinasi huruf dan angka.';
    return '';
  }
  if (kind === 'name' && authView === 'signup') {
    if (!(value || '').trim()) return 'Nama panggilan wajib diisi.';
    return '';
  }
  return '';
}

function authFriendlyError(message) {
  const raw = String(message || '').toLowerCase();
  if (!raw) return 'Ada kendala kecil. Coba lagi ya.';
  if (raw.includes('invalid login credentials')) return 'Email atau password belum cocok. Coba cek lagi ya.';
  if (raw.includes('email not confirmed')) return 'Email kamu belum terverifikasi. Cek inbox lalu klik link verifikasi.';
  if (raw.includes('already')) return 'Email ini sudah terdaftar. Coba masuk atau reset password.';
  return String(message);
}

function renderAuthModalContent(view) {
  const inner = document.getElementById('auth-modal-inner');
  if (!inner) return;

  authView = view || 'login';
  const remembered = getRememberedAuth();
  const isLogin = authView === 'login';
  const isSignup = authView === 'signup';
  const isForgot = authView === 'forgot';
  const isProfileSetup = authView === 'profile-setup';

  const title = isForgot
    ? 'Atur ulang akses'
    : isProfileSetup
      ? 'Satu langkah lagi'
      : isSignup
        ? 'Buat akun Sentra'
        : 'Masuk ke Sentra';
  const subtitle = isForgot
    ? 'Masukkan email terdaftar. Kami kirim link reset password yang aman ke inbox kamu.'
    : isProfileSetup
      ? 'Biar pengalamanmu terasa lebih personal, isi nama panggilan dulu ya.'
      : 'Masuk atau daftar untuk menyimpan insight, melanjutkan analisis, dan membuka pengalaman Sentra yang lebih personal.';

  let content = '';

  if (isForgot) {
    content = `
      <form id="auth-forgot-form" class="auth-form-shell">
        <label class="auth-field">
          <span class="auth-field-label">Email</span>
          <div class="auth-input-shell">
            <i class="fa-regular fa-envelope auth-input-icon"></i>
            <input id="auth-email" type="email" placeholder="nama@email.com" class="auth-input auth-input-modern" autocomplete="email" value="${remembered.email || ''}" />
          </div>
          <div class="auth-field-meta">
            <span class="auth-helper">Kami akan mengirim link reset password ke email ini.</span>
            <span id="auth-email-status" class="auth-status-text"></span>
          </div>
        </label>
        <button type="submit" id="auth-submit-btn" class="auth-submit auth-submit-modern">
          <span class="auth-submit-label">Kirim Link Reset</span>
        </button>
        <button type="button" class="auth-secondary-link" onclick="switchAuthTab('login')">Kembali ke Login</button>
        <div id="auth-error" class="auth-feedback error"></div>
        <div id="auth-success" class="auth-feedback success"></div>
      </form>
    `;
  } else if (isProfileSetup) {
    content = `
      <form id="auth-profile-form" class="auth-form-shell">
        <label class="auth-field">
          <span class="auth-field-label">Nama panggilan</span>
          <div class="auth-input-shell">
            <i class="fa-regular fa-user auth-input-icon"></i>
            <input type="text" class="auth-input auth-input-modern" id="profile-nama-input" placeholder="Contoh: Rani" maxlength="50" />
          </div>
        </label>
        <button type="submit" id="auth-submit-btn" class="auth-submit auth-submit-modern">
          <span class="auth-submit-label">Simpan & Mulai</span>
        </button>
        <div id="auth-error" class="auth-feedback error"></div>
      </form>
    `;
  } else {
    content = `
      <div class="auth-tab-wrap">
        <div class="auth-tabs">
          <button class="auth-tab-btn ${isLogin ? 'active' : ''}" type="button" onclick="switchAuthTab('login')">Login</button>
          <button class="auth-tab-btn ${isSignup ? 'active' : ''}" type="button" onclick="switchAuthTab('signup')">Daftar</button>
          <div class="auth-tab-glider ${isSignup ? 'is-signup' : ''}"></div>
        </div>
      </div>

      <form id="auth-main-form" class="auth-form-shell" style="gap: 10px;">
        ${isSignup ? `
          <label class="auth-field" style="gap: 4px;">
            <span class="auth-field-label">Nama panggilan</span>
            <div class="auth-input-shell">
              <i class="fa-regular fa-user auth-input-icon"></i>
              <input id="auth-name" type="text" placeholder="Contoh: Budi" class="auth-input auth-input-modern" autocomplete="name" />
            </div>
            <div id="auth-name-status" class="auth-status-text" style="font-size: 10px; margin-top: -4px;"></div>
          </label>` : ''}

        <label class="auth-field" style="gap: 4px;">
          <span class="auth-field-label">Email</span>
          <div class="auth-input-shell">
            <i class="fa-regular fa-envelope auth-input-icon"></i>
            <input id="auth-email" type="email" placeholder="nama@email.com" class="auth-input auth-input-modern" autocomplete="email" value="${remembered.enabled ? remembered.email : ''}" />
          </div>
          <div id="auth-email-status" class="auth-status-text" style="font-size: 10px; margin-top: -4px;"></div>
        </label>

        <label class="auth-field" style="gap: 4px;">
          <span class="auth-field-label">Password</span>
          <div class="auth-input-shell">
            <i class="fa-solid fa-lock auth-input-icon"></i>
            <input id="auth-password" type="password" placeholder="${isLogin ? 'Masukkan password kamu' : 'Minimal 8 karakter'}" class="auth-input auth-input-modern" autocomplete="${isLogin ? 'current-password' : 'new-password'}" />
            <button type="button" class="auth-eye-toggle" data-toggle-password aria-label="Tampilkan password">
              <i class="fa-regular fa-eye"></i>
            </button>
          </div>
          <div id="auth-password-status" class="auth-status-text" style="font-size: 10px; margin-top: -4px; height: 12px;"></div>
        </label>

        <div class="auth-row" style="margin-top: 2px;">
          <label class="auth-check">
            <input id="auth-remember" type="checkbox" ${remembered.enabled ? 'checked' : ''} />
            <span class="auth-custom-check"></span>
            <span>Ingat Saya</span>
          </label>
          <button type="button" class="auth-secondary-link" onclick="switchAuthTab('forgot')" style="font-size: 12px;">Lupa Password?</button>
        </div>

        <button type="submit" id="auth-submit-btn" class="auth-submit auth-submit-modern" style="margin-top: 6px;">
          <span class="auth-submit-label">${isSignup ? 'Buat Akun Sekarang' : 'Masuk ke Sentra'}</span>
        </button>


        <div id="auth-error" class="auth-feedback error"></div>
        <div id="auth-success" class="auth-feedback success"></div>
      </form>
    `;
  }

  inner.innerHTML = `
    <div class="auth-modern-shell">
      <div class="auth-modern-grid"></div>
      <div class="auth-glow auth-glow-a"></div>
      <div class="auth-glow auth-glow-b"></div>

      <div class="auth-modern-head" style="margin-bottom: 16px;">
        <div>
          <div class="auth-modern-eyebrow">Sentra AI Access</div>
          <h3 class="auth-modern-title" style="font-size: 24px;">${title}</h3>
          <p class="auth-modern-sub" style="font-size: 13px; line-height: 1.4;">${subtitle}</p>
        </div>
        <button type="button" class="auth-modal-close modern" onclick="closeAuthModal()" aria-label="Tutup"><i class="fa-solid fa-xmark"></i></button>
      </div>

      ${content}
    </div>
  `;

  wireAuthModalInteractions();
}

function openAuthModal(tab) {
  const nextView = tab === 'daftar' ? 'signup' : (tab || 'login');
  authMode = nextView;
  renderAuthModalContent(nextView);

  const overlay = document.getElementById('auth-overlay');
  const modal = document.getElementById('auth-modal');
  if (typeof gsap !== 'undefined') {
    gsap.killTweensOf([overlay, modal]);
  }
  if (overlay) overlay.classList.add('open');
  if (modal) modal.classList.add('open');
  document.body.style.overflow = 'hidden';
  if (document.documentElement) {
    document.documentElement.style.overflow = 'hidden';
    document.documentElement.style.position = 'fixed';
    document.documentElement.style.width = '100%';
  }

  if (typeof gsap !== 'undefined' && modal && overlay) {
    gsap.fromTo(overlay, { opacity: 0 }, { opacity: 1, duration: 0.3, ease: 'power2.out' });
    gsap.fromTo(
      modal,
      { xPercent: -50, yPercent: -50, y: 32, opacity: 0, scale: 0.96 },
      { xPercent: -50, yPercent: -50, y: 0, opacity: 1, scale: 1, duration: 0.5, ease: 'power4.out' }
    );
  }
}

function closeAuthModal() {
  const overlay = document.getElementById('auth-overlay');
  const modal = document.getElementById('auth-modal');
  const finishClose = () => {
    if (overlay) {
      overlay.classList.remove('open');
      overlay.style.removeProperty('opacity');
      overlay.style.removeProperty('pointer-events');
    }
    if (modal) {
      modal.classList.remove('open');
      modal.style.removeProperty('opacity');
      modal.style.removeProperty('pointer-events');
      modal.style.removeProperty('transform');
    }
    document.body.style.removeProperty('overflow');
    if (document.documentElement) {
      document.documentElement.style.removeProperty('overflow');
      document.documentElement.style.removeProperty('position');
      document.documentElement.style.removeProperty('width');
    }
    setAuthMessage('clear', '');
  };

  if (typeof gsap !== 'undefined' && overlay && modal) {
    gsap.killTweensOf([overlay, modal]);
    gsap.to(overlay, {
      opacity: 0,
      duration: 0.18,
      ease: 'power2.out'
    });
    gsap.to(modal, {
      xPercent: -50,
      yPercent: -50,
      y: 12,
      opacity: 0,
      duration: 0.2,
      ease: 'power2.out',
      onComplete: finishClose
    });
    return;
  }

  finishClose();
}

function switchAuthTab(tab) {
  const nextView = tab === 'daftar' ? 'signup' : tab;
  authMode = nextView;
  const shell = document.querySelector('.auth-modern-shell');
  if (typeof gsap !== 'undefined' && shell) {
    gsap.to(shell, {
      opacity: 0,
      y: 8,
      duration: 0.16,
      ease: 'power2.in',
      onComplete: () => {
        renderAuthModalContent(nextView);
        const fresh = document.querySelector('.auth-modern-shell');
        if (fresh) gsap.fromTo(fresh, { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.24, ease: 'power2.out' });
      }
    });
    return;
  }
  renderAuthModalContent(nextView);
}

function setAuthLoading(isLoading, teksAsli) {
  const btn = document.getElementById('auth-submit-btn');
  const label = btn?.querySelector('.auth-submit-label');
  if (!btn) return;
  if (isLoading) {
    btn.disabled = true;
    btn.classList.add('loading');
    if (label) {
      label.innerHTML = '<span class="auth-dots"><span></span><span></span><span></span></span>';
    }
  } else {
    btn.disabled = false;
    btn.classList.remove('loading');
    if (label) label.textContent = teksAsli;
  }
}

function setAuthMessage(type, message) {
  const err = document.getElementById('auth-error');
  const success = document.getElementById('auth-success');
  if (err) err.textContent = type === 'error' ? message : '';
  if (success) success.textContent = type === 'success' ? message : '';
}

function pulseAuthSuccess() {
  const shell = document.querySelector('.auth-modern-shell');
  if (typeof gsap === 'undefined' || !shell) return;
  gsap.fromTo(shell, { boxShadow: '0 24px 90px rgba(0,0,0,0.65)' }, {
    boxShadow: '0 24px 90px rgba(250,204,21,0.18)',
    duration: 0.24,
    yoyo: true,
    repeat: 1
  });
}

function updateFieldStatus(fieldKey, message, state) {
  const el = document.getElementById(`auth-${fieldKey}-status`);
  if (!el) return;
  el.textContent = message || '';
  el.className = `auth-status-text ${message ? 'show' : ''} ${state || ''}`.trim();
}

function runAuthRealtimeValidation() {
  const email = document.getElementById('auth-email');
  const password = document.getElementById('auth-password');
  const name = document.getElementById('auth-name');
  if (email) {
    email.addEventListener('input', () => {
      const err = validateAuthInput('email', email.value);
      updateFieldStatus('email', err || 'Email siap dipakai', err ? 'error' : 'success');
    });
  }
  if (password) {
    password.addEventListener('input', () => {
      if (authView === 'signup') {
        const meta = getPasswordStrengthMeta(password.value);
        updateFieldStatus('password', `Password: ${meta.label}`, meta.tone);
      } else if (password.value) {
        updateFieldStatus('password', 'Password terisi', 'success');
      }
    });
  }
  if (name) {
    name.addEventListener('input', () => {
      const err = validateAuthInput('name', name.value);
      updateFieldStatus('name', err || 'Siap, panggilan ini akan dipakai di dashboard', err ? 'error' : 'success');
    });
  }
}

function wireAuthModalInteractions() {
  const passwordToggle = document.querySelector('[data-toggle-password]');
  const passwordInput = document.getElementById('auth-password');
  const remembered = getRememberedAuth();

  if (passwordToggle && passwordInput) {
    passwordToggle.addEventListener('click', () => {
      const nextType = passwordInput.type === 'password' ? 'text' : 'password';
      passwordInput.type = nextType;
      passwordToggle.innerHTML = `<i class="fa-regular ${nextType === 'password' ? 'fa-eye' : 'fa-eye-slash'}"></i>`;
    });
  }

  runAuthRealtimeValidation();

  const form = document.getElementById('auth-main-form');
  form?.addEventListener('submit', (e) => {
    e.preventDefault();
    if (authView === 'signup') handleRegister();
    else handleLoginAction();
  });

  document.getElementById('auth-forgot-form')?.addEventListener('submit', (e) => {
    e.preventDefault();
    handleForgotPassword();
  });

  document.getElementById('auth-profile-form')?.addEventListener('submit', (e) => {
    e.preventDefault();
    saveProfileName();
  });

  if (remembered.enabled) updateFieldStatus('email', 'Email tersimpan di perangkat ini', 'success');

  const closeBtn = document.querySelector('.auth-modal-close.modern');
  closeBtn?.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    closeAuthModal();
  });
}

async function syncSupabaseSession(session) {
  if (!sb || !session?.access_token || !session?.refresh_token) return;
  try {
    await sb.auth.setSession({
      access_token: session.access_token,
      refresh_token: session.refresh_token
    });
  } catch (e) { /* silent */ }
}

async function handleLoginAction() {
  const email = document.getElementById('auth-email')?.value?.trim();
  const password = document.getElementById('auth-password')?.value;
  const remember = Boolean(document.getElementById('auth-remember')?.checked);
  const emailErr = validateAuthInput('email', email);
  const passwordErr = validateAuthInput('password-login', password);
  if (emailErr || passwordErr) {
    setAuthMessage('error', emailErr || passwordErr);
    return;
  }

  setAuthMessage('clear', '');
  setAuthLoading(true, 'Masuk ke Sentra');
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, remember_me: remember })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Login belum berhasil.');

    persistRememberMe(email, remember);
    await syncSupabaseSession(data.session);
    setAuthMessage('success', data.message || 'Berhasil masuk.');
    pulseAuthSuccess();
    setTimeout(() => closeAuthModal(), 520);
  } catch (e) {
    setAuthMessage('error', authFriendlyError(e.message || e));
    const form = document.querySelector('.auth-form-shell');
    if (form) {
      form.classList.add('auth-shake');
      setTimeout(() => form.classList.remove('auth-shake'), 500);
    }
  } finally {
    setAuthLoading(false, 'Masuk ke Sentra');
  }
}

async function handleRegister() {
  const fullName = document.getElementById('auth-name')?.value?.trim();
  const email = document.getElementById('auth-email')?.value?.trim();
  const password = document.getElementById('auth-password')?.value;
  const remember = Boolean(document.getElementById('auth-remember')?.checked);
  const emailErr = validateAuthInput('email', email);
  const passwordErr = validateAuthInput('password-signup', password);
  const nameErr = validateAuthInput('name', fullName);

  if (nameErr || emailErr || passwordErr) {
    setAuthMessage('error', nameErr || emailErr || passwordErr);
    return;
  }

  setAuthMessage('clear', '');
  setAuthLoading(true, 'Buat Akun Sentra');
  try {
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, full_name: fullName, remember_me: remember })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Pendaftaran belum berhasil.');

    persistRememberMe(email, remember);
    if (data.session?.access_token && data.session?.refresh_token) {
      await syncSupabaseSession(data.session);
    }
    setAuthMessage('success', data.message || 'Akun berhasil dibuat.');
    pulseAuthSuccess();
    if (data.needs_email_verification) {
      setTimeout(() => switchAuthTab('login'), 900);
      return;
    }
    currentUser = data.user || currentUser;
    setTimeout(() => openProfileSetup(), 560);
  } catch (e) {
    setAuthMessage('error', authFriendlyError(e.message || e));
  } finally {
    setAuthLoading(false, 'Buat Akun Sentra');
  }
}

/*  PROFILE SETUP (after first register)  */

function openProfileSetup() {
  openAuthModal('profile-setup');
}

async function saveProfileName() {
  var namaInput = document.getElementById('profile-nama-input');
  var nama = namaInput ? namaInput.value.trim() : '';
  if (!nama || !sb || !currentUser) {
    setAuthMessage('error', 'Nama panggilan wajib diisi.');
    return;
  }

  setAuthMessage('clear', '');
  setAuthLoading(true, 'Simpan & Mulai');
  try {
    await sb.from('profiles').update({ nama: nama }).eq('id', currentUser.id);
    await loadProfile(currentUser.id);
    updateNavAuth();
    setAuthMessage('success', 'Profil siap. Selamat datang di Sentra.');
    pulseAuthSuccess();
    setTimeout(function () {
      closeAuthModal();
      openProfilePanel();
    }, 420);
  } catch (e) {
    setAuthMessage('error', 'Nama belum berhasil disimpan. Coba lagi ya.');
  } finally {
    setAuthLoading(false, 'Simpan & Mulai');
  }
}

async function handleForgotPassword() {
  const email = document.getElementById('auth-email')?.value?.trim();
  const emailErr = validateAuthInput('email', email);
  if (emailErr) {
    setAuthMessage('error', emailErr);
    return;
  }

  setAuthMessage('clear', '');
  setAuthLoading(true, 'Kirim Link Reset');
  try {
    const res = await fetch('/api/auth/forgot-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Belum bisa mengirim link reset.');
    setAuthMessage('success', data.message || 'Link reset sudah dikirim.');
    pulseAuthSuccess();
  } catch (e) {
    setAuthMessage('error', authFriendlyError(e.message || e));
  } finally {
    setAuthLoading(false, 'Kirim Link Reset');
  }
}

async function handleGoogleLogin() {
  if (!sb) {
    setAuthMessage('error', 'Koneksi auth belum siap. Coba lagi ya.');
    return;
  }
  try {
    const redirectTo = window.location.origin;
    await sb.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo }
    });
  } catch (e) {
    setAuthMessage('error', 'Google login belum berhasil dibuka. Coba lagi ya.');
  }
}

/*  PROFILE DROPDOWN  */

function openProfileDropdown() {

  renderProfileDropdown();

  document.getElementById('profile-dropdown').classList.add('open');

}

function closeProfileDropdown() {

  document.getElementById('profile-dropdown').classList.remove('open');

}

function renderProfileDropdown() {

  var inner = document.getElementById('profile-dropdown-inner');

  if (!inner || !currentUser) return;

  var initial = _getInitial();

  var displayName = (currentProfile && currentProfile.nama) ? currentProfile.nama : (currentUser.email || '');

  var email = currentUser.email || '';

  var plan = (currentProfile && currentProfile.plan === 'pro') ? 'pro' : 'free';

  var planLabel = plan === 'pro' ? 'PRO' : 'FREE';

  var usahaHTML = '';

  if (currentProfile && currentProfile.usaha_nama) {

    usahaHTML =

      '<div class="profile-usaha-wrapper">' +

      '<div class="profile-usaha-label">USAHAMU</div>' +

      '<div class="profile-usaha-nama">' + currentProfile.usaha_nama + '</div>' +

      '<div class="profile-usaha-detail">' +

      (currentProfile.usaha_kategori || '') +

      (currentProfile.usaha_deskripsi ? '  ' + currentProfile.usaha_deskripsi : '') +

      '</div>' +

      '<button class="profile-usaha-edit" onclick="openUsahaSetup()">Ubah</button>' +

      '</div>';

  } else {

    usahaHTML =

      '<button class="profile-usaha-btn" onclick="openUsahaSetup()">MULAI USAHAMU</button>';

  }

  inner.innerHTML =

    '<div class="profile-dropdown-header">' +

    '<div class="profile-avatar-md">' + initial + '</div>' +

    '<div class="profile-info-col">' +

    '<div class="profile-name">' + displayName + '</div>' +

    '<div class="profile-email">' + email + '</div>' +

    '</div>' +

    '</div>' +

    '<div class="profile-plan-badge ' + plan + '">' + planLabel + '</div>' +

    '<hr class="profile-divider">' +

    usahaHTML +

    '<hr class="profile-divider">' +

    '<button class="profile-logout-btn" onclick="handleLogout()">Keluar</button>';

}

async function handleLogout() {

  if (!sb) return;

  await sb.auth.signOut();

  closeProfileDropdown();

}

document.addEventListener('click', function (e) {

  var dropdown = document.getElementById('profile-dropdown');

  var btn = document.getElementById('auth-profile-btn');

  if (dropdown && dropdown.classList.contains('open')) {

    if (!dropdown.contains(e.target) && (!btn || !btn.contains(e.target))) {

      closeProfileDropdown();

    }

  }

});

/*  USAHA SETUP MODAL  */

let selectedUsahaKategori = null;

function openUsahaSetup() {

  closeProfileDropdown();

  selectedUsahaKategori = null; // Reset setiap kali buka

  var inner = document.getElementById('auth-modal-inner');

  var existingNama = (currentProfile && currentProfile.usaha_nama) || '';

  var existingKat = (currentProfile && currentProfile.usaha_kategori) || '';

  var existingDesc = (currentProfile && currentProfile.usaha_deskripsi) || '';

  var categories = ['Makanan', 'Minuman', 'Fashion', 'Kecantikan', 'Aksesoris', 'Handmade', 'Digital', 'Rumah Tangga', 'Hobi & Kreatif', 'Produk Anak'];

  var chipsHTML = categories.map(function (cat) {

    var isSelected = (cat === existingKat) ? 'selected' : '';

    if (isSelected) selectedUsahaKategori = cat;

    return '<div class="usaha-cat-chip ' + isSelected + '" onclick="selectUsahaCategory(this, \'' + cat + '\')">' + cat + '</div>';

  }).join('');

  inner.innerHTML =

    '<div class="auth-modal-header" style="flex-direction:column; align-items:flex-start; margin-bottom: 40px;">' +

    '<div style="font-family:\'DM Mono\',monospace; font-size:9px; letter-spacing:4px; color:var(--gold); margin-bottom:20px; text-transform:uppercase;">PROFIL USAHA</div>' +

    '<div style="font-family:\'Cormorant Garamond\',serif; font-size:44px; font-weight:600; line-height:1.1; color:var(--text);">Usaha apa yang akan<br>kamu mulai?</div>' +

    '<button class="auth-modal-close" onclick="closeAuthModal()" style="position:absolute; top:40px; right:40px;">&times;</button>' +

    '</div>' +

    '<div style="margin-bottom: 32px;">' +

    '<label style="font-family:\'DM Mono\',monospace; font-size:9px; letter-spacing:3px; color:var(--text-faint); display:block; margin-bottom:8px; text-transform:uppercase;">NAMA USAHA</label>' +

    '<div class="usaha-input-wrapper" id="usaha-nama-wrapper">' +

    '<span style="font-family:\'DM Mono\',monospace; font-size:14px; color:var(--gold); margin-right:10px; flex-shrink:0;">_</span>' +

    '<input type="text" id="usaha-nama-input" placeholder="ketik nama usahamu..." value="' + existingNama.replace(/"/g, '&quot;') + '" autocomplete="off" />' +

    '</div>' +

    '</div>' +

    '<div style="margin-bottom: 32px;">' +

    '<label style="font-family:\'DM Mono\',monospace; font-size:9px; letter-spacing:3px; color:var(--text-faint); display:block; margin-bottom:12px; text-transform:uppercase;">KATEGORI</label>' +

    '<div id="usaha-cat-grid" style="display:grid; grid-template-columns:repeat(auto-fit, minmax(80px, 1fr)); gap:6px;">' + chipsHTML + '</div>' +

    '</div>' +

    '<div style="margin-bottom: 40px;">' +

    '<label style="font-family:\'DM Mono\',monospace; font-size:9px; letter-spacing:3px; color:var(--text-faint); display:block; margin-bottom:8px; text-transform:uppercase;">DESKRIPSI SINGKAT</label>' +

    '<textarea id="usaha-deskripsi-input" rows="2" placeholder="ceritakan singkat usahamu...">' + existingDesc + '</textarea>' +

    '</div>' +

    '<button class="usaha-submit" onclick="validateAndSaveUsaha()">SIMPAN USAHA</button>' +

    '<div id="usaha-error" style="font-family:\'DM Mono\',monospace; font-size:11px; color:#ef4444; text-align:center; margin-top:12px; min-height:16px;"></div>';

  document.getElementById('auth-overlay').classList.add('open');

  document.getElementById('auth-modal').classList.add('open');

  document.body.style.overflow = 'hidden';

  // Auto focus on name if empty

  if (!existingNama) {

    setTimeout(function () {

      var input = document.getElementById('usaha-nama-input');

      if (input) input.focus();

    }, 100);

  }

}

function selectUsahaCategory(element, category) {

  if (!element || !category) return;

  var chips = document.querySelectorAll('.usaha-cat-chip');

  chips.forEach(function (c) { c.classList.remove('selected'); });

  element.classList.add('selected');

  selectedUsahaKategori = category;

  var err = document.getElementById('usaha-error');

  if (err) err.textContent = '';

}

function validateAndSaveUsaha() {

  var namaInput = document.getElementById('usaha-nama-input');

  var deskripsiInput = document.getElementById('usaha-deskripsi-input');

  var namaWrapper = document.getElementById('usaha-nama-wrapper');

  var catGrid = document.getElementById('usaha-cat-grid');

  var err = document.getElementById('usaha-error');

  var nama = namaInput ? namaInput.value.trim() : '';

  var deskripsi = deskripsiInput ? deskripsiInput.value.trim() : '';

  if (!nama || !selectedUsahaKategori) {

    if (err) err.textContent = 'Nama usaha dan kategori wajib diisi.';

    if (!nama && namaWrapper) {

      namaWrapper.style.borderBottomColor = '#ef4444';

      setTimeout(function () { namaWrapper.style.borderBottomColor = ''; }, 2000);

    }

    if (!selectedUsahaKategori && catGrid) {

      var chips = catGrid.querySelectorAll('.usaha-cat-chip');

      chips.forEach(function (c) {

        var oldBorder = c.style.borderColor;

        c.style.borderColor = '#ef4444';

        setTimeout(function () { c.style.borderColor = oldBorder; }, 2000);

      });

    }

    return;

  }

  saveUsaha_internal(nama, selectedUsahaKategori, deskripsi);

}

async function saveUsaha_internal(nama, kategori, deskripsi) {

  if (!nama || !sb || !currentUser) return;

  await sb.from('profiles').update({

    usaha_nama: nama,

    usaha_kategori: kategori,

    usaha_deskripsi: deskripsi

  }).eq('id', currentUser.id);

  await loadProfile(currentUser.id);

  closeAuthModal();

  renderProfileDropdown();

  openProfileDropdown();

}

// Initialize on load — show login button immediately

document.addEventListener('DOMContentLoaded', () => {

  initAuth();

  updateNavAuth();

  initSupabase();

});

/* 

   SECTION 1 — Market Snapshot: Counter Animation

 */

function animateCounter(el, from, to, duration = 1800, suffix = '') {

  let start = null;

  const step = (timestamp) => {

    if (!start) start = timestamp;

    const progress = Math.min((timestamp - start) / duration, 1);

    const eased = 1 - Math.pow(1 - progress, 3); // cubic ease-out

    el.textContent = Math.floor(eased * (to - from) + from).toLocaleString('id-ID') + suffix;

    if (progress < 1) requestAnimationFrame(step);

  };

  requestAnimationFrame(step);

}

function initMarketSnapshot() {

  // Animate keyword count from 0 to ~1247

  const countEl = document.getElementById('snap-count');

  if (countEl) animateCounter(countEl, 0, 1247, 2000);

  // Update timestamp

  const timeEl = document.getElementById('snap-time');

  if (timeEl) {

    const now = new Date();

    timeEl.textContent = now.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' }) + ' WIB';

  }

  // Update AI panel timestamp

  const panelTs = document.getElementById('ai-panel-ts');

  if (panelTs) {

    const now = new Date();

    panelTs.textContent = `Generated ${now.toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric' })} -- ${now.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })} WIB`;

  }

}

/* 

   SECTION 2 — Live Market Intelligence Preview Chart

 */

let intelChartInstance = null;

function initHomepageSections() {

  initMarketSnapshot();

}

// Tetap panggil setelah splash selesai

setTimeout(initHomepageSections, 2600);

const STICKY_SCROLL_SHOW = 320;

const STICKY_OFFSET = 80;

const stickyNav = document.getElementById('sticky-nav');

const stickyNavButtons = stickyNav ? Array.from(stickyNav.querySelectorAll('[data-target]')) : [];

const stickySectionIds = ['kw', 'how-to-use', 'sector-dashboard', 'whitepaper', 'pricing'];

function scrollWithOffsetTo(targetId) {

  if (targetId === 'top') {

    window.scrollTo({ top: 0, behavior: 'smooth' });

    return;

  }

  const el = document.getElementById(targetId);

  if (!el) return;

  const top = window.pageYOffset + el.getBoundingClientRect().top - STICKY_OFFSET;

  window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });

  if (targetId === 'kw') {

    setTimeout(() => el.focus(), 420);

  }

}

function updateStickyVisibility() {

  if (!stickyNav) return;

  if (window.scrollY > STICKY_SCROLL_SHOW) stickyNav.classList.add('visible');

  else stickyNav.classList.remove('visible');

}

function updateStickyActiveLink() {

  if (!stickyNavButtons.length) return;

  const viewportProbe = window.scrollY + STICKY_OFFSET + 120;

  let activeId = 'kw';

  for (const id of stickySectionIds) {

    const section = document.getElementById(id);

    if (!section) continue;

    if (section.offsetTop <= viewportProbe) activeId = id;

  }

  stickyNavButtons.forEach(btn => {

    const target = btn.getAttribute('data-target');

    const shouldActive = target === activeId || (activeId === 'kw' && target === 'kw');

    btn.classList.toggle('active', !!shouldActive && btn.classList.contains('sticky-nav-link'));

  });

}

function handleStickyScroll() {

  updateStickyVisibility();

  updateStickyActiveLink();

}

stickyNavButtons.forEach(btn => {

  btn.addEventListener('click', () => {

    const target = btn.getAttribute('data-target');

    scrollWithOffsetTo(target);

  });

});

window.addEventListener('scroll', handleStickyScroll);

window.addEventListener('resize', updateStickyActiveLink);

handleStickyScroll();

document.getElementById('kw').addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });

document.getElementById('kw-a').addEventListener('keydown', e => { if (e.key === 'Enter') document.getElementById('kw-b').focus(); });

document.getElementById('kw-b').addEventListener('keydown', e => { if (e.key === 'Enter') doCompare(); });

/*  MODE TOGGLE  */

function toggleCompareMode() {

  compareMode = !compareMode;

  const toggle = document.getElementById('mode-toggle');

  const single = document.getElementById('single-search');

  const compare = document.getElementById('compare-inputs');

  const lblS = document.getElementById('lbl-single');

  const lblC = document.getElementById('lbl-compare');

  toggle.classList.toggle('on', compareMode);

  single.classList.toggle('hidden', compareMode);

  compare.classList.toggle('active', compareMode);

  lblS.classList.toggle('active', !compareMode);

  lblC.classList.toggle('active', compareMode);

  // Hide results when switching modes

  document.getElementById('results').style.display = 'none';

  document.getElementById('compare-results').style.display = 'none';

}

/*  LOADING  */

function startSteps(steps) {

  let i = 0;

  const loadText = document.getElementById('load-text');

  if (loadText) loadText.textContent = steps[0];

  if (stepTimer) clearInterval(stepTimer);

  stepTimer = setInterval(() => {

    i++;

    if (i >= steps.length) {

      clearInterval(stepTimer);

    } else {

      if (loadText) loadText.textContent = steps[i];

    }

  }, 1500);

}

function stopSteps() {

  if (stepTimer) clearInterval(stepTimer);

}

function showErr(msg) {

  const el = document.getElementById('err');

  el.textContent = ' ' + msg; el.style.display = 'block';

  setTimeout(() => el.style.display = 'none', 7000);

}

function setLoading(on, isCompare = false) {

  const loadEl = document.getElementById('loading');

  const hintText = document.getElementById('ip-entry');

  const btnSingle = document.getElementById('btn');

  const btnCompare = document.getElementById('btn-compare');

  if (on) {

    if (hintText) {

      hintText.style.opacity = '0';

      hintText.style.pointerEvents = 'none';

    }

    loadEl.style.display = 'block';

    if (!isCompare && btnSingle) btnSingle.disabled = true;

    if (isCompare && btnCompare) btnCompare.disabled = true;

    document.getElementById('results').style.display = 'none';

    document.getElementById('compare-results').style.display = 'none';

    startSteps(isCompare ? COMPARE_STEPS : STEPS);

  } else {

    stopSteps();

    loadEl.style.display = 'none';

    if (!isCompare && btnSingle) btnSingle.disabled = false;

    if (isCompare && btnCompare) btnCompare.disabled = false;

  }

}

/*  SINGLE KEYWORD HELPERS  */

function timingDesc(s) {

  if (s >= 80) return 'Kondisi pasar sangat mendukung. Ini momen ideal untuk memulai atau memperluas bisnis di segmen ini.';

  if (s >= 60) return 'Timing cukup bagus. Mulai persiapan sekarang agar siap saat tren mencapai puncaknya.';

  if (s >= 40) return 'Boleh masuk tapi perlu strategi yang matang. Pantau pergerakan beberapa minggu ke depan.';

  if (s >= 20) return 'Tren belum stabil atau sedang menurun. Sebaiknya tunggu sinyal pemulihan lebih jelas.';

  return 'Kondisi pasar tidak mendukung saat ini. Sebaiknya alokasikan resources ke peluang lain.';

}

function renderPulse(score) {

  const v = Math.max(0, Math.min(100, score || 0));

  const ring = document.getElementById('r-pulse-fill-bar');

  const text = document.getElementById('r-pulse');

  const cond = document.getElementById('r-pulse-condition');

  if (ring) {

    gsap.to(ring, { width: v + '%', duration: 1.5, ease: 'power2.out' });

  }

  if (text) {

    let obj = { val: 0 };

    gsap.to(obj, {

      val: v,

      duration: 1.5,

      ease: 'power2.out',

      onUpdate: () => {

        text.textContent = Math.round(obj.val) + '/100';

      }

    });

  }

  if (cond) {

    cond.textContent = v >= 75 ? 'PASAR SANGAT SEHAT' : v >= 50 ? 'PASAR CUKUP AKTIF' : v >= 30 ? 'PASAR MULAI LESU' : 'PASAR TIDAK SEHAT';

    cond.className = 'font-bold uppercase tracking-wider ' + (v >= 75 ? 'text-green-400' : v >= 50 ? 'text-brand' : 'text-red-400');

  }

}

function renderRing(score) {

  const v = Math.max(0, Math.min(100, score));

  const ringFill = document.getElementById('timing-ring-fill');

  const numEl = document.getElementById('r-ring-num');

  const badge = document.getElementById('timing-status-badge');

  const pointer = document.getElementById('timing-pointer');

  if (ringFill) {

    const circumference = 283; // 2r (r=45)

    const offset = circumference - (v / 100) * circumference;

    gsap.to(ringFill, { strokeDashoffset: offset, duration: 2, ease: 'elastic.out(1, 0.5)' });

  }

  if (numEl) {

    let obj = { val: 0 };

    gsap.to(obj, {

      val: v,

      duration: 2,

      ease: 'power2.out',

      onUpdate: () => {

        numEl.textContent = Math.round(obj.val);

      }

    });

  }

  if (badge) {

    let label = 'HINDARI DULU';

    let colorClass = 'text-red-400 border-red-400/50 bg-red-400/10';

    if (v >= 80) { label = 'GAS SEKARANG!'; colorClass = 'text-green-400 border-green-400/50 bg-green-400/10'; }

    else if (v >= 60) { label = 'SIAP-SIAP STOK'; colorClass = 'text-brand border-brand/50 bg-brand/10'; }

    else if (v >= 40) { label = 'PANTAU KETAT'; colorClass = 'text-yellow-400 border-yellow-400/50 bg-yellow-400/10'; }

    badge.textContent = label;

    badge.className = `mt-6 px-6 py-2 border font-syne text-[11px] font-bold tracking-[3px] uppercase ${colorClass}`;

  }

  if (pointer) {

    gsap.to(pointer, { left: v + '%', duration: 1.5, ease: 'back.out(1.7)' });

  }

}

function renderForecast(val, conf) {

  const v = Math.max(0, Math.min(100, val));

  setTimeout(() => document.getElementById('r-fc-bar').style.width = v + '%', 120);

  document.getElementById('r-fc-val').textContent = v.toFixed(1) + ' / 100';

  const cl = conf >= 0.7 ? 'Tinggi' : conf >= 0.4 ? 'Sedang' : 'Rendah';

  document.getElementById('r-fc-conf').textContent = `${cl} (${(conf * 100).toFixed(0)}%)`;

}

function renderMonths(peaks) {

  const wrap = document.getElementById('r-months');

  wrap.innerHTML = '';

  for (let i = 1; i <= 12; i++) {

    const ch = document.createElement('span');

    ch.className = 'chip season-month' + (peaks.includes(i) ? ' peak' : ' off');

    ch.textContent = MONTHS[i - 1];

    wrap.appendChild(ch);

  }

}

function typeWriter(el, text, speed = 7) {

  el.textContent = ''; el.classList.add('typing');

  let i = 0;

  const t = setInterval(() => {

    el.textContent += text[i++];

    if (i >= text.length) { clearInterval(t); el.classList.remove('typing'); }

  }, speed);

}

function renderResults(d) {

  if (!d) return;

  _detailData = d;

  lastAnalysisData = d;

  lastAnalysisResult = d;

  const resultsEl = document.getElementById('results');

  if (!resultsEl) return;

  // Force Reset visibility — display MUST be set to block here

  // because setLoading(true) sets inline style.display = 'none'

  resultsEl.style.display = 'block';

  resultsEl.style.opacity = '1';

  resultsEl.style.transform = 'none';

  resultsEl.style.visibility = 'visible';

  // 1. Header Information

  const kwTag = document.getElementById('r-kw');

  if (kwTag) kwTag.textContent = d.keyword;

  const tsTag = document.getElementById('r-ts');

  if (tsTag) tsTag.textContent = new Date().toLocaleString('id-ID', { dateStyle: 'medium', timeStyle: 'short' });

  // 2. Badges (Stage & Risk)

  const stageEl = document.getElementById('r-stage');

  if (stageEl) {

    stageEl.textContent = 'Fase: ' + d.lifecycle_stage;

    // Simple color mapping

    const colors = { Rising: 'brand', Emerging: 'blue-400', Peak: 'orange-400', Stable: 'zinc-400', Declining: 'red-400' };

    const c = colors[d.lifecycle_stage] || 'brand';

    stageEl.className = `px-3 py-1 bg-${c}/10 border border-${c}/20 text-${c} text-[11px] font-mono font-bold tracking-widest uppercase rounded`;

  }

  const riskEl = document.getElementById('r-risk');

  if (riskEl) {

    riskEl.textContent = 'Resiko: ' + d.risk_level;

    const isHigh = d.risk_level.toLowerCase().includes('high');

    const isMed = d.risk_level.toLowerCase().includes('medium');

    const c = isHigh ? 'red-500' : isMed ? 'orange-400' : 'green-400';

    riskEl.className = `px-3 py-1 bg-${c}/10 border border-${c}/20 text-${c} text-[11px] font-mono font-bold tracking-widest uppercase rounded`;

  }

  const growthVal = d.growth;

  const growthEl = document.getElementById('r-growth');

  if (growthEl) {

    growthEl.textContent = (growthVal >= 0 ? '+' : '') + (growthVal * 100).toFixed(1) + '%';

    growthEl.className = growthVal > 0 ? 'text-green-400' : growthVal < 0 ? 'text-red-400' : 'text-zinc-400';

  }

  // 3. KPI Metrics interpretation with GSAP Number Animation

  const animateKpiValue = (id, value, suffix = '', isFloat = false) => {

    const el = document.getElementById(id);

    if (!el) return;

    const obj = { val: parseFloat(el.textContent.replace(/[^-0-9.]/g, '')) || 0 };

    gsap.to(obj, {

      val: value,

      duration: 2,

      ease: "power3.out",

      onUpdate: () => {

        el.textContent = (obj.val >= 0 && id.includes('mom') ? '+' : '') +

          (isFloat ? obj.val.toFixed(2) : (id.includes('mom') ? (obj.val * 100).toFixed(1) : Math.round(obj.val))) +

          suffix;

      }

    });

  };

  const setT = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };

  // Values with animations

  animateKpiValue('r-mom-val', d.momentum, '%');

  animateKpiValue('r-vol-val', d.volatility * 100, '%');

  animateKpiValue('r-fomo', d.fomo_index, '', true);

  animateKpiValue('r-sat-val', d.saturation_index * 100, '%');

  // Tags (Badges)

  const momTxt = d.momentum > 0.3 ? 'Sangat Semangat' : d.momentum > 0 ? 'Mulai Ramai' : d.momentum > -0.3 ? 'Mulai Lesu' : 'Sepi Peminat';

  const volTxt = d.volatility < 0.3 ? 'Stabil (Aman)' : d.volatility < 0.5 ? 'Wajar' : 'Gampang Berubah';

  const fomoTxt = d.fomo_index < 0.3 ? 'Tren Nyata' : d.fomo_index < 0.6 ? 'Mulai Viral' : 'Hati-hati Hype';

  const satTxt = d.saturation_index < 0.4 ? 'Pasar Terbuka' : d.saturation_index < 0.7 ? 'Mulai Sesak' : 'Sudah Padat';

  setT('mc-mom-tag', momTxt);

  setT('mc-vol-tag', volTxt);

  setT('mc-fomo-tag', fomoTxt);

  setT('mc-sat-tag', satTxt);

  // Human-readable interpretation

  setT('r-mom-interp', d.momentum > 0 ? 'Orang mulai banyak nyari barang ini.' : 'Minat lagi turun, jangan stok terlalu banyak.');

  setT('r-vol-interp', d.volatility < 0.3 ? 'Permintaan stabil, resiko rugi kecil.' : 'Peminat naik turun, belanja stok secukupnya.');

  setT('r-fomo-interp', d.fomo_index < 0.4 ? 'Laku karena beneran butuh.' : 'Laku karena lagi viral/ngetren di sosmed.');

  setT('r-sat-interp', d.saturation_index < 0.4 ? 'Belum banyak saingan di toko sebelah.' : 'Saingan sudah banyak, siapin promo menarik!');

  // 4. Recommendation & Verdict

  let verdictSuffix = '';

  if (d.entry_timing_score >= 80) {

    verdictSuffix = '  Waktu terbaik untuk jualan!';

  } else if (d.entry_timing_score >= 60) {

    verdictSuffix = '  Siapkan stok sekarang!';

  }



  setT('summary-verdict', d.entry_timing_label + verdictSuffix);

  setT('timing-meaning', d.risk_level + '. ' + (d.entry_timing_score >= 60 ? 'Manfaatkan momentum ini sebelum pasar jenuh.' : 'Pertimbangkan resiko sebelum berinvestasi besar.'));

  setT('timing-status-badge', d.entry_timing_label);

  // Score animator

  const ringNum = document.getElementById('r-ring-num');

  const scoreToPercent = (s) => (283 - (s / 100) * 283);

  if (ringNum) {

    gsap.to(ringNum, {

      innerText: Math.round(d.entry_timing_score),

      duration: 1.5,

      snap: { innerText: 1 },

      ease: "power2.out"

    });

  }

  const ringFill = document.getElementById('timing-ring-fill');

  if (ringFill) {

    gsap.to(ringFill, {

      strokeDashoffset: scoreToPercent(d.entry_timing_score),

      duration: 1.5,

      ease: "power2.out"

    });

  }

  const pointer = document.getElementById('timing-pointer');

  if (pointer) {

    pointer.style.left = d.entry_timing_score + '%';

  }

  // Pulse bar

  const pNum = document.getElementById('r-pulse');

  if (pNum) pNum.textContent = d.market_pulse_score + '/100';

  const pFill = document.getElementById('r-pulse-fill-bar');

  if (pFill) pFill.style.width = d.market_pulse_score + '%';

  setT('r-pulse-condition', d.market_pulse_score >= 70 ? 'Pasar Sedang Membara' : d.market_pulse_score >= 50 ? 'Pasar Cukup Sehat' : 'Pasar Terlihat Lesu');

  // Seasonality - 3-level coloring: peak / active / off

  const monthsEl = document.getElementById('r-months');

  if (monthsEl) {

    monthsEl.innerHTML = '';

    const months = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];

    const peaks = d.seasonal_peak_months || [];

    const actives = d.seasonal_active_months || peaks;

    months.forEach((m, idx) => {

      const monthNum = idx + 1;

      const isPeak = peaks.includes(monthNum);

      const isActive = actives.includes(monthNum);

      const div = document.createElement('div');



      div.style.cssText = isPeak

        ? 'background:rgba(212,168,67,0.25);border:1px solid #D4A843;color:#D4A843;box-shadow:0 0 12px rgba(212,168,67,0.25);'

        : isActive

          ? 'background:rgba(212,168,67,0.08);border:1px solid rgba(212,168,67,0.3);color:rgba(212,168,67,0.6);'

          : 'background:rgba(39,39,42,0.2);border:1px solid rgba(39,39,42,0.5);color:#52525b;';



      div.className = 'flex items-center justify-center rounded-lg font-mono text-xs font-bold cursor-default min-h-[60px]';

      div.title = isPeak ? 'Bulan puncak' : isActive ? 'Aktivitas di atas rata-rata' : 'Aktivitas rendah';

      div.textContent = m;

      monthsEl.appendChild(div);

    });

  }

  const sBadge = document.getElementById('r-season-badge');

  if (sBadge) {

    const peaks = d.seasonal_peak_months || [];

    const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agt", "Sep", "Okt", "Nov", "Des"];

    if (peaks.length > 0) {

      sBadge.textContent = 'Puncak: ' + peaks.map(p => MONTH_NAMES[p - 1]).join(', ');

      sBadge.style.borderColor = 'rgba(212,168,67,0.4)';

      sBadge.style.color = '#D4A843';

    } else {

      sBadge.textContent = 'Aktivitas: Konsisten';

      sBadge.style.borderColor = 'rgba(100,100,100,0.3)';

      sBadge.style.color = '#666';

    }

  }

  setT('r-trend-range', d.raw_trend ? (d.raw_trend.dates.length + ' Hari Terakhir') : '12 Bulan');

  setT('r-fc-val', d.forecast_30d_avg ? d.forecast_30d_avg.toFixed(1) : '—');

  // Initialize chart — fixed: was calling renderSingleChart (undefined), correct name is renderSingleTrendChart

  if (typeof renderSingleTrendChart === 'function') {

    renderSingleTrendChart(d);

  }

  // 5. Regional Interest (Heatmap)

  const regSec = document.getElementById('regional-section');

  const regionalInterest = normalizeRegionalInterestData(d.regional_interest);
  d.regional_interest = regionalInterest;

  if (regionalInterest.length > 0) {

    if (regSec) regSec.style.display = 'block';
    if (window.MapLogic && typeof window.MapLogic.refresh === 'function') {
      window.MapLogic.refresh();
    }

    // Update the MapLogic (Indonesia Tile Map)

    if (window.MapLogic && typeof window.MapLogic.update === 'function') {

      // Normalize formatting if needed: {name, value} or {province, value}

      const mapData = regionalInterest.map(item => ({

        name: item.province || item.name,

        value: item.value

      }));

      window.MapLogic.update(mapData);

    }

    // Update Top Regions List

    const topList = document.getElementById('top-regions-list');

    if (topList) {

      topList.innerHTML = regionalInterest.slice(0, 5).map((item, i) => `

              <div class="flex items-center justify-between p-3 bg-zinc-900/60 border border-zinc-800 rounded-xl">

                  <div class="flex items-center gap-3">

                      <div class="w-6 h-6 rounded-full bg-brand/10 text-brand text-[10px] font-mono flex items-center justify-center border border-brand/20">${i + 1}</div>

                      <div class="text-zinc-100 text-sm font-jakarta font-medium">${item.province || item.name}</div>

                  </div>

                  <div class="text-brand font-mono text-sm font-bold">${item.value}%</div>

              </div>

          `).join('');

    }

  } else {

    if (regSec) regSec.style.display = 'none';

  }

  // Show Results with GSAP Stagger

  resultsEl.classList.remove('hidden');

  gsap.fromTo(resultsEl.children,

    { y: 30, opacity: 0 },

    { y: 0, opacity: 1, duration: 0.8, stagger: 0.15, ease: 'power3.out' }

  );

  setTimeout(() => resultsEl.scrollIntoView({ behavior: 'smooth', block: 'start' }), 300);

  // AI Autopilot OFF: Reset trigger state for new results
  _aiInsightGenerated = false;
  const aiTrigger = document.getElementById('ai-trigger-state');
  const aiResult = document.getElementById('ai-result-state');
  const aiLoading = document.getElementById('ai-loading-state');

  if (d.ai_insight && d.ai_insight.trim() !== "") {
    if (aiTrigger) aiTrigger.classList.add('hidden');
    if (aiLoading) aiLoading.classList.add('hidden');
    if (aiResult) aiResult.classList.remove('hidden');
    renderAiCards(d.ai_insight);
    _aiInsightGenerated = true;
  } else {
    showAiTriggerState();
  }
}

let _techSectionOpen = false;

function setTechnicalToggleState(isOpen) {

  const section = document.getElementById('tech-section');

  const btn = document.getElementById('tech-toggle-btn');

  _techSectionOpen = !!isOpen;

  if (section) {

    if (isOpen) {

      section.classList.add('open');

    } else {

      section.classList.remove('open');

    }

  }

  if (btn) {

    btn.textContent = isOpen

      ? '-- Sembunyikan Analisis Teknikal '

      : '-- Lihat Analisis Teknikal Lengkap ';

    btn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');

  }

}

function toggleTechnicalSection() {

  setTechnicalToggleState(!_techSectionOpen);

}

function renderGrowthSpark(d) {

  const raw = d && d.raw_trend;

  if (!raw || !Array.isArray(raw.values) || raw.values.length === 0) return;

  const values = raw.values.slice(-7);

  drawSparkline('growth-spark', values, '#C9A84C');

}

function renderMomentumRange(value) {

  const thumb = document.getElementById('mom-thumb');

  if (!thumb) return;

  const v = Math.max(-2, Math.min(2, value || 0));

  const pct = ((v + 2) / 4) * 100;

  thumb.style.left = pct + '%';

}

function renderVolatilityRange(value) {

  const thumb = document.getElementById('vol-thumb');

  if (!thumb) return;

  const v = Math.max(0, Math.min(1, value || 0));

  thumb.style.left = (v * 100) + '%';

}

function renderFomoRange(value) {

  const thumb = document.getElementById('fomo-thumb');

  if (!thumb) return;

  const v = Math.max(0, Math.min(1, value || 0));

  thumb.style.left = (v * 100) + '%';

}

function renderSaturationRange(value) {

  const thumb = document.getElementById('sat-thumb');

  if (!thumb) return;

  const v = Math.max(0, Math.min(1, value || 0));

  thumb.style.left = (v * 100) + '%';

}

function renderTechnicalDetails(d) {

  renderGrowthSpark(d);

  renderMomentumRange(d.momentum);

  renderVolatilityRange(d.volatility);

  renderFomoRange(d.fomo_index);

  renderSaturationRange(d.saturation_index);

}

/*  SINGLE TREND CHART  */

let singleChart = null;

let forecastVisible = false;


function renderSingleTrendChart(d) {

  const canvas = document.getElementById('single-chart');

  if (!canvas) return;

  if (singleChart) { singleChart.destroy(); singleChart = null; }

  const raw = d.raw_trend || null;

  if (!raw || !Array.isArray(raw.dates) || raw.dates.length === 0) {

    document.getElementById('r-trend-range').textContent = '';

    canvas.parentElement.style.display = 'none';

    const monthLabelContainerEmpty = document.getElementById('chart-month-labels');

    if (monthLabelContainerEmpty) monthLabelContainerEmpty.innerHTML = '';

    const btnEmpty = document.getElementById('btn-toggle-forecast');

    if (btnEmpty) {

      btnEmpty.textContent = ' TAMPILKAN FORECAST 90 HARI';

      btnEmpty.classList.remove('active');

    }

    forecastVisible = false;

    return;

  }

  // Filter tanggal yang masuk akal (tidak lebih dari 14 hari dari sekarang)

  const today = new Date();

  const maxDate = new Date(today.getTime() + 14 * 24 * 60 * 60 * 1000);

  const filteredDates = raw.dates.filter(dt => new Date(dt) <= maxDate);

  const filteredValues = raw.values.slice(0, filteredDates.length);

  if (filteredDates.length === 0) {

    document.getElementById('r-trend-range').textContent = '';

    canvas.parentElement.style.display = 'none';

    const monthLabelContainerEmpty = document.getElementById('chart-month-labels');

    if (monthLabelContainerEmpty) monthLabelContainerEmpty.innerHTML = '';

    return;

  }

  canvas.parentElement.style.display = 'block';

  forecastVisible = false;

  const btn = document.getElementById('btn-toggle-forecast');

  if (btn) {

    btn.textContent = ' TAMPILKAN FORECAST 90 HARI';

    btn.classList.remove('active');

  }

  const labels = filteredDates.map(dt => {

    const d = new Date(dt);

    return d.toLocaleDateString('id-ID', { day: 'numeric', month: 'short' });

  });

  // Generate label bulan dinamis untuk sumbu bawah

  const monthLabelContainer = document.getElementById('chart-month-labels');

  if (monthLabelContainer && filteredDates.length > 0) {

    const totalPts = filteredDates.length;

    const step = Math.max(1, Math.floor(totalPts / 5));

    const monthLabels = [];

    for (let i = 0; i < totalPts; i += step) {

      const dt = new Date(filteredDates[i]);

      monthLabels.push(MONTHS_ID[dt.getMonth()]);

    }

    if (monthLabels.length > 0) monthLabels[monthLabels.length - 1] += '—';

    monthLabelContainer.innerHTML = monthLabels.map(m => `<span>${m}</span>`).join('');

  }

  // Hitung range dari data historis saja (sebelum forecast ditambahkan)

  if (filteredDates.length > 0) {

    const first = new Date(filteredDates[0]).toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric' });

    const last = new Date(filteredDates[filteredDates.length - 1]).toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric' });

    document.getElementById('r-trend-range').textContent = `${first}  ${last}`;

  }

  // Default chart: hanya data historis.

  // Forecast baru ditambahkan saat user klik tombol toggle.

  const histValues = [...filteredValues]; // copy agar tidak mutate source values

  const ctx = canvas.getContext('2d');

  const grad = ctx.createLinearGradient(0, 0, 0, 400);

  grad.addColorStop(0, 'rgba(212,168,67,0.15)');

  grad.addColorStop(1, 'rgba(212,168,67,0)');

  singleChart = new Chart(ctx, {

    type: 'line',

    data: {

      labels,

      datasets: [

        {

          label: d.keyword,

          data: histValues,

          borderColor: '#D4A843',

          backgroundColor: grad,

          borderWidth: 3,

          pointRadius: 0,

          pointHoverRadius: 6,

          pointHoverBackgroundColor: '#0A0A08',

          pointHoverBorderColor: '#F0C855',

          pointHoverBorderWidth: 3,

          tension: 0.4,

          fill: true,

          shadowColor: 'rgba(212,168,67, 0.5)',

          shadowBlur: 10

        }

      ]

    },

    options: {

      responsive: true,

      maintainAspectRatio: false,

      interaction: { mode: 'index', intersect: false },

      plugins: {

        legend: { display: false },

        tooltip: {

          backgroundColor: 'rgba(10, 10, 8, 0.95)',

          titleColor: '#D4A843',

          bodyColor: '#fff',

          borderColor: 'rgba(212,168,67, 0.3)',

          borderWidth: 1,

          padding: 12,

          cornerRadius: 8,

          titleFont: { family: 'Plus Jakarta Sans', size: 12, weight: 'bold' },

          bodyFont: { family: 'DM Mono', size: 13 },

          displayColors: false,

          callbacks: { label: c => `Minat: ${c.parsed.y}` }

        }

      },

      scales: {

        x: {

          grid: { display: false },

          ticks: { color: '#444', font: { family: 'DM Mono', size: 10 }, maxRotation: 0 }

        },

        y: {

          grid: { color: 'rgba(212,168,67, 0.05)' },

          ticks: { display: false },

          beginAtZero: true,

          max: 110,

        }

      }

    }

  });

}

function toggleForecast() {

  if (!lastAnalysisData || !singleChart) return;

  forecastVisible = !forecastVisible;

  const btn = document.getElementById('btn-toggle-forecast');

  if (btn) {

    btn.textContent = forecastVisible ? ' SEMBUNYIKAN FORECAST' : ' TAMPILKAN FORECAST 90 HARI';

    btn.classList.toggle('active', forecastVisible);

  }

  if (forecastVisible) {

    const fcAvg = lastAnalysisData.forecast_30d_avg || 0;

    const dates = lastAnalysisData.raw_trend.dates;

    const lastDateStr = dates[dates.length - 1];

    const lastDate = new Date(lastDateStr);

    const fcLabels = [];

    const fcValues = [];

    const histLen = lastAnalysisData.raw_trend.values.length;

    for (let i = 1; i <= 4; i++) {

      const d = new Date(lastDate);

      d.setDate(d.getDate() + i * 7);

      fcLabels.push(d.toLocaleDateString('id-ID', { day: 'numeric', month: 'short' }));

      const lastVal = lastAnalysisData.raw_trend.values[histLen - 1];

      fcValues.push(Math.round(lastVal + (fcAvg - lastVal) * (i / 4)));

    }

    const allLabels = [...singleChart.data.labels, ...fcLabels];

    const fcDataPadded = new Array(singleChart.data.datasets[0].data.length).fill(null).concat(fcValues);

    singleChart.data.labels = allLabels;

    if (singleChart.data.datasets.length === 1) {

      singleChart.data.datasets.push({

        label: 'Proyeksi (AI)',

        data: fcDataPadded,

        borderColor: '#D4A843',

        borderDash: [5, 5],

        borderWidth: 2,

        pointRadius: 0,

        fill: false,

        tension: 0.4

      });

    }

    singleChart.update();

  } else {

    renderSingleTrendChart(lastAnalysisData);

  }

}

/*  REGIONAL BAR CHART  */

let regionalBarChart = null;

function renderRegionalBarChart(data) {

  const canvas = document.getElementById('regional-bar-chart');

  if (!canvas) return;

  if (regionalBarChart) { regionalBarChart.destroy(); regionalBarChart = null; }

  const topNodes = data.slice(0, 10);

  const labels = topNodes.map(d => d.province || d.name);

  const values = topNodes.map(d => d.value);

  if (typeof Chart !== 'undefined') {

    regionalBarChart = new Chart(canvas, {

      type: 'bar',

      data: {

        labels: labels,

        datasets: [{

          label: 'Indeks Minat',

          data: values,

          backgroundColor: 'rgba(212, 168, 67, 0.4)',

          borderColor: 'rgba(212, 168, 67, 1)',

          borderWidth: 1,

          borderRadius: 4

        }]

      },

      options: {

        indexAxis: 'y',

        responsive: true,

        maintainAspectRatio: false,

        plugins: {

          legend: { display: false },

          tooltip: {

            backgroundColor: '#1a1a1a',

            titleFont: { family: 'Syne' },

            bodyFont: { family: 'Plus Jakarta Sans' }

          }

        },

        scales: {

          x: {

            display: true,

            grid: { color: 'rgba(255,255,255,0.05)' },

            ticks: { color: '#666', font: { size: 10 } },

            max: 100

          },

          y: {

            grid: { display: false },

            ticks: { color: '#aaa', font: { size: 11, family: 'Plus Jakarta Sans' } }

          }

        }

      }

    });

  }

}

/*  REGIONAL BREAKDOWN  */

function renderRegionalBreakdown(data) {

  const canvas = document.getElementById('regional-chart');

  if (!canvas || !data.regional_breakdown) return;

  if (regionalChart) { regionalChart.destroy(); regionalChart = null; }

  const top10 = data.regional_breakdown.slice(0, 10);

  const provinceLabels = top10.map(r => r.province);

  const values = top10.map(r => r.value);

  const ctx = canvas.getContext('2d');

  regionalChart = new Chart(ctx, {

    type: 'bar',

    data: {

      labels: provinceLabels,

      datasets: [{

        label: 'Skor Minat',

        data: values,

        backgroundColor: values.map((v, i) => {

          const alpha = 0.2 + (v / 100) * 0.7;

          return i === 0 ? '#D4A843' : `rgba(212,168,67,${alpha})`;

        }),

        borderRadius: 6,

        borderWidth: 0,

        indexAxis: 'y'

      }]

    },

    options: {

      responsive: true,

      maintainAspectRatio: false,

      plugins: {

        legend: { display: false },

        tooltip: {

          backgroundColor: 'rgba(10,10,8,0.95)',

          titleColor: '#D4A843',

          padding: 12,

          cornerRadius: 8,

          callbacks: { label: c => ` Skor Minat: ${c.parsed.x}/100` }

        }

      },

      scales: {

        x: { grid: { color: 'rgba(212,168,67,0.05)' }, max: 100, beginAtZero: true, ticks: { color: '#666', font: { family: 'DM Mono', size: 10 } } },

        y: { grid: { display: false }, ticks: { color: '#aaa', font: { family: 'Plus Jakarta Sans', size: 11, weight: '500' } } }

      }

    }

  });

  // Top 3 Medals

  const medalContainer = document.getElementById('r-top-3-medals');

  if (medalContainer) {

    const medals = ['', '', ''];

    const medalStyles = [

      'from-brand/20 to-brand/5 border-brand/40',

      'from-zinc-400/20 to-zinc-400/5 border-zinc-400/30',

      'from-orange-700/20 to-orange-700/5 border-orange-700/30'

    ];

    medalContainer.innerHTML = data.regional_breakdown.slice(0, 3).map((r, i) => `

      <div class="flex items-center gap-4 p-4 bg-gradient-to-r ${medalStyles[i]} border rounded-xl hover:scale-[1.02] transition-all duration-300">

        <div class="text-3xl">${medals[i]}</div>

        <div class="flex-1">

          <div class="text-[10px] font-bold text-zinc-100 uppercase tracking-[2px] mb-1.5">${r.province}</div>

          <div class="flex items-center gap-3">

            <div class="h-1.5 flex-1 bg-black/40 rounded-full overflow-hidden">

               <div class="h-full bg-brand shadow-[0_0_10px_rgba(212,168,67,0.5)]" style="width:${r.value}%"></div>

            </div>

            <div class="text-[10px] font-mono font-bold text-brand">${r.value}</div>

          </div>

        </div>

      </div>

    `).join('');

  }

  // Other Regions List

  const gridContainer = document.getElementById('r-other-regions-grid');

  if (gridContainer) {

    gridContainer.innerHTML = data.regional_breakdown.slice(3, 15).map(r => `

      <div class="flex justify-between items-center py-2.5 border-b border-zinc-800/50 group hover:bg-white/2 px-2 rounded-lg transition-colors">

        <div class="flex items-center gap-3">

           <span class="text-[9px] font-mono text-zinc-600">#${r.rank}</span>

           <span class="text-[11px] text-zinc-500 group-hover:text-zinc-300 transition-colors">${r.province}</span>

        </div>

        <span class="text-[10px] font-mono text-zinc-400 group-hover:text-brand transition-colors">${r.value}%</span>

      </div>

    `).join('');

  }

  // Summary

  const badge = document.getElementById('r-top-province-badge');

  if (badge && data.top_province) badge.textContent = `TOP: ${data.top_province}`;

  const summary = document.getElementById('r-regional-summary');

  if (summary && data.top_province && data.top_3 && data.top_3.length >= 2) {

    summary.innerHTML = `Analisis satelit menunjukkan tingkat minat tertinggi berpusat di <strong class="text-brand">${data.top_province}</strong> (${data.regional_breakdown[0].value}/100), diikuti oleh <span class="text-zinc-200">${data.top_3[1] || ''}</span> dan <span class="text-zinc-200">${data.top_3[2] || ''}</span>.`;

  }

}

/*  AI INSIGHT PARSER — 3 CARD  */

function parseAiSections(text) {

  // Try to split by numbered sections: "1.", "2.", "3."

  const sectionRegex = /(?:^|\n)\s*\d+\.\s*[^\n]*/g;

  const matches = [...text.matchAll(/(?:^|\n)\s*(\d+)\.\s*([^\n]*)/g)];

  if (matches.length >= 3) {

    const indices = matches.map(m => text.indexOf(m[0]));

    // Strip only the leading "N. " prefix — NOT the whole line
    // (AI writes content on the same line as the number)
    const pasar = text.substring(indices[0], indices[1]).replace(/^\s*\d+\.\s*/, '').trim();

    const aksi = text.substring(indices[1], indices[2]).replace(/^\s*\d+\.\s*/, '').trim();

    const waktu = text.substring(indices[2]).replace(/^\s*\d+\.\s*/, '').trim();

    return { pasar, aksi, waktu };

  }

  // Fallback: split into 3 roughly equal paragraphs

  const paragraphs = text.split(/\n\n+/).filter(p => p.trim());

  if (paragraphs.length >= 3) {

    return {

      pasar: paragraphs.slice(0, Math.ceil(paragraphs.length / 3)).join('\n\n'),

      aksi: paragraphs.slice(Math.ceil(paragraphs.length / 3), Math.ceil(2 * paragraphs.length / 3)).join('\n\n'),

      waktu: paragraphs.slice(Math.ceil(2 * paragraphs.length / 3)).join('\n\n'),

    };

  }

  // Last resort: split by sentences

  const sentences = text.split(/(?<=\.)\s+/);

  const third = Math.ceil(sentences.length / 3);

  return {

    pasar: sentences.slice(0, third).join(' '),

    aksi: sentences.slice(third, third * 2).join(' '),

    waktu: sentences.slice(third * 2).join(' '),

  };

}

function boldifyText(text) {

  // Bold key phrases: numbers with %, scores, and important action words

  let html = text

    .replace(/(\d+[\.,]?\d*\s*%)/g, '<strong>$1</strong>')

    .replace(/(\d+[\.,]?\d*\s*\/\s*100)/g, '<strong>$1</strong>')

    .replace(/(Entry Timing Score[^.]*)/gi, '<strong>$1</strong>')

    .replace(/(waktu terbaik|tancap gas|segera|hati-hati|tunggu|hindari|persiapan|pantau)/gi, '<strong>$1</strong>');

  return html;

}

function renderAiCards(text) {

  const sections = parseAiSections(text);

  const targets = [

    { id: 'r-ai-pasar', content: sections.pasar },

    { id: 'r-ai-aksi', content: sections.aksi },

    { id: 'r-ai-waktu', content: sections.waktu }

  ];

  targets.forEach((t, i) => {

    const el = document.getElementById(t.id);

    if (el) {

      el.classList.remove('visible');

      setTimeout(() => {

        el.innerHTML = boldifyText(t.content);

        el.classList.add('visible');

      }, i * 400); // Stagger by 400ms each

    }

  });

}

function renderSummaryCard(d) {

  const card = document.getElementById('summary-card');

  if (!card || !d) return;

  // Reset news section untuk keyword baru

  const newsSection = document.getElementById('summary-news-section');

  const newsList = document.getElementById('summary-news-list');

  if (newsSection) newsSection.style.display = 'none';

  if (newsList) {

    newsList.innerHTML = `

          <div class="news-skeleton">

            <div class="skeleton-line" style="width:90%;height:13px;margin-bottom:6px;"></div>

            <div class="skeleton-line" style="width:40%;height:10px;"></div>

          </div>

          <div class="news-skeleton">

            <div class="skeleton-line" style="width:85%;height:13px;margin-bottom:6px;"></div>

            <div class="skeleton-line" style="width:35%;height:10px;"></div>

          </div>

          <div class="news-skeleton">

            <div class="skeleton-line" style="width:88%;height:13px;margin-bottom:6px;"></div>

            <div class="skeleton-line" style="width:42%;height:10px;"></div>

          </div>

        `;

  }

  const getValue = (metricName, value) => {

    switch (metricName) {

      case 'growth': {

        const g = (value || 0) * 100; // to percent

        const clamped = Math.max(-50, Math.min(150, g));

        const gauge = ((clamped + 50) / 200) * 100; // -50..150 -> 0..100

        let status = 'warn';

        let label = 'Pertumbuhan moderat';

        if (g > 30) {

          status = 'good';

          label = 'Pertumbuhan kuat';

        } else if (g < 0) {

          status = 'bad';

          label = 'Sedang turun';

        }

        const text = (g >= 0 ? '+' : '') + g.toFixed(1) + '%';

        return { status, text, label, gauge };

      }

      case 'momentum': {

        const m = value || 0;

        const clamped = Math.max(-2, Math.min(2, m));

        const gauge = ((clamped + 2) / 4) * 100; // -2..2 -> 0..100

        let status, label;

        if (m > 0.3) {

          status = 'good';

          label = 'Tren sedang menguat ';

        } else if (m >= -0.3) {

          status = 'warn';

          label = 'Tren bergerak sideways ';

        } else {

          status = 'bad';

          label = 'Tren sedang melemah ';

        }

        const text = (m >= 0 ? '-- ' : ' ') + Math.abs(m).toFixed(3);

        return { status, text, label, gauge };

      }

      case 'volatility': {

        const v = (value || 0) * 100;

        const clamped = Math.max(0, Math.min(100, v));

        const gauge = clamped;

        let status, label;

        if (v < 35) {

          status = 'good';

          label = 'Stabil';

        } else if (v <= 60) {

          status = 'warn';

          label = 'Fluktuasi sedang';

        } else {

          status = 'bad';

          label = 'Fluktuasi tinggi';

        }

        const text = v.toFixed(1) + '%';

        return { status, text, label, gauge };

      }

      case 'pulse': {

        const p = value || 0;

        const clamped = Math.max(0, Math.min(100, p));

        const gauge = clamped;

        let status, label;

        if (p > 65) {

          status = 'good';

          label = 'Pasar sehat';

        } else if (p >= 40) {

          status = 'warn';

          label = 'Cukup sehat';

        } else {

          status = 'bad';

          label = 'Pasar lemah';

        }

        const text = p.toFixed(0) + '/100';

        return { status, text, label, gauge };

      }

      case 'timing': {

        const t = value || 0;

        const clamped = Math.max(0, Math.min(100, t));

        const gauge = clamped;

        let status, label;

        if (t > 70) {

          status = 'good';

          label = 'Waktu sangat baik';

        } else if (t >= 45) {

          status = 'warn';

          label = 'Waktu cukup baik';

        } else {

          status = 'bad';

          label = 'Belum saat terbaik';

        }

        const text = t.toFixed(0) + '/100';

        return { status, text, label, gauge };

      }

      case 'fomo': {

        const f = value || 0;

        const clamped = Math.max(0, Math.min(1, f));

        const gauge = clamped * 100;

        let status, label;

        if (f < 0.2) {

          status = 'good';

          label = 'Tren organik';

        } else if (f <= 0.5) {

          status = 'warn';

          label = 'Ada indikasi hype';

        } else {

          status = 'bad';

          label = 'Hype tinggi, waspada';

        }

        const text = f.toFixed(2);

        return { status, text, label, gauge };

      }

      default:

        return { status: 'neutral', text: '—', label: '', gauge: 0 };

    }

  };

  // ── BADGE SYSTEM (4 STATES) 

  const badgeEl = document.getElementById('summary-badge');

  const score = d.entry_timing_score || 0;

  let badgeClass = '', badgeText = '';

  if (score >= 80) { badgeClass = 'good'; badgeText = 'Kondisi Baik'; }

  else if (score >= 60) { badgeClass = 'warn'; badgeText = 'Perlu Persiapan'; }

  else if (score >= 40) { badgeClass = 'alert'; badgeText = 'Hati-hati'; }

  else { badgeClass = 'bad'; badgeText = 'Tidak Disarankan'; }

  badgeEl.innerHTML = `<div class="summary-badge-item ${badgeClass}">${badgeText}</div>`;

  const verdictEl = document.getElementById('summary-verdict');

  const keyword = d.keyword || '(keyword)';

  let verdictText = '';

  if (score >= 80) verdictText = `Ini waktu yang <strong>bagus</strong> untuk mulai jualan <strong>${keyword}</strong>. Data menunjukkan pasar sedang tumbuh dan persaingan masih bisa ditembus.`;

  else if (score >= 60) verdictText = `Peluang untuk <strong>${keyword}</strong> cukup menjanjikan, tapi <em>perlu persiapan</em>. Pasar aktif tapi ada beberapa hal yang perlu kamu waspadai.`;

  else if (score >= 40) verdictText = `Hati-hati sebelum jual <strong>${keyword}</strong>. Kondisi pasar sedang kurang stabil. Boleh dicoba tapi dengan modal kecil dulu.`;

  else verdictText = `Saat ini <em>bukan waktu terbaik</em> untuk <strong>${keyword}</strong>. Tren sedang turun atau pasar sudah terlalu penuh.`;

  verdictEl.innerHTML = `<p>${verdictText}</p>`;

  // ── 6-ITEM METRIC GRID (3-COLUMN) 

  const gridEl = document.getElementById('summary-grid');

  gridEl.innerHTML = '';

  const metrics = [

    {

      key: 'growth',

      label: 'Pertumbuhan 7 Hari',

      getValue: () => getValue('growth', d.growth || 0),

      getExplain: (val) => val.label

    },

    {

      key: 'momentum',

      label: 'Momentum',

      getValue: () => getValue('momentum', d.momentum || 0),

      getExplain: (val) => val.label

    },

    {

      key: 'volatility',

      label: 'Volatilitas',

      getValue: () => getValue('volatility', d.volatility || 0),

      getExplain: (val) => `Status: ${val.label}`

    },

    {

      key: 'pulse',

      label: 'Kesehatan Pasar',

      getValue: () => getValue('pulse', d.market_pulse_score || 0),

      getExplain: (val) => `Status: ${val.label}`

    },

    {

      key: 'timing',

      label: 'Entry Timing',

      getValue: () => getValue('timing', d.entry_timing_score || 0),

      getExplain: (val) => val.label

    },

    {

      key: 'fomo',

      label: 'FOMO Index',

      getValue: () => getValue('fomo', d.fomo_index || 0),

      getExplain: (val) => val.label

    }

  ];

  metrics.forEach(metric => {

    const val = metric.getValue();

    const status = val.status || 'neutral';

    const gauge = typeof val.gauge === 'number' ? Math.max(0, Math.min(100, val.gauge)) : 0;

    const explain = metric.getExplain ? metric.getExplain(val, d) : (metric.explain || '');

    const div = document.createElement('div');

    div.className = `summary-item si-${status}`;

    div.innerHTML = `

          <div class="summary-item-label">${metric.label}</div>

          <div class="summary-item-main">

            <div class="summary-item-value ${status}">${val.text}</div>

            <div class="summary-item-status status-${status}">${val.label || ''}</div>

          </div>

          <div class="summary-item-gauge">

            <div class="summary-metric-gauge-track">

              <div class="summary-metric-gauge-fill status-${status}" data-target="${gauge}"></div>

            </div>

          </div>

          <div class="summary-item-explanation">${explain}</div>

        `;

    gridEl.appendChild(div);

  });

  // Animate gauge bars after DOM insertion

  requestAnimationFrame(() => {

    gridEl.querySelectorAll('.summary-metric-gauge-fill').forEach(el => {

      const target = parseFloat(el.getAttribute('data-target') || '0');

      const pct = Math.max(0, Math.min(100, target));

      el.style.width = pct + '%';

    });

  });

  // ── NEWS SECTION (if data exists) 

  if (d.news && Array.isArray(d.news) && d.news.length > 0) {

    const newsSection = document.getElementById('summary-news-section');

    const newsList = document.getElementById('summary-news-list');

    newsList.innerHTML = '';

    d.news.forEach(item => {

      const newsItem = document.createElement('a');

      newsItem.href = item.url || '#';

      newsItem.target = '_blank';

      newsItem.className = 'summary-news-item';

      newsItem.innerHTML = `

            <div class="summary-news-item-title">${item.title}</div>

            <div class="summary-news-item-meta">

              <span>${item.source || 'Berita'}</span>

              <span>${item.time_ago || 'Baru'}</span>

            </div>

          `;

      newsList.appendChild(newsItem);

    });

    newsSection.style.display = 'block';

  } else {

    document.getElementById('summary-news-section').style.display = 'none';

  }

  // ── ACTION HINT (REKOMENDASI) 

  const hintEl = document.getElementById('summary-action-hint');

  let hint = '';

  if (score >= 80) {

    hint = `Kondisi amat mendukung. <strong>Segera siapkan stok</strong>, buat konten promosi, dan mulai listing produk. Manfaatkan momentum sebelum kompetitor bertambah.`;

  } else if (score >= 60) {

    hint = `Mulai persiapkan bisnis sekarang. <strong>Riset kompetitor</strong>, tentukan harga, dan siapkan modal. Jangan tunggu momentum hilang.`;

  } else if (score >= 40) {

    hint = `Boleh coba dengan modal minimal. <strong>Uji dulu pasar</strong> dengan jumlah kecil sebelum investasi besar. Pantau 23 minggu ke depan.`;

  } else {

    hint = `Sebaiknya <strong>tahan dulu</strong> dan cari peluang lain. Gunakan Mode Banding untuk mencari produk yang lebih menjanjikan.`;

  }

  hintEl.innerHTML = hint;

  card.style.display = 'block';

}

function setAiInsightState(mode) {
  const trigger = document.getElementById('ai-trigger-state');
  const loading = document.getElementById('ai-loading-state');
  const result = document.getElementById('ai-result-state');

  const states = { trigger, loading, result };
  Object.values(states).forEach((el) => {
    if (!el) return;
    el.classList.add('hidden');
    el.style.removeProperty('display');
  });

  const active = states[mode];
  if (active) {
    active.classList.remove('hidden');
    if (mode === 'result') {
      active.style.display = 'grid';
    } else if (mode === 'trigger') {
      active.style.display = 'block';
    } else if (mode === 'loading') {
      active.style.display = 'flex';
    }
  }
}

function showAiTriggerState() {
  setAiInsightState('trigger');
  const btn = document.getElementById('ai-trigger-btn');
  if (btn) {
    btn.disabled = false;
    btn.textContent = 'Dapatkan Insight Bisnis AI';
  }
}

function scrollToAiInsight() {

  scrollToSection('#ai-card-wrapper'); // SENTRA AUDIT — primary CTA helper

}

async function triggerAiInsight() {

  if (_aiInsightGenerated || !lastAnalysisData) return;

  const triggerState = document.getElementById('ai-trigger-state');

  const loadingState = document.getElementById('ai-loading-state');

  const resultState = document.getElementById('ai-result-state');

  const btn = document.getElementById('ai-trigger-btn');

  if (btn) btn.disabled = true;

  setAiInsightState('loading');

  try {

    const res = await fetch('/api/get-ai-insight', {

      method: 'POST',

      headers: getAuthHeaders(),

      body: JSON.stringify(lastAnalysisData)

    });

    const aiData = await res.json();

    if (!res.ok) throw new Error(aiData.error || 'AI Error');

    setAiInsightState('result');

    if (aiData.ai_insight) {

      renderAiCards(aiData.ai_insight);

      _aiInsightGenerated = true;

      // Defer GSAP until after all staggered setTimeout insertions finish
      // renderAiCards uses 0/400/800ms delays — 900ms ensures all are done
      setTimeout(() => {
        if (typeof gsap !== 'undefined') {
          gsap.fromTo('#ai-result-state > div',
            { y: 20, opacity: 0 },
            { y: 0, opacity: 1, duration: 0.6, stagger: 0.15, ease: 'power2.out' }
          );
        }
      }, 900);

    }

  } catch (err) {

    console.error('[AI INSIGHT]', err);

    setAiInsightState('trigger');

    if (btn) {

      btn.disabled = false;

      btn.textContent = 'Coba Lagi';

    }

    async function triggerCompareAi() {
      const el = document.getElementById('cmp-ai');
      if (!el || !lastCompareData) return;
      el.innerHTML = '<span class="text-[10px] animate-pulse">Membandingkan tren...</span>';
      try {
        const res = await fetch('/api/get-compare-ai', {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify(lastCompareData)
        });
        const d = await res.json();
        if (d.ai_insight) {
          typeWriter(el, d.ai_insight.replace(/\*\*/g, ''), 6);
        } else {
          el.textContent = "Analisis tidak tersedia.";
        }
      } catch (e) { el.textContent = "Gagal memuat AI."; }
    }

    async function triggerLocalAi() {
      const el = document.getElementById('r-local-insight');
      if (!el || !lastAnalysisResult) return;
      el.innerHTML = '<span class="text-[10px] animate-pulse">Menganalisis wilayah...</span>';
      try {
        const res = await fetch('/api/get-local-ai', {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify({
            keyword: lastAnalysisResult.keyword,
            regional_data: lastAnalysisResult.regional_interest
          })
        });
        const d = await res.json();
        if (d.ai_insight) {
          typeWriter(el, d.ai_insight, 5);
        } else {
          el.textContent = "Strategi lokal tidak tersedia.";
        }
      } catch (e) { el.textContent = "Error AI."; }
    }

  }

}

/*  KEYWORD NEWS (Google News RSS via backend)  */

async function fetchKeywordNews(keyword) {

  const list = document.getElementById('summary-news-list');

  if (!list) return;

  try {

    const res = await fetch('/api/keyword-news', {

      method: 'POST',

      headers: { 'Content-Type': 'application/json' },

      body: JSON.stringify({ keyword })

    });

    const data = await res.json();

    if (!res.ok || !data.news || data.news.length === 0) {

      list.innerHTML = `<div class="text-zinc-600 text-xs py-4 italic">Tidak ada berita terbaru untuk "${keyword}"</div>`;

      return;

    }

    list.innerHTML = '';

    data.news.slice(0, 4).forEach((item, i) => {

      const div = document.createElement('div');

      div.className = 'group relative pl-6 pb-4 border-l border-zinc-800 last:pb-0';

      div.innerHTML = `

            <div class="absolute left-[-5px] top-0 w-2.5 h-2.5 bg-zinc-800 border border-zinc-700 rounded-full group-hover:bg-brand transition-colors"></div>

            <a href="${item.url}" target="_blank" class="block">

              <div class="text-[10px] font-mono text-zinc-500 uppercase tracking-widest mb-1 group-hover:text-brand transition-colors">

                ${item.source || 'News'} -- ${item.time_ago || 'Baru'}

              </div>

              <div class="text-xs text-zinc-300 line-clamp-2 leading-relaxed group-hover:text-white transition-colors">

                ${item.title}

              </div>

            </a>

          `;

      list.appendChild(div);

    });

    gsap.from(list.children, { x: 10, opacity: 0, duration: 0.5, stagger: 0.1 });

  } catch (err) {

    list.innerHTML = `<div class="text-zinc-600 text-xs py-4">Gagal memuat berita.</div>`;

  }

}

/*  SECTOR CATEGORY  */

const CATEGORY_KEYWORDS = {

  fashion: 'baju wanita',

  beauty: 'skincare',

  fnb: 'kuliner Indonesia',

  gadget: 'earbuds wireless',

  home: 'dekorasi rumah',

  hobi: 'peralatan olahraga',

  musiman: 'hampers lebaran',

};

function analyzeCategory(type) {

  const kw = CATEGORY_KEYWORDS[type];

  if (!kw) return;

  // Exit compare mode if active

  if (compareMode) toggleCompareMode();

  // Fill in search input

  document.getElementById('kw').value = kw;

  // Visual feedback — mark card as active

  document.querySelectorAll('.sector-card').forEach(c => c.classList.remove('loading-sector'));

  const card = document.getElementById('sc-' + type);

  if (card) card.classList.add('loading-sector');

  // Scroll to search area then trigger search

  document.getElementById('single-search').scrollIntoView({ behavior: 'smooth', block: 'center' });

  setTimeout(() => {

    doSearch();

    if (card) card.classList.remove('loading-sector');

  }, 400);

}

/*  COMPARE RENDERING  */

function renderCompareResults(d) {

  lastCompareData = d;

  // Force reset visibility

  const cmpEl = document.getElementById('compare-results');

  cmpEl.style.opacity = '1';

  cmpEl.style.transform = 'none';

  cmpEl.style.visibility = 'visible';

  const a = d.keyword_a;

  const b = d.keyword_b;

  const c = d.comparison;

  const t = d.trend_data;

  // Header

  document.getElementById('cmp-kw-a').textContent = a.keyword;

  document.getElementById('cmp-kw-b').textContent = b.keyword;

  document.getElementById('cmp-ts').textContent =

    new Date().toLocaleString('id-ID', { dateStyle: 'medium', timeStyle: 'short' });

  // Table headers

  document.getElementById('cmp-th-a').textContent = a.keyword;

  document.getElementById('cmp-th-b').textContent = b.keyword;

  // Winner banner

  document.getElementById('cmp-winner').textContent = c.winner_overall;

  document.getElementById('cmp-winner-score').textContent =

    `Skor Gabungan  ${a.keyword}: ${c.score_a} -- ${b.keyword}: ${c.score_b}`;

  // Build table rows

  const metrics = [

    { label: 'Growth 7 Hari', va: (a.growth * 100).toFixed(1) + '%', vb: (b.growth * 100).toFixed(1) + '%', winner: c.winner_growth },

    { label: 'Momentum', va: a.momentum.toFixed(3), vb: b.momentum.toFixed(3), winner: c.winner_momentum },

    { label: 'Volatilitas', va: (a.volatility * 100).toFixed(1) + '%', vb: (b.volatility * 100).toFixed(1) + '%', winner: c.winner_stability },

    { label: 'Market Pulse', va: a.market_pulse_score.toFixed(1), vb: b.market_pulse_score.toFixed(1), winner: c.winner_pulse },

    { label: 'Entry Timing', va: a.entry_timing_score.toFixed(1), vb: b.entry_timing_score.toFixed(1), winner: c.winner_timing },

    { label: 'FOMO Index', va: a.fomo_index.toFixed(2), vb: b.fomo_index.toFixed(2), winner: c.winner_fomo },

    { label: 'Saturasi', va: a.saturation_index.toFixed(1), vb: b.saturation_index.toFixed(1), winner: c.winner_saturation },

    { label: 'Fase Lifecycle', va: a.lifecycle_stage, vb: b.lifecycle_stage, winner: '—' },

    { label: 'Risk Level', va: a.risk_level, vb: b.risk_level, winner: '—' },

  ];

  const tbody = document.getElementById('cmp-tbody');

  tbody.innerHTML = '';

  metrics.forEach(m => {

    const tr = document.createElement('tr');

    const isWinA = m.winner === a.keyword;

    const isWinB = m.winner === b.keyword;

    tr.innerHTML = `

      <td>${m.label}</td>

      <td class="col-a ${isWinA ? 'val-winner' : 'val-loser'}">${m.va}</td>

      <td class="col-b ${isWinB ? 'val-winner' : 'val-loser'}">${m.vb}</td>

      <td class="winner-cell">${m.winner}</td>

    `;

    tbody.appendChild(tr);

  });

  // Chart.js

  renderTrendChart(t, a.keyword, b.keyword);

  // AI Insight (Manual only)

  const aiEl = document.getElementById('cmp-ai');

  if (aiEl) aiEl.innerHTML = '<button class="px-4 py-2 border border-brand/30 text-brand text-[10px] uppercase tracking-widest hover:bg-brand/10 transition-all" onclick="triggerCompareAi()">Generate AI Comparison</button>';

  // cleaned: removed dead code — duplicate switchTab() nested inside compare handler (correct global definition exists below)

  const observer = new IntersectionObserver((entries) => {

    entries.forEach(entry => {

      if (entry.isIntersecting) {

        entry.target.style.animationPlayState = 'running';

      }

    });

  }, { threshold: 0.1 });

  document.querySelectorAll('.howto-card, .tip-card, .metric-guide-card').forEach(el => {

    el.style.animationPlayState = 'paused';

    observer.observe(el);

  });

  // Show

  document.getElementById('compare-results').style.display = 'block';

  setTimeout(() => document.getElementById('compare-results').scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);

}

function renderTrendChart(trendData, labelA, labelB) {

  const canvas = document.getElementById('cmp-chart');

  if (trendChart) { trendChart.destroy(); trendChart = null; }

  if (!trendData || !trendData.dates) {

    canvas.parentElement.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-dim)">Data tren tidak tersedia</div>';

    return;

  }

  const labels = trendData.dates.map(d => {

    const dt = new Date(d);

    return dt.toLocaleDateString('id-ID', { day: 'numeric', month: 'short' });

  });

  const ctx = canvas.getContext('2d');

  trendChart = new Chart(ctx, {

    type: 'line',

    data: {

      labels: labels,

      datasets: [

        {

          label: labelA,

          data: trendData.values_a,

          borderColor: '#D4A843',

          backgroundColor: 'rgba(212,168,67,.1)',

          borderWidth: 2.5,

          pointRadius: 0,

          pointHoverRadius: 5,

          pointHoverBackgroundColor: '#D4A843',

          tension: 0.35,

          fill: true,

        },

        {

          label: labelB,

          data: trendData.values_b,

          borderColor: '#3498DB',

          backgroundColor: 'rgba(52,152,219,.1)',

          borderWidth: 2.5,

          pointRadius: 0,

          pointHoverRadius: 5,

          pointHoverBackgroundColor: '#3498DB',

          tension: 0.35,

          fill: true,

        }

      ]

    },

    options: {

      responsive: true,

      maintainAspectRatio: false,

      interaction: {

        mode: 'index',

        intersect: false,

      },

      plugins: {

        legend: {

          display: true,

          position: 'top',

          align: 'end',

          labels: {

            color: '#B0A888',

            font: { family: "'Syne',sans-serif", size: 11, weight: '600' },

            boxWidth: 14,

            boxHeight: 3,

            padding: 16,

            usePointStyle: false,

          }

        },

        tooltip: {

          backgroundColor: '#181510',

          titleColor: '#F2ECD8',

          bodyColor: '#B0A888',

          borderColor: 'rgba(212,168,67,.3)',

          borderWidth: 1,

          padding: 12,

          titleFont: { family: "'Syne',sans-serif", size: 11, weight: '700' },

          bodyFont: { family: "'DM Mono',monospace", size: 12 },

          callbacks: {

            label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y}`

          }

        }

      },

      scales: {

        x: {

          grid: { color: 'rgba(74,69,53,.2)', drawBorder: false },

          ticks: {

            color: '#4A4535',

            font: { family: "'DM Mono',monospace", size: 10 },

            maxTicksLimit: 12,

            maxRotation: 0,

          }

        },

        y: {

          grid: { color: 'rgba(74,69,53,.15)', drawBorder: false },

          ticks: {

            color: '#4A4535',

            font: { family: "'DM Mono',monospace", size: 10 },

          },

          beginAtZero: true,

          max: 100,

          title: {

            display: true,

            text: 'Interest',

            color: '#4A4535',

            font: { family: "'Syne',sans-serif", size: 10, weight: '600' }

          }

        }

      }

    }

  });

}

/*  TEXT SANITIZATION  */

function sanitizeText(str) {
  if (!str) return '';
  return String(str)
    .replace(/<[^>]*>/g, '')
    .replace(/\s{2,}/g, ' ')
    .trim();
}

function normalizeRegionalInterestData(items) {
  if (!Array.isArray(items)) return [];
  return items
    .map((item) => {
      const province = item?.province || item?.name || item?.region || item?.wilayah || '';
      const rawValue = item?.value ?? item?.score ?? item?.index ?? item?.interest ?? item?.search_interest ?? 0;
      const value = Math.max(0, Math.min(100, Number(rawValue) || 0));
      return {
        province: String(province).trim(),
        value
      };
    })
    .filter((item) => item.province.length > 0);
}

async function doSearch() {

  const kw = document.getElementById('kw').value.trim();

  const geo = document.getElementById('geo-select')?.value || 'ID';

  if (!kw) { showErr('Masukkan keyword terlebih dahulu.'); return; }

  setLoading(true, false);

  const regionalSec = document.getElementById('regional-section');

  if (regionalSec) regionalSec.style.display = 'none';

  try {

    const controller = new AbortController();

    const timeout = setTimeout(() => controller.abort(), 90000);

    const apiParams = { keyword: kw, geo: geo, user_id: userState.userId || '', cat: 0 };

    const [res, resLocal] = await Promise.all([

      fetch('/api/analyze', { method: 'POST', headers: getAuthHeaders(), body: JSON.stringify(apiParams), signal: controller.signal }),

      fetch('/api/analyze-local', { method: 'POST', headers: getAuthHeaders(), body: JSON.stringify(apiParams), signal: controller.signal }).catch(e => {

        console.error("[doSearch] /api/analyze-local CRASHED:", e);

        return null;

      })

    ]);

    console.log("[DEBUG] Main API Status:", res.status);

    console.log("[DEBUG] Local API Response:", resLocal);

    if (resLocal) console.log("[DEBUG] Local API Status:", resLocal.status);

    clearTimeout(timeout);

    const data = await res.json();

    if (res.status === 403 && data.error_code === 'LIMIT_EXCEEDED') {

      showUpgradeModal('limit'); setLoading(false, false); return;

    }

    if (!res.ok || data.error) {

      showErr(data.error || 'Terjadi kesalahan.'); setLoading(false, false); return;

    }

    if (resLocal && resLocal.ok) {

      try {

        const localData = await resLocal.json();

        if (localData) {

          const localRegionalRaw =
            localData.regional_data ||
            localData.regional_interest ||
            localData.regional_breakdown ||
            data.regional_interest ||
            [];
          data.regional_interest = normalizeRegionalInterestData(localRegionalRaw);

          data.regional_breakdown = localData.regional_breakdown || [];

          data.local_insight = localData.local_insight || "";

        }

      } catch (e) {

        console.warn('[doSearch] Gagal parse localData', e);

      }

    }

    // Sanitize news

    if (data.news) data.news = data.news.map(n => ({ ...n, title: sanitizeText(n.title) }));
    data.regional_interest = normalizeRegionalInterestData(data.regional_interest);

    lastAnalysisResult = data;

    renderResults(data);

    // Handle UI visibility & triggers for merged regional data

    if (regionalSec && data.regional_interest && data.regional_interest.length > 0) {

      regionalSec.style.display = 'block';
      if (window.MapLogic && typeof window.MapLogic.refresh === 'function') {
        window.MapLogic.refresh();
      }

      const loader = document.getElementById('map-loader');

      if (loader) loader.style.display = 'none';

      // Update map specifically

      if (window.MapLogic) window.MapLogic.update(data.regional_interest);

      // Trigger insight typing

      if (!data.local_insight) {
        const insightEl = document.getElementById('r-local-insight');
        if (insightEl) insightEl.innerHTML = '<button class="text-[10px] text-brand/60 underline uppercase tracking-tighter" onclick="triggerLocalAi()">Klik untuk Strategi Lokal</button>';
      } else {
        const insightEl = document.getElementById('r-local-insight');
        if (insightEl) typeWriter(insightEl, sanitizeText(data.local_insight), 5);
      }

    }

    fetchKeywordNews(kw);

    setLoading(false, false);

  } catch (e) {

    console.error('[doSearch]', e);

    showErr(e.name === 'AbortError' ? 'Waktu habis. Coba lagi.' : 'Terjadi kesalahan. Coba lagi.');

    setLoading(false, false);

  }

}

/* -- UPGRADE MODAL -- */

function showUpgradeModal(reason) {

  const title = document.getElementById('modal-title');

  const desc = document.getElementById('modal-desc');

  if (reason === 'pdf') {

    if (title) title.textContent = 'Fitur Khusus Pro';

    if (desc) desc.innerHTML = 'Download PDF hanya tersedia untuk pengguna <strong>Pro</strong>.<br>Upgrade sekarang untuk akses penuh ke semua fitur premium.';

  } else {

    if (title) title.textContent = 'Buka Akses Penuh Sentra';

    if (desc) desc.innerHTML = 'Kamu sudah menggunakan 5 riset hari ini.<br>Upgrade ke <strong>Pro</strong> untuk riset tanpa batas, analisis per-provinsi, dan ekspor laporan bisnis.';

  }

  document.getElementById('upgrade-modal').classList.add('open');

  document.body.style.overflow = 'hidden';

}

function closeUpgradeModal() {

  document.getElementById('upgrade-modal').classList.remove('open');

  unlockScroll();

}

function handleModalOverlayClick(e) {

  if (e.target === document.getElementById('upgrade-modal')) closeUpgradeModal();

}

/*  IDE PRODUK WIZARD  */

const IP_KATEGORI = [

  { svg: '<svg width="28" height="28" viewBox="0 0 24 24"><path d="M3 2v7c0 1.1.9 2 2 2h2v11M7 2v20M15 2c0 0-2 2-2 5s2 5 2 5v10M19 2v5h-4"/></svg>', nama: 'Makanan', value: 'Makanan' },

  { svg: '<svg width="28" height="28" viewBox="0 0 24 24"><path d="M5 3h14l-2 16H7L5 3z"/><path d="M3 3h18M10 7l4 4"/></svg>', nama: 'Minuman', value: 'Minuman' },

  { svg: '<svg width="28" height="28" viewBox="0 0 24 24"><path d="M12 3a2 2 0 0 1 2 2c0 .74-.4 1.38-1 1.73V8l8 6H3l8-6V6.73A2 2 0 0 1 10 5a2 2 0 0 1 2-2z"/><path d="M3 14v5a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5"/></svg>', nama: 'Fashion', value: 'Fashion' },

  { svg: '<svg width="28" height="28" viewBox="0 0 24 24"><rect x="7" y="8" width="10" height="13" rx="2"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/><path d="M12 12v4M10 14h4"/></svg>', nama: 'Kecantikan', value: 'Produk Kecantikan' },

  { svg: '<svg width="28" height="28" viewBox="0 0 24 24"><path d="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z"/><path d="M9 8l-2 3h10l-2-3H9zM7 11l5 7 5-7"/></svg>', nama: 'Aksesoris', value: 'Aksesoris' },

  { svg: '<svg width="28" height="28" viewBox="0 0 24 24"><path d="M3.5 20.5l10-10M8 3c0 0 1 4-1 6s-4 2-4 2"/><path d="M20.5 3.5c0 0-6 1-8 6s0 10 0 10"/><path d="M15 6l3-3 3 3-3 3-3-3z"/></svg>', nama: 'Handmade', value: 'Handmade' },

  { svg: '<svg width="28" height="28" viewBox="0 0 24 24"><rect x="2" y="4" width="20" height="14" rx="2"/><path d="M2 18h20M10 11l2-3 2 3-2 1-2-1z"/></svg>', nama: 'Digital', value: 'Produk Digital' },

  { svg: '<svg width="28" height="28" viewBox="0 0 24 24"><path d="M3 12L12 3l9 9"/><path d="M9 21V12h6v9"/><path d="M3 12v9h18v-9"/></svg>', nama: 'Rumah Tangga', value: 'Produk Rumah Tangga' },

  { svg: '<svg width="28" height="28" viewBox="0 0 24 24"><path d="M12 19c-1.5 0-3-1-3-3 0-2 2-3 2-5"/><circle cx="12" cy="5" r="2"/><path d="M8 19h8"/><path d="M15 8c1.5 1 3 2.5 3 5a6 6 0 0 1-12 0c0-2.5 1.5-4 3-5"/></svg>', nama: 'Hobi & Kreatif', value: 'Hobi & Kreatif' },

  { svg: '<svg width="28" height="28" viewBox="0 0 24 24"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>', nama: 'Produk Anak', value: 'Produk Anak' }

];

const IP_MODAL = [

  { label: 'Modal Kecil', ket: 'Di bawah Rp 10 juta', kode: 'KCL', tier: 'Kecil' },

  { label: 'Modal Menengah', ket: 'Rp 10 — 50 juta', kode: 'MNG', tier: 'Menengah' },

  { label: 'Modal Besar', ket: 'Di atas Rp 50 juta', kode: 'BSR', tier: 'Besar' }

];

function openIdeWizard() {

  document.getElementById('ip-overlay').classList.add('open');

  document.getElementById('ip-modal').classList.add('open');

  document.body.style.overflow = 'hidden';

  renderIdeState(1);

}

function closeIdeWizard() {

  document.getElementById('ip-overlay').classList.remove('open');

  document.getElementById('ip-modal').classList.remove('open');

  document.body.style.removeProperty('overflow');

}

function resetIdeWizard() {

  selectedKategori = null;

  selectedModalTier = null;

  renderIdeState(1);

}

function ipHeaderHtml() {

  return '<div class="ip-header"><span class="ip-header-label">SENTRA — IDE PRODUK</span><button type="button" class="ip-header-close" onclick="closeIdeWizard()">&times;</button></div><hr class="ip-divider">';

}

function renderIdeState(step, data) {

  const inner = document.getElementById('ip-modal-inner');

  if (!inner) return;

  let body = '';

  if (step === 1) {

    body = '<div class="ip-step-indicator">01 / 02</div><h2 class="ip-title">Kategori mana yang ingin kamu masuki?</h2><div class="ip-cat-grid">' +

      IP_KATEGORI.map(k => '<div class="ip-cat-card' + (selectedKategori === k.value ? ' selected' : '') + '" onclick="handleKategoriSelect(\'' + k.value.replace(/'/g, "\\'") + '\')">' + k.svg + '<span class="ip-cat-name">' + k.nama + '</span></div>').join('') +

      '</div>';

  } else if (step === 2) {

    body = '<div class="ip-step-indicator">02 / 02</div><h2 class="ip-title">Berapa modal yang siap kamu alokasikan?</h2><div class="ip-modal-grid">' +

      IP_MODAL.map((m, i) => '<div class="ip-modal-card' + (selectedModalTier === m.tier ? ' selected' : '') + '" data-index="' + (i + 1) + '" onclick="handleModalSelect(\'' + m.tier + '\')"><span class="ip-modal-label">' + m.label + '</span><span class="ip-modal-ket">' + m.ket + '</span><span class="ip-modal-code">' + m.kode + '</span></div>').join('') +

      '</div>';

  } else if (step === 3) {

    body = '<div class="ai-gen-header"><div class="ai-gen-icon-pulse">&#10022;</div><div class="ai-gen-title">Sentra memindai database...</div></div><div class="ai-gen-steps">' +

      '<div class="ai-gen-step" id="ip-gen-step-1"><span class="step-dot active"></span><span class="step-text">Memfilter berdasarkan kategori & modal...</span></div>' +

      '<div class="ai-gen-step" id="ip-gen-step-2"><span class="step-dot"></span><span class="step-text">Menghitung skor peluang...</span></div>' +

      '<div class="ai-gen-step" id="ip-gen-step-3"><span class="step-dot"></span><span class="step-text">Menyiapkan rekomendasi terbaik...</span></div></div>' +

      '<div class="ai-gen-bar-track"><div class="ai-gen-bar-fill" id="ip-gen-bar"></div></div>';

  } else if (step === 4) {

    const list = data && data.length ? data : [];

    const catLabel = selectedKategori || '';

    const tierLabel = selectedModalTier || '';

    body = '<div class="ip-result-header"><span class="ip-chip">' + catLabel + '</span><span class="ip-chip">' + tierLabel + '</span><span class="ip-result-count">-- ' + list.length + ' ide ditemukan</span></div>';

    if (list.length === 0) {

      body += '<div class="ip-empty"><p class="ip-empty-title">Belum ada data untuk kombinasi ini.</p><p class="ip-empty-sub">Coba kategori atau modal yang berbeda.</p><button type="button" class="ip-reset-btn" onclick="resetIdeWizard()">Cari dengan kriteria lain</button></div>';

    } else {

      body += '<div class="ip-card-grid">' + list.map((row, i) => {

        const status = (row.status_pasar || '').toLowerCase().replace(/\s/g, '-');

        const rec = (row.rekomendasi || '').toLowerCase().replace(/\s/g, '-');

        const statusClass = status ? 'ip-badge-status-' + status : '';

        const recClass = rec ? 'ip-badge-rec-' + rec : '';

        const skor = Number(row.skor_peluang) || 0;

        const fillColor = skor > 75 ? '#22c55e' : skor > 50 ? 'var(--gold)' : '#ef4444';

        return '<div class="ip-card" style="--i: ' + i + '"><div class="ip-badge-row"><span class="ip-badge ' + statusClass + '">' + (row.status_pasar || '—') + '</span><span class="ip-badge ' + recClass + '">' + (row.rekomendasi || '—') + '</span></div><div class="ip-name">' + (row.nama_produk || '—') + '</div><div class="ip-highlight">' + (row.highlight || '—') + '</div><div class="ip-stats-grid"><div><span class="ip-stat-label">Tren</span><span class="ip-stat-value">' + (row.tren_persen != null ? row.tren_persen + '%' : '—') + '</span></div><div><span class="ip-stat-label">Margin</span><span class="ip-stat-value">' + (row.margin_persen != null ? row.margin_persen + '%' : '—') + '</span></div><div><span class="ip-stat-label">Kompetisi</span><span class="ip-stat-value">' + (row.kompetisi || '—') + '</span></div><div><span class="ip-stat-label">Target</span><span class="ip-stat-value">' + (row.target || '—') + '</span></div></div><div class="ip-skor-row"><span class="ip-skor-label">Skor peluang</span><span class="ip-skor-value">' + skor + '</span></div><div class="ip-skor-track"><div class="ip-skor-fill" id="ip-skor-fill-' + i + '" style="width:0;background:' + fillColor + '"></div></div><div class="ip-card-footer">Rp ' + (row.modal_min_juta != null ? row.modal_min_juta : '—') + '  ' + (row.modal_max_juta != null ? row.modal_max_juta : '—') + ' juta  --  ' + (row.puncak_penjualan || '—') + '</div></div>';

      }).join('') + '</div><button type="button" class="ip-reset-btn" onclick="resetIdeWizard()">Cari dengan kriteria lain</button>';

    }

  }

  inner.innerHTML = ipHeaderHtml() + body;

  if (step === 3) startIdeLoadingAnim();

  if (step === 4 && data && data.length) {

    requestAnimationFrame(() => {

      data.forEach((row, i) => {

        const el = document.getElementById('ip-skor-fill-' + i);

        if (el) {

          const skor = Math.min(100, Math.max(0, Number(row.skor_peluang) || 0));

          el.style.width = skor + '%';

        }

      });

    });

  }

}

function startIdeLoadingAnim() {

  const bar = document.getElementById('ip-gen-bar');

  const steps = [

    { id: 'ip-gen-step-1', delay: 0, progress: 30 },

    { id: 'ip-gen-step-2', delay: 700, progress: 65 },

    { id: 'ip-gen-step-3', delay: 1400, progress: 85 }

  ];

  steps.forEach((s, i) => {

    setTimeout(() => {

      if (i > 0) {

        const prev = document.getElementById(steps[i - 1].id);

        if (prev) { prev.classList.add('done'); const dot = prev.querySelector('.step-dot'); if (dot) { dot.classList.remove('active'); dot.classList.add('done'); } }

      }

      const cur = document.getElementById(s.id);

      if (cur) { const dot = cur.querySelector('.step-dot'); if (dot) dot.classList.add('active'); }

      if (bar) bar.style.width = s.progress + '%';

    }, s.delay);

  });

  setTimeout(() => {

    steps.forEach(s => {

      const el = document.getElementById(s.id);

      if (el) { el.classList.add('done'); const dot = el.querySelector('.step-dot'); if (dot) { dot.classList.remove('active'); dot.classList.add('done'); } }

    });

    if (bar) bar.style.width = '100%';

  }, 2100);

}

function handleKategoriSelect(supabaseValue) {

  selectedKategori = supabaseValue;

  setTimeout(() => renderIdeState(2), 350);

}

function handleModalSelect(tier) {

  selectedModalTier = tier;

  renderIdeState(3);

  fetchIdeProduk();

}

async function fetchIdeProduk() {

  const inner = document.getElementById('ip-modal-inner');

  const start = Date.now();

  let data = [];

  let err = null;

  try {

    const url = '/api/ide-produk?kategori=' + encodeURIComponent(selectedKategori || '') + '&modal_tier=' + encodeURIComponent(selectedModalTier || '');

    const res = await fetch(url);

    const json = await res.json();

    data = json.data || [];

    if (!res.ok) err = json.error || res.statusText;

  } catch (e) {

    err = e.message || 'Gagal memuat data';

  }

  const elapsed = Date.now() - start;

  const remaining = Math.max(0, 2000 - elapsed);

  setTimeout(() => {

    if (err && inner) {

      const msg = (err && err.length > 300) ? err.slice(0, 300) + '' : (err || 'Gagal memuat data. Coba lagi.');

      inner.innerHTML = ipHeaderHtml() + '<p class="ip-empty-title" style="padding:24px 0; max-width:520px; margin:0 auto;">' + msg + '</p><button type="button" class="ip-reset-btn" onclick="resetIdeWizard()">Cari dengan kriteria lain</button>';

    } else {

      renderIdeState(4, data);

    }

  }, remaining);

}

// Close modal on Escape key — unified handler

document.addEventListener('keydown', e => {

  if (e.key !== 'Escape') return;

  var authModal = document.getElementById('auth-modal');

  if (authModal && authModal.classList.contains('open')) {

    closeAuthModal();

    return;

  }

  var profilePanel = document.getElementById('profile-panel');

  if (profilePanel && profilePanel.classList.contains('open')) {

    closeProfilePanel();

    return;

  }

  var ipModal = document.getElementById('ip-modal');

  if (ipModal && ipModal.classList.contains('open')) {

    closeIdeWizard();

    return;

  }

  var radarPanel = document.getElementById('radar-float-panel');

  if (radarPanel && radarPanel.classList.contains('open')) {

    closeRadarPanel();

  } else {

    closeUpgradeModal();

  }

});

/*  TAB SWITCHER (How To Use)  */

function switchTab(tab) {

  document.querySelectorAll('.howto-tab').forEach(btn => btn.classList.remove('active'));

  const activeTab = document.getElementById('tab-' + tab);

  if (activeTab) activeTab.classList.add('active');

  document.querySelectorAll('.howto-pane').forEach(pane => {

    pane.classList.remove('active');

  });

  const targetPane = document.getElementById('pane-' + tab);

  if (targetPane) {

    targetPane.classList.add('active');

    const cards = targetPane.querySelectorAll('.howto-card, .tip-card, .metric-guide-card');

    cards.forEach((card, i) => {

      card.style.animation = 'none';

      card.offsetHeight; // reflow

      card.style.animation = `fadeUp .4s ease ${i * 0.08}s both`;

    });

  }

}

/*  RADAR PELUANG SEKTOR  */

// Data cache — pre-seeded by initRadarHeadlines

const radarDataCache = {};
const radarSparklineCharts = {};

const SECTOR_NAMES = {

  fashion: 'Fashion', beauty: 'Beauty & Perawatan',

  fnb: 'Makanan & Minuman', gadget: 'Gadget & Elektronik',

  home: 'Home & Living', hobi: 'Hobi & Lifestyle', musiman: 'Tren Musiman'

};

const SECTOR_BADGES = {

  fashion: 'FSH', beauty: 'BTY', fnb: 'FNB', gadget: 'GDG',

  home: 'HME', hobi: 'HBI', musiman: 'MSM'

};

function renderRadarSkeleton() {

  return `

        <button class="panel-close-btn" onclick="closeRadarPanel()">&#215;</button>

        <div style="padding:8px 0 32px;">

          <div class="skeleton-line" style="height:36px;width:55%;margin-bottom:24px;"></div>

          <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1px;margin-bottom:28px;">

            <div class="skeleton-line" style="height:80px;"></div>

            <div class="skeleton-line" style="height:80px;"></div>

            <div class="skeleton-line" style="height:80px;"></div>

          </div>

          <div class="skeleton-line" style="height:14px;width:30%;margin-bottom:14px;"></div>

          <div class="skeleton-line" style="height:100px;margin-bottom:28px;"></div>

          <div class="skeleton-line" style="height:14px;width:30%;margin-bottom:14px;"></div>

          <div class="skeleton-line" style="height:120px;margin-bottom:32px;"></div>

          <div class="skeleton-line" style="height:52px;"></div>

        </div>

      `;

}

function renderRadarExpand(sector, data) {

  const s = data.static || {};

  const news = data.news || [];

  const aiSignal = data.ai_signal || '';

  const badge = SECTOR_BADGES[sector] || 'SEC';

  const name = SECTOR_NAMES[sector] || sector;

  const pillsHTML = (s.top_subsectors || [])

    .map(sub => `<span class="radar-subsector-pill">${sub}</span>`)

    .join('');

  const newsHTML = news.length > 0

    ? news.slice(0, 3).map(n => `

            <div class="panel-news-item">

              <div class="panel-news-item-title">${n.title || 'Berita'}</div>

              <div class="panel-news-item-meta">

                <span>${n.source || 'Sumber'}</span>

                <span>·</span>

                <span>${n.time_ago || 'baru saja'}</span>

              </div>

            </div>`).join('')

    : `<div style="color:rgba(245,240,224,.25);font-size:12px;padding:16px 0;font-family:'DM Mono',monospace">Tidak ada berita terkini</div>`;

  const aiHTML = aiSignal

    ? `<div class="panel-ai-signal">

             <span class="panel-ai-label"> AI SIGNAL</span>

             <div class="panel-ai-text">${aiSignal}</div>

           </div>`

    : '';

  return `

        <button class="panel-close-btn" onclick="closeRadarPanel()">&#215;</button>

        <div class="panel-header">

          <div class="panel-sector-name">${name}</div>

          <div class="panel-badge">${badge}</div>

        </div>

        <div class="panel-stats-row">

          <div class="panel-stat">

            <div class="panel-stat-label">Nilai Pasar</div>

            <div class="panel-stat-value">${s.market_size_label || '—'}</div>

          </div>

          <div class="panel-stat">

            <div class="panel-stat-label">Growth YoY</div>

            <div class="panel-stat-value" style="color:var(--green)">+${s.yoy_growth || 0}%</div>

          </div>

          <div class="panel-stat">

            <div class="panel-stat-label">UMKM Share</div>

            <div class="panel-stat-value">${s.umkm_share || 0}%</div>

          </div>

        </div>

        <div class="panel-divider"></div>

        <span class="panel-section-label">Sub-sektor Populer</span>

        <div class="panel-subsectors-list">${pillsHTML}</div>

        <span class="panel-section-label">Berita Terkini</span>

        <div class="panel-news-items">${newsHTML}</div>

        ${aiHTML}

        <button class="panel-analyze-btn" onclick="closeRadarPanel(); analyzeCategory('${sector}')">

          Cek Peluang Lebih Dalam 

        </button>

      `;

}

function closeRadarPanel() {

  const panel = document.getElementById('radar-float-panel');

  const overlay = document.getElementById('radar-overlay');

  if (!panel || !overlay) return;

  panel.classList.remove('open');

  overlay.classList.remove('open');

  document.querySelectorAll('.radar-card').forEach(c => c.classList.remove('active'));

  panel.style.pointerEvents = 'none';

  overlay.style.pointerEvents = 'none';

  unlockScroll();

}

const SECTOR_CONFIG = {

  fashion: { name: "Fashion & Apparel", code: "FSH", color: "#EC4899" }, // Pink

  beauty: { name: "Beauty & Care", code: "BTY", color: "#A855F7" }, // Purple

  fnb: { name: "Food & Beverage", code: "FNB", color: "#F97316" }, // Orange

  gadget: { name: "Gadget & Elec", code: "GDT", color: "#3B82F6" }, // Blue

  home: { name: "Home & Living", code: "HME", color: "#14B8A6" }, // Teal

  hobi: { name: "Hobby & Lifestyle", code: "HBY", color: "#EF4444" }, // Red

  musiman: { name: "Tren Musiman", code: "SSN", color: "#EAB308" }  // Gold

};

const hardcodedData = {

  fashion: { yoy: 12.5, share: 15, spark: [50, 55, 60, 58, 65, 70, 75, 80] },

  beauty: { yoy: 28.4, share: 22, spark: [40, 48, 55, 60, 65, 75, 85, 95] },

  fnb: { yoy: 18.2, share: 25, spark: [80, 82, 85, 84, 88, 90, 89, 95] },

  gadget: { yoy: 8.4, share: 8, spark: [30, 32, 30, 35, 38, 40, 42, 45] },

  home: { yoy: 14.1, share: 12, spark: [45, 48, 50, 55, 52, 58, 60, 65] },

  hobi: { yoy: -2.3, share: 5, spark: [35, 32, 30, 28, 25, 26, 22, 20] },

  musiman: { yoy: 45.0, share: 18, spark: [10, 15, 20, 40, 80, 95, 85, 40] }

};

function getCompetitionBadge(share) {
  let label = 'Rendah';
  let cls = 'low';
  if (share > 20) { label = 'Tinggi'; cls = 'high'; }
  else if (share > 10) { label = 'Sedang'; cls = 'medium'; }

  return `
    <div class="radar-comp-tag ${cls}">
      <span class="radar-comp-dot"></span>
      <span class="radar-comp-text">${label}</span>
    </div>
  `;
}

function renderModernGrid() {

  const container = document.getElementById('radar-grid-modern');

  if (!container) return;



  // Find the sector with the highest YoY to mark as "hottest"

  let hottestSector = 'musiman';

  let maxGrowth = -999;



  Object.keys(hardcodedData).forEach(sector => {

    if (hardcodedData[sector].yoy > maxGrowth) {

      maxGrowth = hardcodedData[sector].yoy;

      hottestSector = sector;

    }

  });

  container.innerHTML = '';



  Object.keys(SECTOR_CONFIG).forEach(sector => {

    const conf = SECTOR_CONFIG[sector];

    const data = hardcodedData[sector];



    const growth = data.yoy;

    const colorClass = growth >= 0 ? 'text-green-400' : 'text-red-400';



    const isHottest = (sector === hottestSector);

    const flameHtml = isHottest ? '<span class="radar-card-hot" title="Paling panas minggu ini"><i class="fa-solid fa-fire"></i></span>' : '';

    const cardHtml = `
          <button class="radar-card-premium sector-card-modern group" type="button" style="--accent: ${conf.color};" aria-label="Lihat sektor ${conf.name}">
            <div class="radar-card-sheen"></div>
            
            <div class="radar-card-top">
              <div class="radar-card-code" style="background-color: ${conf.color}16; color: ${conf.color}; border-color: ${conf.color}35;">
                ${conf.code}
              </div>
              ${flameHtml}
            </div>

            <div class="radar-card-body">
              <h3 class="radar-sector-title" title="${conf.name}">${conf.name}</h3>
              
              <div class="radar-stats-grid">
                <div class="radar-stat-item">
                  <div class="radar-stat-value ${colorClass} sector-growth-counter" data-target="${growth}">0%</div>
                  <div class="radar-stat-label">Pertumbuhan YoY</div>
                </div>
              </div>

              <div class="radar-meta-row">
                <div class="radar-comp-wrapper">
                  <span class="radar-meta-hint">Persaingan</span>
                  ${getCompetitionBadge(data.share)}
                </div>
              </div>
            </div>

            <div class="radar-chart-area">
              <canvas id="spark-modern-${sector}"></canvas>
            </div>

            <div class="radar-card-accent-glow" style="background-color: ${conf.color};"></div>
          </button>
        `;



    container.innerHTML += cardHtml;

  });



  // Auto-update timestamp

  const now = new Date();

  const timeString = now.getHours().toString().padStart(2, '0') + ':' + now.getMinutes().toString().padStart(2, '0');

  if (document.getElementById('radar-uptime')) document.getElementById('radar-uptime').textContent = "LAST SYNC: " + timeString;



  // Render the charts

  renderPremiumSparklines();



  // Trigger GSAP

  initRadarAnimations();

}



function renderPremiumSparklines() {

  if (typeof Chart === 'undefined') return;

  Object.keys(SECTOR_CONFIG).forEach(sector => {

    const conf = SECTOR_CONFIG[sector];

    const canvas = document.getElementById('spark-modern-' + sector);

    if (!canvas) return;

    const values = hardcodedData[sector].spark;

    if (radarSparklineCharts[sector]) {
      radarSparklineCharts[sector].destroy();
    }

    radarSparklineCharts[sector] = new Chart(canvas, {

      type: 'line',

      data: {

        labels: values.map((_, i) => i),

        datasets: [{

          data: values,

          borderColor: conf.color,

          borderWidth: 2,

          tension: 0.5,

          pointRadius: 0,

          fill: true,

          backgroundColor: ctx => {

            const gradient = ctx.chart.ctx.createLinearGradient(0, 0, 0, 60);

            gradient.addColorStop(0, conf.color + '2B');

            gradient.addColorStop(1, 'transparent');

            return gradient;

          }

        }]

      },

      options: {

        events: [],

        responsive: true,

        maintainAspectRatio: false,

        plugins: { legend: { display: false }, tooltip: { enabled: false } },

        scales: { x: { display: false }, y: { display: false, min: Math.min(...values) - 5 } },

        animation: { duration: 1500, easing: 'easeOutQuart' }

      }

    });

  });

}



function initRadarModern() {

  renderModernGrid();

}

if (document.readyState === 'loading') {

  document.addEventListener('DOMContentLoaded', initRadarModern);

} else {

  initRadarModern();

};

function toggleRadarCard(sector, element) {

  const panel = document.getElementById('radar-float-panel');

  const overlay = document.getElementById('radar-overlay');

  document.querySelectorAll('.radar-card').forEach(c => c.classList.remove('active'));

  element.classList.add('active');

  panel.innerHTML = renderRadarSkeleton();

  panel.classList.add('open');

  overlay.classList.add('open');

  document.body.style.overflow = 'hidden';

  if (radarDataCache[sector]) {

    panel.innerHTML = renderRadarExpand(sector, radarDataCache[sector]);

    return;

  }

  fetch('/api/sector-radar', {

    method: 'POST',

    headers: { 'Content-Type': 'application/json' },

    body: JSON.stringify({ sector })

  })

    .then(r => r.json())

    .then(data => {

      if (data && !data.error) {

        radarDataCache[sector] = data;

        if (panel.classList.contains('open')) {

          panel.innerHTML = renderRadarExpand(sector, data);

        }

      } else {

        panel.innerHTML = `<button class="panel-close-btn" onclick="closeRadarPanel()">&#215;</button>

              <div style="padding:60px 0;text-align:center;color:rgba(245,240,224,.4);font-family:'DM Mono',monospace;font-size:12px">

                Gagal memuat data sektor

              </div>`;

      }

    })

    .catch(() => {

      panel.innerHTML = `<button class="panel-close-btn" onclick="closeRadarPanel()">&#215;</button>

            <div style="padding:60px 0;text-align:center;color:rgba(245,240,224,.4);font-family:'DM Mono',monospace;font-size:12px">

              Koneksi gagal

            </div>`;

    });

}

// Initialize card headline teasers async after DOM ready

function initRadarHeadlines() {

  const sectors = ['fashion', 'beauty', 'fnb', 'gadget', 'home', 'hobi', 'musiman'];

  sectors.forEach(sector => {

    if (radarDataCache[sector]) {

      _applyHeadline(sector, radarDataCache[sector]);

      return;

    }

    fetch('/api/sector-radar', {

      method: 'POST',

      headers: { 'Content-Type': 'application/json' },

      body: JSON.stringify({ sector })

    })

      .then(r => r.json())

      .then(data => {

        if (data && !data.error) {

          radarDataCache[sector] = data;

          _applyHeadline(sector, data);

        }

      })

      .catch(e => console.warn(`Radar headline ${sector}:`, e));

  });

}

function _applyHeadline(sector, data) {

  const headline = (data.news && data.news[0] && data.news[0].title) || '';

  const el = document.getElementById('hl-' + sector);

  if (el && headline) el.textContent = headline;

}

/*  SPARKLINE ENGINE  */

const SPARKLINE_COLORS = {

  fashion: '#D4A843',

  beauty: '#FF5252',

  fnb: '#D4A843',

  gadget: '#448AFF',

  home: '#D4A843',

  hobi: '#00E676',

  musiman: '#FF5252',

};

function generateMockSparkline(sector) {

  const base = {

    fashion: [45, 48, 44, 50, 52, 49, 55, 53, 58, 56, 60, 58, 62, 59, 64],

    beauty: [55, 58, 62, 65, 60, 68, 72, 70, 75, 73, 78, 76, 80, 82, 85],

    fnb: [50, 52, 48, 55, 53, 58, 56, 60, 58, 62, 65, 63, 67, 65, 70],

    gadget: [40, 42, 38, 41, 44, 40, 43, 45, 42, 46, 44, 47, 45, 48, 46],

    home: [42, 45, 43, 47, 44, 48, 46, 50, 48, 52, 50, 54, 52, 56, 54],

    hobi: [48, 52, 50, 55, 53, 58, 56, 60, 62, 58, 64, 62, 66, 64, 68],

    musiman: [35, 38, 42, 48, 55, 65, 75, 82, 88, 92, 95, 90, 85, 88, 92],

  };

  return base[sector] || [50, 52, 48, 55, 53, 58, 56, 60];

}

/*  RADAR PELUANG SEKTOR (MODERN)  */

function initSparklines() {

  const SECTOR_COLORS = {

    fashion: '#EF4444', beauty: '#A855F7', fnb: '#F97316',

    gadget: '#3B82F6', home: '#6366F1', hobi: '#10B981', musiman: '#FACC15'

  };

  Object.keys(SECTOR_COLORS).forEach(sector => {

    const canvas = document.getElementById('spark-' + sector);

    if (!canvas) return;

    const values = generateMockSparkline(sector);

    const color = SECTOR_COLORS[sector];

    if (typeof Chart !== 'undefined') {

      new Chart(canvas, {

        type: 'line',

        data: {

          labels: values.map((_, i) => i),

          datasets: [{

            data: values,

            borderColor: color,

            borderWidth: 2,

            tension: 0.4,

            pointRadius: 0,

            fill: true,

            backgroundColor: ctx => {

              const gradient = ctx.chart.ctx.createLinearGradient(0, 0, 0, 60);

              gradient.addColorStop(0, color + '22');

              gradient.addColorStop(1, 'transparent');

              return gradient;

            }

          }]

        },

        options: {

          responsive: true,

          maintainAspectRatio: false,

          plugins: { legend: { display: false }, tooltip: { enabled: false } },

          scales: { x: { display: false }, y: { display: false, min: Math.min(...values) - 10 } },

          animation: { duration: 2000, easing: 'easeOutQuart' }

        }

      });

    }

  });

}

function initRadarAnimations() {
  const cards = gsap.utils.toArray('.radar-card-premium');
  if (!cards.length) return;

  // Simple staggered entry for the grid
  gsap.fromTo(cards,
    { y: 30, opacity: 0 },
    {
      y: 0, opacity: 1,
      duration: 0.8,
      stagger: 0.1,
      ease: "power2.out",
      scrollTrigger: {
        trigger: ".radar-grid-modern",
        start: "top 85%"
      }
    }
  );
  // 4. Counter Animations
  document.querySelectorAll('.sector-growth-counter').forEach(el => {
    const targetValue = parseFloat(el.getAttribute('data-target')) || 0;
    const obj = { val: 0 };
    gsap.to(obj, {
      val: targetValue,
      duration: 2,
      scrollTrigger: { trigger: el, start: "top 95%" },
      onUpdate: () => {
        el.textContent = (obj.val >= 0 ? '+' : '') + obj.val.toFixed(1) + '%';
      }
    });
  });
}

if (document.readyState === 'loading') {

  document.addEventListener('DOMContentLoaded', () => {

    initRadarHeadlines();

    initSparklines();

    initRadarAnimations();

  });

} else {

  initRadarHeadlines();

  initSparklines();

  initRadarAnimations();

}

// ── ANIMATED TYPING PLACEHOLDER 

/*  SHARING & EXPORT  */

function shareToWhatsApp() {

  if (typeof lastAnalysisResult === 'undefined' || !lastAnalysisResult) {

    showErr("Lakukan analisis terlebih dahulu untuk membagikan hasil.");

    return;

  }

  const d = lastAnalysisResult;

  const kw = d.keyword || "Produk";

  const score = d.market_pulse_score || 0;

  const timing = d.entry_timing_label || "Fase Tidak Diketahui";



  const text = encodeURIComponent(

    ` *Sentra AI — Hasil Analisis Pasar*\n\n` +

    ` *Produk:* ${kw.toUpperCase()}\n` +

    ` *Skor Kesehatan:* ${score}/100\n` +

    ` *Fase Strategis:* ${timing}\n\n` +

    `Analisis mendalam lainnya bisa dicek di: ${window.location.origin}`

  );

  window.open(`https://wa.me/?text=${text}`, '_blank');

}

function downloadPdf() {

  window.print();

}

function initTypingPlaceholder() {

  const input = document.getElementById('kw');

  if (!input) return;

  const phrases = [

    "coba: sepatu sneakers lokal",

    "coba: kue kering lebaran",

    "coba: skincare vitamin c",

    "coba: tas rajut handmade",

    "coba: kopi arabika kemasan",

    "coba: baju gamis modern",

    "coba: lilin aromaterapi",

    "coba: camilan sehat anak"

  ];

  const TYPING_SPEED = 55;   // ms per karakter saat mengetik

  const DELETING_SPEED = 28;   // ms per karakter saat menghapus

  const PAUSE_FULL = 2200; // jeda setelah teks penuh sebelum dihapus

  const PAUSE_EMPTY = 400;  // jeda setelah teks terhapus sebelum teks berikutnya

  // Semua state disimpan dalam closure — tidak ada variabel global

  let currentIndex = 0;

  let charIndex = 0;

  let isDeleting = false;

  let isPaused = false;

  let timeoutId = null;

  function tick() {

    if (isPaused) return;

    const phrase = phrases[currentIndex];

    if (!isDeleting) {

      // Fase mengetik: tambah satu karakter

      charIndex++;

      input.placeholder = phrase.slice(0, charIndex);

      if (charIndex === phrase.length) {

        // Teks penuh — jeda sebelum mulai menghapus

        isDeleting = true;

        timeoutId = setTimeout(tick, PAUSE_FULL);

      } else {

        timeoutId = setTimeout(tick, TYPING_SPEED);

      }

    } else {

      // Fase menghapus: kurangi satu karakter

      charIndex--;

      input.placeholder = phrase.slice(0, charIndex);

      if (charIndex === 0) {

        // Teks habis — pindah ke item berikutnya lalu jeda

        isDeleting = false;

        currentIndex = (currentIndex + 1) % phrases.length;

        timeoutId = setTimeout(tick, PAUSE_EMPTY);

      } else {

        timeoutId = setTimeout(tick, DELETING_SPEED);

      }

    }

  }

  // Berhenti total saat input mendapat fokus

  input.addEventListener('focus', function () {

    isPaused = true;

    clearTimeout(timeoutId);

    input.placeholder = '';

  });

  input.addEventListener('blur', function () {

    if (input.value === '') {

      isPaused = false;

      currentIndex = (currentIndex + 1) % phrases.length;

      charIndex = 0;

      isDeleting = false;

      timeoutId = setTimeout(tick, PAUSE_EMPTY);

    }

  });

  timeoutId = setTimeout(tick, PAUSE_EMPTY);

}

initTypingPlaceholder();

// Scroll-to-top behavior (muncul setelah scroll > 400px)

const scrollTopBtn = document.getElementById('scrollTopBtn');

if (scrollTopBtn) {

  window.addEventListener('scroll', function () {

    if (window.scrollY > 400) {

      scrollTopBtn.classList.add('is-visible');

    } else {

      scrollTopBtn.classList.remove('is-visible');

    }

  });

  scrollTopBtn.addEventListener('click', function () {

    window.scrollTo({ top: 0, behavior: 'smooth' });

  });

}

// ── TESTIMONIAL CAROUSEL 

(function () {

  const track = document.getElementById('testiTrack');

  const dotsWrap = document.getElementById('testiDots');

  if (!track) return;

  const slides = track.querySelectorAll('.testi-slide');

  const total = slides.length;

  let current = 0;

  let autoTimer = null;

  // Buat dots

  slides.forEach((_, i) => {

    const d = document.createElement('div');

    d.className = 'testi-dot' + (i === 0 ? ' active' : '');

    d.onclick = () => goTo(i);

    dotsWrap.appendChild(d);

  });

  function goTo(idx) {

    current = (idx + total) % total;

    const slideWidth = slides[0].offsetWidth + 16;

    track.style.transform = `translateX(-${current * slideWidth}px)`;

    dotsWrap.querySelectorAll('.testi-dot').forEach((d, i) => {

      d.classList.toggle('active', i === current);

    });

  }

  // Auto-scroll setiap 3.5 detik

  function startAuto() {

    autoTimer = setInterval(() => goTo(current + 1), 3500);

  }

  function stopAuto() {

    clearInterval(autoTimer);

  }

  startAuto();

  // Touch / mouse drag

  let startX = 0, isDragging = false, dragDelta = 0;

  track.addEventListener('mousedown', e => {

    isDragging = true;

    startX = e.clientX;

    track.classList.add('dragging');

    stopAuto();

  });

  track.addEventListener('touchstart', e => {

    startX = e.touches[0].clientX;

    stopAuto();

  }, { passive: true });

  track.addEventListener('mousemove', e => {

    if (!isDragging) return;

    dragDelta = e.clientX - startX;

  });

  track.addEventListener('touchmove', e => {

    dragDelta = e.touches[0].clientX - startX;

  }, { passive: true });

  function endDrag() {

    if (Math.abs(dragDelta) > 50) {

      goTo(dragDelta < 0 ? current + 1 : current - 1);

    } else {

      goTo(current);

    }

    isDragging = false;

    dragDelta = 0;

    track.classList.remove('dragging');

    startAuto();

  }

  track.addEventListener('mouseup', endDrag);

  track.addEventListener('mouseleave', () => {

    if (isDragging) endDrag();

  });

  track.addEventListener('touchend', endDrag);

  // Pause saat hover

  track.addEventListener('mouseenter', stopAuto);

  track.addEventListener('mouseleave', startAuto);

})();

let _detailData = null;

function openDetailPanel() {

  if (!_detailData) return;

  populateDetailPanel(_detailData);

  document.getElementById('detail-overlay').style.display = 'block';

  document.getElementById('detail-panel').style.display = 'block';

  document.body.style.overflow = 'hidden';

}

function closeDetailPanel() {

  document.getElementById('detail-overlay').style.display = 'none';

  document.getElementById('detail-panel').style.display = 'none';

  document.body.style.removeProperty('overflow');

}

function _dmGauge(val, max, colorClass) {

  var pct = Math.min(Math.max((val / max) * 100, 0), 100);

  return '<div class="dm-gauge-track">' +

    '<div class="dm-gauge-fill ' + colorClass + '" style="width:' + pct + '%; background:currentColor;"></div>' +

    '</div>';

}

function _dmBlock(num, label, valueHTML, sublabel, explain, colorClass, extra) {

  return '<div class="detail-metric-block ' + (colorClass || '') + '">' +

    '<div class="dm-number">0' + num + '</div>' +

    '<div class="dm-label">' + label + '</div>' +

    '<div class="dm-value ' + (extra || 'dv-gold') + '">' + valueHTML + '</div>' +

    '<div class="dm-sublabel">' + sublabel + '</div>' +

    (explain ? '<div class="dm-explain">' + explain + '</div>' : '') +

    '</div>';

}

function populateDetailPanel(d) {

  var kw = d.keyword || '—';

  document.getElementById('detail-keyword-label').textContent = kw;

  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agt', 'Sep', 'Okt', 'Nov', 'Des'];

  var c = document.getElementById('detail-metrics-container');

  if (!c) return;

  var html = '';

  // ── KELOMPOK 1: KEPUTUSAN — html += '<div class="dm-section-title">// Keputusan Utama</div>';

  // 1. Entry Timing Score

  var ts = d.entry_timing_score || 0;

  var tl = d.entry_timing_label || '-';

  var tsColor = ts >= 70 ? 'dv-green' : ts >= 50 ? 'dv-gold' : ts >= 30 ? 'dv-amber' : 'dv-red';

  var tsClass = ts >= 70 ? 'dm-green' : ts >= 50 ? 'dm-gold' : ts >= 30 ? 'dm-amber' : 'dm-red';

  html += _dmBlock(1, 'Entry Timing Score', ts + '<span style="font-size:16px;color:var(--text-dim)"> / 100</span>',

    tl,

    'Skor gabungan dari <strong>10 faktor</strong> yang menentukan apakah sekarang adalah waktu terbaik untuk mulai berjualan produk ini. Di atas 70 = waktu terbaik. 50-69 = boleh masuk dengan persiapan. Di bawah 50 = tunggu atau hindari.',

    tsClass, tsColor);

  // 2. Lifecycle Stage

  var stage = d.lifecycle_stage || '-';

  var stageMap = {

    'Emerging': { color: 'dv-gold', cls: 'dm-gold', desc: 'Produk baru mulai dikenal pasar. <strong>Peluang awal yang bagus</strong>  masuk sekarang sebelum ramai.' },

    'Rising': { color: 'dv-green', cls: 'dm-green', desc: 'Tren sedang naik tajam. <strong>Momentum kuat</strong>  pasar sedang tumbuh aktif.' },

    'Peak': { color: 'dv-amber', cls: 'dm-amber', desc: 'Produk sedang di puncak popularitas. <strong>Hati-hati</strong>  persaingan tinggi, mungkin akan turun.' },

    'Stable': { color: 'dv-text', cls: '', desc: 'Tren relatif datar dan stabil. <strong>Pasar matang</strong>  bisa masuk tapi persaingan sudah ada.' },

    'Declining': { color: 'dv-red', cls: 'dm-red', desc: 'Minat pasar sedang menurun. <strong>Tidak disarankan</strong> untuk mulai berjualan saat ini.' }

  };

  var si = stageMap[stage] || { color: 'dv-text', cls: '', desc: '—' };

  html += _dmBlock(2, 'Lifecycle Stage', stage, 'Fase siklus hidup produk', si.desc, si.cls, si.color);

  // 3. Risk Level

  var risk = d.risk_level || '—';

  var riskMap = {

    'Low Risk': { color: 'dv-green', cls: 'dm-green', desc: 'Volatilitas rendah dan tidak ada sinyal hype berlebihan. <strong>Risiko investasi relatif kecil.</strong>' },

    'Medium Risk': { color: 'dv-amber', cls: 'dm-amber', desc: 'Ada potensi fluktuasi yang perlu diwaspadai. <strong>Masih layak, tapi siapkan strategi cadangan.</strong>' },

    'High Risk': { color: 'dv-red', cls: 'dm-red', desc: 'Tren sangat tidak stabil atau terdeteksi hype sesaat. <strong>Hindari investasi besar di produk ini sekarang.</strong>' }

  };

  var ri = riskMap[risk] || { color: 'dv-text', cls: '', desc: '—' };

  html += _dmBlock(3, 'Risk Level', risk, 'Berdasarkan volatilitas + FOMO index', ri.desc, ri.cls, ri.color);

  // ── KELOMPOK 2: METRIK PASAR — html += '<div class="dm-section-title">// Metrik Pasar</div>';

  html += '<div class="dm-grid-2">';

  // 4. Growth 7 Hari

  var gr = d.growth || 0;

  var grPct = (gr * 100).toFixed(1);

  var grColor = gr > 0 ? 'dv-green' : gr > -0.1 ? 'dv-amber' : 'dv-red';

  var grCls = gr > 0 ? 'dm-green' : gr > -0.1 ? 'dm-amber' : 'dm-red';

  html += _dmBlock(4, 'Growth 7 Hari',

    (gr >= 0 ? '+' : '') + grPct + '%',

    'Dibanding 7 hari sebelumnya',

    'Selisih rata-rata minat <strong>7 hari terakhir</strong> vs <strong>7 hari sebelumnya</strong>.',

    grCls, grColor);

  // 5. Momentum

  var mom = d.momentum || 0;

  var momFmt = (mom >= 0 ? '+' : '') + mom.toFixed(3);

  var momColor = mom > 0.2 ? 'dv-green' : mom > 0 ? 'dv-gold' : mom > -0.2 ? 'dv-amber' : 'dv-red';

  var momCls = mom > 0.2 ? 'dm-green' : mom > 0 ? 'dm-gold' : mom > -0.2 ? 'dm-amber' : 'dm-red';

  html += _dmBlock(5, 'Momentum',

    momFmt,

    mom > 0 ? 'Tren naik' : mom < 0 ? 'Tren turun' : 'Datar',

    'Kemiringan garis tren (regresi linear). <strong>Positif = naik, negatif = turun.</strong> Makin jauh dari 0, makin kuat tren-nya.',

    momCls, momColor);

  html += '</div><div class="dm-grid-2">';

  // 6. Volatilitas

  var vol = d.volatility || 0;

  var volPct = (vol * 100).toFixed(1);

  var volColor = vol < 0.3 ? 'dv-green' : vol < 0.5 ? 'dv-amber' : 'dv-red';

  var volCls = vol < 0.3 ? 'dm-green' : vol < 0.5 ? 'dm-amber' : 'dm-red';

  html += _dmBlock(6, 'Volatilitas',

    volPct + '%',

    vol < 0.3 ? 'Stabil' : vol < 0.5 ? 'Fluktuasi sedang' : 'Sangat fluktuatif',

    'Koefisien variasi minat. <strong>Makin kecil = makin stabil</strong> dan mudah diprediksi.',

    volCls, volColor);

  // 7. Market Pulse Score

  var pulse = d.market_pulse_score || 0;

  var pulseColor = pulse >= 65 ? 'dv-green' : pulse >= 45 ? 'dv-gold' : 'dv-red';

  var pulseCls = pulse >= 65 ? 'dm-green' : pulse >= 45 ? 'dm-gold' : 'dm-red';

  html += _dmBlock(7, 'Market Pulse',

    pulse + '<span style="font-size:14px;color:var(--text-dim)"> / 100</span>',

    'Kesehatan pasar keseluruhan',

    'Gabungan dari growth (40%), momentum (35%), dan stabilitas (25%). <strong>Di atas 65 = kondisi pasar sehat.</strong>',

    pulseCls, pulseColor);

  html += '</div><div class="dm-grid-2">';

  // 8. FOMO Index

  var fomo = d.fomo_index || 0;

  var fomoColor = fomo < 0.3 ? 'dv-green' : fomo < 0.6 ? 'dv-amber' : 'dv-red';

  var fomoCls = fomo < 0.3 ? 'dm-green' : fomo < 0.6 ? 'dm-amber' : 'dm-red';

  var fomoLabel = fomo < 0.3 ? 'Tren organik' : fomo < 0.6 ? 'Ada sinyal hype' : 'Hype tinggi — waspada';

  html += _dmBlock(8, 'FOMO Index',

    fomo.toFixed(3),

    fomoLabel,

    'Rasio minat <strong>7 hari terakhir vs rata-rata sebelumnya</strong>. Nilai tinggi (> 0.6) = kemungkinan tren sesaat yang akan cepat turun.',

    fomoCls, fomoColor);

  // 9. Saturasi

  var sat = d.saturation_index || 0;

  var satColor = sat < 0.4 ? 'dv-green' : sat < 0.65 ? 'dv-amber' : 'dv-red';

  var satCls = sat < 0.4 ? 'dm-green' : sat < 0.65 ? 'dm-amber' : 'dm-red';

  var satLabel = sat < 0.4 ? 'Pasar terbuka' : sat < 0.65 ? 'Mulai padat' : 'Pasar jenuh';

  html += _dmBlock(9, 'Saturasi Pasar',

    sat.toFixed(2),

    satLabel,

    'Estimasi kejenuhan pasar berdasarkan <strong>pertumbuhan vs momentum</strong>. Makin rendah = makin banyak ruang untuk pemain baru.',

    satCls, satColor);

  html += '</div>';

  // ── KELOMPOK 3: PROYEKSI — html += '<div class="dm-section-title">// Proyeksi & Pola</div>';

  // 10. Forecast 30 Hari

  var fc = d.forecast_30d_avg || 0;

  var fcConf = d.forecast_confidence || 0;

  var fcConfPct = (fcConf * 100).toFixed(0);

  var fcColor = fc > 50 ? 'dv-green' : fc > 25 ? 'dv-gold' : 'dv-amber';

  html += _dmBlock(10, 'Forecast 30 Hari',

    fc.toFixed(1),

    'Proyeksi rata-rata minat',

    'Prediksi minat 30 hari ke depan menggunakan <strong>regresi linear</strong> dari data 3 bulan terakhir. ' +

    '<strong>Akurasi: ' + fcConfPct + '%</strong>  ' +

    (fcConf >= 0.7 ? 'proyeksi cukup dapat diandalkan.' : fcConf >= 0.5 ? 'proyeksi moderat, ada ketidakpastian.' : 'proyeksi lemah karena data fluktuatif.'),

    'dm-blue', fcColor);

  // 11. Pola Musiman

  var isSeas = d.is_seasonal || false;

  var seasConf = d.seasonal_confidence || 0;

  var seasPct = (seasConf * 100).toFixed(0);

  var peakMonths = d.seasonal_peak_months || [];

  var peakNames = peakMonths.map(function (m) { return MONTHS[m - 1]; }).join(', ');

  var seasValue = isSeas ? 'YA' : 'TIDAK';

  var seasColor = isSeas ? 'dv-amber' : 'dv-text';

  var seasCls = isSeas ? 'dm-amber' : '';

  var seasDesc = isSeas

    ? 'Produk ini <strong>memiliki pola musiman</strong> yang terdeteksi (keyakinan ' + seasPct + '%). ' +

    (peakNames ? 'Bulan puncak biasanya di: <strong>' + peakNames + '</strong>. Siapkan stok sebelum bulan-bulan ini.' : 'Data bulan puncak belum tersedia.')

    : 'Tidak terdeteksi pola musiman yang signifikan. <strong>Permintaan cenderung konsisten</strong> sepanjang tahun.';

  html += _dmBlock(11, 'Pola Musiman',

    seasValue,

    isSeas ? 'Musiman terdeteksi — keyakinan ' + seasPct + '%' : 'Tidak musiman',

    seasDesc, seasCls, seasColor);

  // Footer note

  html += '<div style="' +

    'margin-top:32px; padding:14px 16px;' +

    'background:rgba(212,168,67,0.04);' +

    'border:1px dashed rgba(212,168,67,0.2);' +

    'font-family:\'DM Mono\',monospace;' +

    'font-size:10px; line-height:1.8;' +

    'color:var(--text-faint); letter-spacing:0.03em;' +

    '">' +

    '// Data bersumber dari Google Trends via SerpApi<br>' +

    '// Analisis dihitung oleh Sentra Engine v2.0<br>' +

    '// Semua metrik bersifat indikatif — bukan jaminan hasil bisnis' +

    '</div>';

  c.innerHTML = html;

}

/* --

   SECTION — TESTIMONI CAROUSEL (GSAP)

-- */

function initTestimonialCarousel() {

  const track = document.getElementById('tcTrack');

  const viewport = document.getElementById('tcViewport');

  const dotsContainer = document.getElementById('tcDots');

  const prevBtn = document.getElementById('tcPrev');

  const nextBtn = document.getElementById('tcNext');

  if (!track || !viewport) return;

  const slides = Array.from(track.children);

  const slideCount = slides.length;

  if (slideCount === 0) return;

  let currentIndex = 0;

  let isAnimating = false;

  let autoPlayTimer = null;

  const interval = 5000;

  // 1. Setup Dots

  slides.forEach((_, i) => {

    const dot = document.createElement('div');

    dot.className = 'tc-dot' + (i === 0 ? ' active' : '');

    dot.addEventListener('click', () => goToSlide(i));

    dotsContainer.appendChild(dot);

  });

  const dots = Array.from(dotsContainer.children);

  // 2. Clone for Seamless Loop

  const firstClone = slides[0].cloneNode(true);

  const lastClone = slides[slideCount - 1].cloneNode(true);

  track.appendChild(firstClone);

  track.insertBefore(lastClone, slides[0]);

  // 3. Initial Position

  const updateTrackPosition = () => {

    const slideWidth = slides[0].offsetWidth + 30; // 30 is gap

    gsap.set(track, { x: -(currentIndex + 1) * slideWidth });

  };

  window.addEventListener('resize', updateTrackPosition);

  updateTrackPosition();

  function goToSlide(index, direction = 'next') {

    if (isAnimating) return;

    isAnimating = true;

    const slideWidth = slides[0].offsetWidth + 30;

    currentIndex = index;

    // Update dots

    dots.forEach((d, i) => {

      let activeIdx = currentIndex;

      if (currentIndex >= slideCount) activeIdx = 0;

      if (currentIndex < 0) activeIdx = slideCount - 1;

      d.classList.toggle('active', i === activeIdx);

    });

    gsap.to(track, {

      x: -(currentIndex + 1) * slideWidth,

      duration: 0.8,

      ease: "power2.inOut",

      onComplete: () => {

        isAnimating = false;

        // Loop logic

        if (currentIndex >= slideCount) {

          currentIndex = 0;

          gsap.set(track, { x: -slideWidth });

        } else if (currentIndex < 0) {

          currentIndex = slideCount - 1;

          gsap.set(track, { x: -slideCount * slideWidth });

        }

      }

    });

  }

  function nextSlide() { goToSlide(currentIndex + 1); }

  function prevSlide() { goToSlide(currentIndex - 1); }

  nextBtn.addEventListener('click', () => { stopAutoPlay(); nextSlide(); startAutoPlay(); });

  prevBtn.addEventListener('click', () => { stopAutoPlay(); prevSlide(); startAutoPlay(); });

  // Auto Play

  function startAutoPlay() {

    if (autoPlayTimer) return;

    autoPlayTimer = setInterval(nextSlide, interval);

  }

  function stopAutoPlay() {

    clearInterval(autoPlayTimer);

    autoPlayTimer = null;

  }

  startAutoPlay();

  viewport.addEventListener('mouseenter', stopAutoPlay);

  viewport.addEventListener('mouseleave', startAutoPlay);

  // Swipe Support

  let startX = 0;

  viewport.addEventListener('touchstart', (e) => {

    stopAutoPlay();

    startX = e.touches[0].clientX;

  }, { passive: true });

  viewport.addEventListener('touchend', (e) => {

    const endX = e.changedTouches[0].clientX;

    const diff = startX - endX;

    if (Math.abs(diff) > 50) {

      if (diff > 0) nextSlide();

      else prevSlide();

    }

    startAutoPlay();

  }, { passive: true });

}

// Initialize carousel on load

if (document.readyState === 'loading') {

  document.addEventListener('DOMContentLoaded', initTestimonialCarousel);

} else {

  initTestimonialCarousel();

}

