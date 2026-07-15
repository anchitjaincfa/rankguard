const trackingKeys = new Set(["fbclid", "gclid", "gbraid", "mc_cid", "mc_eid", "msclkid", "wbraid"]);
const sampleOld = `https://example.com/products/red-running-shoes
https://example.com/products/blue-running-shoes
https://example.com/blog/how-to-size-running-shoes
https://example.com/pages/shipping-policy
https://example.com/products/discontinued-green-hat`;
const sampleNew = `https://new.example.com/shop/red-running-shoes
https://new.example.com/shop/blue-running-shoes
https://new.example.com/guides/running-shoe-size-guide
https://new.example.com/policies/shipping-policy
https://new.example.com/collections/running`;

const state = {
  result: null,
  csv: "",
  json: "",
  report: "",
  rules: "",
};

const el = {
  oldInput: document.querySelector("#oldInput"),
  newInput: document.querySelector("#newInput"),
  oldFile: document.querySelector("#oldFile"),
  newFile: document.querySelector("#newFile"),
  loadSample: document.querySelector("#loadSample"),
  minScore: document.querySelector("#minScore"),
  scoreValue: document.querySelector("#scoreValue"),
  rulesFormat: document.querySelector("#rulesFormat"),
  generate: document.querySelector("#generate"),
  copyCsv: document.querySelector("#copyCsv"),
  downloadCsv: document.querySelector("#downloadCsv"),
  downloadJson: document.querySelector("#downloadJson"),
  downloadReport: document.querySelector("#downloadReport"),
  downloadRules: document.querySelector("#downloadRules"),
  mappedMetric: document.querySelector("#mappedMetric"),
  unmatchedMetric: document.querySelector("#unmatchedMetric"),
  lowMetric: document.querySelector("#lowMetric"),
  riskMetric: document.querySelector("#riskMetric"),
  issueCount: document.querySelector("#issueCount"),
  mappingCount: document.querySelector("#mappingCount"),
  issues: document.querySelector("#issues"),
  mappingRows: document.querySelector("#mappingRows"),
  issueTemplate: document.querySelector("#issueTemplate"),
};

el.minScore.addEventListener("input", () => {
  el.scoreValue.value = Number(el.minScore.value).toFixed(2);
});
el.loadSample.addEventListener("click", () => {
  el.oldInput.value = sampleOld;
  el.newInput.value = sampleNew;
  runPlan();
});
el.generate.addEventListener("click", runPlan);
el.rulesFormat.addEventListener("change", () => {
  if (state.result) {
    state.rules = renderRules(state.result.candidates, el.rulesFormat.value);
  }
});
el.oldFile.addEventListener("change", () => readFileInto(el.oldFile, el.oldInput));
el.newFile.addEventListener("change", () => readFileInto(el.newFile, el.newInput));
el.copyCsv.addEventListener("click", copyCsv);
el.downloadCsv.addEventListener("click", () => download("rankguard-redirects.csv", state.csv, "text/csv"));
el.downloadJson.addEventListener("click", () => download("rankguard-report.json", state.json, "application/json"));
el.downloadReport.addEventListener("click", () => download("rankguard-report.html", state.report, "text/html"));
el.downloadRules.addEventListener("click", () => {
  const ext = el.rulesFormat.value === "apache" ? "htaccess" : "conf";
  download(`rankguard-${el.rulesFormat.value}-redirects.${ext}`, state.rules, "text/plain");
});

function readFileInto(input, textarea) {
  const file = input.files && input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    textarea.value = String(reader.result || "");
  };
  reader.readAsText(file);
}

function runPlan() {
  try {
    const oldRecords = parseInventory(el.oldInput.value, "old input");
    const newRecords = parseInventory(el.newInput.value, "new input");
    if (!oldRecords.length || !newRecords.length) {
      throw new Error("Both inventories need at least one URL.");
    }
    const result = generateRedirectMap(oldRecords, newRecords, Number(el.minScore.value));
    const issues = mappingIssues(result);
    state.result = result;
    state.csv = renderCsv(result.candidates);
    state.json = JSON.stringify({ summary: result.summary, issues, result }, null, 2);
    state.report = renderReport(result, issues);
    state.rules = renderRules(result.candidates, el.rulesFormat.value);
    renderUi(result, issues);
    setDownloads(true);
  } catch (error) {
    renderError(error instanceof Error ? error.message : String(error));
    setDownloads(false);
  }
}

