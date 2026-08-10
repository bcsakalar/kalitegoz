# Arayüz Denetimi — kendi çıktıma bakarak

> Tarih: 2026-08-10 · Araç: Playwright (`scripts/shots.mjs`)
> Kapsam: 16 sayfa × 2 tema = 32 ekran görüntüsü, `docs/screens/`
> Tur sayısı: 3 (ikisi zorunluydu, üçüncüsü ikinci turda bulunan kusurlar için)

Bu denetimin amacı "güzel mi" değil, **"çalışıyor mu"** sorusuydu. Ekran
görüntüsüne bakmak, koda bakmakla bulunamayacak bir sınıf hatayı ortaya
çıkardı: **sessizce hiçbir şey yapmayan stiller.**

---

## Aracın kendisi iki kez kırıldı

Denetim raporunun ilk bulgusu araç hakkında.

**1. `networkidle` hiç oturmuyor.** İlk sürüm her sayfayı `waitUntil:
"networkidle"` ile bekliyordu. Uygulamada canlı alarm WebSocket'i açık
durduğu için ağ **asla** boşalmıyor; her sayfa 30 saniye timeout'a girdi ve
50 dakikada 2 görüntü alınabildi. `domcontentloaded` + sabit bekleme ile
çözüldü.

**2. Giriş arayüzüne bağımlılık.** İkinci sürüm giriş formunu doldurmayı
deniyordu. Ama giriş ekranının görünümü sistemin durumuna bağlı: gerçek
kurum yoksa "Kurumunuzu oluşturun" ekranı çıkıyor ve form gizleniyor.
Araç, denetlemek istediği 16 sayfaya ulaşmak için giriş arayüzünün o anki
durumuna bağımlı olmamalı — oturum artık API üzerinden açılıp token
doğrudan `localStorage`'a yazılıyor. Giriş ekranı zaten ayrı bir kare olarak
çekiliyor.

---

## B35 — `make eval` giriş ekranını kırıyordu

**Bu, denetimin en değerli bulgusu ve tamamen tesadüfen çıktı.**

İlk turda 32 görüntünün 30'u **giriş sayfasıydı**. Sebep:

```
make eval  ->  "__golden__" kiracisi olusturur
/auth/config  ->  org_slug: "golden"   (ic kiraci "gercek kurum" sanildi)
tarayici  ->  POST /auth/login {tenant_slug: "golden"}
kullanicilar  ->  "demo" kiracisinda
sonuc  ->  HER GIRIS 401
```

Yani **`make eval` koşulan bir makinede arayüze hiç girilemiyordu.** Hiçbir
hata logu yok; sadece giriş çalışmıyor. Üstelik ortama bağlı: eval koşmamış
bir makinede sorun görünmüyor — "bende çalışıyor" türünden bir hata.

**Düzeltme:** Çift alt çizgiyle başlayan kiracı adı = iç kiracı, kullanıcıya
asla kurum olarak sunulmaz. `onboarding._gercek_kurum_sorgusu`.

**Düzeltmenin kendisi de bir hata içeriyordu** ve testler yakaladı: SQL
`LIKE` içinde `_` tek karakter jokeridir, dolayısıyla `name LIKE '__%'`
deseni **adı 2+ karakter olan her kurumu** eliyordu ve `primary_tenant`
`None` dönüyordu. `autoescape=True` ile çözüldü.

**Regresyon:** `backend/tests/test_internal_tenants.py` (6 vaka).

---

## Sessizce hiçbir şey yapmayan stiller

Ekran görüntülerine bakınca bazı durum göstergelerinin renksiz olduğunu fark
ettim. Kaynağı aramak sistematik bir sorunu ortaya çıkardı.

### 33 tanımsız CSS değişkeni kullanımı

| Kullanılan | Doğrusu | Kaç yerde |
|---|---|---|
| `var(--status-ok)` | `var(--status-good)` | 18 |
| `var(--status-warn)` | `var(--status-warning)` | 12 |
| `var(--series)` | `var(--series-1)` | 2 |

