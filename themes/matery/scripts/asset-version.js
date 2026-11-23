/**
 * 静态资源 URL 带内容哈希 —— 绕开 nginx 的 30 天 immutable 缓存。
 *
 * **背景（2026-11-23）**：nginx 对 .css/.js 一律
 *
 *     expires 30d;
 *     add_header Cache-Control "public, immutable";
 *
 * 而这些资源的 URL 是稳的 —— /css/my.css 五年不变。于是 CSS 一改，
 * 同一个 URL 的**新内容浏览器根本不会去取**：immutable 明确告诉浏览器
 * 「30 天内别来问，也别拿本地那份旧的来烦我」。
 *
 * 2026-11-20 首页统计条从「五张白卡片」重做成「一整条五格」之后，服务器
 * 上明明已经是新样式了，老访客看到的却还是旧版：≤992px 时旧 CSS 是
 * `repeat(3, 1fr)`，五张卡排成「3 + 2」**两行**，数字还是 30px 的黑体。
 * 新样式一次都没送到他们眼前 —— 浏览器手里那份旧 CSS 被 immutable
 * 锁了整整 30 天。
 *
 * **办法**：URL 里带内容哈希。内容变 → URL 变 → 浏览器必须重新取；
 * 内容没变 → URL 不变 → 继续吃长缓存（这正是 immutable 想要的）。
 *
 * 哈希取的是**主题 source 目录里那个文件**的内容，不是构建时间戳：
 * 时间戳会让每次构建的 URL 都变，等于把长缓存废掉；内容哈希只在该改的
 * 时候才变。
 *
 * 覆盖范围：/css/ /js/ /libs/ 下的**本地**文件（CDN 上的库不归我们管，
 * 也不该由我们加版本号）。/medias/ 下的图片不在这儿 —— 图片是新增文件、
 * 名字带日期，本来就是新 URL。/sw.js 也不加：service worker 必须在
 * **稳定的 URL** 上，浏览器才拿得到新版本。
 */

'use strict';

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

// 只给这几类目录下的本地文件加版本号
const VERSIONED_DIRS = ['/css/', '/js/', '/libs/'];

// 一次构建里同一个文件只算一次哈希（首页之外还有 580 篇文章，每篇都
// 要过一遍这个过滤器）
const hashCache = Object.create(null);

/**
 * 文件内容的短哈希。文件不在（路径拼错、库没拷进来）就返回空串 ——
 * 那就让 URL 原样过去，别给一个 404 加上版本号。
 */
function contentHash(absPath) {
  if (hashCache[absPath] !== undefined) return hashCache[absPath];

  let hash = '';
  try {
    hash = crypto.createHash('sha1').update(fs.readFileSync(absPath)).digest('hex').slice(0, 8);
  } catch (e) {
    hash = '';
  }

  hashCache[absPath] = hash;
  return hash;
}

hexo.extend.filter.register('after_render:html', function (content) {
  const root = hexo.config.root || '/';
  const sourceDir = path.join(hexo.theme_dir, 'source');

  // 只碰 src=/href= 里的本地静态资源
  return content.replace(/(\s(?:src|href)=)(["'])([^"'\s]+)\2/g, function (match, prefix, quote, url) {
    // 外链、锚点、data: URI —— 一律不动
    if (!url || url.indexOf('//') !== -1 || url.charAt(0) === '#' || url.indexOf('data:') === 0) {
      return match;
    }
    // 已经带版本号了（别把自己加两遍）
    if (/[?&]v=/.test(url)) return match;

    const bare = url.split('#')[0].split('?')[0];
    if (!bare) return match;

    // 必须是站点根目录下的路径
    if (root !== '/' && bare.indexOf(root) !== 0) return match;

    // 去掉站点根，剩下的才是主题 source 目录里的相对路径
    // root='/'      → '/css/my.css'
    // root='/blog/' → '/css/my.css'（镜像站）
    const rel = root === '/' ? bare : bare.slice(root.length - 1);

    let versioned = false;
    for (let i = 0; i < VERSIONED_DIRS.length; i++) {
      if (rel.indexOf(VERSIONED_DIRS[i]) === 0) {
        versioned = true;
        break;
      }
    }
    if (!versioned) return match;

    const hash = contentHash(path.join(sourceDir, rel));
    if (!hash) return match;

    const sep = url.indexOf('?') === -1 ? '?' : '&';
    return prefix + quote + url + sep + 'v=' + hash + quote;
  });
});
