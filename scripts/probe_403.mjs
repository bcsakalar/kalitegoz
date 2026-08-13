/**
 * /admin/users 403'unu izole et: TEMIZ bir bağlamda, rol geçişi olmadan.
 *
 * Süpürmede bu hata rol değişiminden sonraki sayfada görünüyordu; bu, ya
 * gecikmiş bir isteğin yanlış sayfaya yazılması ya da o sayfanın gerçekten
 * yetkisi olmayan bir uç çağırması demek. İkisi çok farklı şeyler.
 */
import { chromium } from "playwright";
import { readFileSync } from "node:fs";

const BASE = "http://localhost:3000";
const API = "http://localhost:8000";
const PAROLA = (readFileSync(new URL("../.env", import.meta.url), "utf-8")
  .match(/^ADMIN_PASSWORD=(.*)$/m) || [, ""])[1].trim();

const VAKALAR = [
  ["/search", "admin@demo.local"],
  ["/account", "ayse.yilmaz@demo.local"],
  ["/cockpit", "admin@demo.local"],
  ["/leaderboard", "sef.destek@demo.local"],
];

const browser = await chromium.launch();
for (const [yol, eposta] of VAKALAR) {
  const ctx = await browser.newContext();      // HER VAKA TEMIZ BAGLAM
  const page = await ctx.newPage();
  const olaylar = [];
  page.on("response", async (r) => {
    if (r.url().includes("/api/v1/") && r.status() >= 400) {
      olaylar.push(`${r.status()} ${r.url().replace(API, "")}  <- ${r.request().frame()?.url() || "?"}`);
    }
  });

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
  }, { api: API, eposta, parola: PAROLA });

  await page.goto(`${BASE}${yol}`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(3500);
  console.log(`${yol.padEnd(14)} ${eposta.padEnd(24)} giris=${ok}  4xx=${olaylar.length}`);
  for (const o of olaylar) console.log("     ", o);
  await ctx.close();
}
await browser.close();