**Neden tehlikeli:** Tanımsız bir CSS değişkeni **hata vermez**, renk hiç
uygulanmaz. "Durum: iyi" göstergesi renksiz kalır ve kimse fark etmez —
çünkü konsolda bir şey yok, testler geçiyor, sayfa açılıyor.

Somut sonuç: kenar çubuğundaki **canlı bağlantı göstergesi hiç
görünmüyordu** (`bg-[var(--status-ok)]`).

### 12 tanımsız Tailwind renk sınıfı

| Sınıf | Sonuç |
|---|---|
| `bg-surface2` (10 yer) | Config'te tanımlı değil → native `<select>` tarayıcı varsayılanına düşüyor → **koyu temada beyaz kutu** |
| `text-danger` (2 yer) | Hata metni renksiz |

Kokpitteki "QA İnceleme Kuyruğu" formunun üç alanı koyu temada beyaz kutu
olarak görünüyordu. Değişkenler (`--surface-2`, `--status-critical`) zaten
vardı; eksik olan Tailwind config bağlantısıydı.

### Ders ve kalıcı önlem

Bu iki hata sınıfının ortak özelliği: **başarısızlıkları sessiz.** Yanlış
yazılmış bir değişken adı, çalışmayan bir kod satırından farklı olarak
hiçbir sinyal üretmez.

`scripts/ui_audit.py` bu kontrolleri kalıcı hale getirdi ve `make audit`
ile CI'a bağlandı:

```
Tailwind rounded-* sinifi          TEMIZ
inline borderRadius (0 disi)       TEMIZ
CSS border-radius (token disi)     TEMIZ
SVG rx/ry ozniteligi               TEMIZ
SVG yuvarlak uc                    TEMIZ
tanimsiz CSS degiskeni             TEMIZ
tanimsiz Tailwind rengi            TEMIZ
```

---

## Keskin köşe geçişi

**Tek kaynak:** `frontend/app/globals.css` içinde `--radius: 0`.

**İki katmanlı savunma:**

1. `tailwind.config.ts` içinde `borderRadius` ölçeği **ezildi** (extend
   değil): `none`'dan `full`'e her anahtar `var(--radius)`e çözülüyor.
   Yani ileride biri `rounded-lg` yazsa bile sonuç 0.
2. Markup'taki 124 `rounded-*` sınıfı 25 dosyadan **silindi**. Ölçek zaten
   tokena bağlı olduğu için bunlar işlevsizdi — ama duruyor olmaları sonraki
   geliştiriciye "burada yuvarlak köşe var" derdi. **Yanlış bilgi de bir
   hatadır.**

Ayrıca: 1 inline `borderRadius`, 2 SVG `strokeLinecap/Linejoin="round"`.

### Hiyerarşi neyle telafi edildi

Radius gidince "yüzen kart" hissi de gider. Üç şeyle karşılandı:

**Kenarlık ağırlığı.** Yeni `--border-strong` tokenı (açık temada
`rgba(11,11,11,0.16)`, koyuda `rgba(255,255,255,0.20)`). Kart, buton ve input
kenarlıkları buna geçti — yuvarlak köşe yokken zayıf bir çizgi, kartın nerede
bittiğini söylemeye yetmiyor.

**Gölge yeniden tanımlandı.** Kare köşede geniş-bulanık gölge "hata" gibi
görünür. `0 1px 2px + 0 4px 12px` yerine tek bir keskin `0 1px 0`.

**Tipografi.** `.eyebrow` sınıfı: 0.6875rem, 700 ağırlık, 0.08em harf
aralığı, büyük harf. Bölüm başlıklarından önce gelen "bu bölüm ne" işareti.

**Rozetler** hap şeklinden çıkınca anlam taşıyıcı olarak **2px sol kenar
şeridi** eklendi; renk + her zaman görünür metin kuralı korundu.

**Aktif nav işareti** yuvarlak "hap"tan tam yükseklik kenar şeridine
dönüştü — keskin dile uyuyor ve tarama sırasında daha net yakalanıyor.

---

## Erişilebilirlik düzeltmeleri

