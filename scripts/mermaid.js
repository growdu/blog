'use strict';

// Convert ```mermaid fences into <div class="mermaid"> BEFORE markdown
// rendering, so the renderer treats them as raw HTML instead of code
// blocks (a ```mermaid fence would otherwise become <pre><code> and
// mermaid would never see it).
//
// The regular expression allows trailing whitespace between the language
// tag and the newline, which the previous stricter copy did not.
//
// The content is HTML-escaped here because it is injected as raw HTML;
// the browser turns the entities back into characters, which is exactly
// what mermaid's parser expects to read from the div's textContent.
hexo.extend.filter.register('before_post_render', function (data) {
  data.content = data.content.replace(
    /```mermaid[ \t]*\r?\n([\s\S]*?)```/g,
    function (match, code) {
      code = code
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
      return '<div class="mermaid">' + code + '</div>';
    }
  );
  return data;
});

// Fallback: if the renderer still produced a <pre><code class="language-mermaid">
// block (e.g. a fence with unusual whitespace), convert it to a mermaid
// div AFTER rendering.
hexo.extend.filter.register('after_post_render', function (data) {
  data.content = data.content.replace(
    /<pre[^>]*>\s*<code[^>]*class="[^"]*language-mermaid[^"]*"[^>]*>([\s\S]*?)<\/code>\s*<\/pre>/g,
    function (match, code) {
      return '<div class="mermaid">' + code + '</div>';
    }
  );
  return data;
});
