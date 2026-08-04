'use strict';

// HTML renderer for .html and .htm files in source/_posts/.
//
// Strips the outer <html>/<head>/<body> wrapper from self-contained
// HTML documents and returns only the <style> blocks + <body> content.
// This lets Hexo wrap the result in matery's post layout, which adds
// header, footer, reward, comments, related posts, and prev/next nav.
//
// If the input doesn't have a <body> tag, the entire content is
// returned as-is (defensive fallback).
//
// scripts/mermaid.js and other before_post_render filters still run
// on every post, so HTML content is processed by them just like
// markdown.

const STYLE_RE = /<style[\s\S]*?<\/style>/gi;
const BODY_RE  = /<body[^>]*>([\s\S]*)<\/body>/i;

function extractBodyAndStyles(html) {
  const styles = [];
  let m;
  while ((m = STYLE_RE.exec(html)) !== null) {
    styles.push(m[0]);
  }
  const bodyMatch = BODY_RE.exec(html);
  const body = bodyMatch ? bodyMatch[1].trim() : html;
  return styles.join('\n') + '\n' + body;
}

hexo.extend.renderer.register('html', 'html', function (data) {
  return extractBodyAndStyles(data.text);
}, true);

hexo.extend.renderer.register('htm', 'html', function (data) {
  return extractBodyAndStyles(data.text);
}, true);
