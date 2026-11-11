// check_export_browser.mjs - load the HTML export in a browser, offline, and assert its behaviour.
//
// Usage:
//   node check_export_browser.mjs FILE --shots DIR [--puppeteer-config FILE]
//
// Chrome comes from PUPPETEER_EXECUTABLE_PATH. --puppeteer-config is a JSON file
// with an "args" list, for a runner that needs --no-sandbox.
// Prints one pass or fail line per assertion, then the screenshot paths.
// Exit 0 if every assertion passed, 1 if any failed, 2 on bad input.
// Assertions are on state (computed display, aria-pressed, geometry, counts),
// never on a word appearing on the page.

import { createHash } from "node:crypto";
import { mkdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import puppeteer from "puppeteer";

const argv = process.argv.slice(2);
function opt(name) {
  const i = argv.indexOf(name);
  return i >= 0 ? argv[i + 1] : undefined;
}
const file = argv.find((a, i) => !a.startsWith("--") && !(i > 0 && argv[i - 1].startsWith("--")));
const shots = opt("--shots");
if (!file || !shots) {
  console.error("usage: node check_export_browser.mjs FILE --shots DIR [--puppeteer-config FILE]");
  process.exit(2);
}
const extraArgs = opt("--puppeteer-config")
  ? JSON.parse(readFileSync(opt("--puppeteer-config"), "utf8")).args ?? []
  : [];
mkdirSync(shots, { recursive: true });

const PROFILES = ["uaf", "dodaf202", "naf4"];
// Hard-coded counts, and how they are made up. Change them with the thing they count.
//   29 views, plus the front page and the declarations page                  = 31
//   30 capability pages: one per capability in model/openddil.sysml CapabilityTaxonomy
//   50 decision pages: one per decisions/ADR-*.md (49) plus the roadmap note (1)
const BASE_PAGES = 31;
const CAPABILITY_PAGES = 30;
const DECISION_PAGES = 50;
const TOTAL_PAGES = BASE_PAGES + CAPABILITY_PAGES + DECISION_PAGES;
let failed = 0;
let passed = 0;
function check(ok, what, detail = "") {
  if (ok) passed++;
  else failed++;
  console.log(`${ok ? "pass" : "FAIL"}: ${what}${!ok && detail ? ` (${detail})` : ""}`);
}

const browser = await puppeteer.launch({
  headless: true,
  executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || undefined,
  args: extraArgs,
});
const written = [];
try {
  const page = await browser.newPage();
  const badRequests = [];
  const consoleErrors = [];
  page.on("request", (r) => {
    const u = r.url();
    if (!u.startsWith("file:") && !u.startsWith("data:")) badRequests.push(u);
  });
  page.on("console", (m) => {
    if (m.type() === "error") consoleErrors.push(m.text());
  });
  page.on("pageerror", (e) => consoleErrors.push(String(e)));
  await page.setOfflineMode(true);
  await page.setViewport({ width: 1280, height: 900 });
  const url = pathToFileURL(resolve(file)).href;
  await page.goto(url, { waitUntil: "load" });
  // Record the state of the details at the moment printing starts, after the page's own handler ran.
  await page.evaluate(() => {
    window.__printOpen = [];
    window.addEventListener("beforeprint", () => {
      window.__printOpen = [...document.querySelectorAll("details")].map((d) => d.open);
    });
  });

  const display = (sel) =>
    page.evaluate((s) => {
      const e = document.querySelector(s);
      return e ? getComputedStyle(e).display : "missing";
    }, sel);
  const go = async (hash) => {
    await page.evaluate((h) => { location.hash = h; }, hash);
    await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => r())));
  };
  const click = async (profile) => {
    await page.click(`[data-profile-btn="${profile}"]`);
  };
  const pressed = () =>
    page.evaluate(() =>
      Object.fromEntries([...document.querySelectorAll("[data-profile-btn]")]
        .map((b) => [b.getAttribute("data-profile-btn"), b.getAttribute("aria-pressed")])));
  const views = await page.evaluate(() => [...document.querySelectorAll("section[data-view]")].map((s) => s.dataset.view));
  const shot = async (name) => {
    const p = resolve(shots, name);
    await page.screenshot({ path: p });
    written.push(p);
  };
  const body = (profile) =>
    page.evaluate(() =>
      Object.fromEntries([...document.querySelectorAll("section[data-view]")].map((s) => {
        const c = s.cloneNode(true);
        c.querySelectorAll(".pname,[data-profile-only]").forEach((e) => e.remove());
        return [s.dataset.view, c.textContent];
      })));
  const hash = (t) => createHash("sha256").update(t).digest("hex");

  // --- front, UAF ---
  check(views.length === 29, "29 view sections", String(views.length));
  check((await display("#front")) === "block", "front is visible on load");
  let pr = await pressed();
  check(pr.uaf === "true" && pr.dodaf202 === "false" && pr.naf4 === "false", "UAF button is pressed on load", JSON.stringify(pr));
  const filled = await page.evaluate(() => document.querySelectorAll("#grid-uaf .filled").length);
  const links = await page.evaluate(() => document.querySelectorAll("#grid-uaf a").length);
  check(filled === links && links === views.length, "UAF grid: filled cells equal links equal views", `${filled} ${links} ${views.length}`);
  const emptyLinked = await page.evaluate(() => document.querySelectorAll("#grid-uaf .empty a").length);
  check(emptyLinked === 0, "UAF grid: empty cells hold no link");
  await shot("front-uaf.png");
  await page.click('#grid-uaf a[href="#view-Rs-Cn"]');
  check((await display("#view-Rs-Cn")) === "block" && (await display("#front")) === "none",
    "clicking a filled cell shows that view and hides the front");
  const provCount = await page.evaluate(() => document.querySelectorAll("[data-provenance]").length);
  check(provCount === TOTAL_PAGES, `a provenance block on every page (${TOTAL_PAGES}: ${BASE_PAGES} + ${CAPABILITY_PAGES} capability + ${DECISION_PAGES} decision)`, String(provCount));
  const kinds = await page.evaluate(() => [document.querySelectorAll("section.capability").length, document.querySelectorAll("section.decision").length]);
  check(kinds[0] === CAPABILITY_PAGES && kinds[1] === DECISION_PAGES, `${CAPABILITY_PAGES} capability pages and ${DECISION_PAGES} decision pages`, kinds.join(" "));

  // --- capability and decision pages ---
  await go("#front");
  const navs = await page.evaluate(() => [document.querySelectorAll("nav.capabilities a").length, document.querySelectorAll("nav.decisions a").length]);
  check(navs[0] === CAPABILITY_PAGES && navs[1] === DECISION_PAGES, "front: a link per capability page and per decision page", navs.join(" "));
  await go("#view-St-Tx");
  const capHref = await page.evaluate(() => { const a = document.querySelector('#view-St-Tx a[href^="#cap-"]'); return a ? a.getAttribute("href") : null; });
  check(capHref !== null, "CV-2: a capability name is a link", String(capHref));
  if (capHref) {
    await page.click(`#view-St-Tx a[href="${capHref}"]`);
    check((await display(capHref)) === "block" && (await display("#view-St-Tx")) === "none" && (await display("#front")) === "none",
      "CV-2: clicking a capability name shows its page", capHref);
  }
  const decHref = await page.evaluate(() => {
    for (const sec of document.querySelectorAll("section.capability")) {
      const a = sec.querySelector('a[href^="#adr-"]');
      if (a) return [sec.id, a.getAttribute("href")];
    }
    return null;
  });
  check(decHref !== null, "a capability page links a decision section", JSON.stringify(decHref));
  if (decHref) {
    await go("#" + decHref[0]);
    await page.click(`#${decHref[0]} a[href="${decHref[1]}"]`);
    const landed = await page.evaluate((h) => {
      const e = document.getElementById(h.slice(1));
      if (!e) return null;
      const r = e.getBoundingClientRect();
      return [location.hash === h, /^H[2-4]$/.test(e.tagName), r.height > 0, getComputedStyle(e.closest(".page")).display];
    }, decHref[1]);
    check(landed !== null && landed[0] && landed[1] && landed[2] && landed[3] === "block",
      "a decision link on a capability page lands on the section heading, shown", JSON.stringify(landed));
  }
  const stamps = await page.evaluate(() => [...document.querySelectorAll("section.decision")].map((s) => s.id));
  const unstamped = [];
  for (const id of stamps) {
    await go("#" + id);
    const t = await page.evaluate((i) => {
      const e = document.querySelector(`#${i} [data-stamp]`);
      return e && getComputedStyle(e).display !== "none" && e.getBoundingClientRect().height > 0 ? e.textContent : "";
    }, id);
    if (!/^Commit [0-9a-f]{7,}, \d{4}-\d{2}-\d{2}: decisions\/.+\.md/.test(t)) unstamped.push(id);
  }
  check(stamps.length === DECISION_PAGES && unstamped.length === 0, "every decision page shows its stamp", unstamped.slice(0, 3).join(","));
  await go("#view-Rs-Cn");

  const uafBody = await body("uaf");
  const uafH1 = await page.evaluate(() => document.querySelector("#view-Rs-Cn h1").textContent);
  const uafTh = await page.evaluate(() => [...document.querySelectorAll("#view-Rs-Cn th.pname")].map((e) => e.textContent));
  const uafTitle = await page.title();

  // --- the other profiles ---
  for (const p of PROFILES.slice(1)) {
    await go("#front");
    await click(p);
    pr = await pressed();
    check(Object.entries(pr).every(([k, v]) => v === (k === p ? "true" : "false")), `${p}: pressed state moved`, JSON.stringify(pr));
    const shown = await Promise.all(PROFILES.map((q) => display(`#grid-${q}`)));
    check(PROFILES.every((q, i) => (shown[i] !== "none") === (q === p)), `${p}: only its grid is displayed`, shown.join(","));
    check((await page.evaluate(() => document.documentElement.getAttribute("data-profile"))) === p, `${p}: data-profile set`);
    check((await page.title()) !== uafTitle, `${p}: document title changed`);
    const filledP = await page.evaluate((q) => document.querySelectorAll(`#grid-${q} .filled`).length, p);
    const linksP = await page.evaluate((q) => document.querySelectorAll(`#grid-${q} a`).length, p);
    check(filledP > 0 && linksP >= filledP, `${p}: grid has filled cells with links`, `${filledP} ${linksP}`);
    const emptyP = await page.evaluate((q) => document.querySelectorAll(`#grid-${q} .empty a`).length, p);
    check(emptyP === 0, `${p}: empty cells hold no link`);
    await shot(`front-${p}.png`);
    await go("#view-Rs-Cn");
    const h1 = await page.evaluate(() => document.querySelector("#view-Rs-Cn h1").textContent);
    check(h1 !== uafH1, `${p}: a view H1 changed`, h1);
    const th = await page.evaluate(() => [...document.querySelectorAll("#view-Rs-Cn th.pname")].map((e) => e.textContent));
    check(th.length === uafTh.length && th.length > 0 && th.join("|") !== uafTh.join("|"), `${p}: a data-exchange th changed`, th.join("|"));
    const b = await body(p);
    const diff = views.filter((v) => hash(b[v]) !== hash(uafBody[v]));
    check(diff.length === 0, `${p}: text outside names is the same as UAF in every view`, diff.join(","));
    const only = await page.evaluate((q) => {
      const e = document.querySelector(`#view-Sc-Sr .profile-only[data-for="${q}"]`);
      return e ? getComputedStyle(e).display : "missing";
    }, p);
    check(only === "block", `${p}: a view with no export shows its reason`, only);
  }
  await go("#front");
  await click("uaf");
  check((await page.evaluate(() => document.querySelector("#view-Rs-Cn h1").textContent)) === uafH1, "back to UAF: H1 restored");

  // --- diagrams ---
  let svgs = 0;
  let zero = [];
  for (const v of views) {
    await go(`#view-${v}`);
    const boxes = await page.evaluate((id) =>
      [...document.querySelectorAll(`#view-${id} figure.diagram svg`)].map((s) => {
        const r = s.getBoundingClientRect();
        return r.width > 0 && r.height > 0;
      }), v);
    svgs += boxes.length;
    zero = zero.concat(boxes.map((ok, i) => (ok ? null : `${v}#${i + 1}`)).filter(Boolean));
  }
  check(svgs > 0 && zero.length === 0, `every SVG (${svgs}) has a non-zero box when its page is shown`, zero.join(","));
  await go("#view-Op-Tx");
  await shot("view-diagram-Op-Tx.png");

  // --- exceptions ---
  await go("#view-Rs-Cn");
  const d0 = await page.evaluate(() => document.querySelector("details.exceptions").open);
  check(d0 === false, "details.exceptions is closed by default");
  await page.click("details.exceptions summary");
  const d1 = await page.evaluate(() => {
    const d = document.querySelector("details.exceptions");
    return [d.open, d.querySelector("table").getBoundingClientRect().height];
  });
  check(d1[0] === true && d1[1] > 0, "details.exceptions opens on click and its table has height", String(d1));
  await page.click("details.exceptions summary");
  await shot("view-Rs-Cn.png");

  // --- search ---
  await go("#front");
  await page.click("#q");
  await page.keyboard.type("qzxqzxqzx");
  let n = await page.evaluate(() => document.querySelectorAll("#results li").length);
  check(n === 0, "search: a nonsense term gives 0 results", String(n));
  await page.keyboard.press("Escape");
  check((await page.evaluate(() => document.getElementById("q").value)) === "", "search: Esc clears the box");
  await page.keyboard.type("Which resource talks to which");
  n = await page.evaluate(() => document.querySelectorAll("#results li").length);
  check(n >= 1, "search: a term from a view gives results", String(n));
  const hit = await page.evaluate(() => !!document.querySelector('#results a[href="#view-Rs-Cn"]'));
  check(hit, "search: the result links the view that holds the term");
  if (hit) {
    await page.click('#results a[href="#view-Rs-Cn"]');
    check((await display("#view-Rs-Cn")) === "block" && (await display("#front")) === "none", "search: the link opens that page");
  }
  await page.keyboard.press("Escape");

  // --- phone width ---
  await page.setViewport({ width: 390, height: 800 });
  for (const p of PROFILES) {
    await go("#front");
    await click(p);
    const w = await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]);
    check(w[0] <= w[1], `phone width 390: front in ${p} does not scroll sideways`, String(w));
  }
  await click("uaf");
  for (const v of ["Rs-Cn", "Op-Tx"]) {
    await go(`#view-${v}`);
    const w = await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]);
    check(w[0] <= w[1], `phone width 390: ${v} does not scroll sideways`, String(w));
  }
  await go("#view-Rs-Cn");
  await shot("phone-Rs-Cn.png");
  await page.setViewport({ width: 1280, height: 900 });

  // --- print ---
  await go("#view-Op-Tx");
  await page.emulateMediaType("print");
  const shown = await page.evaluate(() => [...document.querySelectorAll(".page")].filter((e) => getComputedStyle(e).display !== "none").length);
  check(shown === TOTAL_PAGES, `print: all ${TOTAL_PAGES} pages are displayed`, String(shown));
  check((await display(".bar")) === "none", "print: the bar is hidden");
  check((await display("#results")) === "none", "print: the search panel is hidden");
  const gridsShown = await page.evaluate(() => [...document.querySelectorAll(".grid")].filter((e) => getComputedStyle(e).display !== "none").length);
  check(gridsShown === 1, "print: only the current profile's grid is shown", String(gridsShown));
  await shot("print-view.png");
  const pdf = Buffer.from(await page.pdf({ format: "A4", printBackground: true, preferCSSPageSize: true }));
  const count = (pdf.toString("latin1").match(/\/Type\s*\/Page(?![A-Za-z])/g) || []).length;
  check(count >= 30, "print: the PDF has at least 30 pages", String(count));
  const openAtPrint = await page.evaluate(() => window.__printOpen);
  check(openAtPrint.length > 0 && openAtPrint.every(Boolean), "print: details are open when the PDF is made", JSON.stringify(openAtPrint));
  await page.emulateMediaType("screen");
  const restored = await page.evaluate(() => [...document.querySelectorAll("details")].every((d) => !d.open));
  check(restored, "print: details are restored afterwards");

  // --- table styling ---
  // Words: measure every whitespace-delimited token in the visible tables; wrapped if its last character sits
  // below the bottom of its first. Details are opened for the measure and restored.
  const measure = (firstCol, lastCol) =>
    page.evaluate((c0, c1) => {
      const dets = [...document.querySelectorAll("details")];
      const was = dets.map((d) => d.open);
      dets.forEach((d) => { d.open = true; });
      const out = { tokens: 0, wrapped: 0, unmeasured: 0, fails: [] };
      const tables = [...document.querySelectorAll("table")].filter((t) => t.getClientRects().length > 0);
      for (const t of tables) {
        const sec = t.closest("section,.grid");
        const where = sec ? (sec.dataset.view || sec.id || "front") : "?";
        for (const tr of t.querySelectorAll("tr")) {
          const cells = [...tr.children].filter((c) => c.tagName === "TD" || c.tagName === "TH");
          for (let ci = c0; ci < Math.min(cells.length, c1); ci++) {
            const w = document.createTreeWalker(cells[ci], NodeFilter.SHOW_TEXT);
            let cur = null;
            const end = () => {
              if (!cur) return;
              const rect = (n, o) => {
                const r = document.createRange();
                r.setStart(n, o);
                r.setEnd(n, o + 1);
                return r.getClientRects()[0];
              };
              const a = rect(cur.fn, cur.fo);
              const b = rect(cur.ln, cur.lo);
              if (!a || !b) out.unmeasured++;
              else {
                out.tokens++;
                if (b.top >= a.bottom - 2) {
                  out.wrapped++;
                  if (out.fails.length < 5) out.fails.push(`${where} col ${ci + 1} "${cur.text.slice(0, 30)}"`);
                }
              }
              cur = null;
            };
            for (let n = w.nextNode(); n; n = w.nextNode()) {
              const s = n.nodeValue;
              for (let i = 0; i < s.length; i++) {
                if (/\s/.test(s[i])) end();
                else if (!cur) cur = { fn: n, fo: i, ln: n, lo: i, text: s[i] };
                else { cur.ln = n; cur.lo = i; cur.text += s[i]; }
              }
            }
            end();
          }
        }
      }
      dets.forEach((d, i) => { d.open = was[i]; });
      return out;
    }, firstCol, lastCol);
  const sweep = async (firstCol, lastCol, profiles, pagesAtOnce) => {
    const tot = { tokens: 0, wrapped: 0, unmeasured: 0, fails: [] };
    const add = (r, tag) => {
      tot.tokens += r.tokens;
      tot.wrapped += r.wrapped;
      tot.unmeasured += r.unmeasured;
      for (const f of r.fails) if (tot.fails.length < 5) tot.fails.push(`${f} ${tag}`);
    };
    for (const p of profiles) {
      await go("#front");
      if (!pagesAtOnce) await click(p);
      if (pagesAtOnce) add(await measure(firstCol, lastCol), `${p} ${pagesAtOnce}`);
      else {
        const vw = page.viewport().width;
        for (const v of ["front", ...views.map((x) => `view-${x}`)]) {
          await go(`#${v}`);
          add(await measure(firstCol, lastCol), `${p} ${vw}px`);
        }
      }
    }
    await go("#front");
    if (!pagesAtOnce) await click("uaf");
    return tot;
  };
  const midWord = { tokens: 0, wrapped: 0, unmeasured: 0, fails: [] };
  const fold = (r) => {
    midWord.tokens += r.tokens;
    midWord.wrapped += r.wrapped;
    midWord.unmeasured += r.unmeasured;
    midWord.fails.push(...r.fails);
  };
  const info = [];
  fold(await sweep(0, 3, PROFILES));
  info.push(["screen 1280", await sweep(3, 99, PROFILES)]);
  await page.setViewport({ width: 390, height: 800 });
  fold(await sweep(0, 3, PROFILES));
  info.push(["screen 390", await sweep(3, 99, PROFILES)]);
  await page.setViewport({ width: 980, height: 700 });
  await page.emulateMediaType("print");
  fold(await sweep(0, 3, ["uaf"], "print 980"));
  info.push(["print 980", await sweep(3, 99, ["uaf"], "print 980")]);
  await page.emulateMediaType("screen");
  await page.setViewport({ width: 1280, height: 900 });
  check(midWord.wrapped === 0 && midWord.unmeasured === 0 && midWord.tokens >= 1000,
    `mid-word: no word wraps in the first three columns (${midWord.tokens} tokens, ${midWord.wrapped} wrapped, ${midWord.unmeasured} unmeasured)`,
    `${midWord.tokens} tokens, ${midWord.wrapped} wrapped, ${midWord.unmeasured} unmeasured; first: ${midWord.fails.slice(0, 5).join("; ")}`);
  for (const [tag, r] of info) console.log(`info: columns 4 and later, ${tag}: ${r.tokens} tokens, ${r.wrapped} wrapped, ${r.unmeasured} unmeasured`);

  // Styling, by computed style.
  const lum = `
    const rgb = (s) => (s.match(/[\\d.]+/g) || []).slice(0, 3).map(Number);
    const lin = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    const L = (c) => 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2]);
    const contrast = (a, b) => { const x = L(rgb(a)), y = L(rgb(b)); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  `;
  const inPage = (body, ...args) => page.evaluate(new Function("...a", `${lum}; return (async (...a) => { ${body} })(...a);`), ...args);
  const TRANSPARENT = "rgba(0, 0, 0, 0)";

  await page.setViewport({ width: 1600, height: 900 });
  await go("#view-Op-Tx");
  const full = await page.evaluate(() => {
    const m = document.querySelector("main");
    const cs = getComputedStyle(m);
    const inner = m.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
    const t = document.querySelector("#view-Op-Tx .scroll table");
    return [inner, t.getBoundingClientRect().width];
  });
  await page.setViewport({ width: 1280, height: 900 });
  check(full[0] > 1100 && full[1] >= 0.95 * full[0], "tables: a view table is at least 95% of main, and main is wider than 1100 at 1600", full.join(" "));

  const mins = await page.evaluate(() => {
    const ths = [...document.querySelectorAll("th[style*=min-width]")];
    return [new Set(ths.map((t) => t.closest("table"))).size, ths.filter((t) => { const v = getComputedStyle(t).minWidth; return v === "0px" || v === "" || v === "auto"; }).length];
  });
  check(mins[0] >= 30 && mins[1] === 0, "tables: min-width headers on at least 30 tables, none computing to 0", mins.join(" "));

  await go("#view-St-Rm-P");
  const cap = await page.evaluate(() => {
    const t = document.querySelector("#view-St-Rm-P .scroll table");
    const s = t && t.closest(".scroll");
    if (!s) return null;
    const c = document.createElement("span");
    c.style.cssText = "display:inline-block;width:1ch";
    t.rows[1].cells[0].appendChild(c);
    const ch = c.getBoundingClientRect().width;
    c.remove();
    return [t.rows[0].cells.length, s.scrollWidth, s.clientWidth, ch];
  });
  // Minimums are in ch, so the fit depends on the reader's font. A wide default font fits at 1600 instead.
  const capWide = cap !== null && cap[3] > 8;
  if (capWide) await page.setViewport({ width: 1600, height: 900 });
  const capFit = capWide ? await page.evaluate(() => { const s = document.querySelector("#view-St-Rm-P .scroll"); return s.scrollWidth <= s.clientWidth + 1; }) : cap !== null && cap[1] <= cap[2] + 1;
  if (capWide) await page.setViewport({ width: 1280, height: 900 });
  check(cap !== null && cap[0] === 7 && capFit, `tables: the seven-column capability table does not scroll at ${capWide ? 1600 : 1280} (ch ${cap && cap[3].toFixed(2)} px)`, String(cap));
  await go("#view-Rs-Cn");
  const nine = await page.evaluate(() => {
    const t = [...document.querySelectorAll("#view-Rs-Cn table")].find((x) => x.rows[0] && x.rows[0].cells.length === 9);
    if (!t) return null;
    const s = t.closest(".scroll");
    return [s.scrollWidth, s.clientWidth, document.documentElement.scrollWidth, document.documentElement.clientWidth];
  });
  check(nine !== null && nine[0] > nine[1] && nine[2] <= nine[3], "tables: the nine-column table scrolls inside .scroll while the page does not (known sideways scroll at 1280)", String(nine));

  await go("#view-St-Rm-P");
  const badges = await inPage(`
    const bs = [...document.querySelectorAll("#view-St-Rm-P .badge")];
    const names = ["measured", "built unmeasured", "accepted design", "proposed", "row"];
    const cs = bs.map((b) => getComputedStyle(b));
    return { n: bs.length, bgs: new Set(cs.map((c) => c.backgroundColor)).size,
      names: bs.every((b) => names.includes(b.textContent)),
      minC: Math.min(...cs.map((c) => contrast(c.color, c.backgroundColor))) };
  `);
  check(badges.n === 35 && badges.bgs === 5 && badges.names && badges.minC >= 4.5, "badges: 35 in Phase column, 5 backgrounds, phase names, contrast at least 4.5", JSON.stringify(badges));

  const head = await inPage(`
    const hs = [...document.querySelectorAll("#view-Op-Tx thead th")].map((h) => getComputedStyle(h));
    return { n: hs.length, clear: hs.filter((c) => c.backgroundColor === "${TRANSPARENT}").length,
      minC: Math.min(...hs.map((c) => contrast(c.color, c.backgroundColor))) };
  `);
  check(head.n > 0 && head.clear === 0 && head.minC >= 4.5, "header: thead th has a background and contrast at least 4.5", JSON.stringify(head));

  const zebra = await page.evaluate(() => {
    const t = [...document.querySelectorAll("#view-Op-Tx table, #view-Rs-Cn table")].find((x) => x.tBodies[0] && x.tBodies[0].rows.length >= 4);
    if (!t) return null;
    const r = t.tBodies[0].rows;
    return [getComputedStyle(r[0].cells[1] || r[0].cells[0]).backgroundColor, getComputedStyle(r[1].cells[1] || r[1].cells[0]).backgroundColor];
  });
  check(zebra !== null && zebra[0] !== zebra[1], "zebra: rows 1 and 2 of a table differ in background", String(zebra));

  const lanes = await page.evaluate(() => {
    const r = [...document.querySelectorAll("#view-St-Rm-P tr.lane-start")];
    return [r.length, r.filter((x) => getComputedStyle(x.cells[0]).borderTopWidth !== "2px").length];
  });
  check(lanes[0] === 12 && lanes[1] === 0, "lane rules: 12 lane starts in the roadmap, each a 2px top rule", lanes.join(" "));

  const viewHead = await page.evaluate(() => getComputedStyle(document.querySelector("#view-Op-Tx thead th")).backgroundColor);
  const filledBg = await page.evaluate(() => {
    const p = document.createElement("i");
    p.style.background = "var(--filled)";
    document.body.appendChild(p);
    const c = getComputedStyle(p).backgroundColor;
    p.remove();
    return c;
  });
  await go("#front");
  const gridRes = [];
  for (const p of PROFILES) {
    await click(p);
    gridRes.push(await page.evaluate((q, fb, vh) => {
      const g = document.querySelector(`#grid-${q}`);
      const bg = (e) => getComputedStyle(e).backgroundColor;
      const fcells = [...g.querySelectorAll(".filled")].map((e) => e.closest("td"));
      const plain = [...g.querySelectorAll(".gridtable tbody td")].filter((c) => !c.querySelector(".filled") && !c.classList.contains("filled"));
      const heads = [...g.querySelectorAll(".gridtable thead th")];
      const rows = [...g.querySelectorAll(".gridtable tbody tr")];
      return {
        head: heads.every((h) => bg(h) === vh),
        filled: fcells.length > 0 && fcells.every((c) => bg(c) === fb),
        plain: plain.length > 0 && plain.every((c) => bg(c) !== fb),
        rules: rows.length > 0 && rows.every((r) => [...r.children].every((c) => getComputedStyle(c).borderTopWidth === "2px")),
      };
    }, p, filledBg, viewHead));
  }
  await click("uaf");
  check(gridRes.every((g) => g.head && g.filled && g.plain && g.rules), "grid: header matches a view table, filled cells are --filled and others are not, 2px row rules, in every profile", JSON.stringify(gridRes));

  // Print emulation, all pages at once.
  await go("#view-St-Rm-P");
  const screenBadges = await page.evaluate(() => [...document.querySelectorAll(".badge")].map((b) => b.textContent).join("|"));
  await page.setViewport({ width: 980, height: 700 });
  await page.emulateMediaType("print");
  const pr2 = await inPage(`
    const bs = [...document.querySelectorAll(".badge")];
    const hs = [...document.querySelectorAll("thead th")].map((h) => getComputedStyle(h));
    const ls = [...document.querySelectorAll("tr.lane-start")];
    const wide = [...document.querySelectorAll("table")].filter((t) => t.getClientRects().length > 0 && t.scrollWidth > t.parentElement.clientWidth + 1);
    return { texts: bs.map((b) => b.textContent).join("|"),
      badgeClear: bs.filter((b) => getComputedStyle(b).backgroundColor !== "${TRANSPARENT}").length,
      headBad: hs.filter((c) => c.backgroundColor !== "${TRANSPARENT}" || c.color === "rgb(255, 255, 255)").length,
      lanes: ls.length, laneBad: ls.filter((r) => getComputedStyle(r.cells[0]).borderTopWidth !== "2px").length,
      wide: wide.length };
  `);
  const wideFont = await page.addStyleTag({ content: 'body,table,th,td{font-family:Verdana,"DejaVu Sans"!important}' });
  const pr3 = await page.evaluate(() => {
    const open = [...document.querySelectorAll("details")].map((d) => [d, d.open]);
    open.forEach(([d]) => { d.open = true; });
    const over = [...document.querySelectorAll("table")].filter((t) => t.scrollWidth > t.parentElement.clientWidth + 1).length;
    open.forEach(([d, was]) => { d.open = was; });
    return over;
  });
  await wideFont.evaluate((e) => e.remove());
  await page.emulateMediaType("screen");
  await page.setViewport({ width: 1280, height: 900 });
  check(pr2.texts === screenBadges && pr2.badgeClear === 0, "print: badges lose their fill and keep their words", `${pr2.badgeClear} filled`);
  check(pr2.headBad === 0, "print: thead th has no fill and no white text", String(pr2.headBad));
  check(pr2.lanes > 0 && pr2.laneBad === 0, "print: lane rules are still 2px", `${pr2.lanes} ${pr2.laneBad}`);
  check(pr2.wide === 0, "print: no table is wider than its parent at 980", String(pr2.wide));
  check(pr3 === 0, "print: no table is wider than its parent at 980 under a wide font", String(pr3));
  const boxes = [...pdf.toString("latin1").matchAll(/\/MediaBox\s*\[\s*0 0 ([\d.]+) ([\d.]+)/g)].map((m) => [Number(m[1]), Number(m[2])]);
  check(boxes.length >= 30 && boxes.every(([w, h]) => w > h), "print: the PDF's pages are landscape", `${boxes.length} boxes, first ${boxes[0]}`);

  check(badRequests.length === 0, "no request but file: and data:", badRequests.slice(0, 3).join(" "));
  check(consoleErrors.length === 0, "no console error", consoleErrors.slice(0, 3).join(" | "));
} finally {
  await browser.close();
}
for (const w of written) console.log(`shot: ${w}`);
console.log(`${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