function parseInventory(text, source) {
  const clean = text.trim();
  if (!clean) return [];
  if (clean.startsWith("<") || clean.includes("<urlset") || clean.includes("<sitemapindex")) {
    return parseXml(clean, source);
  }
  const delimiter = detectDelimiter(clean);
  if (delimiter) {
    return parseDelimited(clean, source, delimiter);
  }
  return dedupe(clean.split(/\r?\n/).map((line) => line.trim()).filter((line) => line && !line.startsWith("#")), source);
}

function parseXml(text, source) {
  const doc = new DOMParser().parseFromString(text, "application/xml");
  if (doc.querySelector("parsererror")) {
    throw new Error(`Could not parse XML in ${source}.`);
  }
  const urls = Array.from(doc.querySelectorAll("url > loc, sitemap > loc"))
    .map((node) => node.textContent.trim())
    .filter(Boolean);
  return dedupe(urls, source);
}

function parseDelimited(text, source, delimiter) {
  const rows = parseRows(text, delimiter).filter((row) => row.some(Boolean));
  if (!rows.length) return [];
  const headers = rows[0].map(normalizeHeader);
  const urlIndex = findHeader(headers, ["url", "address", "loc", "location", "oldurl", "newurl", "sourceurl"]);
  if (urlIndex < 0) {
    throw new Error(`Could not find a URL column in ${source}.`);
  }
  const titleIndex = findHeader(headers, ["title", "pagetitle", "h1", "name"]);
  const records = [];
  for (const row of rows.slice(1)) {
    const url = (row[urlIndex] || "").trim();
    if (!url || url.startsWith("#")) continue;
    records.push({ url, title: titleIndex >= 0 ? (row[titleIndex] || "").trim() : "", source });
  }
  return dedupeRecords(records);
}

function detectDelimiter(text) {
  const first = text.split(/\r?\n/).find((line) => line.trim() && !line.trim().startsWith("#")) || "";
  if (!first) return "";
  const candidates = [",", "\t", ";"];
  const best = candidates.map((delimiter) => [delimiter, count(first, delimiter)]).sort((a, b) => b[1] - a[1])[0];
  if (!best || best[1] < 1) return "";
  return parseRows(first, best[0])[0].length > 1 ? best[0] : "";
}

function parseRows(text, delimiter) {
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    const next = text[i + 1];
    if (char === '"' && quoted && next === '"') {
      cell += '"';
      i += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === delimiter && !quoted) {
      row.push(cell);
      cell = "";
    } else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && next === "\n") i += 1;
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += char;
    }
  }
  row.push(cell);
  rows.push(row);
  return rows;
}

function dedupe(urls, source) {
  return dedupeRecords(urls.map((url) => ({ url, title: "", source })));
}

function dedupeRecords(records) {
  const seen = new Set();
  const unique = [];
  for (const record of records) {
    if (seen.has(record.url)) continue;
    seen.add(record.url);
    unique.push(record);
  }
  return unique;
}

function generateRedirectMap(oldRecords, newRecords, minScore) {
  const candidates = [];
  const unmatchedOld = [];
  for (const oldRecord of oldRecords) {
    const scored = newRecords
      .map((newRecord, index) => {
        const pair = scorePair(oldRecord, newRecord);
        return { ...pair, newRecord, index };
      })
      .sort((a, b) => b.score - a.score || a.index - b.index);
    const best = scored[0];
    if (!best || best.score < minScore) {
      unmatchedOld.push(oldRecord);
      continue;
    }
    candidates.push({
      oldUrl: oldRecord.url,
      newUrl: best.newRecord.url,
      score: round(best.score),
      confidence: confidence(best.score),
      reason: best.reason,
      alternatives: scored.slice(1, 4).map((item) => [item.newRecord.url, round(item.score)]),
    });
  }
  const mapped = new Set(candidates.map((candidate) => candidate.newUrl));
  const orphanNew = newRecords.filter((record) => !mapped.has(record.url));
  const conflicts = findConflicts(candidates);
  const summary = summarize(candidates, unmatchedOld, orphanNew, conflicts, minScore);
  return { candidates, unmatchedOld, orphanNew, conflicts, summary };
}

