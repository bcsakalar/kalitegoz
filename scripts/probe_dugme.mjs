/**
 * "Ölü" işaretlenen butonları tek tek sına.
 *
 * İki tuzak vardı ve ikisine de düştüm:
 *
 * 1. Süpürme, zaten AKTİF olan seçeneğe tıklıyordu (dil zaten TR, metrik
 *    zaten "Ortalama puan"). Aktif seçeneğe tıklamak hiçbir şeyi
 *    değiştirmez ve bu **doğru** davranıştır.
 * 2. `getByRole("button", { name: "🌙" })` erişilebilir ADA bakar; butonun
 *    `aria-label`'ı "Koyu" olduğu için eşleşmedi, tıklama sessizce düştü ve
 *    sonuç "ölü" göründü.
 *
 * Bu sürüm butonları DOM'dan metin/emoji ile bulur ve durumu doğrudan
 * `localStorage` + `data-theme` üzerinden ölçer.
 */
import { chromium } from "playwright";
import { readFileSync } from "node:fs";

const BASE = "http://localhost:3000";
const API = "http://localhost:8000";
const PAROLA = (readFileSync(new URL("../.env", import.meta.url), "utf-8")
  .match(/^ADMIN_PASSWORD=(.*)$/m) || [, ""])[1].trim();

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();

await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(1500);

// Once toolbar'daki butonlari LISTELE — neyi tikladigimizi bilelim
const dugmeler = await page.$$eval("button", (bs) =>
  bs.map((b, i) => ({
    i,
    metin: (b.innerText || "").trim().slice(0, 20),
    etiket: b.getAttribute("aria-label") || "",
    baslik: b.getAttribute("title") || "",
  })).filter((x) => x.metin || x.etiket));
console.log("=== GIRIS SAYFASINDAKI BUTONLAR ===");
for (const d of dugmeler) console.log(`  [${d.i}] metin='${d.metin}' aria='${d.etiket}' title='${d.baslik}'`);

async function durum() {
  return page.evaluate(() => ({
    tema: document.documentElement.getAttribute("data-theme") || "(kaldirilmis=system)",
    kayitTema: localStorage.getItem("kg_theme") || "(yok)",
    kayitDil: localStorage.getItem("kg_lang") || "(yok)",
    ilkMetin: (document.body.innerText || "").slice(0, 120).replace(/\n+/g, " | "),
  }));
}

/** Metni/emojisi verilen butona indeksle tıkla (aria-label'a güvenme). */
async function tikla(kalip) {
  const idx = dugmeler.find((d) => kalip.test(d.metin) || kalip.test(d.etiket))?.i;
  if (idx === undefined) { console.log(`     (${kalip} bulunamadi)`); return false; }
  await page.$$eval("button", (bs, i) => bs[i].click(), idx);
  await page.waitForTimeout(800);
  return true;
}

console.log("\n=== TEMA ANAHTARI ===");
console.log("  baslangic:", JSON.stringify(await durum()));
await tikla(/🌙|Koyu|Dark/);
const koyu = await durum();
console.log("  ay tiklandi  :", koyu.tema, "| kayit:", koyu.kayitTema);
await tikla(/☀|Açık|Acik|Light/);
const acik = await durum();
console.log("  gunes tiklandi:", acik.tema, "| kayit:", acik.kayitTema);
await tikla(/🖥|Sistem|System/);
const sistem = await durum();
console.log("  sistem tiklandi:", sistem.tema, "| kayit:", sistem.kayitTema);
const temaOk = koyu.kayitTema === "dark" && acik.kayitTema === "light" && sistem.kayitTema === "system";
console.log(`  SONUC: ${temaOk ? "CALISIYOR — uc secenek de durumu degistiriyor" : "OLU"}`);

console.log("\n=== DIL ANAHTARI ===");
const dilOnce = await durum();
await tikla(/EN/);
const en = await durum();
await tikla(/TR/);
const tr = await durum();
console.log("  baslangic:", dilOnce.kayitDil, "|", dilOnce.ilkMetin.slice(0, 60));
console.log("  EN sonrasi:", en.kayitDil, "|", en.ilkMetin.slice(0, 60));
console.log("  TR sonrasi:", tr.kayitDil, "|", tr.ilkMetin.slice(0, 60));
const dilOk = en.kayitDil === "en" && tr.kayitDil === "tr" && en.ilkMetin !== tr.ilkMetin;
console.log(`  SONUC: ${dilOk ? "CALISIYOR — hem kayit hem metin degisiyor" : "OLU"}`);

// ---- Analitik boyut secicisi
console.log("\n=== ANALITIK: boyut secicisi ===");
await page.evaluate(async ({ api, parola }) => {
  const r = await fetch(`${api}/api/v1/auth/login`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: "admin@demo.local", password: parola, tenant_slug: "demo" }),
  });
  const d = await r.json();
  localStorage.setItem("kg_token", d.access_token);
  localStorage.setItem("kg_refresh", d.refresh_token);
}, { api: API, parola: PAROLA });
await page.goto(`${BASE}/analytics`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(3000);

const boyutlar = await page.$$eval("button", (bs) =>
  bs.map((b, i) => ({ i, metin: (b.innerText || "").trim() }))
    .filter((x) => /^(Takım|Takim|Kampanya|Team|Campaign)$/i.test(x.metin)));
console.log("  bulunan boyut butonlari:", boyutlar.map((b) => b.metin).join(", ") || "(yok)");
for (const b of boyutlar.slice(0, 3)) {
  let istek = false;
  const dinle = (r) => { if (r.url().includes("/api/v1/analytics")) istek = true; };
  page.on("request", dinle);
  const once = await page.evaluate(() => document.body.innerHTML.length);
  await page.$$eval("button", (bs, i) => bs[i].click(), b.i);
  await page.waitForTimeout(1400);
  page.off("request", dinle);
  const sonra = await page.evaluate(() => document.body.innerHTML.length);
  console.log(`  '${b.metin}' → istek=${istek} domDegisti=${once !== sonra} ${istek || once !== sonra ? "✓" : "✗ OLU"}`);
}

await browser.close();
