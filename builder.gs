// Competitors Watch 2.0 - report builder v2. Reads shadow feeds, writes brief to the SAME shadow folder. Sends nothing anywhere.
var FOLDER_ID = '1d2l5o8s5WELR0OfoOzAHLSjrrXca7oFX';
var MODEL = 'openai/gpt-oss-120b';
var COMPANIES = ['Zerodha', 'Groww', 'Angel One', 'Upstox', 'Dhan', 'ICICI Direct', 'INDmoney'];
var PRESS_OWNER = {'zerodha.com': 'Zerodha', 'upstox.com': 'Upstox', 'groww.in': 'Groww', 'angelone.in': 'Angel One'};
var MAX_POSTS = 30;

function newestFile_(folder, name) {
  var it = folder.getFilesByName(name), best = null;
  while (it.hasNext()) { var f = it.next(); if (!best || f.getDateCreated() > best.getDateCreated()) best = f; }
  return best ? JSON.parse(best.getBlob().getDataAsString()) : null;
}

function isNoise_(t) {
  t = (t || '').trim();
  if (t.length < 25) return true;
  return /(happy|wish(es|ing)?|greetings?).{0,40}(diwali|holi|eid|christmas|new year|dussehra)/i.test(t) || /^(happy|wishing)\b/i.test(t);
}

function one_(s, n) { return String(s || '').replace(/\s+/g, ' ').slice(0, n); }

function digestFor_(co, mac, cloud) {
  var out = [], stats = {x: 0, xRT: 0, xNoise: 0, yt: 0, press: 0, men: 0};
  var xs = ((mac && mac.x && mac.x[co] && mac.x[co].posts) || []).slice();
  xs.sort(function (a, b) { return new Date(b.published_at) - new Date(a.published_at); });
  var seen = {};
  xs.forEach(function (p) {
    if (p.is_retweet) { stats.xRT++; return; }
    if (isNoise_(p.text)) { stats.xNoise++; return; }
    if (seen[p.url] || stats.x >= MAX_POSTS) return;
    seen[p.url] = 1; stats.x++;
    out.push('[X @' + (p.handle || p.author) + '] ' + one_(p.text, 330) + ' | ' + p.url);
  });
  var ys = (mac && mac.youtube && mac.youtube[co] && mac.youtube[co].fresh) || [];
  ys.forEach(function (v) {
    stats.yt++;
    out.push('[YouTube ' + (v.published_at || '') + ' | ' + v.author + '] ' + v.title + ' - ' + one_(v.text, 250) + ' | ' + v.url);
  });
  if (cloud && cloud.press) {
    Object.keys(cloud.press).forEach(function (url) {
      var owner = null;
      Object.keys(PRESS_OWNER).forEach(function (d) { if (url.indexOf(d) > -1) owner = PRESS_OWNER[d]; });
      if (owner !== co) return;
      var items = cloud.press[url].items || [];
      if (items[0] && items[0].text) {
        stats.press++;
        out.push('[Official page ' + url + ' - newest entries first; mention only entries dated within the last 48 hours] ' + one_(items[0].text, 1800));
      }
    });
  }
  var ms = (mac && mac.mentions && mac.mentions[co] && mac.mentions[co].posts) || [];
  var mo = [];
  ms.forEach(function (p) {
    if (stats.men >= 8) return;
    stats.men++;
    mo.push('[Customer post by @' + p.author + '] ' + one_(p.text, 280) + ' | ' + p.url);
  });
  return {text: out.join('\n'), men: mo.join('\n'), stats: stats};
}

function askGroq_(co, d, today) {
  var key = PropertiesService.getScriptProperties().getProperty('GROQ_KEY');
  if (!key) return '(GROQ_KEY missing)';
  var prompt = 'You write one section of a daily competitor brief for the Operations head of an Indian broker (Kotak Securities). Competitor: ' + co + '. Today: ' + today + '. The window is the last 24 hours.\n' +
    'Use ONLY the items below. Never invent facts, dates or links.\n' +
    'Output exactly two parts.\n' +
    'UPDATES: up to 6 short bullets from the company items. Start each bullet with [MATERIAL] for a new product feature, launch, pricing/brokerage change, outage, regulatory or leadership/business announcement; otherwise [ROUTINE] for marketing, education, events or market commentary. Webinars, live sessions, teasers and educational videos are ROUTINE, never MATERIAL. Skip posts that are personal, festive, motivational or unrelated to the company\'s products or services; do not list them at all. Mention any new product, feature, market-access (e.g. US stocks, MTF, alerts) or tool announced in a video title or post as MATERIAL. End each bullet with the source link in brackets. If nothing, write: None.\n' +
    'CUSTOMER: up to 3 bullets summarising individual customer complaints from the customer posts, each marked (unconfirmed, single user) and ending with the link. If none are genuine complaints about ' + co + ', write: None.\n\n' +
    'COMPANY ITEMS:\n' + (d.text || '(none)') + '\n\nCUSTOMER POSTS:\n' + (d.men || '(none)');
  var opts = {
    method: 'post', contentType: 'application/json', muteHttpExceptions: true,
    headers: {Authorization: 'Bearer ' + key},
    payload: JSON.stringify({model: MODEL, temperature: 0.2, max_tokens: 1800, reasoning_effort: 'low', messages: [{role: 'user', content: prompt}]})
  };
  for (var attempt = 0; attempt < 2; attempt++) {
    var res = UrlFetchApp.fetch('https://api.groq.com/openai/v1/chat/completions', opts);
    if (res.getResponseCode() === 200) return JSON.parse(res.getContentText()).choices[0].message.content.trim();
    if (res.getResponseCode() === 429 && attempt === 0) { Utilities.sleep(25000); continue; }
    return '(Groq error ' + res.getResponseCode() + ': ' + res.getContentText().slice(0, 150) + ')';
  }
}

function buildBrief() {
  var folder = DriveApp.getFolderById(FOLDER_ID);
  var today = Utilities.formatDate(new Date(), 'Asia/Kolkata', 'yyyy-MM-dd');
  var mac = newestFile_(folder, 'feed-' + today + '-mac.json');
  var cloud = newestFile_(folder, 'feed-' + today + '.json');
  var lines = ['COMPETITORS WATCH 2.0 (shadow) - ' + today, 'Window: ' + (mac && mac.window ? mac.window : 'unknown'), 'Sources: ' + (mac ? 'X+YouTube+mentions (Mac) ' : 'X+YouTube MISSING ') + '| ' + (cloud ? 'Press pages (GitHub)' : 'Press pages MISSING'), ''];
  COMPANIES.forEach(function (co) {
    var d = digestFor_(co, mac, cloud);
    var s = d.stats;
    var body = (d.text || d.men) ? askGroq_(co, d, today) : 'UPDATES: None.\nCUSTOMER: None.';
    lines.push('== ' + co + '  (X ' + s.x + ', YouTube ' + s.yt + ', official page ' + s.press + ', customer posts ' + s.men + '; skipped: ' + s.xRT + ' retweets, ' + s.xNoise + ' greetings)');
    lines.push(body, '');
    if (d.text || d.men) Utilities.sleep(9000);
  });
  folder.createFile('brief-' + today + '.txt', lines.join('\n'), MimeType.PLAIN_TEXT);
}
