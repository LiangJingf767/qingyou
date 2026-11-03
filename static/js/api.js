/* ============================================================
   前端公共工具：API 封装 / 格式化 / Toast / Sheet / 导航 / 图标
   ============================================================ */
(function () {
  'use strict';

  /* ---- DOM ---- */
  window.$ = (s, el) => (el || document).querySelector(s);
  window.$$ = (s, el) => Array.from((el || document).querySelectorAll(s));

  /* ---- API ---- */
  // 统一响应信封：{code, message, data}；code==0 返回 data，否则抛错。
  window.api = async function (path, opts) {
    opts = opts || {};
    const init = { headers: { 'Content-Type': 'application/json' } };
    if (opts.method) init.method = opts.method;
    if (opts.body !== undefined) init.body = JSON.stringify(opts.body);
    let res, body;
    try {
      res = await fetch(path, init);
      body = await res.json();
    } catch (e) {
      throw new Error('网络异常，请稍后重试');
    }
    if (!body || body.code !== 0) {
      throw new Error((body && body.message) || '请求失败');
    }
    return body.data;
  };

  /* ---- 截图 OCR（multipart 上传图片，返回识别文本） ---- */
  window.ocrImage = async function (file) {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch('/api/v1/ocr', { method: 'POST', body: fd });
    const b = await res.json();
    if (!b || b.code !== 0) throw new Error((b && b.message) || 'OCR 识别失败');
    return b.data.text;
  };

  /* ---- 参数 / 导航 ---- */
  window.qs = function (name) { return new URLSearchParams(location.search).get(name); };
  window.goto = function (path) { location.href = path; };
  window.curPid = function () { return localStorage.getItem('cur_pid') || ''; };
  window.setCurPid = function (pid) { localStorage.setItem('cur_pid', pid); };
  window.goProject = function (pid, page) {
    setCurPid(pid);
    location.href = '/' + page + '?project_id=' + pid;
  };

  /* ---- 格式化 ---- */
  window.fmtPrice = function (x) {
    if (x === null || x === undefined || x === '') return '—';
    x = Number(x);
    if (x === 0) return '免费';
    return '¥' + (Number.isInteger(x) ? x : x.toFixed(2));
  };
  window.fmtMoney = function (x) {
    if (x === null || x === undefined) return '—';
    x = Number(x);
    return '¥' + (Number.isInteger(x) ? x : x.toFixed(2));
  };
  window.fmtNum = function (x) {
    if (x === null || x === undefined) return '—';
    x = Number(x);
    return Number.isInteger(x) ? String(x) : x.toFixed(1);
  };
  window.todayStr = function () {
    const d = new Date();
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  };
  window.dateLabel = function (s) {
    if (!s) return '';
    const d = s.slice(0, 10);
    if (d === todayStr()) return '今天';
    const y = new Date(); y.setDate(y.getDate() - 1);
    const yStr = y.getFullYear() + '-' + String(y.getMonth() + 1).padStart(2, '0') + '-' + String(y.getDate()).padStart(2, '0');
    if (d === yStr) return '昨天';
    return d.slice(5).replace('-', '/');
  };
  window.esc = function (s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  };

  /* ---- Toast ---- */
  let _toastTimer = null;
  window.toast = function (msg) {
    const el = document.getElementById('toast');
    if (!el) return;
    el.textContent = msg;
    el.classList.add('show');
    clearTimeout(_toastTimer);
    _toastTimer = setTimeout(() => el.classList.remove('show'), 1800);
  };

  /* ---- Sheet ---- */
  window.openSheet = function () {
    const m = document.getElementById('sheet-mask');
    const s = document.getElementById('sheet');
    if (m) m.classList.add('show');
    if (s) s.classList.add('show');
  };
  window.closeSheet = function () {
    const m = document.getElementById('sheet-mask');
    const s = document.getElementById('sheet');
    if (m) m.classList.remove('show');
    if (s) s.classList.remove('show');
  };
  document.addEventListener('click', e => {
    if (e.target && e.target.id === 'sheet-mask') closeSheet();
  });

  /* ---- 图标（线性，stroke=currentColor） ---- */
  window.icon = function (name, size) {
    const s = size || 22;
    const P = {
      home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/>',
      list: '<path d="M8 6h13M8 12h13M8 18h13"/><circle cx="3.5" cy="6" r="1"/><circle cx="3.5" cy="12" r="1"/><circle cx="3.5" cy="18" r="1"/>',
      plus: '<path d="M12 5v14M5 12h14"/>',
      wallet: '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/>',
      gear: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9 17 7M7 17l-2.1 2.1"/>',
      search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
      back: '<path d="m15 5-7 7 7 7"/>',
      export: '<path d="M12 3v12"/><path d="m7 8 5 5 5-5"/><path d="M4 21h16"/>',
      map: '<path d="M3 6l6-3 6 3 6-3v15l-6 3-6-3-6 3z"/><path d="M9 3v15M15 6v15"/>',
      calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
      pin: '<path d="M12 21s-7-5.5-7-11a7 7 0 0 1 14 0c0 5.5-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
      drag: '<path d="M9 5h.01M9 12h.01M9 19h.01M15 5h.01M15 12h.01M15 19h.01"/>',
      edit: '<path d="M4 20h4L20 8l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>',
      check: '<path d="m5 12 5 5L20 7"/>',
      chevR: '<path d="m9 5 7 7-7 7"/>',
      clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/>',
      image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8.5" cy="9" r="1.5"/><path d="m3 17 5-5 4 4 3-3 6 6"/>',
      doc: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/>',
      link: '<path d="M10 13a5 5 0 0 0 7 0l2-2a5 5 0 0 0-7-7l-1 1"/><path d="M14 11a5 5 0 0 0-7 0l-2 2a5 5 0 0 0 7 7l1-1"/>',
      trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
      star: '<path d="m12 3 2.7 5.6 6.3.9-4.5 4.4 1 6.1L12 17l-5.5 3 1-6.1L3 9.5l6.3-.9z"/>',
      heart: '<path d="M12 20s-7-4.5-9-9a5 5 0 0 1 9-3 5 5 0 0 1 9 3c-2 4.5-9 9-9 9z"/>',
      camera: '<rect x="3" y="7" width="18" height="13" rx="2"/><circle cx="12" cy="13" r="3.5"/><path d="M8 7l1.5-3h5L16 7"/>',
      refresh: '<path d="M21 12a9 9 0 1 1-2.6-6.4"/><path d="M21 3v6h-6"/>'
    };
    const d = P[name] || P.pin;
    return '<svg width="' + s + '" height="' + s + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' + d + '</svg>';
  };

  /* ---- 底部导航（含「新建」FAB） ---- */
  window.renderNav = function (active) {
    const el = document.getElementById('navbar');
    if (!el) return;
    const items = [
      { key: 'home', label: '首页', icon: 'home', href: '/home' },
      { key: 'itinerary', label: '行程', icon: 'list', href: '/itinerary?project_id=' + curPid() },
      { key: 'fab', label: '', icon: '', href: '/new-plan' },
      { key: 'budget', label: '账本', icon: 'wallet', href: '/budget' },
      { key: 'settings', label: '设置', icon: 'gear', href: '/settings' }
    ];
    el.innerHTML = items.map(it => {
      if (it.key === 'fab') {
        return '<div class="nav-fab"><a class="fab" href="' + it.href + '">' + icon('plus', 26) + '</a></div>';
      }
      return '<a class="nav-item ' + (active === it.key ? 'on' : '') + '" href="' + it.href + '">' + icon(it.icon) + '<span>' + it.label + '</span></a>';
    }).join('');
  };
})();
