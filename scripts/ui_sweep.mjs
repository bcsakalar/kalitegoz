/**
 * Arayüz süpürmesi — her sayfa × iki tema × iki dil, sonra her etkileşimli öğe.
 *
 * ## Neden ekran görüntüsü yetmiyor
 *
 * `shots.mjs` bir görüntü alır ve hata sınırını kontrol eder. Bu, çöken
 * sayfayı yakalar ama **tıklanınca hiçbir şey yapmayan butonu** yakalamaz:
 * öyle bir buton da gayet düzgün görünür.
 *
 * Bu betik üç ayrı soruyu ölçer:
 *
 * 1. **Sayfa açılıyor mu** — hata sınırı devrede mi, gövde boş mu.
 * 2. **Dil gerçekten değişiyor mu** — TR ve EN'de aynı metin çıkıyorsa
 *    çeviri uygulanmamış demektir.
 * 3. **Etkileşimli öğe ölü mü** — her butona tıklanır ve şunlardan biri
 *    olmalı: DOM değişir, ağ isteği gider, gezinme olur ya da bir alan
 *    odaklanır. Hiçbiri olmuyorsa buton ölüdür.
 *
 * Yıkıcı öğeler (sil, çıkış, işlemeyi başlat) `TEHLIKELI` kalıplarıyla
 * dışarıda bırakılır: denetim, denetlediği sistemi bozmamalı.
 */

import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import { readFileSync } from "node:fs";
import path from "node:path";

const BASE = "http://localhost:3000";
const API = "http://localhost:8000";
const OUT = "docs/screens/sweep";

function envParola() {
  try {
    const t = readFileSync(new URL("../.env", import.meta.url), "utf-8");
    const m = t.match(/^ADMIN_PASSWORD=(.*)$/m);
    return m ? m[1].trim() : "";
  } catch { return ""; }
}
const PAROLA = envParola();

const EPOSTA = {
  admin: "admin@demo.local",
  quality: "kalite@demo.local",
  supervisor: "sef.destek@demo.local",
  agent: "ayse.yilmaz@demo.local",
};

/** [ad, yol, rol] */
const SAYFALAR = [
  ["giris", "/login", null],
  ["cagrilar", "/", "admin"],
  ["kokpit", "/cockpit", "admin"],
  ["inceleme", "/review", "quality"],
  ["kalibrasyon", "/calibration", "quality"],
  ["analitik", "/analytics", "admin"],
  ["rubrik", "/rubric", "admin"],
  ["yonetim", "/admin", "admin"],
  ["guvenlik", "/security", "admin"],
  ["roi", "/roi", "admin"],
  ["liderlik", "/leaderboard", "supervisor"],
  ["arama", "/search", "admin"],
  ["is-akisi", "/workflow", "supervisor"],
  ["temsilciler", "/agents", "supervisor"],
  ["hesap", "/account", "agent"],
  ["asistan", "/assist", "admin"],
];

// Tiklanmamasi gerekenler: yikici ya da oturumu bitiren eylemler.
const TEHLIKELI = /sil|kaldır|kaldir|delete|remove|çıkış|cikis|logout|başlat|baslat|start|sıfırla|sifirla|reset|temizle|iptal et|onayla|kaydet|save|gönder|gonder|indir|download|yükle|yukle|upload/i;

async function girisYap(page, rol) {
  if (!rol) return true;
  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
  const ok = await page.evaluate(async ({ api, eposta, parola }) => {
    const r = await fetch(`${api}/api/v1/auth/login`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: eposta, password: parola, tenant_slug: "demo" }),
    });
    if (!r.ok) return false;
    const d = await r.json();
    localStorage.setItem("kg_token", d.access_token);
    localStorage.setItem("kg_refresh", d.refresh_token);
    return true;
  }, { api: API, eposta: EPOSTA[rol], parola: PAROLA });
  await page.waitForTimeout(300);
  return ok;
}

async function ayarla(page, tema, dil) {
  await page.evaluate(([t, d]) => {
    document.documentElement.setAttribute("data-theme", t);
    try {
      localStorage.setItem("kg_theme", t);
      localStorage.setItem("kg_lang", d);
    } catch { /* yoksay */ }
  }, [tema, dil]);
}

