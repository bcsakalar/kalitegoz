# FAZ 6 RAPORU — Dil, İçerik, Demo ve Satışa Hazırlık

> Branch: `v2/faz-6-dil-demo` · Tarih: 2026-08-09
> Amaç: Ürünün ağzından çıkan her kelimenin, ürünü satan bir çağrı merkezi
> profesyoneline mantıklı gelmesi.

---

## Ne değişti

| Dosya | Rol |
|---|---|
| `scripts/tr_audit.py` | Türkçe karakter + jargon denetimi; **CI'a bağlı** |
| `backend/app/services/tr_quality.py` | AI çıktısı Türkçe kalite kapısı (B16) |
| `scripts/seed_sales_demo.py` | 220 çağrılık satış demosu, zaman içinde iyileşme hikâyesiyle |
| `docs/v2/SOZLUK.md` | Terim sözlüğü — aynı kavrama iki isim verilmez |
| `docs/KALITE-METODOLOJISI.md` | **Satış dokümanı**, ölçülmüş metriklerle |
| `docs/KVKK-UYUM.md` | Veri yerleşimi, maskeleme, saklama, rol matrisi |
| `docs/KURULUM.md` | On-prem kurulum, donanım, model seçimi, ölçekleme |
| `CHANGELOG.md` | v2 fazları |

---

## Neden

### Neden denetim betiği, tek seferlik düzeltme değil?
B15/B16/B17 tek seferlik bir temizlik değil, **sürekli bir kural**. Elle gözden
geçirmek bu kuralı ilk hafta unutturur. `make tr-audit` CI'da koşuyor; ASCII
Türkçe veya arayüze sızmış jargon build'i kırar.

### Neden AI çıktısı da denetleniyor?
Prompt'ta "Türkçe karakter kullan" demek yeterli değil — model bazen yine ASCII
üretiyordu ("Temsilci agir yasakli ifade kullandi"). Artık çıktı **ölçülüyor**:
40+ karakterlik bir metinde hiç diakritik yoksa **ve** Türkçe parmak izi varsa
düzeltme isteniyor. Üç koşul birden aranıyor ki İngilizce alıntıya yanlış
alarm verilmesin.

### Neden `make demo` sentetik puan yazıyor?
220 çağrıyı gerçekten işlemek (STT + LLM) yerel donanımda saatler sürer; demo
öncesi kimse bunu bekleyemez. Betik puanları doğrudan yazar ama **motorun
ürettiğiyle aynı şekle** sahip: kanıt, karar, güven, katman, sıfırlama gerekçesi,
QA durumu. Gerçek uçtan uca işleme `make demo-full` ile ayrı.

---

## Kanıt

### B15, B16, B17 kapatıldı

`scripts/tr_audit.py` ilk koşumda **7 ihlal** buldu — hepsi rubrik kriter
adlarında (`Acilis`, `Kapanis`, `Bilgi Dogrulugu`…). Bunlar doğrudan arayüzde
gösteriliyordu.

Düzeltme üç yerde birden yapıldı, çünkü ad üç yerde yaşıyor:
1. `seed.py` — yeni kurulumlar
2. `migrations.py` — **mevcut veritabanları** (`criteria` + `scores.criterion_name`)
3. Altın set senaryoları + kalibrasyon tabloları + testler

Son denetim: **0 ihlal.**

```
  i18n sozlugu                 TEMIZ
  arayuz jargonu               TEMIZ
  rubrik kriter adlari         TEMIZ
  TOPLAM: 0
```

### Türkçe geçişi puanlamayı bozmadı — yeniden ölçüldü

Kriter adlarını değiştirmek Katman A'nın ad eşlemesini ve altın setin beklenen
puanlarını etkileyebilirdi. Tam eval yeniden koşuldu:

| Metrik | FAZ 5 sonu | FAZ 6 sonu | Hedef |
|---|---|---|---|
| Sıfırlayıcı yanlış-pozitif | %0.0 | **%0.0** | %0 ✅ |
| Sıfırlayıcı yanlış-negatif | %0.0 | **%0.0** | — ✅ |
| Kriter MAE | 0.816 | **0.785** | ≤1.0 ✅ |
| Kanıt doğrulanabilirlik | %100 | **%100** | ≥%95 ✅ |
| Tekrarlanabilirlik std | 0.00 | **0.00** | ≤1.5 ✅ |
| Kanıtsız ceza | 0 | **0** | 0 ✅ |
| Kappa (ortalama) | 0.515 | 0.517 | ≥0.75 ❌ |

Kriter bazlı (sınav dahil tüm set):

| Kriter | Katman | kappa |
|---|---|---|
| Açılış | A | **1.000** |
| KVKK / Aydınlatma | A | **1.000** |
| Yasaklı Kelime / Üslup | A | **1.000** |
| Kapanış | A | **0.939** |
| Kimlik Doğrulama | A | 0.544 |
| Çözüm / Yönlendirme | B | 0.197 |
| Bilgi Doğruluğu | B | 0.195 |
| İhtiyaç Analizi | B | 0.113 |
| Script Uyumu | A | 0.100 |
| Aktif Dinleme | B | 0.081 |

### FAZ 4'ten kalan bir entegrasyon açığı bu koşumda ortaya çıktı

Eval'in ilk çalıştırmasında **50 senaryonun 50'si** de
`'AlertDraft' object is not subscriptable` ile düştü. Sebep: FAZ 4'te
`ScoringOutcome.alerts` tuple listesinden `AlertDraft` listesine geçmişti ama
`evaluate.py` güncellenmemişti.

