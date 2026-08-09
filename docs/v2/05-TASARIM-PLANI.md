# 05 — Tasarım Planı (FAZ 5.1)

> Kod yazılmadan önce üretildi. Dört skill fiilen okundu; aşağıda **hangisinin
> neyi belirlediği** tek tek yazılı.

---

## 0. Hangi skill neyi belirledi

| Skill | Bu planda neyi belirledi |
|---|---|
| **frontend-design** | Görsel dil, tipografi eşleşmesi, "imza öğesi" kavramı, AI-klişesi paletlerden kaçınma, kopya (metin) tonu |
| **ui-ux-pro-max** | Öncelik sırası (erişilebilirlik → dokunma → performans → stil), yoğunluk kararı, ters piramit bilgi mimarisi, semantik renk token disiplini |
| **web-design-guidelines** (vercel) | Erişilebilirlik, odak yönetimi, form, tablo, klavye, yükleme/boş/hata durumları ve hareket kuralları — hepsi denetlenebilir madde olarak |
| **vercel-react-best-practices** | İstek şelalesi kırma, dinamik import, gereksiz client component'ten kaçınma, sanallaştırma, re-render disiplini |

### Skill'lerin doğrudan uygulanan somut kuralları

`web-design-guidelines`'dan bu projede **denetlenecek** maddeler:
- İkon-yalnız butonlar `aria-label` ister
- `outline-none` yalnız odak değiştiricisiyle birlikte; `:focus-visible` tercih
- Eylem `<button>`, gezinme `<a>/<Link>` — `<div onClick>` yasak
- Dekoratif ikon `aria-hidden="true"`
- Async güncellemeler (toast, doğrulama) `aria-live="polite"`
- Tablo semantik: `<table>/<thead>/<tbody>/<th scope>`
- Yükleme metinleri `…` ile biter ("Yükleniyor…")
- Hata mesajı **düzeltme adımı** içerir, yalnız sorunu söylemez
- Boş dizide bozuk UI çizilmez
- `prefers-reduced-motion` saygısı; yalnız `transform`/`opacity` animasyonu;
  `transition: all` yasak
- Kaydedilmemiş değişiklikte gezinme uyarısı

`ui-ux-pro-max` öncelik tablosundan alınanlar:
- Öncelik 1 (KRİTİK): kontrast 4.5:1, klavye gezinme, aria etiketleri
- Öncelik 2 (KRİTİK): dokunma hedefi ≥ 44×44px, 8px+ aralık, yükleme geri bildirimi
- Öncelik 6: gövde metni ≥ 16px, satır yüksekliği 1.5, **bileşende ham hex yok**
- Öncelik 7: animasyon 150–300 ms, anlam taşımalı
- Anti-patern: emoji ikon olarak kullanılmaz → **mevcut sidebar'da 13 emoji ikon var, değişecek**

---

## 1. Ürünün konumu — tasarımın dayanağı

Bu bir pazarlama sayfası değil, **vardiya boyunca kullanılan bir operasyon
aracı**. Kullanıcı günde 30-50 çağrı inceleyen bir kalite uzmanı; ekranda
geçirdiği süre 6-8 saat. Bu üç şeyi belirler:

1. **Yoğunluk yüksek olmalı.** `ui-ux-pro-max` yoğunluk kadranında "dense/
   dashboard" (8-32px) tarafındayız. Bol boşluk burada zarafet değil, kaydırma
   demektir.
2. **Sakinlik zorunlu.** Doygun renk ve hareket, 8 saat sonra yorgunluk yaratır.
   Renk yalnız **anlam** taşır.
3. **Klavye birinci sınıf.** Fare ile 30 çağrı incelemek 8 dakika/çağrı demektir;
   hedef 2 dakika.

---

## 2. Renk sistemi

Mevcut `globals.css` zaten rol-tabanlı token kullanıyor (ham hex bileşende yok)
ve **korunuyor**. Eksik olan **semantik anlam katmanı** ekleniyor.

### Semantik roller (dekoratif renk YOK)
| Token | Anlam | Açık | Koyu |
|---|---|---|---|
| `--status-good` | kriter karşılandı, sistem sağlıklı | `#0ca30c` | `#0ca30c` |
| `--status-warning` | kısmen karşılandı, dikkat | `#fab219` | `#fab219` |
| `--status-serious` | yetersiz kanıt, insan onayı bekliyor | `#ec835a` | `#ec835a` |
| `--status-critical` | sıfırlayıcı ihlal, kriz | `#d03b3b` | `#d03b3b` |
| `--series-1` | veri serisi (tek seri; çok seride türetilir) | `#2a78d6` | `#3987e5` |

**Beş semantik renk** — `ui-ux-pro-max` sınırı 3-5. Dekoratif altıncı renk yok.

### Puan rozeti eşikleri TEK MERKEZDEN
`lib/scoreColor.ts` — bugün üç ayrı bileşen kendi eşiğini uyguluyor.
Sıfırlanmış çağrıda rozet **"0 — sıfırlayıcı ihlal"** ve tooltip'te gerekçe (B5).

### AI klişelerinden kaçınma (frontend-design)
Skill üç varsayılan görünüm sayıyor: krem + serif + terracotta; near-black +
asit yeşili; kenarlıksız gazete kolonları. **Üçü de kullanılmıyor.** Palet
nötr gri-mavi zemin üzerine yalnız semantik renk — bir operasyon konsolunun
kendi dünyasından geliyor, moda bir estetikten değil.

---

## 3. Tipografi

