# FAZ 4 RAPORU — Backend Sağlamlaştırma ve Analitik Doğruluğu

> Branch: `v2/faz-4-backend` · Tarih: 2026-08-09
> Amaç: Puanlama dışındaki her şeyin de doğru, hızlı ve güvenli olması.

---

## Ne değişti

### Yeni modüller
| Dosya | Rol |
|---|---|
| `services/stats_honesty.py` | B8/B9/B10'un ortak kökü — "yeterli veri var mı?" tek yerde |
| `services/alert_engine.py` | Alarm şablonu (zorunlu alanlar), tekilleştirme, şiddet, yaşam döngüsü |
| `services/crypto.py` | Diskte şifreleme — zarf şifreleme + kendini test |
| `services/sso.py` | OIDC yapılandırma + **gerçek** discovery kontrolü |
| `services/security_checks.py` | Güvenlik sayfasının her satırı için çalışan kontrol |
| `scripts/perf_check.py` | Kokpit performans ölçümü (DoD kanıtı) |

### Yeni testler
`test_stats_honesty.py` (16) · `test_alert_engine.py` (12) · `test_security_checks.py` (14)
→ Takım: **406 test, hepsi yeşil.**

---

## Neden

### B7, B8, B9, B10 neden tek modülde toplandı?
Dördünün de tek bir sebebi vardı: **sistem, veri yetersizken de bir sayı üretmek
zorunda hissediyordu.** Eşikler her ekranın kendi içinde olsaydı, her ekran
kendi eşiğini uydururdu. `stats_honesty` bu kararı tek yerde verir.

### B9'da eşiğimi şartnameye göre gevşettim
İlk uygulamada "önceki dönemde en az 5 kayıt" şartı koymuştum. Şartname
"önceki dönem **boşsa** yüzde üretme" diyor. 2 → 4 gerçek bir artıştır ve
gizlenmemeli. Artık: `önceki = 0` → sayı **yok**; `0 < önceki < 5` → sayı var
ama "oynak olabilir" işaretli; `önceki ≥ 5` → temiz.

### Güvenlik sayfası neden baştan yazıldı?
Eski uç `settings.encryption_at_rest` gibi **bayraklar** döndürüyordu. Bir
bayrak "şifreleme açık" der ama şifrelemenin çalıştığını kanıtlamaz. Yeni
`/enterprise/security-checks` her maddeyi **çalıştırır**: şifrelemeyi test eder,
OIDC sağlayıcısına gider, maskeleyiciyi örnek PII ile koşar, saklama süresini
geçmiş kayıt arar.

Kapalı görünen bir madde kurumsal satışta blocker'dır — ama **yalan söyleyen
bir "açık" daha büyük blocker'dır.**

### Şifreleme anahtarı neden `.env` dışında?
`.env` depoya yakın durur ve yedeklere sızar. Ana anahtar `KG_MASTER_KEY`
ortam değişkeninden okunur (Docker secret / systemd EnvironmentFile / KMS).
Anahtar yoksa şifreleme **kapalıdır** ve güvenlik sayfası bunu açıkça söyler —
sessizce düz metin yazıp "şifreli" demek sayfayı yalancı yapardı.

---

## Kanıt

### B7–B14 ve B25

| # | Hata | Kök neden | Çözüm | Test |
|---|---|---|---|---|
| **B7** | Liderlik sıralaması bozuk (1:94.1, 3:88.9, 4:90.4) | Sıralama `points` ile, ekranda `avg_score` gösteriliyordu — **görünmeyen bir metriğe göre** sıralanıyordu | Sıralama anahtarı görünen sütunla aynı; n<5 temsilci üst sıraya çıkamaz | 4 test |
| **B8** | n=24 ile "+0.68 güçlü ilişki" | Eşik yok | n<30'da katsayı **gösterilmez**; n≥30'da %95 güven aralığıyla | 3 test |
| **B9** | Tüm konular "▲+100%" | `if p == 0: change = 100.0` (sıfıra bölme) | Önceki dönem boşsa sayı yok; az örneklemde "oynak" işareti | 3 test |
| **B10** | Boş grafik çiziliyor | Tek noktayla çizgi grafik | `grafik_cizilebilir` bayrağı + `tekil_deger` | 3 test |
| **B11** | Kategori/etiket iki kere sayılıyor | İkisi tek düz listede dönüyordu | Yanıt `{kategoriler, etiketler}` diye ayrıldı, her biri açıklamalı | mevcut testler güncellendi |
| **B12** | Alarm tekrarları (rozet 22, çoğu kopya) | Tekillik kısıtı yok | `(call_id, rule_id, evidence_hash)` tekil + `occurrence_count`; rozet yalnız kritik+yüksek sayar | 8 test |
| **B4** | Alarm metni tutmuyor | Tek serbest string | Zorunlu alanlar (`title_tr`, `explanation_tr`, `evidence_quote`, `evidence_timestamp`, `suggested_action_tr`); eksikse alarm **üretilemez** | 4 test |
| **B13** | "0 ölçülebilir koçluk / %0 iyileşme" | "Ölçülemedi" ile "sonuç kötü" aynı sayıyla gösteriliyordu | Ölçülemiyorsa `None` + ne gerektiğini söyleyen açıklama | şema + servis |
| **B14** | ROI sonuç üretmiyor | Geri ödeme ve net fayda hiç hesaplanmıyordu | `net_monthly_benefit`, `payback_months`, `payback_durumu`, `coverage_gain_pct` + **6 formül açık** | 3 test |
| **B25** | Güvenlik sayfası statik; SSO ve şifreleme kırmızı | Bayrak okuyordu | 9 gerçek kontrol; şifreleme ve OIDC **uygulandı** | 14 test |