| Bulgu | Düzeltme |
|---|---|
| **Açık temada `--muted` AA'yı geçmiyordu** — `#8a8a86` beyaz üzerinde 3.46:1 (AA eşiği 4.5) | `#6f6f6b` → **5.05:1**. Koyu temadaki değer zaten 5.12:1 idi, dokunulmadı. |
| Odak halkası `:focus` kullanıyordu | `:focus-visible` — fareyle tıklamada halka çıkmıyor, klavyede çıkıyor. Kapsam genişletildi: `a`, `button`, `select`, `textarea`, `[tabindex]`. Kare köşede halka dikdörtgen olarak net okunuyor, `outline-offset: 2px`. |
| Butonlarda dokunma gecikmesi | `touch-action: manipulation` + `-webkit-tap-highlight-color: transparent` |
| Hareket tercihi yok sayılıyordu | `@media (prefers-reduced-motion: reduce)` — geçişler kapanıyor, işlev değişmiyor |
| Buton `:active` durumu yoktu | Eklendi; hover kenarlığı da `--border-strong`a çıkıyor (etkileşim kontrastı artırır kuralı) |

---

## Düzen ve içerik kusurları

| # | Bulgu | Düzeltme |
|---|---|---|
| 1 | Kenar çubuğu başlığında **iki ayrı `ml-auto`** — zil ve "canlı" etiketi birbirinden kopuyor, etiket kenara yapışıp kırpılıyordu | Tek sağ küme, tek `ml-auto`, `gap-2` |
| 2 | Kokpit "Konu keşfi" kartında **aynı metin hem butonda hem gövdede** ("Analiz ediliyor…") | Gövde artık ne beklendiğini söylüyor: "Çağrılar kümeleniyor — büyük veri setinde bir dakika sürebilir." |
| 3 | Yan yana kartlar birbirine göre geriliyor, altları düzensiz | Grid'lere `items-start` |
| 4 | Güvenlik sayfasındaki "NASIL AÇILIR" metni **S12 öncesinden kalma** — `KG_MASTER_KEY` ortam değişkeni öneriyordu | Dosya tabanlı anahtar (`KG_MASTER_KEY_FILE`) birinci sırada; SSO için "Yönetim → Kurumsal Kimlik ekranı" |

---

## Bakılıp kusur bulunmayan yerler

Dürüstlük için: her ekranda hata yoktu.

- **Tablolar** (Çağrılar, Temsilciler, Arama) — kare köşede hairline ayrımı
  net çalışıyor, satır yoğunluğu okunabilir.
- **İnceleme kuyruğu kriter kartları** — kanıt alıntısı, zaman damgası,
  onayla/düzelt eylemleri her iki temada da düzgün.
- **Güvenlik sayfası** — 9 kontrolün durumu, kanıtı ve "nasıl açılır" kutusu
  koyu temada okunaklı.
- **Kenar çubuğu taşması** — 900px yükseklikte son öğe fold altında kalıyor
  ama `overflow-y-auto` ile kaydırılabiliyor. Kusur sayılmadı.

---

## Bilinen sınırlar

**Görsel regresyon karşılaştırması yok.** Ekran görüntüleri alınıyor ama
öncekiyle piksel bazında karşılaştırılmıyor. Bir sonraki UI değişikliğinde
"ne değişti" sorusu yine gözle cevaplanacak.

*Neden yapılmadı:* Piksel karşılaştırması, veri değiştiğinde (yeni çağrı,
farklı puan) yanlış alarm üretir. Anlamlı olması için sabit veriyle çalışan
ayrı bir ortam gerekir. Bu turun kapsamını aşıyor; `docs/ROADMAP.md`'ye
yazıldı.

**Mobil görünüm denetlenmedi.** Tüm görüntüler 1440×900. Ürünün birincil
kullanımı masaüstü (kalite uzmanı gün boyu ekranda) ama kenar çubuğunun
mobil davranışı ölçülmedi.

**Ekran okuyucu ile test edilmedi.** ARIA etiketleri ve semantik HTML
kodda mevcut, ama gerçek bir ekran okuyucuyla gezilmedi.