function scorePair(oldRecord, newRecord) {
  const oldPath = normalizedPath(oldRecord.url);
  const newPath = normalizedPath(newRecord.url);
  if (oldPath === newPath) {
    return { score: 1, reason: "same normalized path" };
  }
  const oldTokens = urlTokens(oldRecord.url);
  const newTokens = urlTokens(newRecord.url);
  const shared = intersection(oldTokens, newTokens);
  const tokenScore = jaccard(oldTokens, newTokens);
  const oldTail = tailSlug(oldRecord.url);
  const newTail = tailSlug(newRecord.url);
  const tailScore = oldTail && oldTail === newTail ? 1 : 0;
  const tailTokenScore = jaccard(segmentTokens(oldTail), segmentTokens(newTail));
  const sectionScore = sectionKey(oldRecord.url) && sectionKey(oldRecord.url) === sectionKey(newRecord.url) ? 1 : 0;
  const titleScore = jaccard(titleTokens(oldRecord.title || ""), titleTokens(newRecord.title || ""));
  const numericBonus = shared.some((token) => /\d/.test(token)) ? 0.08 : 0;
  let score = editSimilarity(oldPath, newPath) * 0.25
    + tokenScore * 0.22
    + tailTokenScore * 0.18
    + tailScore * 0.22
    + sectionScore * 0.07
    + titleScore * 0.06
    + numericBonus;
  if (tailScore && segmentTokens(oldTail).length >= 2 && tokenScore >= 0.45) score = Math.max(score, 0.88);
  else if (tailScore && tokenScore >= 0.5) score = Math.max(score, 0.78);
  else if (oldTail && newTail && tailTokenScore === 1 && tokenScore >= 0.5) score = Math.max(score, 0.74);
  score = Math.min(score, 0.99);
  const reasons = [];
  if (tailScore) reasons.push("same slug");
  else if (tailTokenScore) reasons.push("similar slug");
  if (sectionScore) reasons.push("same section");
  if (shared.length) reasons.push(`shared tokens: ${shared.sort().slice(0, 5).join(", ")}`);
  if (titleScore) reasons.push("similar title");
  return { score, reason: reasons.length ? reasons.join("; ") : "path similarity" };
}

function normalizeUrl(value, keepQuery = false) {
  const url = new URL(value.includes("://") ? value.trim() : `https://${value.trim().replace(/^\/+/, "")}`);
  url.protocol = url.protocol.toLowerCase();
  url.hostname = url.hostname.toLowerCase().replace(/\.$/, "");
  let path = decodeURIComponent(url.pathname || "/").replace(/\\/g, "/").replace(/\/+/g, "/");
  path = path.replace(/\/$/, "") || "/";
  url.pathname = path;
  if (!keepQuery) {
    url.search = "";
  } else {
    for (const key of Array.from(url.searchParams.keys())) {
      const lower = key.toLowerCase();
      if (lower.startsWith("utm_") || trackingKeys.has(lower)) {
        url.searchParams.delete(key);
      }
    }
  }
  url.hash = "";
  return url.toString().replace(/\/$/, path === "/" ? "/" : "");
}

function normalizedPath(url) {
  return new URL(normalizeUrl(url)).pathname.toLowerCase().replace(/\/$/, "") || "/";
}

function pathSegments(url) {
  return normalizedPath(url).split("/").filter(Boolean);
}

function contentSegments(url) {
  const segments = pathSegments(url);
  return segments[0] && /^[a-z]{2}(-[a-z]{2})?$/i.test(segments[0]) ? segments.slice(1) : segments;
}

function sectionKey(url) {
  return contentSegments(url)[0] || "";
}

function tailSlug(url) {
  const segments = contentSegments(url);
  return segments[segments.length - 1] || "";
}

function urlTokens(url) {
  return new Set(contentSegments(url).flatMap((segment) => Array.from(segmentTokens(segment))));
}

function segmentTokens(segment) {
  const matches = decodeURIComponent(segment || "").toLowerCase().match(/[a-z0-9]+/g) || [];
  return new Set(matches.filter((token) => token.length > 1).map(stemLightly));
}

function titleTokens(title) {
  const matches = (title || "").toLowerCase().match(/[a-z0-9]+/g) || [];
  return new Set(matches.filter((token) => token.length > 2).map(stemLightly));
}

function stemLightly(token) {
  if (token.length > 4 && token.endsWith("ies")) return `${token.slice(0, -3)}y`;
  if (token.length > 4 && token.endsWith("s")) return token.slice(0, -1);
  return token;
}

