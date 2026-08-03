'use strict';

// Pass-through renderer for .html and .htm files in source/_posts/.
//
// Hexo's default renderer registry has no entry for the .html extension,
// so a bare HTML doc in source/_posts/ would error during generation.
// We register a synchronous renderer that returns the file body verbatim
// — no transformation, no wrapping.
//
// Layout behaviour:
//   * With `layout: false` in front matter (set by sync-hexo.py for HTML
//     docs so they publish as standalone pages), the rendered HTML body
//     is written directly to public/<slug>/index.html — useful for
//     self-contained HTML pages.
//   * Without `layout: false`, Hexo wraps the body in matery's post
//     layout (article chrome + footer). Useful if you want HTML
//     fragments inside a normal post.
//
// Either way, scripts/mermaid.js and any other `before_post_render`
// filters in this folder still run on every post, so HTML content is
// processed by them just like markdown.

hexo.extend.renderer.register('html', 'html', function (data) {
  return data.text;
}, true);

hexo.extend.renderer.register('htm', 'html', function (data) {
  return data.text;
}, true);
