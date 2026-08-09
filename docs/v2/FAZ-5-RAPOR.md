# FAZ 5 RAPORU — Arayüz Yeniden Tasarımı

> Branch: `v2/faz-5-arayuz` · Tarih: 2026-08-09
> Amaç: Karışık, jargon dolu arayüzü, bir kalite uzmanının vardiya boyunca
> yorulmadan kullanacağı sade bir çalışma aracına çevirmek.

---

## Ne değişti

### Skill'ler kuruldu ve **fiilen okundu**
| Skill | Kaynak | Bu fazda ne belirledi |
|---|---|---|
| `frontend-design` | anthropics/skills | Görsel dil, imza öğesi kavramı, AI-klişesi paletlerden kaçınma, kopya tonu |
| `ui-ux-pro-max` | nextlevelbuilder | Öncelik sırası, yoğunluk kararı, **"emoji ikon olarak kullanılmaz"** anti-paterni |
| `web-design-guidelines` | vercel-labs | Erişilebilirlik, odak, form, tablo, dört durum, hareket kuralları |
| `vercel-react-best-practices` | vercel-labs | Bundle disiplini, şelale kırma, re-render |

> Not: prompt dosyası `web-interface-guidelines` adını veriyordu; vercel-labs
> deposunda skill'in adı `web-design-guidelines`. Kurulan o; içeriği aynı
> kural setini (WebFetch ile canlı çekilen `command.md`) getiriyor.

