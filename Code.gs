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

const AUTH_KEY = "CHANGE_ME_TO_A_STRONG_SECRET";   // key between client and apps script
const VPS_URL  = "http://YOUR_VPS_IP:8080/relay";   // vps ip address
const VPS_KEY  = "CHANGE_ME_TO_A_STRONG_SECRET";   // key between apps script and vps

const SKIP_HEADERS = {
  host: 1, connection: 1, "content-length": 1,
  "transfer-encoding": 1, "proxy-connection": 1,
  "proxy-authorization": 1, "priority": 1, te: 1,
};

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


function _doSingle(req) {
  if (!_validUrl(req.u)) return _json({ e: "bad url" });

  var resp = UrlFetchApp.fetch(VPS_URL, {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify({
      vk: VPS_KEY,
      m:  req.m  || "GET",
      u:  req.u,
      h:  _filterHeaders(req.h),
      b:  req.b  || "",
      ct: req.ct || "",
      r:  req.r !== false,
    }),
    muteHttpExceptions: true,
    validateHttpsCertificates: true,
  });

  return _json(JSON.parse(resp.getContentText()));
}

function _doBatch(items) {
  var fetchArgs = [];
  var errorMap  = {};

  for (var i = 0; i < items.length; i++) {
    var item = items[i];
    if (!_validUrl(item.u)) {
      errorMap[i] = "bad url";
      continue;
    }
    fetchArgs.push({
      _i: i,
      url: VPS_URL,
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify({
        vk: VPS_KEY,
        m:  item.m  || "GET",
        u:  item.u,
        h:  _filterHeaders(item.h),
        b:  item.b  || "",
        ct: item.ct || "",
        r:  item.r !== false,
      }),
      muteHttpExceptions: true,
      validateHttpsCertificates: true,
    });
  }

  var responses = fetchArgs.length > 0
    ? UrlFetchApp.fetchAll(fetchArgs)
    : [];

  var results = [];
  var rIdx = 0;
  for (var i = 0; i < items.length; i++) {
    if (errorMap.hasOwnProperty(i)) {
      results.push({ e: errorMap[i] });
    } else {
      try {
        results.push(JSON.parse(responses[rIdx].getContentText()));
      } catch (err) {
        results.push({ e: "parse error" });
      }
      rIdx++;
    }
  }

  return _json({ q: results });
}


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
