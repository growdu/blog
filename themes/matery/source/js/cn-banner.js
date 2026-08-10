/**
 * cn-region-banner detection logic.
 *
 * Decides whether to show the regional banner based on the visitor's
 * navigator.language and timezone heuristic, and persists dismissal
 * state in localStorage. Intended to be loaded once via
 * <script src="/js/cn-banner.js"></script> on the home page only.
 *
 * The banner DOM element is expected to be #cn-region-banner and is
 * hidden by default via the [hidden] attribute in cn-banner.ejs.
 */
(function () {
  'use strict';
  if (typeof window === 'undefined') return;
  var banner = document.getElementById('cn-region-banner');
  if (!banner) return;

  // Already on the Chinese-facing domain — nothing to do.
  var host = window.location.hostname;
  if (host === 'growdu.cn' || host === 'www.growdu.cn') {
    banner.hidden = true;
    return;
  }

  // User previously dismissed the banner.
  var dismissed = false;
  try { dismissed = localStorage.getItem('cn-banner-dismissed') === '1'; } catch (e) {}
  if (dismissed) return;

  // Heuristic: Chinese navigator language OR Asia/Shanghai-family timezone.
  var lang = (navigator.language || navigator.userLanguage || '').toLowerCase();
  var isCN = (lang === 'zh-cn' || lang.indexOf('zh-hans') === 0 || lang === 'zh');
  if (!isCN && typeof Intl !== 'undefined' && Intl.DateTimeFormat) {
    try {
      var tz = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
      if (tz === 'Asia/Shanghai' || tz === 'Asia/Chongqing' ||
          tz === 'Asia/Harbin'   || tz === 'Asia/Urumqi'  ||
          tz === 'Asia/Hong_Kong') {
        isCN = true;
      }
    } catch (e) { /* ignore */ }
  }
  if (!isCN) return;

  banner.hidden = false;
  var close = banner.querySelector('.cn-region-banner__close');
  if (close) {
    close.addEventListener('click', function () {
      banner.hidden = true;
      try { localStorage.setItem('cn-banner-dismissed', '1'); } catch (e) {}
    });
  }
})();
