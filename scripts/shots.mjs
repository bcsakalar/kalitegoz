/**
 * Arayüz ekran görüntüsü alıcı — her sayfa, aydınlık + karanlık.
 *
 * ## Neden bir betik, elle tıklamak değil
 *
 * Arayüz denetimi bir kez yapılıp bitmiyor: her UI değişikliğinden sonra
 * "hangi sayfa bozuldu" sorusu yeniden soruluyor. Elle 20 sayfa × 2 tema
 * gezmek ikinci turda yapılmaz. Betik, denetimi tekrarlanabilir kılar.
 *
 * ## Rol bazlı giriş
 *
 * Her sayfa her role açık değil. Betik her sayfayı, o sayfayı görebilen EN
 * DÜŞÜK yetkili rolle çeker — çünkü ekranın gerçekten kırıldığı yer genelde
 * "yönetici her şeyi görüyor" değil, "temsilci yarısını göremiyor" durumudur.
 *
 * ## Kullanım
 *
 *   node scripts/shots.mjs [--out docs/screens] [--base http://localhost:3000]
 *   node scripts/shots.mjs --only cockpit,review
 */

import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import { readFileSync } from "node:fs";
import path from "node:path";

const arg = (ad, varsayilan) => {
  const i = process.argv.indexOf(`--${ad}`);
  return i > -1 && process.argv[i + 1] ? process.argv[i + 1] : varsayilan;
};

const BASE = arg("base", "http://localhost:3000");
const API = arg("api", "http://localhost:8000");
const OUT = arg("out", "docs/screens");
const ONLY = arg("only", "");
// Parola .env'den okunur; sabit varsayilan YOK (acik kaynak depoda sabit
// parola, herkesin bildigi parola demektir).
function envParola() {
  try {
    const t = readFileSync(new URL("../.env", import.meta.url), "utf-8");
    const m = t.match(/^ADMIN_PASSWORD=(.*)$/m);
    return m ? m[1].trim() : "";
  } catch { return ""; }
}
const PAROLA = arg("password", envParola());

/**
 * Sayfa listesi: [dosya adı, yol, giriş yapılacak rol, bekleme ipucu, sekme]
 *
 * `sekme` verilirse sayfa açıldıktan sonra o ada uyan düğmeye tıklanır.
 * Neden gerekli: Yönetim ekranının 12 alt sekmesi React durumu ile seçiliyor,
 * URL değişmiyor. Denetim yalnızca ilk sekmeyi (İşleme) görüyordu; geri
 * kalan 11 sekme — yapay zekâ, kullanıcılar, SSO, rubrik — hiç ekran
 * görüntüsü alınmadan geçiyordu. Çöken bir alt sekme fark edilmezdi.
 *
 * Ad hem TR hem EN olabilir: arayüz dili tarayıcı tercihine göre değişiyor.
 */
const SAYFALAR = [
  ["01-giris", "/login", null, "text=Kalite"],
  ["02-cagrilar", "/", "admin", null],
  ["03-kokpit", "/cockpit", "admin", null],
  ["04-inceleme-kuyrugu", "/review", "quality", null],
  ["05-kalibrasyon", "/calibration", "quality", null],
  ["06-analitik", "/analytics", "admin", null],
  ["07-rubrik", "/rubric", "admin", null],
  ["08-yonetim", "/admin", "admin", null],
  ["08a-yonetim-yapay-zeka", "/admin", "admin", null, /^(Yapay Zekâ|AI)$/],
  ["08b-yonetim-kullanicilar", "/admin", "admin", null, /^(Kullanıcılar|Users)$/],
  ["08c-yonetim-bilgi-bankasi", "/admin", "admin", null, /Bilgi Bankası|Knowledge base/i],
  ["08d-yonetim-kurumsal-kimlik", "/admin", "admin", null, /^(Kurumsal Kimlik|Enterprise Identity)$/],
  ["09-guvenlik", "/security", "admin", null],
  ["10-roi", "/roi", "admin", null],
  ["11-liderlik", "/leaderboard", "supervisor", null],
  ["12-arama", "/search", "admin", null],
  ["13-is-akisi", "/workflow", "supervisor", null],
  ["14-temsilciler", "/agents", "supervisor", null],
  ["15-hesap", "/account", "agent", null],
  ["16-asistan", "/assist", "admin", null],
];