| Rol | Yüzey | Gerekçe |
|---|---|---|
| Arayüz / gövde | `Inter` (sistem yığını yedek) | Türkçe diakritikleri doğru, 13-16px'te net |
| Sayısal / veri | `Inter` + `font-variant-numeric: tabular-nums` | Puan sütunları **hizalı** olmalı; 89.6 ile 100.0 aynı genişlikte |
| Kod / teknik | `ui-monospace` | Yalnız geliştirici görünümünde |

**Üç seviye hiyerarşi** (skill sınırı): sayfa başlığı 20px/600 · bölüm 15px/600
· gövde 14px/400. Tarama boyut ve ağırlıkla yapılır, renkle değil.

Türkçe kuralı: **tüm sayısal veri `tabular-nums`**, puanlar her yerde **tek ondalık**.

---

## 4. Izgara ve yoğunluk

8px ızgara. Yoğunluk anahtarı: **sıkışık** (satır 36px) / **rahat** (satır 48px),
tercih `localStorage`'da. Varsayılan sıkışık — vardiya kullanıcısı için.

Gruplama **boşlukla** yapılır, kenarlıkla değil (`ui-ux-pro-max`: 8px ızgara
kenarlıktan etkili gruplama sağlar).

---

## 5. İmza öğesi — **kanıt-transkript bağı**

Prompt dosyasının önerisi aynen benimsendi, çünkü ürünün tüm iddiası bu:
**"her puanın kanıtı var."**

```
┌─ Kriter kartı ────────────────────┐     ┌─ Transkript ──────────────┐
│ KVKK / Aydınlatma        10/10 ●  │     │ 00:01 TEMSİLCİ  Netik...  │
│ Kayıt bildirimi ve aydınlatma      │     │ 00:05 TEMSİLCİ  Görüşme…  │◀── vurgulanır
│ yapıldı.                           │     │ 00:12 MÜŞTERİ   Faturam…  │
│ ▸ "Görüşmemiz kayıt altına…"  ⏱05 │────▶│                            │
└────────────────────────────────────┘     └────────────────────────────┘
        tıkla → ses 00:05'e atlar, satır vurgulanır, odak oraya gider
```

Cesaret **tek yere** harcanıyor (frontend-design: "spend your boldness in one
place"). Çevresindeki her şey sakin ve disiplinli.

Erişilebilirlik: kanıt bir `<button>`, `aria-label="Kanıta git: 5. saniye"`,
hedef satır `aria-current="true"` ve `scroll-margin-top` ile konumlanır.
`prefers-reduced-motion` açıksa kaydırma anında yapılır.

---

## 6. Bilgi mimarisi (B21, B24)

14 düz menü → **rol bazlı, 5 grup**:

```
İZLEME     Kokpit · Analitik
ÇALIŞMA    Çağrılar · İnceleme Kuyruğum · Kalibrasyon · Arama
EKİP       Temsilciler · Lig · Koçluk
KURULUM    Rubrik · Kampanyalar · Bilgi Bankası · Yasaklı Kelimeler
SİSTEM     Kullanıcılar · Güvenlik · ROI · Denetim Günlüğü
```

- Rolle ilgisiz öğe **gizlenir**, gri gösterilmez.
- Rol bazlı açılış: `kaliteci` → İnceleme Kuyruğum · `supervizor`/`yonetici` →
  Kokpit · `temsilci` → Kendi Karnem.
- Yönetim'deki 10 sekme → sol dikey alt-navigasyon (B24 taşması biter).
- **Emoji ikonlar kaldırılıyor** (`ui-ux-pro-max` anti-pattern: "Emoji as icons").
  Yerine inline SVG; `aria-hidden="true"`.

---

## 7. Dört durum — istisnasız

`web-design-guidelines`: boş dizide bozuk UI çizilmez.

| Durum | Kural |
|---|---|
| Yükleniyor | İskelet (spinner yalnız <1 sn işlemde); metin "…" ile biter |
| Boş | **ne yok + neden + tek eylem** — "Henüz inceleme yok. Çağrılar puanlandıkça kuyruk dolar. → Çağrı yükle" |
| Hata | **ne oldu + ne yapmalı**; özür yok, "bir şeyler ters gitti" yok |
| Dolu | — |

Backend zaten bu dili konuşuyor: `stats_honesty` "yeterli veri yok + ne
gerekiyor" döndürüyor, `security_checks` "nasıl açılır" döndürüyor. Arayüz bu
alanları **gösterecek**, kendi metnini uydurmayacak.

---

## 8. Performans (vercel-react-best-practices)

| Kural | Bu projede |
|---|---|
| `async-parallel` | Kokpit verisi `Promise.all` — sıralı `await` zinciri yok |
| `bundle-dynamic-imports` | Grafik bileşenleri `next/dynamic` |
| `server-serialization` | Client component'e minimum veri |
| `rerender-memo` | Uzun listelerde satır bileşeni memo |
| virtualize-lists | Çağrı listesi sanal kaydırma + sunucu sayfalama |

**Ölçüm zorunlu:** Kokpit ve Çağrılar için önce/sonra LCP, INP, bundle boyutu.

---

## 9. Bilinçli olarak YAPILMAYACAKLAR

- **Grafik kütüphanesi eklenmiyor.** Mevcut `TrendChart` saf SVG; bir kütüphane
  bundle'a 40-100 KB ekler ve `bundle-` kuralına aykırı olur.
- **Animasyon kütüphanesi yok.** Gerekli hareket CSS `transform`/`opacity` ile.
- **Tasarım sistemi kütüphanesi yok.** Mevcut token seti yeterli; shadcn/ui
  eklemek 200+ dosya getirir ve kazanç sağlamaz.
- **Mobil öncelikli tasarım yapılmıyor** ama mobilde **bozulmuyor**. Kullanıcı
  masaüstünde çalışıyor; bunu varsaymak dürüst, mobili kırmak değil.