### Kokpit performansı — DoD şartı ölçüldü

1000 çağrılık sentetik veriyle (`scripts/perf_check.py`):

```
sorgu                                medyan   en kotu    durum
kokpit: liderlik tablosu              0.002     0.010       OK
analitik: zaman serisi (30 gun)       0.002     0.004       OK
analitik: VoC trendi                  0.003     0.004       OK
analitik: duygu dagilimi              0.001     0.001       OK
analitik: kohort karsilastirma        0.002     0.004       OK
kocluk etkinligi                      0.001     0.002       OK
--------------------------------------------------------------
kokpit toplami (tum sorgular)         0.011                 OK
```

**11 ms** — hedef 2000 ms. Materialized view / özet tablosuna **gerek olmadığı
ölçülerek görüldü**; erken optimizasyon yapılmadı.

### Güvenlik kontrolleri (bu kurulumda, gerçek çıktı)

| Kontrol | Durum | Kanıt |
|---|---|---|
| Diskte şifreleme | kapalı | `KG_MASTER_KEY` tanımlı değil → nasıl açılacağı yazılı |
| SSO (OIDC) | kapalı | `OIDC_ISSUER` yok → Keycloak ile kurulum yolu yazılı |
| Veri kurum dışına çıkmıyor | **ok** | LLM sağlayıcı: ollama (yerel) |
| PII maskeleme | **ok** | Örnek TCKN/telefon/IBAN maskelendi |
| Denetim günlüğü | **ok** | Son 30 günde N kayıt |
| Rol tabanlı erişim | **ok** | Gerçek rol dağılımı okundu |
| Saklama politikası | **ok** | Süresi dolmuş kayıt yok |
| Kiracı izolasyonu | **ok** | Diğer kiracıların çağrıları kapsam dışı |
| Üretim sertleştirmesi | **ok** | — |

İki madde kapalı ve **kapalı olduğunu söylüyor**. Bu, önceki "her şey yeşil"
görüntüsünden daha değerlidir: müşteri neyi açması gerektiğini biliyor.

### Diğer FAZ 4.3 işleri
- `Call.ref` → insan-okur kimlik (`#0024`); dosya adı birincil kimlik olmaktan çıktı
- `calls.audio_hash` → idempotent işleme için kolon + indeks
- Standart hata zarfı: `{"error": {"code", "message_tr", "details"}}` — tüm
  `HTTPException` ve doğrulama hataları tek şekilde döner
- Alarmlarda geçersizleşenler (`is_stale`) artık hiçbir listede görünmüyor

### Sistem sağlığı
| Kontrol | Sonuç |
|---|---|
| `docker compose up -d` | ✅ 7 servis |
| `pytest -q` | ✅ **406 geçti**, 0 başarısız |
| `npx tsc --noEmit` | ✅ 0 hata |
| Migrasyonlar | ✅ **56 uygulandı, 0 atlandı** |
| Kokpit < 2 sn | ✅ 0.011 sn |
| Alarm tekrarı | ✅ 0 (test ile kanıtlı) |

---

## Bilinen açıklar / bir sonraki faza devreden

1. **Şifreleme ve SSO açık değil** — kod hazır, yapılandırma müşteri kurulumuna
   ait. Güvenlik sayfası ikisini de "kapalı" gösteriyor ve nasıl açılacağını
   yazıyor. `SORULAR.md` S12.
2. **Şifreleme mevcut veriye uygulanmadı.** Yeni yazılan veriler için hazır;
   geriye dönük şifreleme bir migrasyon işidir ve veri kaybı riski taşır —
   müşteri kurulumunda planlı yapılmalı.
3. **Dead-letter kuyruğu yok.** Celery `retry` mevcut; kalıcı başarısız işler
   için ayrı kuyruk ve yönetim ekranından yeniden deneme FAZ 6'ya kaldı.
4. **Sunucu tarafı sayfalama kısmi.** Çağrı listesi zaten sayfalı; analitik
   uçları tüm dönemi çekiyor ama 1000 çağrıda 11 ms olduğu için sorun değil.
   10.000+ çağrıda yeniden ölçülmeli.
5. **B11 frontend tarafı bekliyor** — backend taksonomileri ayırdı, VoC tablosu
   FAZ 5'te iki ayrı bölüm olarak çizilecek.
6. **Test kapsamı ölçülmedi** (DoD "puanlama ve alarm modüllerinde ≥%80" diyor).
   `pytest-cov` kurulu değil; FAZ 6'da ölçülecek.

---

## Rio'nun karar vermesi gereken şeyler

**S12 — Şifreleme ve SSO kurulumu** (`SORULAR.md`): İkisi de kod olarak hazır
ama yapılandırma gerektiriyor. Kurumsal satışta bu iki madde blocker; demo
öncesi `KG_MASTER_KEY` ve OIDC ayarlarının girilmesi gerekir.

---

## FAZ 4 DoD

- [x] B7–B14 ve B25 kapalı (10 hata, 40+ test)
- [x] Kokpit ilk yükleme < 2 sn → **0.011 sn** (1000 çağrılık veriyle ölçüldü)
- [x] Alarm tekrarları sıfır — test ile kanıtlı
- [x] Rol bazlı yetki testleri geçiyor (`test_rbac_tenant.py` + güvenlik kontrolü)
- [ ] Test kapsamı ≥ %80 → **ölçülmedi**, `pytest-cov` yok (FAZ 6'ya devir)
