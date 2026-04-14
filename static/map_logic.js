/**
 * Sentra BI Heatmap Logic (Tile Map Version)
 * Handles Indonesia Province Heatmap using CSS Grid Tiles
 */

const MapLogic = (() => {
    let regionalData = [];
    let tooltipEl = null;

    // Standard Mapping: Pytrends Name -> Tile ID
    const PROVINCE_MAPPING = {
        "Aceh": "ACE",
        "Sumatera Barat": "SBR",
        "Riau": "RIU",
        "Kepulauan Riau": "KPR",
        "Kalimantan Utara": "KLU",
        "Kalimantan Timur": "KTI",
        "Sulawesi Utara": "SUU",
        "Maluku Utara": "MUT",
        "Papua Barat": "PAB",
        "Sumatera Utara": "SBU",
        "Jambi": "JAM",
        "Sumatera Selatan": "SS",
        "Kepulauan Bangka Belitung": "BBL",
        "Kalimantan Barat": "KTB",
        "Kalimantan Tengah": "KTG",
        "Kalimantan Selatan": "KTS",
        "Sulawesi Tenggara": "SLU",
        "Gorontalo": "GRT",
        "Papua": "PAP",
        "Bengkulu": "BKL",
        "Lampung": "LPG",
        "DKI Jakarta": "JKT",
        "Jawa Barat": "JBR",
        "Sulawesi Tengah": "STG",
        "Sulawesi Selatan": "SGO",
        "Maluku": "MLD",
        "Banten": "BTN",
        "Jawa Tengah": "JTG",
        "DI Yogyakarta": "DIY",
        "Jawa Timur": "JTM",
        "Nusa Tenggara Barat": "NTB",
        "Nusa Tenggara Timur": "NTT",
        "Bali": "BLI",
        "Sulawesi Barat": "SBU", // Map to nearby or existing
        "Kalimantan": "KTS", // Fallback
        "Papua Barat Daya": "PAB"
    };

    function hexToRgb(hex) {
        const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        return result ? {
            r: parseInt(result[1], 16),
            g: parseInt(result[2], 16),
            b: parseInt(result[3], 16)
        } : null;
    }

    function rgbToHex(r, g, b) {
        return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
    }

    function interpolateColor(color1, color2, factor) {
        const c1 = hexToRgb(color1);
        const c2 = hexToRgb(color2);
        const r = Math.round(c1.r + factor * (c2.r - c1.r));
        const g = Math.round(c1.g + factor * (c2.g - c1.g));
        const b = Math.round(c1.b + factor * (c2.b - c1.b));
        return rgbToHex(r, g, b);
    }

    function getProvinceColor(value) {
        if (value === 0 || value === null || value === undefined) return "#1a1a1a";
        
        // Ranges:
        // 1-25   => #2a2a2a to #7a5c00
        // 26-60  => #7a5c00 to #d4a017
        // 61-100 => #d4a017 to #FFD700
        
        if (value <= 25) {
            return interpolateColor("#2a2a2a", "#7a5c00", value / 25);
        } else if (value <= 60) {
            return interpolateColor("#7a5c00", "#d4a017", (value - 25) / (60 - 25));
        } else {
            return interpolateColor("#d4a017", "#FFD700", (value - 60) / (100 - 60));
        }
    }

    function createTooltip() {
        if (tooltipEl) return;
        tooltipEl = document.createElement('div');
        tooltipEl.className = 'map-tooltip';
        document.body.appendChild(tooltipEl);
    }

    function showTooltip(e, name, value) {
        if (!tooltipEl) createTooltip();
        
        const safeValue = value || 0;
        tooltipEl.innerHTML = `
            <div class="map-tooltip-title">${name}</div>
            <div class="map-tooltip-value">Indeks Minat: ${safeValue}/100</div>
            <div class="tooltip-bar-bg">
                <div class="tooltip-bar-fill" style="width: ${safeValue}%"></div>
            </div>
        `;
        
        tooltipEl.style.display = 'block';
        moveTooltip(e);
    }

    function moveTooltip(e) {
        if (!tooltipEl) return;
        tooltipEl.style.left = e.pageX + 'px';
        tooltipEl.style.top = e.pageY + 'px';
    }

    function hideTooltip() {
        if (tooltipEl) tooltipEl.style.display = 'none';
    }

    function init() {
        // Prepare events for existing tiles
        document.querySelectorAll('.province-tile').forEach(tile => {
            tile.addEventListener('mouseenter', (e) => {
                const name = tile.getAttribute('data-name');
                const val = tile.getAttribute('data-value');
                showTooltip(e, name, val);
            });
            tile.addEventListener('mousemove', moveTooltip);
            tile.addEventListener('mouseleave', hideTooltip);
        });
    }

    function update(data) {
        regionalData = data;
        
        // Reset all tiles first
        document.querySelectorAll('.province-tile').forEach(tile => {
            tile.style.background = '#1a1a1a';
            tile.style.boxShadow = 'none';
            tile.setAttribute('data-value', 0);
            tile.querySelector('span').style.color = '#888';
        });

        // Map and update
        data.forEach((item, index) => {
            const tileId = PROVINCE_MAPPING[item.name] || PROVINCE_MAPPING[item.name.replace('Provinsi ', '')];
            if (tileId) {
                const tile = document.getElementById('tile-' + tileId);
                if (tile) {
                    const val = item.value;
                    const color = getProvinceColor(val);
                    
                    // Delay for stagger effect
                    setTimeout(() => {
                        tile.style.background = color;
                        tile.setAttribute('data-value', val);
                        
                        // Text color contrast
                        if (val > 40) {
                            tile.querySelector('span').style.color = '#fff';
                        } else {
                            tile.querySelector('span').style.color = '#888';
                        }

                        // Rare Peak glow
                        if (val >= 90) {
                            tile.style.boxShadow = `0 0 15px ${color}88`;
                        } else {
                            tile.style.boxShadow = 'none';
                        }
                    }, index * 20);
                }
            }
        });
    }

    return { init, update };
})();

// Initialize map events
document.addEventListener('DOMContentLoaded', MapLogic.init);
window.MapLogic = MapLogic;