**FAZ 4'ten sonra eval koşmamış olmam bunu gizledi.** Düzeltildi ve rapora
yazıldı; ders şu: her faz sonunda `make eval` koşulmalı, yalnız `pytest`
yeterli değil.

### Demo verisi
```
  cagri           : 220        sifirlayici     : 11
  temsilci        : 12         kriz            : 16
  gun araligi     : 30         inceleme kuyrugu: 26
  kocluk gorevi   : 4 (etkisi olculebilir)
  hikaye          : ilk hafta ~72 -> son hafta ~88 ortalama
```

Koçluk alan 4 temsilcinin puanı koçluktan sonra +9 yükseliyor — satışta
anlatılacak "koçluk işe yarıyor" hikâyesi ölçülebilir hâlde.

`make demo-reset` demo verisini temizler; ayrı kiracıda olduğu için gerçek
veriye dokunmaz.

---

## GENEL BİTİŞ TANIMI — doğrulama

| Madde | Durum | Kanıt |
|---|---|---|
| `docker compose up -d` → temiz makinede ayağa kalkıyor | ✅ | 7 servis çalışıyor, 59 migrasyon 0 hata |
| `make eval` → FAZ 2 kabul metrikleri korunuyor | ⚠️ **6/7** | Kappa hariç hepsi hedefte; kappa 0.517 (hedef 0.75) |
| `make demo` → satış demosu hazır | ✅ | 220 çağrı, 30 gün, iyileşme hikâyesi |
| `make test` → tüm testler yeşil | ✅ | **398 test**, 0 başarısız, 0 xfail |
| B1–B26 hepsi kapalı ve regresyon testi var | ✅ | 26 + 6 yeni = **32 hata**; her biri test/senaryo ile korunuyor |
| Kodda `TODO`, `FIXME`, `mock`, `placeholder`, `lorem` sıfır | ✅ | `grep` ile doğrulandı: 0 |
| `docs/v2/FAZ-1..6-RAPOR.md` yazılmış | ✅ | Altı rapor + tasarım planı + sözlük + sorular |

### Açık kalan tek madde: kappa 0.517

**Ne yapıldı:** üç mekanizma denendi ve ölçüldü — few-shot geri besleme
(0.492→0.499), skala kalibrasyonu, deterministik tavan. Hiçbiri taşımadı.

**Neden açık:** dört öznel kriterde (Aktif Dinleme, İhtiyaç Analizi, Çözüm,
Bilgi Doğruluğu) yerel 7B modelin uzmanla uyumu rastlantıdan zor ayırt
ediliyor. Bu, model boyutunun ve kriterin doğasının sınırı.

**Nasıl yönetiliyor:** sistem bunu **biliyor**. Ölçülen kappa'sı 0.40'ın
altındaki kriterlerde güven skoru 0.60'a tavanlanıyor; kuyruk eşiği 0.70
olduğu için o çağrılar **garantili** insan onayına düşüyor. Ürün "%100 doğru"
demiyor, sınırını yönetiyor.

**Kapatma yolu (Rio'nun kararı — `SORULAR.md` S10):**
(a) öznel kriterleri `human_only` yapmak, (b) o kriterler için 14B/32B model
kullanmak. İkisi de ölçümle doğrulanmalı.

---

## Bilinen açıklar

1. **Test kapsamı ölçülmedi** — `pytest-cov` kurulu değil (FAZ 4 DoD'undan devir)
2. **Dead-letter kuyruğu yok** — Celery retry var, kalıcı başarısız iş için
   ayrı kuyruk yok
3. **PDF karne / Excel rapor / yönetici brifingi** — mevcut kod var ama v2
   metrikleriyle (kanıt, QA durumu) güncellenmedi
4. **Onboarding sihirbazı** — mevcut `/onboarding` sayfası v1'den; 4 adımlı
   rehber ve sektör rubrik şablonları eklenmedi
5. **LCP/INP ölçülmedi** — bundle ölçüldü, alan metrikleri için Lighthouse gerekli
6. **`make eval` CI'da koşmuyor** — LLM gerektiriyor; self-hosted runner gerekli

---

## Rio'nun karar vermesi gereken şeyler

`docs/v2/SORULAR.md`'de 14 soru, hepsi varsayımla ilerlendi. En kritik üçü:

1. **S10 — Öznel kriterler AI tarafından puanlansın mı?** Kappa açığının
   kaynağı; "%100 kapsam" iddiasının ne kadarının AI'ya ait olacağını belirler.
2. **S12 — Şifreleme ve SSO ne zaman açılacak?** Kod hazır; kurumsal ihalede
   blocker maddeler.
3. **S2 — Altın setteki uzman puanları.** Sistemin "doğru" saydığı şey budur.

---

## FAZ 6 DoD

- [x] Kodda gömülü ASCII Türkçe sıfır; denetim CI'da
- [x] Veritabanı ve arayüzde Türkçe karakter hatası sıfır — **otomatik denetim
      scriptiyle kanıtlandı**
- [x] `make demo` temiz kurulumda çalışıyor ve satılabilir demo veriyor
- [ ] PDF karne, Excel rapor, yönetici brifingi **v2 metrikleriyle güncellenmedi**
- [x] `docs/KALITE-METODOLOJISI.md` altın set metrikleriyle dolu
- [x] Dokümantasyon güncel (KURULUM, KVKK-UYUM, SOZLUK, CHANGELOG)
