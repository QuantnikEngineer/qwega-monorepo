// Website source — fetch a single URL, extract the readable body text via
// cheerio, return one document. v1 deliberately does NOT crawl outbound
// links; user adds each page they care about explicitly.
//
// Strips <script>, <style>, <nav>, <footer>, <aside> before extracting text
// so the chunk count isn't dominated by boilerplate.

import * as cheerio from 'cheerio';

const STRIP_TAGS = ['script', 'style', 'nav', 'footer', 'aside', 'noscript', 'svg'];

export async function fetchDocuments(source) {
  const cfg = JSON.parse(source.config || '{}');
  const url = cfg.url;
  if (!url) throw new Error('website source missing config.url');

  let resp;
  try {
    resp = await fetch(url, {
      headers: { 'User-Agent': 'quantnik-context-fabric/1.0 (RAG ingest)' },
      redirect: 'follow',
    });
  } catch (e) {
    throw new Error(`network: ${e.message}`);
  }
  if (!resp.ok) throw new Error(`HTTP ${resp.status} fetching ${url}`);

  const html = await resp.text();
  const $ = cheerio.load(html);

  // Title preference: <meta og:title> → <title> → <h1>
  const title =
    $('meta[property="og:title"]').attr('content') ||
    $('title').text().trim() ||
    $('h1').first().text().trim() ||
    url;

  for (const t of STRIP_TAGS) $(t).remove();

  // Prefer main / article when present; fall back to body.
  const $root = $('article').length ? $('article')
              : $('main').length    ? $('main')
              :                       $('body');
  const text = $root.text()
    .replace(/ /g, ' ')
    .replace(/[ \t]+/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim();

  return [{
    title,
    uri:         url,
    external_id: url,
    content:     text,
  }];
}
