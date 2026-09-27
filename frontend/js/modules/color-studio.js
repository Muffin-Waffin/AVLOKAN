/* ==========================================================================
   AVLOKAN - Color Palette Studio & Theme Customizer Engine
   ========================================================================== */

(function(window, document) {
  'use strict';

  // --- PALETTE PRESETS ---
  const PRESETS = [
    {
      id: 'sandstone',
      name: 'Sovereign Sandstone',
      mode: 'light',
      desc: 'Default warm earthen & sand telemetry palette',
      swatches: ['#f5f1e6', '#fbf8ef', '#5b8c89', '#7c9a78', '#403a2c'],
      vars: {
        '--bg': '#f5f1e6',
        '--bg2': '#eee7d5',
        '--panel': '#fbf8ef',
        '--panel2': '#f2ecdc',
        '--line': '#e3dcc8',
        '--line2': '#d3cab0',
        '--text': '#403a2c',
        '--muted': '#7c7566',
        '--faint': '#a39a86',
        '--cyan': '#7ba6a3',
        '--cyan2': '#5b8c89',
        '--cyan-d': '#41706d',
        '--green': '#7c9a78',
        '--green-d': '#4e6b4f',
        '--amber': '#d3a656',
        '--amber-d': '#96701d',
        '--red': '#c98b8b',
        '--red-d': '#8f4e4e',
        '--violet': '#a894ad',
        '--violet-d': '#6f5a77',
        '--orange': '#c98d68',
        '--orange-d': '#9c6244'
      }
    },
    {
      id: 'midnight',
      name: 'Tactical Midnight',
      mode: 'dark',
      desc: 'Stealth night-ops cyber command center dark mode',
      swatches: ['#0c1017', '#1a2332', '#38bdf8', '#34d399', '#f1f5f9'],
      vars: {
        '--bg': '#0c1017',
        '--bg2': '#131924',
        '--panel': '#1a2332',
        '--panel2': '#222d40',
        '--line': '#2b3a51',
        '--line2': '#3c506f',
        '--text': '#f1f5f9',
        '--muted': '#94a3b8',
        '--faint': '#64748b',
        '--cyan': '#38bdf8',
        '--cyan2': '#0ea5e9',
        '--cyan-d': '#0284c7',
        '--green': '#34d399',
        '--green-d': '#10b981',
        '--amber': '#fbbf24',
        '--amber-d': '#d97706',
        '--red': '#f87171',
        '--red-d': '#ef4444',
        '--violet': '#c084fc',
        '--violet-d': '#a855f7',
        '--orange': '#fb923c',
        '--orange-d': '#f97316'
      }
    },
    {
      id: 'cosmos',
      name: 'ISRO Deep Cosmos',
      mode: 'dark',
      desc: 'Deep space navy with celestial cyan & saffron gold',
      swatches: ['#090d1a', '#141d36', '#4cc9f0', '#ffaa00', '#f8fafc'],
      vars: {
        '--bg': '#090d1a',
        '--bg2': '#0e1529',
        '--panel': '#141d36',
        '--panel2': '#1c284a',
        '--line': '#283966',
        '--line2': '#3b5394',
        '--text': '#f8fafc',
        '--muted': '#a0b1d8',
        '--faint': '#687fae',
        '--cyan': '#4cc9f0',
        '--cyan2': '#4361ee',
        '--cyan-d': '#3a0ca3',
        '--green': '#4ade80',
        '--green-d': '#22c55e',
        '--amber': '#ffaa00',
        '--amber-d': '#e08b00',
        '--red': '#ff5c5c',
        '--red-d': '#dc2626',
        '--violet': '#b5179e',
        '--violet-d': '#7209b7',
        '--orange': '#ff7b00',
        '--orange-d': '#e65c00'
      }
    },
    {
      id: 'biosphere',
      name: 'Emerald Biosphere',
      mode: 'dark',
      desc: 'Earth observation vegetation and rainforest monitoring',
      swatches: ['#0d1713', '#182b23', '#52b788', '#e9c46a', '#e8f5ed'],
      vars: {
        '--bg': '#0d1713',
        '--bg2': '#12211b',
        '--panel': '#182b23',
        '--panel2': '#20392e',
        '--line': '#2b4d3f',
        '--line2': '#3d6c58',
        '--text': '#e8f5ed',
        '--muted': '#95b8a5',
        '--faint': '#638573',
        '--cyan': '#48cae4',
        '--cyan2': '#0096c7',
        '--cyan-d': '#0077b6',
        '--green': '#52b788',
        '--green-d': '#2d6a4f',
        '--amber': '#e9c46a',
        '--amber-d': '#c49b38',
        '--red': '#e76f51',
        '--red-d': '#b84931',
        '--violet': '#b08968',
        '--violet-d': '#7f5539',
        '--orange': '#f4a261',
        '--orange-d': '#d47b33'
      }
    },
    {
      id: 'arctic',
      name: 'Arctic Glacial',
      mode: 'dark',
      desc: 'High-latitude polar radar & cryosphere observation',
      swatches: ['#0c1424', '#17243c', '#67e8f9', '#a5b4fc', '#f1f5f9'],
      vars: {
        '--bg': '#0c1424',
        '--bg2': '#111b30',
        '--panel': '#17243c',
        '--panel2': '#1e304f',
        '--line': '#2c436b',
        '--line2': '#3f5d94',
        '--text': '#f1f5f9',
        '--muted': '#94a3b8',
        '--faint': '#64748b',
        '--cyan': '#67e8f9',
        '--cyan2': '#06b6d4',
        '--cyan-d': '#0891b2',
        '--green': '#6ee7b7',
        '--green-d': '#10b981',
        '--amber': '#fcd34d',
        '--amber-d': '#b45309',
        '--red': '#fda4af',
        '--red-d': '#f43f5e',
        '--violet': '#c4b5fd',
        '--violet-d': '#8b5cf6',
        '--orange': '#fed7aa',
        '--orange-d': '#ea580c'
      }
    },
    {
      id: 'cleanroom',
      name: 'Cleanroom Light',
      mode: 'light',
      desc: 'Ultra-clean clinical laboratory & satellite integration bay',
      swatches: ['#f8fafc', '#ffffff', '#0284c7', '#16a34a', '#0f172a'],
      vars: {
        '--bg': '#f8fafc',
        '--bg2': '#f1f5f9',
        '--panel': '#ffffff',
        '--panel2': '#f8fafc',
        '--line': '#e2e8f0',
        '--line2': '#cbd5e1',
        '--text': '#0f172a',
        '--muted': '#475569',
        '--faint': '#94a3b8',
        '--cyan': '#0284c7',
        '--cyan2': '#0369a1',
        '--cyan-d': '#075985',
        '--green': '#16a34a',
        '--green-d': '#15803d',
        '--amber': '#d97706',
        '--amber-d': '#b45309',
        '--red': '#dc2626',
        '--red-d': '#b91c1c',
        '--violet': '#7c3aed',
        '--violet-d': '#6d28d9',
        '--orange': '#ea580c',
        '--orange-d': '#c2410c'
      }
    },
    {
      id: 'desert',
      name: 'Thar Desert Quartz',
      mode: 'dark',
      desc: 'Warm terracotta, titanium & arid desert reconnaissance',
      swatches: ['#231c17', '#362c25', '#e5b060', '#78a8a4', '#faf5f0'],
      vars: {
        '--bg': '#231c17',
        '--bg2': '#2c231d',
        '--panel': '#362c25',
        '--panel2': '#43372f',
        '--line': '#54463c',
        '--line2': '#6b5a4d',
        '--text': '#faf5f0',
        '--muted': '#c5b8ab',
        '--faint': '#8f8072',
        '--cyan': '#78a8a4',
        '--cyan2': '#598783',
        '--cyan-d': '#3f6662',
        '--green': '#99aa7e',
        '--green-d': '#6f8252',
        '--amber': '#e5b060',
        '--amber-d': '#ad7c31',
        '--red': '#d97768',
        '--red-d': '#a6483a',
        '--violet': '#bca0b2',
        '--violet-d': '#8c6e81',
        '--orange': '#e08b58',
        '--orange-d': '#b35a26'
      }
    },
    {
      id: 'radar',
      name: 'Radar Phosphor',
      mode: 'dark',
      desc: 'Night-vision synthetic radar terminal phosphor',
      swatches: ['#040805', '#0c1a0e', '#22c55e', '#a3e635', '#bbf7d0'],
      vars: {
        '--bg': '#040805',
        '--bg2': '#08120a',
        '--panel': '#0c1a0e',
        '--panel2': '#122615',
        '--line': '#1b3a20',
        '--line2': '#27522d',
        '--text': '#bbf7d0',
        '--muted': '#4ade80',
        '--faint': '#22c55e',
        '--cyan': '#2dd4bf',
        '--cyan2': '#14b8a6',
        '--cyan-d': '#0f766e',
        '--green': '#22c55e',
        '--green-d': '#16a34a',
        '--amber': '#eab308',
        '--amber-d': '#ca8a04',
        '--red': '#ef4444',
        '--red-d': '#dc2626',
        '--violet': '#a855f7',
        '--violet-d': '#7e22ce',
        '--orange': '#f97316',
        '--orange-d': '#ea580c'
      }
    },
    {
      id: 'solar',
      name: 'Solar Flare (Infrared)',
      mode: 'dark',
      desc: 'Multispectral thermal infrared radiance gradient',
      swatches: ['#160c14', '#261522', '#f43f5e', '#ff6b4a', '#fff1f5'],
      vars: {
        '--bg': '#160c14',
        '--bg2': '#1e101c',
        '--panel': '#261522',
        '--panel2': '#321c2d',
        '--line': '#4a2943',
        '--line2': '#66385c',
        '--text': '#fff1f5',
        '--muted': '#e09fbe',
        '--faint': '#a86687',
        '--cyan': '#06b6d4',
        '--cyan2': '#0891b2',
        '--cyan-d': '#0e7490',
        '--green': '#10b981',
        '--green-d': '#059669',
        '--amber': '#f59e0b',
        '--amber-d': '#d97706',
        '--red': '#f43f5e',
        '--red-d': '#e11d48',
        '--violet': '#d946ef',
        '--violet-d': '#c026d3',
        '--orange': '#ff6b4a',
        '--orange-d': '#e04825'
      }
    },
    {
      id: 'cyberpunk',
      name: 'Cyberpunk Synthwave',
      mode: 'dark',
      desc: 'Neon luminescent purple, cyan & synthwave grid',
      swatches: ['#0b0518', '#1c0d3d', '#00f5d4', '#fee440', '#fdf4ff'],
      vars: {
        '--bg': '#0b0518',
        '--bg2': '#14092b',
        '--panel': '#1c0d3d',
        '--panel2': '#261252',
        '--line': '#3e1d85',
        '--line2': '#5628b8',
        '--text': '#fdf4ff',
        '--muted': '#d8b4fe',
        '--faint': '#a855f7',
        '--cyan': '#00f5d4',
        '--cyan2': '#00bbf9',
        '--cyan-d': '#0077b6',
        '--green': '#70e000',
        '--green-d': '#38b000',
        '--amber': '#fee440',
        '--amber-d': '#f72585',
        '--red': '#ff0054',
        '--red-d': '#9e0059',
        '--violet': '#b5179e',
        '--violet-d': '#7209b7',
        '--orange': '#ff5400',
        '--orange-d': '#9d0208'
      }
    }
  ];

  // Key customizable tokens
  const KEY_TOKENS = [
    { key: '--bg', label: 'Canvas Background' },
    { key: '--bg2', label: 'Secondary BG' },
    { key: '--panel', label: 'Panel Surface' },
    { key: '--panel2', label: 'Panel Header' },
    { key: '--line', label: 'Border Line' },
    { key: '--line2', label: 'Strong Border' },
    { key: '--text', label: 'Primary Text' },
    { key: '--muted', label: 'Muted Text' },
    { key: '--faint', label: 'Faint Text' },
    { key: '--cyan', label: 'Primary Accent (Cyan)' },
    { key: '--cyan2', label: 'Darker Accent (Cyan 2)' },
    { key: '--green', label: 'Verified Green' },
    { key: '--amber', label: 'Warning Amber' },
    { key: '--red', label: 'Alert Red' },
    { key: '--violet', label: 'SAR Violet' },
    { key: '--orange', label: 'Heat Orange' }
  ];

  let currentThemeId = 'sandstone';
  let activeTab = 'presets';

  // --- CONTRAST CALCULATOR ---
  function hexToRgb(hex) {
    hex = hex.replace(/^#/, '');
    if (hex.length === 3) hex = hex.split('').map(function(c) { return c + c; }).join('');
    const num = parseInt(hex, 16);
    return [(num >> 16) & 255, (num >> 8) & 255, num & 255];
  }

  function getLuminance(r, g, b) {
    const a = [r, g, b].map(function(v) {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return a[0] * 0.2126 + a[1] * 0.7152 + a[2] * 0.0722;
  }

  function getContrast(hex1, hex2) {
    try {
      const rgb1 = hexToRgb(hex1);
      const rgb2 = hexToRgb(hex2);
      const l1 = getLuminance(rgb1[0], rgb1[1], rgb1[2]);
      const l2 = getLuminance(rgb2[0], rgb2[1], rgb2[2]);
      const brightest = Math.max(l1, l2);
      const darkest = Math.min(l1, l2);
      return (brightest + 0.05) / (darkest + 0.05);
    } catch(e) {
      return 1;
    }
  }

  // --- DOM INJECTION ---
  function buildStudioDOM() {
    if (document.getElementById('colorStudioDrawer')) return;

    // Overlay
    const overlay = document.createElement('div');
    overlay.className = 'cs-drawer-overlay';
    overlay.id = 'colorStudioOverlay';
    overlay.onclick = function() { toggleColorStudio(false); };
    document.body.appendChild(overlay);

    // Drawer
    const drawer = document.createElement('div');
    drawer.className = 'cs-drawer';
    drawer.id = 'colorStudioDrawer';

    drawer.innerHTML = `
      <div class="cs-header">
        <div class="cs-title-wrap">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/><path d="M12 2a10 10 0 0 0-4 19.19V17a2 2 0 0 1 2-2h4a2 2 0 0 0 2-2v-1a2 2 0 0 0-2-2h-2a2 2 0 0 1-2-2V5.5A10 10 0 0 0 12 2z"/>
          </svg>
          <div>
            <div class="cs-title">Palette Studio</div>
            <div class="cs-subtitle">AVLOKAN Theme & Color Engine</div>
          </div>
        </div>
        <button class="cs-close-btn" onclick="toggleColorStudio(false)" title="Close Studio">✕</button>
      </div>

      <div class="cs-tabs">
        <div class="cs-tab active" data-tab="presets" onclick="ColorStudio.setTab('presets')">Curated Palettes</div>
        <div class="cs-tab" data-tab="custom" onclick="ColorStudio.setTab('custom')">Custom Editor</div>
        <div class="cs-tab" data-tab="export" onclick="ColorStudio.setTab('export')">CSS & Export</div>
      </div>

      <div class="cs-body" id="csBody">
        <!-- Rendered by renderBody() -->
      </div>

      <div class="cs-footer">
        <button class="btn btn-ghost" style="flex:1" onclick="ColorStudio.randomizeTheme()">🎲 Randomize</button>
        <button class="btn btn-ghost" style="flex:1" onclick="ColorStudio.resetTheme()">↺ Reset</button>
        <button class="btn btn-primary" style="flex:1" onclick="ColorStudio.copyCSS()">📋 Copy CSS</button>
      </div>
    `;

    document.body.appendChild(drawer);

    // Inject Launcher in Topbar if topbar exists
    const topbarPills = document.querySelector('.topbar .pills');
    if (topbarPills && !document.getElementById('paletteBtnTop')) {
      const topBtn = document.createElement('button');
      topBtn.id = 'paletteBtnTop';
      topBtn.className = 'palette-btn';
      topBtn.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/><path d="M12 2a10 10 0 0 0-4 19.19V17a2 2 0 0 1 2-2h4a2 2 0 0 0 2-2v-1a2 2 0 0 0-2-2h-2a2 2 0 0 1-2-2V5.5A10 10 0 0 0 12 2z"/>
        </svg>
        <span>Palette Studio</span>
      `;
      topBtn.onclick = function() { toggleColorStudio(true); };
      topbarPills.prepend(topBtn);
    }

    // Inject Launcher in Sidebar before s-foot
    const sidebar = document.getElementById('sidebar');
    const sfoot = document.querySelector('.sidebar .s-foot');
    if (sidebar && sfoot && !document.getElementById('snavColorStudio')) {
      const snav = document.createElement('a');
      snav.id = 'snavColorStudio';
      snav.className = 'snav';
      snav.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/><path d="M12 2a10 10 0 0 0-4 19.19V17a2 2 0 0 1 2-2h4a2 2 0 0 0 2-2v-1a2 2 0 0 0-2-2h-2a2 2 0 0 1-2-2V5.5A10 10 0 0 0 12 2z"/>
        </svg>
        <span>Palette Studio</span>
        <span class="sbadge" style="background:var(--cyan);color:#fff;border-color:transparent">Live</span>
      `;
      snav.onclick = function(e) {
        e.preventDefault();
        toggleColorStudio(true);
      };
      sidebar.insertBefore(snav, sfoot);
    }
  }

  // --- RENDER DRAWER CONTENT ---
  function renderBody() {
    const body = document.getElementById('csBody');
    if (!body) return;

    if (activeTab === 'presets') {
      body.innerHTML = `
        <div class="cs-section">
          <div class="cs-sec-head">
            <span class="cs-sec-title">EO Mission Palettes (` + PRESETS.length + `)</span>
            <span style="font-size:11px;color:var(--faint)">Instant 1-Click Apply</span>
          </div>
          <div class="cs-presets-grid">
            ` + PRESETS.map(function(p) {
              const isActive = (p.id === currentThemeId);
              return `
                <div class="cs-preset-card ` + (isActive ? 'active' : '') + `" onclick="ColorStudio.applyPreset('` + p.id + `')">
                  <div class="cs-preset-name">
                    <span>` + p.name + `</span>
                    <span class="cs-mode-tag ` + p.mode + `">` + p.mode + `</span>
                  </div>
                  <div class="cs-swatches">
                    ` + p.swatches.map(function(s) {
                      return `<div class="cs-swatch" style="background:` + s + `"></div>`;
                    }).join('') + `
                  </div>
                  <div style="font-size:10px;color:var(--muted);line-height:1.3">` + p.desc + `</div>
                </div>
              `;
            }).join('') + `
          </div>
        </div>

        ` + renderContrastCard() + `
      `;
    } else if (activeTab === 'custom') {
      const rootStyle = getComputedStyle(document.documentElement);
      body.innerHTML = `
        <div class="cs-section">
          <div class="cs-sec-head">
            <span class="cs-sec-title">Fine-Tune Current Colors</span>
            <button class="cs-sec-action" onclick="ColorStudio.resetTheme()">Reset to Default</button>
          </div>
          <div class="cs-pickers-group">
            ` + KEY_TOKENS.map(function(t) {
              const val = rootStyle.getPropertyValue(t.key).trim() || '#000000';
              return `
                <div class="cs-picker-box">
                  <input type="color" class="cs-color-input" value="` + val + `" data-var="` + t.key + `" oninput="ColorStudio.onColorInput(this)">
                  <div class="cs-picker-info">
                    <span class="cs-picker-label">` + t.label + `</span>
                    <input type="text" class="cs-picker-val" value="` + val + `" data-var="` + t.key + `" onchange="ColorStudio.onTextInput(this)">
                  </div>
                </div>
              `;
            }).join('') + `
          </div>
        </div>

        ` + renderContrastCard() + `
      `;
    } else if (activeTab === 'export') {
      const cssBlock = generateCSSSnippet();
      body.innerHTML = `
        <div class="cs-section">
          <div class="cs-sec-head">
            <span class="cs-sec-title">Export CSS Tokens</span>
            <button class="cs-sec-action" onclick="ColorStudio.copyCSS()">Copy Snippet</button>
          </div>
          <div class="cs-code-wrap">
            <button class="cs-copy-btn" onclick="ColorStudio.copyCSS()">Copy</button>
            <pre><code>` + cssBlock.replace(/</g, '&lt;') + `</code></pre>
          </div>
        </div>

        <div class="cs-section">
          <div class="cs-sec-head">
            <span class="cs-sec-title">Theme File Management</span>
          </div>
          <div style="display:flex;gap:10px">
            <button class="btn btn-ghost" style="flex:1" onclick="ColorStudio.downloadThemeJSON()">⬇ Download JSON</button>
            <button class="btn btn-ghost" style="flex:1" onclick="ColorStudio.promptImportJSON()">⬆ Import JSON</button>
          </div>
        </div>

        ` + renderContrastCard() + `
      `;
    }
  }

  function renderContrastCard() {
    const rootStyle = getComputedStyle(document.documentElement);
    const bg = rootStyle.getPropertyValue('--bg').trim() || '#f5f1e6';
    const text = rootStyle.getPropertyValue('--text').trim() || '#403a2c';
    const ratio = getContrast(text, bg).toFixed(2);
    const passesAAA = ratio >= 7;
    const passesAA = ratio >= 4.5;
    const tagClass = passesAA ? 'pass' : 'warn';
    const tagText = passesAAA ? 'WCAG AAA (Enhanced)' : (passesAA ? 'WCAG AA (Standard)' : 'Low Contrast');

    return `
      <div class="cs-contrast-card">
        <div class="cs-contrast-info">
          <div class="cs-contrast-title">WCAG Readability Metric</div>
          <div class="cs-contrast-sub">Contrast between Text (` + text + `) and Background (` + bg + `)</div>
        </div>
        <div class="cs-contrast-meter">
          <div class="cs-contrast-ratio" style="color:var(--text)">` + ratio + ` : 1</div>
          <div class="cs-contrast-tag ` + tagClass + `">` + tagText + `</div>
        </div>
      </div>
    `;
  }

  function generateCSSSnippet() {
    const rootStyle = getComputedStyle(document.documentElement);
    let lines = [':root {'];
    KEY_TOKENS.forEach(function(t) {
      const val = rootStyle.getPropertyValue(t.key).trim();
      if (val) lines.push('  ' + t.key + ': ' + val + ';');
    });
    lines.push('}');
    return lines.join('\n');
  }

  // --- THEME APPLICATION ---
  function applyVariables(varsObj) {
    const root = document.documentElement;
    Object.keys(varsObj).forEach(function(key) {
      root.style.setProperty(key, varsObj[key]);
    });

    // Redraw canvases that rely on palette colors
    try {
      if (typeof window.drawTopo === 'function') window.drawTopo();
      if (typeof window.renderMap === 'function') window.renderMap();
      window.needRender = true;
    } catch(e) {}

    renderBody();
  }

  function applyPreset(presetId) {
    const preset = PRESETS.find(function(p) { return p.id === presetId; });
    if (!preset) return;

    currentThemeId = presetId;
    applyVariables(preset.vars);

    try {
      localStorage.setItem('avlokan_theme_id', presetId);
      localStorage.setItem('avlokan_custom_vars', JSON.stringify(preset.vars));
    } catch(e) {}

    if (typeof window.toast === 'function') {
      window.toast('Switched to "' + preset.name + '" palette');
    }
  }

  function onColorInput(input) {
    const varName = input.dataset.var;
    const color = input.value;
    document.documentElement.style.setProperty(varName, color);

    // Sync corresponding text field
    const textInput = document.querySelector('.cs-picker-val[data-var="' + varName + '"]');
    if (textInput) textInput.value = color;

    saveCustomVars();
    updateContrast();
  }

  function onTextInput(input) {
    let color = input.value.trim();
    if (!color.startsWith('#')) color = '#' + color;
    if (/^#[0-9A-Fa-f]{6}$/.test(color)) {
      const varName = input.dataset.var;
      document.documentElement.style.setProperty(varName, color);

      // Sync color input
      const colorInput = document.querySelector('.cs-color-input[data-var="' + varName + '"]');
      if (colorInput) colorInput.value = color;

      saveCustomVars();
      updateContrast();
    }
  }

  function updateContrast() {
    const rootStyle = getComputedStyle(document.documentElement);
    const bg = rootStyle.getPropertyValue('--bg').trim();
    const text = rootStyle.getPropertyValue('--text').trim();
    const ratioEl = document.querySelector('.cs-contrast-ratio');
    const tagEl = document.querySelector('.cs-contrast-tag');
    if (ratioEl && tagEl && bg && text) {
      const ratio = getContrast(text, bg).toFixed(2);
      ratioEl.textContent = ratio + ' : 1';
      const passesAAA = ratio >= 7;
      const passesAA = ratio >= 4.5;
      tagEl.className = 'cs-contrast-tag ' + (passesAA ? 'pass' : 'warn');
      tagEl.textContent = passesAAA ? 'WCAG AAA (Enhanced)' : (passesAA ? 'WCAG AA (Standard)' : 'Low Contrast');
    }
  }

  function saveCustomVars() {
    const rootStyle = getComputedStyle(document.documentElement);
    const vars = {};
    KEY_TOKENS.forEach(function(t) {
      vars[t.key] = rootStyle.getPropertyValue(t.key).trim();
    });
    try {
      localStorage.setItem('avlokan_custom_vars', JSON.stringify(vars));
    } catch(e) {}
  }

  function copyCSS() {
    const snippet = generateCSSSnippet();
    navigator.clipboard.writeText(snippet).then(function() {
      if (typeof window.toast === 'function') {
        window.toast('Palette CSS copied to clipboard!');
      } else {
        alert('Palette CSS copied to clipboard!');
      }
    });
  }

  function resetTheme() {
    applyPreset('sandstone');
  }

  function randomizeTheme() {
    const isDark = Math.random() > 0.4;
    const baseHue = Math.floor(Math.random() * 360);
    const secHue = (baseHue + 40 + Math.floor(Math.random() * 80)) % 360;

    function hslToHex(h, s, l) {
      l /= 100;
      const a = s * Math.min(l, 1 - l) / 100;
      const f = function(n) {
        const k = (n + h / 30) % 12;
        const color = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
        return Math.round(255 * color).toString(16).padStart(2, '0');
      };
      return '#' + f(0) + f(8) + f(4);
    }

    const vars = isDark ? {
      '--bg': hslToHex(baseHue, 35, 7),
      '--bg2': hslToHex(baseHue, 30, 11),
      '--panel': hslToHex(baseHue, 28, 16),
      '--panel2': hslToHex(baseHue, 25, 21),
      '--line': hslToHex(baseHue, 25, 30),
      '--line2': hslToHex(baseHue, 22, 42),
      '--text': '#f8fafc',
      '--muted': hslToHex(baseHue, 15, 70),
      '--faint': hslToHex(baseHue, 12, 50),
      '--cyan': hslToHex(secHue, 85, 60),
      '--cyan2': hslToHex(secHue, 75, 48),
      '--cyan-d': hslToHex(secHue, 80, 35),
      '--green': '#34d399',
      '--green-d': '#10b981',
      '--amber': '#fbbf24',
      '--amber-d': '#d97706',
      '--red': '#f87171',
      '--red-d': '#ef4444',
      '--violet': hslToHex((secHue + 60) % 360, 75, 65),
      '--violet-d': hslToHex((secHue + 60) % 360, 65, 45),
      '--orange': '#fb923c',
      '--orange-d': '#f97316'
    } : {
      '--bg': hslToHex(baseHue, 20, 94),
      '--bg2': hslToHex(baseHue, 18, 88),
      '--panel': hslToHex(baseHue, 15, 98),
      '--panel2': hslToHex(baseHue, 16, 92),
      '--line': hslToHex(baseHue, 14, 82),
      '--line2': hslToHex(baseHue, 12, 72),
      '--text': hslToHex(baseHue, 30, 15),
      '--muted': hslToHex(baseHue, 15, 40),
      '--faint': hslToHex(baseHue, 12, 55),
      '--cyan': hslToHex(secHue, 65, 45),
      '--cyan2': hslToHex(secHue, 55, 35),
      '--cyan-d': hslToHex(secHue, 60, 25),
      '--green': '#4e6b4f',
      '--green-d': '#2d452e',
      '--amber': '#b45309',
      '--amber-d': '#78350f',
      '--red': '#b91c1c',
      '--red-d': '#7f1d1d',
      '--violet': hslToHex((secHue + 60) % 360, 40, 50),
      '--violet-d': hslToHex((secHue + 60) % 360, 45, 35),
      '--orange': '#c2410c',
      '--orange-d': '#7c2d12'
    };

    currentThemeId = 'custom';
    applyVariables(vars);
    if (typeof window.toast === 'function') {
      window.toast('Generated harmonic ' + (isDark ? 'dark' : 'light') + ' palette!');
    }
  }

  function downloadThemeJSON() {
    const rootStyle = getComputedStyle(document.documentElement);
    const data = {
      name: 'Custom Theme',
      generated: new Date().toISOString(),
      tokens: {}
    };
    KEY_TOKENS.forEach(function(t) {
      data.tokens[t.key] = rootStyle.getPropertyValue(t.key).trim();
    });
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'avlokan-theme-' + Date.now() + '.json';
    a.click();
    URL.revokeObjectURL(url);
  }

  function promptImportJSON() {
    const str = prompt('Paste theme JSON:');
    if (!str) return;
    try {
      const parsed = JSON.parse(str);
      const tokens = parsed.tokens || parsed;
      applyVariables(tokens);
      saveCustomVars();
      if (typeof window.toast === 'function') window.toast('Theme JSON imported successfully!');
    } catch(e) {
      alert('Invalid JSON theme format.');
    }
  }

  // --- TOGGLE STUDIO DRAWER ---
  function toggleColorStudio(show) {
    buildStudioDOM();
    const overlay = document.getElementById('colorStudioOverlay');
    const drawer = document.getElementById('colorStudioDrawer');
    if (!overlay || !drawer) return;

    const isActive = drawer.classList.contains('active');
    const targetState = (show !== undefined) ? show : !isActive;

    if (targetState) {
      renderBody();
      overlay.classList.add('active');
      drawer.classList.add('active');
    } else {
      overlay.classList.remove('active');
      drawer.classList.remove('active');
    }
  }

  function setTab(tab) {
    activeTab = tab;
    document.querySelectorAll('.cs-tab').forEach(function(t) {
      t.classList.toggle('active', t.dataset.tab === tab);
    });
    renderBody();
  }

  // --- RESTORE PERSISTED THEME ON BOOT ---
  function initTheme() {
    buildStudioDOM();
    try {
      const savedThemeId = localStorage.getItem('avlokan_theme_id');
      const savedVars = localStorage.getItem('avlokan_custom_vars');
      if (savedVars) {
        currentThemeId = savedThemeId || 'custom';
        applyVariables(JSON.parse(savedVars));
      } else if (savedThemeId) {
        applyPreset(savedThemeId);
      }
    } catch(e) {}
  }

  // Export to window
  window.ColorStudio = {
    PRESETS: PRESETS,
    KEY_TOKENS: KEY_TOKENS,
    applyPreset: applyPreset,
    applyVariables: applyVariables,
    onColorInput: onColorInput,
    onTextInput: onTextInput,
    setTab: setTab,
    resetTheme: resetTheme,
    randomizeTheme: randomizeTheme,
    copyCSS: copyCSS,
    downloadThemeJSON: downloadThemeJSON,
    promptImportJSON: promptImportJSON,
    init: initTheme
  };

  window.toggleColorStudio = toggleColorStudio;

  // Auto-init on DOMContentLoaded or immediate if ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTheme);
  } else {
    initTheme();
  }

})(window, document);
