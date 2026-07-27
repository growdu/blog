'use strict';

hexo.extend.filter.register('before_post_render', function (data) {
  data.content = data.content.replace(
    /```mermaid\n([\s\S]*?)```/g,
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
'use strict';

// Convert ```mermaid blocks to <div class="mermaid"> BEFORE markdown
// rendering so the renderer treats them as raw HTML, not code blocks.
hexo.extend.filter.register('before_post_render', function (data) {
  data.content = data.content.replace(
    /```mermaid\s*\n([\s\S]*?)```/g,
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
// block, convert it to a mermaid div AFTER rendering.
hexo.extend.filter.register('after_post_render', function (data) {
  data.content = data.content.replace(
    /<pre[^>]*>\s*<code[^>]*class="[^"]*language-mermaid[^"]*"[^>]*>([\s\S]*?)<\/code>\s*<\/pre>/g,
    function (match, code) {
      return '<div class="mermaid">' + code + '</div>';
    }
  );
  return data;
});
