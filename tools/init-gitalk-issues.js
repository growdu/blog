#!/usr/bin/env node
'use strict';
/**
 * Batch-create GitHub Issues for Gitalk comments.
 * Runs after `hexo generate` in CI. Reads data-gitalk-id from generated
 * post HTML, checks for existing issues, and creates missing ones.
 */
const fs = require('fs');
const path = require('path');

const REPO = process.env.GITHUB_REPOSITORY || 'growdu/blog';
const TOKEN = process.env.GITHUB_TOKEN;
const SITE_URL = 'https://growdu.github.io';
const ROOT = '/blog/';

if (!TOKEN) {
  console.log('GITHUB_TOKEN not set, skipping issue creation');
  process.exit(0);
}

function decodeEntities(s) {
  return s
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, '&');
}

function findGitalkPosts(dir, results) {
  results = results || [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      findGitalkPosts(full, results);
    } else if (entry.name === 'index.html') {
      const html = fs.readFileSync(full, 'utf-8');
      if (html.includes('data-gitalk-id')) {
        const idM = html.match(/data-gitalk-id="([^"]+)"/);
        const titleM = html.match(/data-gitalk-title="([^"]+)"/);
        if (idM) {
          const relPath = full.replace(/^public\//, '').replace(/\/index\.html$/, '/');
          results.push({
            id: idM[1],
            title: titleM ? decodeEntities(titleM[1]) : 'Untitled',
            url: SITE_URL + ROOT + relPath,
          });
        }
      }
    }
  }
  return results;
}

async function gh(url, opts) {
  opts = opts || {};
  const res = await fetch('https://api.github.com' + url, {
    ...opts,
    headers: {
      Authorization: 'token ' + TOKEN,
      Accept: 'application/vnd.github.v3+json',
      'Content-Type': 'application/json',
      ...opts.headers,
    },
  });
  return { ok: res.ok, status: res.status, data: await res.json() };
}

async function main() {
  const posts = findGitalkPosts('public');
  console.log('Found ' + posts.length + ' posts with gitalk');

  // Collect existing Gitalk issue labels
  const existing = new Set();
  let page = 1;
  while (true) {
    const r = await gh('/repos/' + REPO + '/issues?labels=Gitalk&state=open&per_page=100&page=' + page);
    if (!r.ok || !Array.isArray(r.data) || r.data.length === 0) break;
    for (const issue of r.data) {
      for (const label of issue.labels || []) {
        if (label.name && /^p\d+$/.test(label.name)) existing.add(label.name);
      }
    }
    if (r.data.length < 100) break;
    page++;
  }
  console.log('Found ' + existing.size + ' existing gitalk issues');

  let created = 0;
  let skipped = 0;
  let failed = 0;
  for (const post of posts) {
    if (existing.has(post.id)) {
      skipped++;
      continue;
    }
    const r = await gh('/repos/' + REPO + '/issues', {
      method: 'POST',
      body: JSON.stringify({
        title: post.title,
        body: post.url,
        labels: [post.id, 'Gitalk', 'Comment'],
      }),
    });
    if (r.ok) {
      created++;
      if (created % 50 === 0) console.log('  created ' + created + ' issues so far...');
    } else {
      failed++;
      console.error('  FAILED: "' + post.title + '" (' + post.id + '): ' + (r.data.message || 'unknown'));
    }
    await new Promise(function (r) { setTimeout(r, 100); });
  }

  console.log('Done: created=' + created + ' skipped=' + skipped + ' failed=' + failed + ' total=' + posts.length);
}

main().catch(function (e) {
  console.error('Error:', e);
  process.exit(1);
});
