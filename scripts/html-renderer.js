'use strict';

// HTML renderer for .html and .htm files in source/_posts/.
//
// Strips the outer <html>/<head>/<body> wrappers from self-contained
// HTML documents and returns only the <style> blocks + <body> content.
// This lets Hexo wrap the result in matery's post layout, which adds
// header, footer, reward, comments, related posts, and prev/next nav.
//
// Standalone HTML articles typically arrive in a "card" layout that was
// designed for full-page viewing:
//
//   <body>
//     <div class="container">       <-- centered, max-width:~1100px,
//       <header>...</header>              rounded card with bg + shadow
//       <div class="content">...</div>
//       <footer>...</footer>
//     </div>
//   </body>
//
// Inside matery's post layout that frame clashes:
//   * `.container { max-width; margin:auto; background:white; border-radius
//     box-shadow }` shrinks the article and adds a "white card on white"
//     halo around it.
//   * `body { background: linear-gradient; padding }` overrides the page
//     chrome.
//   * `<header>` and `<footer>` are decorative page-title / page-footer
//     bands that don't belong inside the article body.
//   * The leading <h1> is the title, which matery's post-cover already
//     renders.
//
// To reconcile, after extracting body+styles we:
//   1. Drop the outermost <div class="container"> wrapper (with proper
//      brace-balanced div tracking so inner divs are not affected).
//   2. Strip standalone <header>...</header> / <footer>...</footer>
//      decorations and the leading <h1>...</h1>.
//   3. Drop the entire CSS rule whose selector is `body` or `html`
//      (those would override matery's page chrome).
//   4. Pass `:root` rules through unchanged so the doc's CSS custom
//      properties still resolve.
//   5. Prefix every other selector with `.html-post-body` so the
//      styles cannot leak past the article slot.
//
// CSS is parsed by a small brace-depth walker rather than regex, so
// @media (max-width: 768px) { ... } blocks with nested rules are
// scoped correctly.

const STYLE_RE = /<style\b[^>]*>[\s\S]*?<\/style>/gi;
const BODY_RE  = /<body\b[^>]*>([\s\S]*)<\/body>/i;

function extractStyles(html) {
  const out = [];
  let m;
  while ((m = STYLE_RE.exec(html)) !== null) out.push(m[0]);
  return out;
}

function extractBody(html) {
  const m = BODY_RE.exec(html);
  return m ? m[1].trim() : html.trim();
}

// Split a CSS selector list at top-level commas.  Attribute selectors
// with parens could in theory contain commas; we don't have any in our
// docs and the resulting false split would just attach a bogus prefix,
// which is harmless.
function splitSelectorList(selector) {
  return selector
    .split(/\s*,\s*/)
    .map(s => s.trim())
    .filter(Boolean);
}

// Walk CSS at brace depth 0.  For each top-level rule, call
// `handler(selector, ruleText, isAtRule, atKind)` and concatenate the
// returned text.  CSS comments are silently dropped (not associated
// with any rule).  Handles @-rules with nested bodies (e.g. @media)
// correctly via the depth counter.
function walkRules(css, handler) {
  let out = '';
  let i = 0;
  let depth = 0;
  let ruleStart = 0;
  let openBrace = -1;

  while (i < css.length) {
    const c = css[i];

    if (c === '/' && css[i + 1] === '*') {
      out += css.slice(ruleStart, i);
      const end = css.indexOf('*/', i + 2);
      const nextPos = end === -1 ? css.length : end + 2;
      ruleStart = nextPos;
      i = nextPos;
      continue;
    }

    if (c === '{') {
      if (depth === 0) openBrace = i;
      depth++;
    } else if (c === '}') {
      depth--;
      if (depth === 0 && openBrace !== -1) {
        const ruleText = css.slice(ruleStart, i + 1);
        const selector = css.slice(ruleStart, openBrace).trim();
        const isAtRule = selector.startsWith('@');
        const atKind = isAtRule
          ? selector.split(/\s+/)[0].toLowerCase()
          : '';
        out += handler(selector, ruleText, isAtRule, atKind) + '\n';
        ruleStart = i + 1;
        openBrace = -1;
      }
    }
    i++;
  }
  if (ruleStart < css.length) out += css.slice(ruleStart);
  return out;
}

