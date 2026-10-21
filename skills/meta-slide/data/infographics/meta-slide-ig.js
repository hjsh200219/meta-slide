/* meta-slide 인포그래픽 런타임 — AntV Infographic(MIT)을 장 안에서 렌더한다.
   쓰는 법(장 안):
     <div class="ms-ig" style="position:absolute; left:120px; top:300px; width:1680px; height:640px">
       <script type="text/x-infographic">
infographic sequence-steps-simple
data
  title …
  sequences
    - label …
       </script>
     </div>
   - theme 블록이 없으면 덱의 색 체계(--ms-ig-1..4, --ms-ig-text)와 한글 본문 서체(--ms-body)를 넣는다.
   - 아이콘은 로컬 Tabler 묶음(icons.js)에서 찾는다 — AntV 기본 동작(weavefox.cn 아이콘 검색 API 로 글을 보냄)을 막는다. */
(function () {
  if (!window.AntVInfographic) { console.error('[meta-slide-ig] infographic.min.js 가 먼저 로드돼야 합니다'); return; }
  var IG = window.AntVInfographic, ICONS = window.MS_ICONS || {}, NAMES = Object.keys(ICONS);
  var cache = {};

  function findIcon(q) {
    q = String(q || '').toLowerCase().replace(/^ref:[a-z]+:/, '').replace(/^[a-z0-9-]+\//, '');
    if (cache[q]) return cache[q];
    var key = q.trim().replace(/\s+/g, '-');
    if (ICONS[key]) return (cache[q] = key);
    var toks = q.split(/[\s_\-\/]+/).filter(Boolean), best = 'circle-dot', score = 0;
    for (var i = 0; i < NAMES.length; i++) {
      var n = NAMES[i], nt = n.split('-'), tags = ' ' + ICONS[n][1] + ' ', s = 0;
      for (var j = 0; j < toks.length; j++) {
        var t = toks[j];
        if (nt.indexOf(t) >= 0) s += 3;
        else if (tags.indexOf(' ' + t + ' ') >= 0) s += 1;
      }
      if (n.indexOf('-off') >= 0 || n.indexOf('-filled') >= 0) s -= 0.5;
      s -= nt.length * 0.05;
      if (s > score) { score = s; best = n; }
    }
    return (cache[q] = best);
  }

  function svgOf(name) {
    var body = (ICONS[name] || ICONS['circle-dot'] || [''])[0];
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
      'stroke-linecap="round" stroke-linejoin="round">' + body + '</svg>';
  }

  if (IG.registerResourceLoader) {
    IG.registerResourceLoader(function (cfg) {
      try { return Promise.resolve(IG.loadSVGResource(svgOf(findIcon(cfg && cfg.data)))); }
      catch (e) { return Promise.resolve(IG.loadSVGResource(svgOf('circle-dot'))); }
    });
  }

  // 내장 서체(중국어 서체 CDN assets.antv.antgroup.com)를 미리 불러오지 않게 주소를 비운다 — 한글은 덱의 서체로 그린다
  try { (IG.getFonts ? IG.getFonts() : []).forEach(function (f) { f.fontWeight = {}; }); } catch (e) {}

  function cssVar(name, fallback) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  }

  function withTheme(src) {
    if (/^theme\b/m.test(src)) return src;
    var pal = [1, 2, 3, 4].map(function (i) { return cssVar('--ms-ig-' + i, ''); }).filter(Boolean);
    var font = cssVar('--ms-body', '').replace(/["']/g, '');
    var out = src.replace(/\s+$/, '') + '\ntheme\n';
    if (pal.length) out += '  palette ' + pal.join(' ') + '\n';
    if (font) out += '  base\n    text\n      font-family ' + font + '\n';
    return out;
  }

  function renderAll() {
    var body = cssVar('--ms-body', '').replace(/["']/g, '');
    if (body && IG.setDefaultFont) IG.setDefaultFont(body);
    var els = document.querySelectorAll('.ms-ig');
    for (var i = 0; i < els.length; i++) {
      var el = els[i], s = el.querySelector('script[type="text/x-infographic"]');
      if (!s) continue;
      var src = withTheme(s.textContent.replace(/^\n+/, ''));
      var host = el.querySelector('.ms-ig-host');
      if (!host) { host = document.createElement('div'); host.className = 'ms-ig-host'; host.style.cssText = 'width:100%;height:100%'; el.appendChild(host); }
      host.replaceChildren();
      try {
        var ig = new IG.Infographic({ container: host, width: '100%', height: '100%' });
        ig.render(src);
        el.setAttribute('data-ms-ig', 'ok');
      } catch (e) { el.setAttribute('data-ms-ig', 'error'); console.error('[meta-slide-ig]', e); }
    }
  }
  window.metaSlideRenderInfographics = renderAll;
  function run() { renderAll(); if (document.fonts && document.fonts.ready) document.fonts.ready.then(renderAll); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run); else run();
})();
