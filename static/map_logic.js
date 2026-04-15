/**
 * Sentra BI Heatmap Logic (Leaflet Circle Map Version)
 */

const MapLogic = (() => {
  let map = null;
  let circlesLayer = null;
  let mapReady = false;

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

  const PROVINCE_ALIAS = {
    "Kep. Riau": "Kepulauan Riau",
    "Babel": "Kepulauan Bangka Belitung",
    "DIY": "DI Yogyakarta",
    "DKI": "DKI Jakarta"
  };

  function normalizeProvinceName(name) {
    if (!name) return "";
    const cleaned = name.replace(/^Provinsi\s+/i, "").trim();
    return PROVINCE_ALIAS[cleaned] || cleaned;
  }

  function getIntensityMeta(value) {
    const score = Math.max(0, Math.min(100, Number(value) || 0));
    if (score < 25) return { level: "Rendah", color: "#6B7280", fillOpacity: 0.45 };
    if (score < 50) return { level: "Sedang", color: "#FACC15", fillOpacity: 0.58 };
    if (score < 75) return { level: "Tinggi", color: "#F97316", fillOpacity: 0.66 };
    return { level: "Tertinggi", color: "#FDE047", fillOpacity: 0.78 };
  }

  function getRadius(score) {
    const safeScore = Math.max(0, Math.min(100, Number(score) || 0));
    return 9000 + safeScore * 1500;
  }

  function removeLoader() {
    const loader = document.getElementById("map-loader");
    if (loader) loader.style.display = "none";
  }

  function init() {
    const mapEl = document.getElementById("regional-interest-map");
    if (!mapEl || mapReady || typeof L === "undefined") return;

    map = L.map("regional-interest-map", {
      zoomControl: true,
      attributionControl: false,
      scrollWheelZoom: false,
      tap: true
    }).setView([-2.4, 118], 5);

    L.tileLayer("https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png", {
      maxZoom: 18
    }).addTo(map);

    circlesLayer = L.layerGroup().addTo(map);
    mapReady = true;

    setTimeout(() => {
      map.invalidateSize();
      removeLoader();
    }, 150);
  }

  function update(data) {
    if (!mapReady || !circlesLayer) return;
    setTimeout(() => map.invalidateSize(), 60);
    circlesLayer.clearLayers();

    const normalized = (Array.isArray(data) ? data : [])
      .map(item => ({
        province: normalizeProvinceName(item.province || item.name),
        value: Math.max(0, Math.min(100, Number(item.value) || 0))
      }))
      .filter(item => PROVINCE_COORDS[item.province]);

    const sorted = [...normalized].sort((a, b) => b.value - a.value);
    const rankingMap = new Map(sorted.map((item, idx) => [item.province, idx + 1]));

    normalized.forEach((item, index) => {
      const meta = getIntensityMeta(item.value);
      const latlng = PROVINCE_COORDS[item.province];
      const isPeak = item.value >= 75;

      const circle = L.circle(latlng, {
        radius: getRadius(item.value),
        color: meta.color,
        weight: isPeak ? 2.5 : 1.8,
        fillColor: meta.color,
        fillOpacity: meta.fillOpacity,
        className: isPeak ? "heat-circle peak" : "heat-circle"
      });

      circle.bindTooltip(
        `
          <div class="sentra-map-tooltip">
            <div class="sentra-map-tooltip-title">${item.province}</div>
            <div class="sentra-map-tooltip-row"><span>Skor Minat</span><strong>${item.value}%</strong></div>
            <div class="sentra-map-tooltip-row"><span>Ranking</span><strong>#${rankingMap.get(item.province)}</strong></div>
            <div class="sentra-map-tooltip-row"><span>Kategori</span><strong>${meta.level}</strong></div>
          </div>
        `,
        { sticky: true, direction: "top", offset: [0, -10], opacity: 1 }
      );

      circle.on("mouseover", (evt) => {
        evt.target.setStyle({ weight: 3, fillOpacity: Math.min(0.9, meta.fillOpacity + 0.15) });
      });
      circle.on("mouseout", (evt) => {
        evt.target.setStyle({ weight: isPeak ? 2.5 : 1.8, fillOpacity: meta.fillOpacity });
      });

      circle.addTo(circlesLayer);

      const el = circle.getElement && circle.getElement();
      if (el && typeof gsap !== "undefined") {
        gsap.set(el, { scale: 0.25, opacity: 0, transformOrigin: "center center" });
        gsap.to(el, {
          scale: 1,
          opacity: 1,
          duration: 0.5,
          delay: index * 0.04,
          ease: "power3.out"
        });
      }
    });

    const top = sorted.slice(0, 5);
    const list = document.getElementById("top-regions-list");
    if (list && top.length > 0) {
      list.innerHTML = top.map((item, i) => `
        <div class="flex items-center justify-between p-3 bg-zinc-900/80 border border-zinc-800 rounded-xl">
          <div class="flex items-center gap-2">
            <div class="w-6 h-6 rounded-full bg-brand/10 text-brand text-[10px] font-mono flex items-center justify-center border border-brand/20">${i + 1}</div>
            <div class="text-zinc-100 text-xs md:text-sm font-jakarta font-medium">${item.province}</div>
          </div>
          <div class="text-brand font-mono text-xs md:text-sm font-bold">${item.value}%</div>
        </div>
      `).join("");
    }
  }

  function refresh() {
    if (!mapReady || !map) return;
    setTimeout(() => map.invalidateSize(), 60);
  }

  return { init, update, refresh };
})();

document.addEventListener("DOMContentLoaded", MapLogic.init);
window.MapLogic = MapLogic;