function prefixSelectorList(selector, prefix) {
  const sels = splitSelectorList(selector);
  return sels.map(s => `${prefix} ${s}`).join(', ');
}

function scopeCss(css, scope) {
  return walkRules(css, (selector, ruleText, isAtRule, atKind) => {
    if (isAtRule) {
      if (atKind === '@media' || atKind === '@supports') {
        // Recurse into the body to scope inner rules too.
        const bodyStart = ruleText.indexOf('{') + 1;
        const bodyEnd = ruleText.lastIndexOf('}');
        const inner = ruleText.slice(bodyStart, bodyEnd);
        return ruleText.slice(0, bodyStart)
             + scopeCss(inner, scope)
             + ruleText.slice(bodyEnd);
      }
      // @keyframes / @font-face / @import — pass through unchanged.
      return ruleText;
    }
    const sel = selector.trim();
    if (sel === ':root') return ruleText;        // pass through (CSS vars)
    if (sel === 'body' || sel === 'html') return '';  // drop
    const bodyStart = ruleText.indexOf('{');
    return prefixSelectorList(selector, scope)
         + ' '
         + ruleText.slice(bodyStart);
  });
}

// Drop the outermost <div ...>...</div> wrapper if the body starts with
// <div ...> and the wrapper can be balanced.  Falls back to no-op when
// the body doesn't start with a div or the depth tracker gets confused.
function stripOuterDiv(body) {
  const trimmed = body.trim();
  if (!/^<div\b/i.test(trimmed)) return body;
  const openTagEnd = trimmed.indexOf('>') + 1;
  let depth = 1;
  let pos = openTagEnd;
  while (pos < trimmed.length && depth > 0) {
    const nextOpen = trimmed.indexOf('<div', pos);
    const nextClose = trimmed.indexOf('</div>', pos);
    if (nextClose === -1) break;
    if (nextOpen !== -1 && nextOpen < nextClose) {
      depth++;
      const tagEnd = trimmed.indexOf('>', nextOpen);
      if (tagEnd === -1) break;
      pos = tagEnd + 1;
    } else {
      depth--;
      pos = nextClose + 6;
    }
  }
  if (depth === 0) {
    return trimmed.slice(openTagEnd, pos - 6).trim();
  }
  return body;
}

// Strip the standalone-page decorations that no longer belong once the
// body is grafted onto matery's post layout.
function stripDecorativeWrappers(body) {
  let s = stripOuterDiv(body);
  s = s.replace(/<header\b[^>]*>[\s\S]*?<\/header>/gi, '');
  s = s.replace(/<footer\b[^>]*>[\s\S]*?<\/footer>/gi, '');
  s = s.replace(/<h1\b[^>]*>[\s\S]*?<\/h1>/i, '');
  return s.trim();
}

function processStyle(styleBlock) {
  let css = styleBlock
    .replace(/^<style\b[^>]*>/i, '')
    .replace(/<\/style>\s*$/i, '');
  css = scopeCss(css, '.html-post-body');
  return `<style>${css}</style>`;
}

function renderHtml(data) {
  const html = data.text;
  const styles = extractStyles(html);
  let body = extractBody(html);
  body = stripDecorativeWrappers(body);
  const scopedStyles = styles.map(processStyle);
  return `<div class="html-post-body">\n${scopedStyles.join('\n')}\n${body}\n</div>`;
}

hexo.extend.renderer.register('html', 'html', renderHtml, true);
hexo.extend.renderer.register('htm', 'html', renderHtml, true);