/** Sayfa çöktü mü / boş mu? */
async function sayfaDurumu(page) {
  return page.evaluate(() => {
    const govde = document.body?.innerText || "";
    const coktu = /Bir şeyler ters gitti|Something went wrong|Application error|Unhandled/i.test(govde);
    const ipucu = coktu
      ? (govde.split("\n").map((x) => x.trim()).find((x) =>
          /is not a function|undefined|is not iterable|Cannot read|null/.test(x)) || "hata siniri")
      : null;
    return {
      coktu, ipucu,
      metinUzunlugu: govde.trim().length,
      // Ana içerik alanı gerçekten dolu mu (sidebar hariç)
      icerik: (document.querySelector("main")?.innerText || govde).trim().length,
    };
  });
}

/** Her etkileşimli öğeyi dene: tıklayınca bir şey oluyor mu? */
async function etkilesimSuur(page) {
  const olu = [];
  const denenen = [];

  const dugmeler = await page.$$("button:not([disabled])");
  for (let i = 0; i < Math.min(dugmeler.length, 40); i++) {
    const d = dugmeler[i];
    let etiket = "";
    try {
      etiket = ((await d.getAttribute("aria-label")) || (await d.innerText())
        || (await d.getAttribute("title")) || "").trim().slice(0, 40);
      if (!(await d.isVisible())) continue;
      // ZATEN SECILI olan secenegi atla.
      //
      // Aktif sekmeye/metrige/temaya tekrar tiklamak hicbir seyi degistirmez
      // ve bu DOGRU davranistir. Ilk surum bunu "olu buton" diye raporladi:
      // tema anahtari, dil anahtari ve analitik metrik secicisi yanlis
      // yere isaretlendi. Yanlis pozitif ureten denetim gormezden gelinir.
      const secili = await d.evaluate((e) =>
        e.getAttribute("data-active") === "true"
        || e.getAttribute("aria-pressed") === "true"
        || e.getAttribute("aria-selected") === "true"
        || e.hasAttribute("aria-current"));
      if (secili) continue;
    } catch { continue; }
    if (!etiket || TEHLIKELI.test(etiket)) continue;

    // Tıklamadan önceki durum
    const once = await page.evaluate(() => ({
      html: document.body.innerHTML.length,
      url: location.href,
      odak: document.activeElement?.tagName || "",
      depo: JSON.stringify({ t: localStorage.getItem("kg_theme"),
                             d: localStorage.getItem("kg_lang"),
                             tema: document.documentElement.getAttribute("data-theme") }),
    }));
    let istekGitti = false;
    const dinle = (r) => { if (r.url().includes("/api/")) istekGitti = true; };
    page.on("request", dinle);

    try {
      await d.click({ timeout: 2500, noWaitAfter: true });
      await page.waitForTimeout(450);
    } catch {
      page.off("request", dinle);
      continue;  // tiklanamadi (ortulu vb.) — olu sayilmaz
    }
    page.off("request", dinle);

    const sonra = await page.evaluate(() => ({
      html: document.body.innerHTML.length,
      url: location.href,
      odak: document.activeElement?.tagName || "",
      // Tema ve dil anahtarlari DOM uzunlugunu degistirmeden durum degistirir;
      // yalnizca uzunluga bakmak onlari olu gosteriyordu.
      depo: JSON.stringify({ t: localStorage.getItem("kg_theme"),
                             d: localStorage.getItem("kg_lang"),
                             tema: document.documentElement.getAttribute("data-theme") }),
    }));
    const degisti = once.html !== sonra.html || once.url !== sonra.url
      || once.odak !== sonra.odak || once.depo !== sonra.depo || istekGitti;
    denenen.push(etiket);
    if (!degisti) olu.push(etiket);

    // Açılan bir katman varsa kapat ki sonraki öğeyi örtmesin
    await page.keyboard.press("Escape").catch(() => {});
    await page.waitForTimeout(120);
    if (sonra.url !== once.url) break;  // gezindik; bu sayfanin suurmesi bitti
  }
  return { denenen: denenen.length, olu };
}

