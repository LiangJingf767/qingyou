/**
 * 高德地图 JS SDK 加载器（前端复用）。
 *
 * 用法：先注入 window.AMAP_CONFIG = { key, securityJsCode }，再 loadAMap(function(AMap){ ... })。
 *
 * 版本选择：
 *   - 配置了 securityJsCode → 加载 v2.0（需“安全密钥”，高德控制台 → 应用管理 → 我的应用 → 对应 Key）
 *   - 未配置              → 加载 v1.4.15（仅需 Key，兼容性最好，适合课程项目）
 */
(function () {
  var cfg = window.AMAP_CONFIG || {};
  var callbacks = [];
  var loading = false;

  function fire(AMap) {
    var cbs = callbacks.slice();
    callbacks = [];
    cbs.forEach(function (cb) {
      try { cb(AMap); } catch (e) { console.error(e); }
    });
  }

  function load(callback) {
    if (window.AMap) {
      callback(window.AMap);
      return;
    }
    callbacks.push(callback);
    if (loading) return; // SDK 加载中，复用同一脚本，待 onload 统一回调
    loading = true;
    if (cfg.securityJsCode) {
      window._AMapSecurityConfig = { securityJsCode: cfg.securityJsCode };
    }
    var version = cfg.securityJsCode ? '2.0' : '1.4.15';
    var s = document.createElement('script');
    s.src = 'https://webapi.amap.com/maps?v=' + version + '&key=' + encodeURIComponent(cfg.key || '');
    s.onload = function () { fire(window.AMap); };
    s.onerror = function () {
      console.error('高德地图 JS SDK 加载失败，请检查 AMAP_JS_KEY / 安全密钥与域名白名单');
      callbacks = [];
      loading = false;
    };
    document.head.appendChild(s);
  }

  window.loadAMap = load;
})();
