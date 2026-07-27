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