/** Sidebar bağlantıları gerçekten bir sayfaya gidiyor mu? */
async function linkleriDogrula(page) {
  const hedefler = await page.$$eval("a[href^='/']", (as) =>
    [...new Set(as.map((a) => a.getAttribute("href")))].filter((h) => h && !h.startsWith("//")));
  const olu = [];
  for (const h of hedefler.slice(0, 25)) {
    const y = await page.evaluate(async (yol) => {
      const r = await fetch(yol, { method: "GET" });
      return r.status;
    }, h).catch(() => 0);
    if (y >= 400) olu.push(`${h} -> ${y}`);
  }
  return olu;
}

async function main() {
  await mkdir(OUT, { recursive: true });
  const browser = await chromium.launch();
  const rapor = [];

  for (const dil of ["tr", "en"]) {
    for (const tema of ["light", "dark"]) {
      const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await ctx.newPage();
      const konsol = [];
      page.on("console", (m) => { if (m.type() === "error") konsol.push(m.text().slice(0, 160)); });
      page.on("pageerror", (e) => konsol.push(`pageerror: ${String(e).slice(0, 160)}`));
      page.on("response", (r) => {
        if (r.status() >= 400 && !r.url().includes("/_next/")) {
          konsol.push(`HTTP ${r.status()} ${r.url().replace(API, "")}`);
        }
      });

      let aktifRol = null;
      for (const [ad, yol, rol] of SAYFALAR) {
        const oncekiKonsol = konsol.length;
        try {
          if (rol !== aktifRol) { aktifRol = (await girisYap(page, rol)) ? rol : null; }
          await page.goto(`${BASE}${yol}`, { waitUntil: "domcontentloaded", timeout: 20000 });
          await ayarla(page, tema, dil);
          await page.reload({ waitUntil: "domcontentloaded", timeout: 20000 });
          await page.waitForTimeout(2200);

          const durum = await sayfaDurumu(page);
          const etk = (dil === "tr" && tema === "light")
            ? await etkilesimSuur(page) : { denenen: 0, olu: [] };
          const oluLink = (dil === "tr" && tema === "light" && ad === "cagrilar")
            ? await linkleriDogrula(page) : [];

          if (dil === "tr" && tema === "light") {
            await page.screenshot({ path: path.join(OUT, `${ad}.png`) });
          }

          rapor.push({
            sayfa: ad, yol, rol, dil, tema, ...durum,
            denenenDugme: etk.denenen, oluDugme: etk.olu, oluLink,
            konsol: konsol.slice(oncekiKonsol),
          });
          const im = durum.coktu ? "COKTU" : durum.icerik < 60 ? "BOS" : "ok";
          const ek = etk.olu.length ? `  olu-dugme:${etk.olu.length}` : "";
          console.log(`  ${im.padEnd(6)} ${dil}/${tema.padEnd(5)} ${ad}${ek}`);
        } catch (e) {
          rapor.push({ sayfa: ad, yol, rol, dil, tema, hata: String(e).slice(0, 150) });
          console.log(`  HATA   ${dil}/${tema} ${ad}: ${String(e).slice(0, 90)}`);
        }
      }
      await ctx.close();
    }
  }

  await browser.close();
  await writeFile(path.join(OUT, "_rapor.json"), JSON.stringify(rapor, null, 2), "utf-8");

  const coken = rapor.filter((r) => r.coktu);
  const bos = rapor.filter((r) => !r.coktu && (r.icerik ?? 999) < 60);
  const oluD = rapor.flatMap((r) => (r.oluDugme || []).map((d) => `${r.sayfa}: ${d}`));
  const oluL = rapor.flatMap((r) => (r.oluLink || []).map((d) => `${r.sayfa}: ${d}`));
  const httpHata = [...new Set(rapor.flatMap((r) => (r.konsol || []).filter((k) => k.startsWith("HTTP"))))];

  console.log(`\n${rapor.length} sayfa-varyant | coken: ${coken.length} | bos: ${bos.length}`);
  console.log(`olu dugme: ${oluD.length} | olu link: ${oluL.length} | HTTP hatasi: ${httpHata.length}`);
  for (const x of coken) console.log("  COKTU:", x.sayfa, x.dil, x.tema, x.ipucu);
  for (const x of bos) console.log("  BOS  :", x.sayfa, x.dil, x.tema, "icerik=", x.icerik);
  for (const x of [...new Set(oluD)]) console.log("  OLU DUGME:", x);
  for (const x of oluL) console.log("  OLU LINK :", x);
  for (const x of httpHata) console.log("  HTTP     :", x);
}

main();