// Seed kullanicilari (backend/app/seed.py). Demo rol butonlari KAPALI bir
// <details> icinde durdugu icin tiklanamiyor; form girisi hem daha saglam
// hem de gercek kullanicinin yaptigi seye daha yakin.
const EPOSTA = {
  admin: "admin@demo.local",
  quality: "kalite@demo.local",
  supervisor: "sef.destek@demo.local",
  agent: "ayse.yilmaz@demo.local",
};

/**
 * Oturumu API uzerinden ac, token'i dogrudan localStorage'a yaz.
 *
 * Neden giris FORMUNU kullanmiyoruz: giris ekraninin gorunumu sisteme bagli
 * (henuz gercek kurum yoksa "Kurumunuzu olusturun" ekrani cikiyor, giris
 * formu gizleniyor). Ekran goruntusu araci, denetlemek istedigi 16 sayfaya
 * ulasmak icin giris arayuzunun o anki durumuna BAGIMLI OLMAMALI.
 *
 * Giris ekraninin kendisi zaten ayri bir kare olarak (01-giris) cekiliyor.
 */
async function girisYap(page, rol) {
  if (!rol) return true;
  const eposta = EPOSTA[rol];
  if (!eposta) return false;

  // Ayni origin'de olmali ki localStorage yazilabilsin
  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });

  const sonuc = await page.evaluate(async ({ api, eposta, parola }) => {
    const slugDene = async (slug) => {
      const r = await fetch(`${api}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: eposta, password: parola, tenant_slug: slug }),
      });
      return r.ok ? r.json() : null;
    };
    let d = await slugDene("demo");
    if (!d) {
      const cfg = await fetch(`${api}/api/v1/auth/config`).then((r) => r.json()).catch(() => null);
      if (cfg?.org_slug) d = await slugDene(cfg.org_slug);
    }
    if (!d) return { ok: false };
    localStorage.setItem("kg_token", d.access_token);
    localStorage.setItem("kg_refresh", d.refresh_token);
    return { ok: true };
  }, { api: API, eposta, parola: PAROLA });

  if (!sonuc.ok) return false;
  await page.waitForTimeout(400);
  return true;
}

async function temaAyarla(page, tema) {
  await page.evaluate((t) => {
    document.documentElement.setAttribute("data-theme", t);
    try { localStorage.setItem("kg_theme", t); } catch {}
  }, tema);
  await page.waitForTimeout(400);
}

async function main() {
  await mkdir(OUT, { recursive: true });
  const browser = await chromium.launch();
  const rapor = [];
  const secili = ONLY ? ONLY.split(",").map((s) => s.trim()) : null;

  for (const tema of ["light", "dark"]) {
    const ctx = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 1,
      colorScheme: tema,
      locale: "tr-TR",
    });
    const page = await ctx.newPage();

    // Konsol hatalarini topla — gorsel denetimin yakalayamadigi kusur burada
    const konsolHatalari = [];
    page.on("console", (m) => {
      if (m.type() === "error") konsolHatalari.push(m.text().slice(0, 200));
    });
    page.on("pageerror", (e) => konsolHatalari.push(`pageerror: ${String(e).slice(0, 200)}`));

    // Basarisiz istekleri URL'SIYLE yakala.
    //
    // Konsol "Failed to load resource: 403 (Forbidden)" diyor ve HANGI
    // kaynak oldugunu SOYLEMIYOR. Bu haliyle rapor bir sey bulundugunu
    // bildiriyor ama iz surulemiyor — denetimin ise yaramasi icin adres sart.
    page.on("response", (r) => {
      const k = r.status();
      if (k >= 400 && !r.url().includes("/_next/")) {
        konsolHatalari.push(`HTTP ${k}  ${r.url().replace(API, "")}`);
      }
    });

    let aktifRol = null;
    for (const [ad, yol, rol, , sekme] of SAYFALAR) {
      if (secili && !secili.some((s) => ad.includes(s) || yol.includes(s))) continue;
      const oncekiHataSayisi = konsolHatalari.length;
      try {
        if (rol && rol !== aktifRol) {
          const ok = await girisYap(page, rol);
          aktifRol = ok ? rol : null;
        }
        // networkidle YOK: canli alarm WebSocket'i acik kaldigi icin ag asla
        // bosalmiyordu ve her sayfa 30 sn timeout'a giriyordu (bizzat yasandi).
        await page.goto(`${BASE}${yol}`, { waitUntil: "domcontentloaded", timeout: 20000 });
        await temaAyarla(page, tema);
        // Icerigin gelmesini bekle: iskelet yerine gercek ekran gorunsun
        await page.waitForLoadState("load", { timeout: 10000 }).catch(() => {});
        await page.waitForTimeout(2200);

        // Alt sekme: URL degismedigi icin tiklamak zorunlu
        if (sekme) {
          await page.getByRole("button", { name: sekme }).first()
            .click({ timeout: 8000 });
          await page.waitForTimeout(2500);  // canli model listesi gelsin
        }

        // HATA SINIRI KONTROLU — bu olmadan cokmus bir sayfa "basarili"
        // sayiliyordu: ekran goruntusu alinir, dosya yazilir, rapor yesil
        // gorunur. Analitik sayfasi tam boyle gozden kacti (B37).
        const hataSiniri = await page.evaluate(() => {
          const t = document.body?.innerText || "";
          if (/Bir şeyler ters gitti|Something went wrong/i.test(t)) {
            const satirlar = t.split("\n").map((x) => x.trim()).filter(Boolean);
            const ipucu = satirlar.find((x) =>
              /is not a function|undefined|is not iterable|Cannot read|null/.test(x));
            return (ipucu || "hata siniri devrede").slice(0, 120);
          }
          return null;
        }).catch(() => null);

        const dosya = path.join(OUT, `${ad}-${tema}.png`);
        // fullPage cok uzun sayfalarda headless shell'i cokerttigi icin yukseklik
        // sinirlaniyor: 3200px hem tum ekrani gosteriyor hem guvenli.
        const yuk = await page.evaluate(() =>
          Math.min(document.documentElement.scrollHeight, 3200));
        await page.setViewportSize({ width: 1440, height: yuk });
        await page.waitForTimeout(300);
        await page.screenshot({ path: dosya });
        await page.setViewportSize({ width: 1440, height: 900 });
        rapor.push({
          sayfa: ad, yol, tema, rol, dosya,
          durum: hataSiniri ? "COKTU" : "ok",
          hata_siniri: hataSiniri,
          url: page.url(),
          konsol_hatalari: konsolHatalari.slice(oncekiHataSayisi),
        });
        console.log(hataSiniri
          ? `  ✗ ${ad} (${tema}) SAYFA COKTU: ${hataSiniri}`
          : `  ✓ ${ad} (${tema})`);
      } catch (e) {
        rapor.push({ sayfa: ad, yol, tema, rol, durum: "hata", hata: String(e).slice(0, 300) });
        console.log(`  ✗ ${ad} (${tema}): ${String(e).slice(0, 120)}`);
      }
    }
    await ctx.close();
  }

  await browser.close();
  await writeFile(path.join(OUT, "_rapor.json"),
    JSON.stringify(rapor, null, 2), "utf-8");

  const coken = rapor.filter((r) => r.durum === "COKTU");
  const ok = rapor.filter((r) => r.durum === "ok").length;
  const hata = rapor.length - ok;
  const konsol = rapor.reduce((n, r) => n + (r.konsol_hatalari?.length || 0), 0);
  console.log(`\n${ok} görüntü alındı, ${hata} hata, ${konsol} konsol hatası`);
  console.log(`Rapor: ${path.join(OUT, "_rapor.json")}`);
}

main().catch((e) => { console.error(e); process.exit(1); });