function editSimilarity(a, b) {
  if (a === b) return 1;
  if (!a.length || !b.length) return 0;
  const previous = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i += 1) {
    let diagonal = previous[0];
    previous[0] = i;
    for (let j = 1; j <= b.length; j += 1) {
      const temp = previous[j];
      previous[j] = Math.min(
        previous[j] + 1,
        previous[j - 1] + 1,
        diagonal + (a[i - 1] === b[j - 1] ? 0 : 1)
      );
      diagonal = temp;
    }
  }
  return 1 - previous[b.length] / Math.max(a.length, b.length);
}

function mappingIssues(result) {
  const issues = [];
  for (const record of result.unmatchedOld) {
    issues.push({ severity: "critical", code: "unmatched_old_url", url: record.url, message: "No redirect target above threshold." });
  }
  for (const candidate of result.candidates) {
    if (candidate.confidence === "low") {
      issues.push({ severity: "warning", code: "low_confidence_mapping", url: candidate.oldUrl, message: `Review target: ${candidate.newUrl}` });
    }
  }
  for (const [target, sources] of Object.entries(result.conflicts)) {
    issues.push({ severity: "warning", code: "many_to_one_redirect", url: target, message: `${sources.length} old URLs map here.` });
  }
  for (const record of result.orphanNew.slice(0, 50)) {
    issues.push({ severity: "notice", code: "orphan_new_url", url: record.url, message: "No old URL maps to this page." });
  }
  return issues;
}

function summarize(candidates, unmatchedOld, orphanNew, conflicts, minScore) {
  const counts = { high: 0, medium: 0, low: 0 };
  for (const candidate of candidates) counts[candidate.confidence] += 1;
  return {
    mapped: candidates.length,
    unmatchedOld: unmatchedOld.length,
    orphanNew: orphanNew.length,
    conflicts: Object.keys(conflicts).length,
    highConfidence: counts.high,
    mediumConfidence: counts.medium,
    lowConfidence: counts.low,
    minScore,
  };
}

function findConflicts(candidates) {
  const targets = {};
  for (const candidate of candidates) {
    targets[candidate.newUrl] ||= [];
    targets[candidate.newUrl].push(candidate.oldUrl);
  }
  return Object.fromEntries(Object.entries(targets).filter(([, sources]) => sources.length > 3));
}

function confidence(score) {
  if (score >= 0.86) return "high";
  if (score >= 0.7) return "medium";
  return "low";
}

function renderUi(result, issues) {
  const summary = result.summary;
  el.mappedMetric.textContent = summary.mapped;
  el.unmatchedMetric.textContent = summary.unmatchedOld;
  el.lowMetric.textContent = summary.lowConfidence;
  el.riskMetric.textContent = riskLabel(summary);
  el.issueCount.textContent = issues.length;
  el.mappingCount.textContent = result.candidates.length;

  el.issues.innerHTML = "";
  if (!issues.length) {
    el.issues.innerHTML = '<div class="empty">No priority issues.</div>';
  } else {
    for (const issue of issues) {
      const node = el.issueTemplate.content.firstElementChild.cloneNode(true);
      node.classList.add(issue.severity);
      node.querySelector("strong").textContent = issue.code;
      node.querySelector("span").textContent = issue.message;
      node.querySelector("code").textContent = issue.url;
      el.issues.append(node);
    }
  }

  if (!result.candidates.length) {
    el.mappingRows.innerHTML = '<tr><td colspan="5" class="empty">No mappings generated.</td></tr>';
    return;
  }
  el.mappingRows.innerHTML = result.candidates.map((candidate) => `
    <tr>
      <td><code>${escapeHtml(candidate.oldUrl)}</code></td>
      <td><code>${escapeHtml(candidate.newUrl)}</code></td>
      <td>${candidate.score.toFixed(3)}</td>
      <td class="confidence-${candidate.confidence}">${candidate.confidence}</td>
      <td>${escapeHtml(candidate.reason)}</td>
    </tr>
  `).join("");
}

function renderError(message) {
  el.mappedMetric.textContent = "0";
  el.unmatchedMetric.textContent = "0";
  el.lowMetric.textContent = "0";
  el.riskMetric.textContent = "Error";
  el.issueCount.textContent = "1";
  el.mappingCount.textContent = "0";
  el.issues.innerHTML = `<div class="issue critical"><strong>input_error</strong><span>${escapeHtml(message)}</span><code>RankGuard</code></div>`;
  el.mappingRows.innerHTML = '<tr><td colspan="5" class="empty">No mappings generated.</td></tr>';
}

