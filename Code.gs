/**
 * DomainFront Relay — Google Apps Script
 *
 * Routes traffic through a VPS for a fixed outbound IP.
 * Compatible with MasterHttpRelayVPN (python_testing branch).
 *
 * SETUP:
 *   1. Go to https://script.google.com → New project
 *   2. Replace all content with this file
 *   3. Change AUTH_KEY, VPS_URL, VPS_KEY below
 *   4. Deploy → New deployment → Web app
 *      Execute as: Me | Who has access: Anyone
 *   5. Copy the Deployment ID into MasterHttpRelayVPN config.json
 */

const AUTH_KEY = "CHANGE_ME_TO_A_STRONG_SECRET";   // کلید بین کلاینت و اپس اسکریپت
const VPS_URL  = "http://YOUR_VPS_IP:8080/relay";   // آدرس VPS
const VPS_KEY  = "CHANGE_ME_TO_A_STRONG_SECRET";   // کلید بین اپس اسکریپت و VPS

const SKIP_HEADERS = {
  host: 1, connection: 1, "content-length": 1,
  "transfer-encoding": 1, "proxy-connection": 1,
  "proxy-authorization": 1, "priority": 1, te: 1,
};

// ── entry point ──────────────────────────────────────────────────────────────

function doPost(e) {
  try {
    var req = JSON.parse(e.postData.contents);
    if (req.k !== AUTH_KEY) return _json({ e: "unauthorized" });
    if (Array.isArray(req.q)) return _doBatch(req.q);
    return _doSingle(req);
  } catch (err) {
    return _json({ e: String(err) });
  }
}

// ── single ───────────────────────────────────────────────────────────────────

function _doSingle(req) {
  if (!_validUrl(req.u)) return _json({ e: "bad url" });
  var resp = UrlFetchApp.fetch(VPS_URL, {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify({
      vk: VPS_KEY,
      m: req.m || "GET", u: req.u,
      h: _filterHeaders(req.h),
      b: req.b || "", ct: req.ct || "",
      r: req.r !== false,
    }),
    muteHttpExceptions: true,
    validateHttpsCertificates: true,
  });
  return _json(JSON.parse(resp.getContentText()));
}

// ── batch — کل batch یکجا به VPS، VPS موازی پردازش می‌کنه ──────────────────

function _doBatch(items) {
  var valid = [];
  var errorMap = {};

  for (var i = 0; i < items.length; i++) {
    if (!_validUrl(items[i].u)) { errorMap[i] = "bad url"; continue; }
    valid.push({ _i: i, item: items[i] });
  }

  if (valid.length === 0) {
    var out = [];
    for (var i = 0; i < items.length; i++) out.push({ e: errorMap[i] || "bad url" });
    return _json({ q: out });
  }

  // fetchAll — همه موازی از اپس اسکریپت به VPS
  var fetchArgs = valid.map(function(v) {
    return {
      url: VPS_URL,
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify({
        vk: VPS_KEY,
        m: v.item.m || "GET", u: v.item.u,
        h: _filterHeaders(v.item.h),
        b: v.item.b || "", ct: v.item.ct || "",
        r: v.item.r !== false,
      }),
      muteHttpExceptions: true,
      validateHttpsCertificates: true,
    };
  });

  var responses = UrlFetchApp.fetchAll(fetchArgs);

  var results = new Array(items.length);
  for (var i = 0; i < items.length; i++) {
    if (errorMap.hasOwnProperty(i)) { results[i] = { e: errorMap[i] }; continue; }
  }
  var rIdx = 0;
  for (var vi = 0; vi < valid.length; vi++) {
    try { results[valid[vi]._i] = JSON.parse(responses[rIdx].getContentText()); }
    catch (e) { results[valid[vi]._i] = { e: "parse error" }; }
    rIdx++;
  }

  return _json({ q: results });
}

// ── helpers ──────────────────────────────────────────────────────────────────

function _validUrl(u) {
  return u && typeof u === "string" && /^https?:\/\//i.test(u);
}

function _filterHeaders(h) {
  if (!h || typeof h !== "object") return {};
  var out = {};
  for (var k in h) {
    if (h.hasOwnProperty(k) && !SKIP_HEADERS[k.toLowerCase()])
      out[k] = h[k];
  }
  return out;
}

function _json(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function doGet(e) {
  return HtmlService.createHtmlOutput(
    "<!DOCTYPE html><html><head><title>Relay</title></head>" +
    "<body style='font-family:sans-serif;max-width:600px;margin:40px auto'>" +
    "<h1>OK</h1><p>Relay is running.</p></body></html>"
  );
}
