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
  check(views.length === 18, "18 view sections", String(views.length));
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
  check(provCount === 19, "a provenance block on every page", String(provCount));

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
  check(shown === 19, "print: all 19 pages are displayed", String(shown));
  check((await display(".bar")) === "none", "print: the bar is hidden");
  check((await display("#results")) === "none", "print: the search panel is hidden");
  const gridsShown = await page.evaluate(() => [...document.querySelectorAll(".grid")].filter((e) => getComputedStyle(e).display !== "none").length);
  check(gridsShown === 1, "print: only the current profile's grid is shown", String(gridsShown));
  await shot("print-view.png");
  const pdf = Buffer.from(await page.pdf({ format: "A4", printBackground: true }));
  const count = (pdf.toString("latin1").match(/\/Type\s*\/Page(?![A-Za-z])/g) || []).length;
  check(count >= 19, "print: the PDF has at least 19 pages", String(count));
  const openAtPrint = await page.evaluate(() => window.__printOpen);
  check(openAtPrint.length > 0 && openAtPrint.every(Boolean), "print: details are open when the PDF is made", JSON.stringify(openAtPrint));
  await page.emulateMediaType("screen");
  const restored = await page.evaluate(() => [...document.querySelectorAll("details")].every((d) => !d.open));
  check(restored, "print: details are restored afterwards");

  check(badRequests.length === 0, "no request but file: and data:", badRequests.slice(0, 3).join(" "));
  check(consoleErrors.length === 0, "no console error", consoleErrors.slice(0, 3).join(" | "));
} finally {
  await browser.close();
}
for (const w of written) console.log(`shot: ${w}`);
console.log(`${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