function renderCsv(candidates) {
  const rows = [["old_url", "new_url", "score", "confidence", "reason", "alternatives"]];
  for (const candidate of candidates) {
    rows.push([
      candidate.oldUrl,
      candidate.newUrl,
      candidate.score.toFixed(3),
      candidate.confidence,
      candidate.reason,
      JSON.stringify(candidate.alternatives),
    ]);
  }
  return rows.map((row) => row.map(csvCell).join(",")).join("\n");
}

function renderRules(candidates, format) {
  const lines = ["# Generated by RankGuard. Review before deploying."];
  if (format === "apache") {
    lines.push("RewriteEngine On");
    for (const candidate of candidates) {
      const path = new URL(normalizeUrl(candidate.oldUrl)).pathname.replace(/^\/+/, "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      lines.push(`RewriteRule ^${path}$ ${normalizeUrl(candidate.newUrl, true)} [R=301,L]`);
    }
  } else {
    for (const candidate of candidates) {
      lines.push(`location = ${new URL(normalizeUrl(candidate.oldUrl)).pathname} { return 301 ${normalizeUrl(candidate.newUrl, true)}; }`);
    }
  }
  return `${lines.join("\n")}\n`;
}

function renderReport(result, issues) {
  const rows = result.candidates.map((candidate) => `
    <tr><td>${escapeHtml(candidate.oldUrl)}</td><td>${escapeHtml(candidate.newUrl)}</td><td>${candidate.score.toFixed(3)}</td><td>${candidate.confidence}</td><td>${escapeHtml(candidate.reason)}</td></tr>
  `).join("");
  const issueRows = issues.map((issue) => `
    <tr><td>${issue.severity}</td><td>${escapeHtml(issue.code)}</td><td>${escapeHtml(issue.url)}</td><td>${escapeHtml(issue.message)}</td></tr>
  `).join("");
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>RankGuard Report</title>
  <style>body{font-family:system-ui,sans-serif;margin:32px;color:#1e2428}table{border-collapse:collapse;width:100%;margin:20px 0}td,th{border:1px solid #d8ddd5;padding:8px;text-align:left}th{background:#f4f5f2}.metrics{display:flex;gap:12px}.metrics div{border:1px solid #d8ddd5;padding:12px;border-radius:8px}</style>
  </head><body><h1>RankGuard Migration Report</h1><section class="metrics"><div>Mapped<br><strong>${result.summary.mapped}</strong></div><div>Unmatched<br><strong>${result.summary.unmatchedOld}</strong></div><div>Low Confidence<br><strong>${result.summary.lowConfidence}</strong></div></section>
  <h2>Issues</h2><table><thead><tr><th>Severity</th><th>Code</th><th>URL</th><th>Message</th></tr></thead><tbody>${issueRows || '<tr><td colspan="4">No issues.</td></tr>'}</tbody></table>
  <h2>Mappings</h2><table><thead><tr><th>Old URL</th><th>New URL</th><th>Score</th><th>Confidence</th><th>Reason</th></tr></thead><tbody>${rows || '<tr><td colspan="5">No mappings.</td></tr>'}</tbody></table></body></html>`;
}

function setDownloads(enabled) {
  for (const button of [el.copyCsv, el.downloadCsv, el.downloadJson, el.downloadReport, el.downloadRules]) {
    button.disabled = !enabled;
  }
}

async function copyCsv() {
  await navigator.clipboard.writeText(state.csv);
  const original = el.copyCsv.textContent;
  el.copyCsv.textContent = "Copied";
  window.setTimeout(() => {
    el.copyCsv.textContent = original;
  }, 1200);
}

function download(filename, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function riskLabel(summary) {
  if (summary.unmatchedOld > 0) return "High";
  if (summary.lowConfidence > 0 || summary.conflicts > 0) return "Medium";
  return "Low";
}

function normalizeHeader(value) {
  return value.replace(/^\ufeff/, "").toLowerCase().replace(/[^a-z0-9]/g, "");
}

function findHeader(headers, names) {
  return headers.findIndex((header) => names.includes(header));
}

function count(text, needle) {
  return text.split(needle).length - 1;
}

function intersection(left, right) {
  return Array.from(left).filter((item) => right.has(item));
}

function jaccard(left, right) {
  const union = new Set([...left, ...right]);
  if (!union.size) return 0;
  return intersection(left, right).length / union.size;
}

function round(value) {
  return Math.round(value * 1000) / 1000;
}

function csvCell(value) {
  const text = String(value ?? "");
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

el.oldInput.value = sampleOld;
el.newInput.value = sampleNew;
runPlan();