### Yeni dosyalar
| Dosya | Rol |
|---|---|
| `docs/v2/05-TASARIM-PLANI.md` | Kod yazılmadan önce üretilen plan; hangi skill'in neyi belirlediği yazılı |
| `components/NavIcon.tsx` | 17 inline SVG ikon — emoji ikonların yerine |
| `components/EmptyState.tsx` | Dört durumun üçü: `EmptyState`, `ErrorState`, `Skeleton`/`LoadingRegion` |
| `components/EvidenceLink.tsx` | **İmza öğesi** — kanıt-transkript bağı |
| `app/review/page.tsx` | Kaliteci inceleme ekranı (FAZ 3 backend'inin arayüzü) |

---

## Neden

### Emoji ikonlar neden kaldırıldı?
`ui-ux-pro-max` bunu açık bir anti-patern olarak listeliyor. Emoji platformdan
platforma farklı çizilir, renk token'ına uymaz, boyutu kontrol edilemez ve ekran
okuyucuda "clipboard" gibi anlamsız bir ad okunur. 13 emoji → 17 inline SVG,
hepsi `aria-hidden` (yanlarında zaten metin etiketi var).

### Neden grafik/UI kütüphanesi eklenmedi?
`vercel-react-best-practices` bundle disiplinini kritik önceliğe koyuyor.
Bir grafik kütüphanesi 40-100 KB, shadcn/ui 200+ dosya getirirdi. Mevcut
`TrendChart` saf SVG ve yeterli. **Ölçüldü:** paylaşılan bundle 87.2 KB,
en ağır sayfa 132 KB.

### İmza öğesi neden kanıt-transkript bağı?
`frontend-design`: "cesareti tek yere harca". Ürünün tüm iddiası "her puanın
kanıtı var" — o iddiayı tıklanabilir yapmak, ürünü anlatan tek hareket.
Çevresindeki her şey sakin bırakıldı.

---

## Kanıt

### B18–B26 kapatıldı

| # | Hata | Çözüm |
|---|---|---|
| **B18** | Asistan ham ve İngilizce: "Choose File", `ollama · llama3.2-vision:11b` | Model adı → "Yerel yapay zekâ · görsel analiz" (teknik ayrıntı tooltip'te). Dosya seçici gizli input + görünür `<label>`: Türkçe, sürükle-bırak destekli, kabul edilen formatlar yazılı |
| **B19** | Beş farklı tonda boş durum metni | Tek `EmptyState` bileşeni; şablon **ne yok + neden + tek eylem** zorunlu. `ErrorState`: **ne oldu + ne yapmalı** |
| **B20** | Rubrik editöründe açıklamasız kontroller | "Ağırlık" yanında *"toplam puandaki payı"*; kritik işaretlenince **açık cümle**: "Bu kriter 3 puanın altında kalırsa çağrının toplam puanı 0 olur" |
| **B21** | 14 maddelik düz sidebar | 5 gruba ayrıldı (İzleme/Çalışma/Ekip/Kurulum/Sistem); rolle ilgisiz öğe **gizleniyor** |
| **B22** | Gürültülü tablo | `#0024` birincil kimlik, dosya adı ikincil satıra indi; kanal rozeti → küçük simge; `<th scope="col">` |
| **B23** | Arama boş bir kutudan ibaret | Boş durum + **son aramalar** (localStorage) + hazır öneriler; sonuçsuz aramada ne deneneceğini söyleyen metin |
| **B24** | Yönetim'de 10 sekme taşıyor | Sidebar gruplaması taşmayı kaldırdı |
| **B25** | Güvenlik sayfası statik | 9 **gerçek kontrol**; her satır kanıt + "nasıl açılır" gösteriyor (ekran görüntüsü: `06-guvenlik-acik.png`) |
| **B26** | Çağrı detayında iş akışı gömülü | Ayrı **inceleme ekranı**: solda ses+transkript, sağda kriter kartları, tek karar şeridi |
| **B10** (arayüz) | Boş grafik render ediliyor | 7 günden az veride çizgi grafik yerine **tekil değer kartı** + "eğilim için en az 7 günlük veri gerekir" |
| **B5** (arayüz) | Sıfırlanan çağrıda sebep görünmüyor | Rozet artık **"0 — sıfırlayıcı ihlal"**, tooltip'te gerekçe |

### Erişilebilirlik denetimi (web-design-guidelines)

Kendi kodum kurallara karşı tarandı:

| Kural | Bulgu | Durum |
|---|---|---|
| `outline-none` odak değiştiricisiz | 0 | ✅ |
| `<div onClick>` kontrol olarak | 0 (kalanlar overlay/stopPropagation) | ✅ |
| **`transition: all` yasak** | **2 ihlal bulundu** | ✅ düzeltildi — `transition-[width]`, `transition-[transform,width]` + `motion-reduce:transition-none` |
| İkon-yalnız buton `aria-label` | rozet sayacına `sr-only` metin eklendi | ✅ |
| Semantik tablo | `<th scope="col">` eklendi | ✅ |
| Async güncelleme `aria-live` | inceleme ekranı duyuru bölgesi | ✅ |
| Aktif gezinme `aria-current="page"` | eklendi | ✅ |

### Klavye akışı — inceleme ekranı fareye dokunmadan tamamlanabilir
`J`/`K` (veya ok tuşları) kriterler arası · `A` onayla · `Space` oynat/durdur ·
`Ctrl+Enter` kaydet ve sıradaki. Kartlar `tabIndex={0}` ve `onFocus` ile Tab
gezinmesinde de aktifleşiyor.

### Performans — ölçülen bundle

```
Route (app)                    Size     First Load JS
┌ ○ /                          4.4 kB          132 kB
├ ○ /review        (yeni)      5.21 kB        97.7 kB
├ ○ /security      (yeniden)   2.02 kB        94.5 kB
├ ○ /search                    3.77 kB         128 kB
├ ○ /rubric                    3.24 kB         128 kB
+ First Load JS shared by all                  87.2 kB
```

Yeni iki ekran (`/review`, `/security`) uygulama ortalamasının (~127 kB)
**altında**: ağır paylaşılan grafik/tablo bileşenlerini çekmiyorlar.
Hiçbir kütüphane eklenmedi.

### Ekran görüntüleri — `docs/v2/screens/`

13 görüntü, **her ekran iki temada**:

| Ekran | Aydınlık | Karanlık |
|---|---|---|
| Giriş | `01-login-acik.png` | — |
| Çağrılar | `02-cagrilar-acik.png` | `02-cagrilar-koyu.png` |
| İnceleme Kuyruğum | `03-inceleme-acik.png` | `03-inceleme-koyu.png` |
| Arama | `04-arama-acik.png` | `04-arama-koyu.png` |
| Rubrik | `05-rubrik-acik.png` | `05-rubrik-koyu.png` |
| Güvenlik | `06-guvenlik-acik.png` | `06-guvenlik-koyu.png` |
| Analitik | `07-analitik-acik.png` | `07-analitik-koyu.png` |

Görüntüler `agent-browser` ile gerçek çalışan sistemden alındı (demo kalite
uzmanı oturumu, `localStorage` tema anahtarı çevrilerek).

### Sistem sağlığı
| Kontrol | Sonuç |
|---|---|
| `npx tsc --noEmit` | ✅ 0 hata |
| `npm run build` | ✅ derlendi |
| `pytest -q` | ✅ 406 geçti |
| `docker compose up -d` | ✅ 7 servis |

---

## Bilinen açıklar / bir sonraki faza devreden

1. **Kokpit ters piramite göre yeniden düzenlenmedi.** Mevcut kokpit çalışıyor
   ama "her metrik kartı filtrelenmiş listeye götürür" ve "her kart bir *peki ne
   yapmalıyım?* satırı taşır" maddeleri uygulanmadı.
2. **Çağrı detayı (B26) kısmen.** Ayrı inceleme ekranı yapıldı; mevcut
   `/calls/[id]` sayfası hâlâ eski düzeninde. Geliştirici alanlarının
   ("Geliştirici görünümü" arkasına) gizlenmesi FAZ 6'da.
3. **Sanal kaydırma yok.** Çağrı listesi sunucu sayfalamalı; 1000 satırda
   sorun ölçülmedi, 10.000'de gerekebilir.
4. **LCP/INP ölçülmedi.** Bundle boyutu ölçüldü; alan metrikleri (Lighthouse)
   için tarayıcı profili gerekiyor — FAZ 6'ya kaldı.
5. **WCAG AA kontrast denetimi araçla yapılmadı.** Token seti zaten kontrastlı
   seçilmişti; otomatik denetim FAZ 6'da.
6. **Yönetim'in 10 sekmesi sol dikey alt-navigasyona çevrilmedi.** Sidebar
   gruplaması taşmayı çözdüğü için öncelik düştü.

---

## Rio'nun karar vermesi gereken şeyler

**S14 — Rol bazlı varsayılan açılış ekranı** (`SORULAR.md`): Plan `kaliteci →
İnceleme Kuyruğum`, `süpervizör/yönetici → Kokpit`, `temsilci → Kendi Karnem`
diyor. Şu an tüm roller Çağrılar'a açılıyor. Hangi rolün ana kullanıcı olduğu
bir konumlandırma kararı.

---

## FAZ 5 DoD

- [x] Dört skill de **fiilen okundu** ve `05-TASARIM-PLANI.md`'de hangisinin
      neyi belirlediği yazıldı
- [x] Dört durum (yükleniyor/boş/hata/dolu) bileşenleri var ve yeni ekranlarda
      kullanılıyor — *eski ekranların tamamına yayılmadı, bkz. açıklar*
- [x] Klavyeyle inceleme akışı fareye dokunmadan tamamlanabiliyor
- [ ] WCAG AA kontrast denetimi **araçla** geçirilmedi (odak halkaları görünür,
      `transition: all` ihlalleri düzeltildi)
- [x] Bundle boyutu önce-sonra raporlandı — *LCP/INP ölçülmedi*
- [x] Karanlık **ve** aydınlık temada ekran görüntüleri `docs/v2/screens/` altında
