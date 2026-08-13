/**
 * İngilizce arayüzde Türkçe metin kalıyor mu?
 *
 * `api.ts` içindeki STATUS_LABELS / CATEGORY_LABELS / CHANNEL_LABELS /
 * VIOLATION_LABELS sabitleri i18n'den GEÇMİYOR — sabit Türkçe. Roller için
 * aynı sorun görülüp `ROLE_LABEL_KEYS` ile çözülmüş ama diğer dört harita
 * öyle bırakılmış. Bu betik iddiayı ölçer.
 */
import { chromium } from "playwright";
import { readFileSync } from "node:fs";

const BASE = "http://localhost:3000";
const API = "http://localhost:8000";
const PAROLA = (readFileSync(new URL("../.env", import.meta.url), "utf-8")
  .match(/^ADMIN_PASSWORD=(.*)$/m) || [, ""])[1].trim();

// Ingilizce arayuzde GORUNMEMESI gereken Turkce etiketler
const TR_ETIKET = [
  "Kuyrukta", "Çözümleniyor", "Puanlanıyor", "Tamamlandı",
  "Fatura", "İptal", "Arıza", "Şikayet", "Diğer",
  "Sesli", "Yazışma", "E-posta",
];

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await ctx.newPage();

await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
await page.evaluate(async ({ api, parola }) => {
  const r = await fetch(`${api}/api/v1/auth/login`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: "admin@demo.local", password: parola, tenant_slug: "demo" }),
  });
  const d = await r.json();
  localStorage.setItem("kg_token", d.access_token);
  localStorage.setItem("kg_refresh", d.refresh_token);
  localStorage.setItem("kg_lang", "en");
  localStorage.setItem("kg_theme", "light");
}, { api: API, parola: PAROLA });

for (const [ad, yol] of [["cagrilar", "/"], ["kokpit", "/cockpit"], ["arama", "/search"]]) {
  await page.goto(`${BASE}${yol}`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2800);
  const govde = await page.innerText("body");
  const bulunan = TR_ETIKET.filter((e) => govde.includes(e));
  console.log(`${ad.padEnd(10)} EN arayuzde kalan TR etiket: ${bulunan.length ? bulunan.join(", ") : "(yok)"}`);
  if (ad === "cagrilar") {
    await page.screenshot({ path: "docs/screens/sweep/cagrilar-en.png" });
  }
}
await browser.close();
