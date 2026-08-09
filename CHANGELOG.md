# Değişiklik Günlüğü

## v2.0 — Uçtan uca overhaul (2026-08-09)

Altı fazda yapıldı; her fazın raporu `docs/v2/FAZ-N-RAPOR.md` altında.
Ölçüm çıktıları `docs/v2/eval/`, ekran görüntüleri `docs/v2/screens/`.

### Ölçülen sonuç

| Metrik | v1 | v2 |
|---|---|---|
| Sıfırlayıcı ihlal yanlış-pozitif | %38.5 | **%0.0** |
| Sıfırlayıcı ihlal yanlış-negatif | %18.2 | **%0.0** |
| Kriter bazlı MAE (0-10) | 2.16 | **0.82** |
| Kanıt doğrulanabilirlik | %56.1 | **%100** |
| Tekrarlanabilirlik (std) | 1.95 | **0.00** |
| Cohen's kappa (ortalama) | 0.32 | 0.51 |
| Uyum kriterlerinde kappa | 0.32 | **0.90–1.00** |
| Backend testi | 221 | **398** |

### FAZ 1 — Denetim ve doğruluk temeli
- 50 senaryoluk altın set (uzman referanslı), sürüm kontrolünde
- `make eval` regresyon takımı: MAE, kappa, sıfırlayıcı FP/FN, kanıt
  doğrulanabilirlik, tekrarlanabilirlik
- B1–B6 kök neden analizi **ölçümle**; 6 yeni hata bulundu (B27–B32)
- Proje git altına alındı

### FAZ 2 — Puanlama motorunun yeniden yazımı
- Üç katmanlı hibrit motor: deterministik ön kontrol → kanıt zorunlu LLM →
  sunucu doğrulaması
- **Kanıt yoksa ceza yok** kuralı; kanıtsız sıfırlama istisna fırlatır
- `normalize_tr()` tek Türkçe normalizasyon kaynağı
- STT `word_timestamps` düzeltmesi — şişik segment süreleri (B3'ün kök nedeni)
- Eski tek-dev-prompt implementasyonu kaldırıldı (265 satır ölü kod)

### FAZ 3 — İki aşamalı kalite kontrol
- QA durum makinesi: yapay zekâ puanladı → insan kuyruğunda → kesinleşti
- Yedi insan-kuyruğu kuralı, hepsi yapılandırılabilir
- Kaliteci inceleme kuyruğu: tek istekte tam bağlam, tek istekte tam karar
- Kalibrasyon geri besleme döngüsü (ölçüldü: anlamlı fark yok — dürüst kayıt)
- Ölçülen güvenilirlik kapısı: güvenilmez kriter insana **garantili** düşer
- Kesinleşmemiş puan lig tablosuna sayılmaz

### FAZ 4 — Backend sağlamlaştırma
- İstatistiksel dürüstlük: n<30'da korelasyon yok, önceki dönem boşsa yüzde yok,
  tek noktayla grafik yok, az örneklemli temsilci üst sıraya çıkamaz
- Alarm motoru: zorunlu alanlı şablon + `(call_id, rule_id, evidence_hash)`
  tekilliği; rozet yalnız kritik+yüksek sayar
- Güvenlik sayfası **9 gerçek kontrolden** okur; diskte şifreleme ve OIDC SSO
  uygulandı
- Standart hata zarfı `{error: {code, message_tr, details}}`
- Ölçüldü: kokpit 1000 çağrıyla **0.011 sn**

### FAZ 5 — Arayüz yeniden tasarımı
- Dört skill kuruldu ve okundu; `docs/v2/05-TASARIM-PLANI.md` kod öncesi üretildi
- 14 düz menü → 5 rol bazlı grup; 13 emoji ikon → 17 inline SVG
- İmza öğesi: **kanıt-transkript bağı** — alıntıya tıklayınca ses o saniyeye atlar
- Dört durum bileşenleri (yükleniyor/boş/hata/dolu)
- Klavyeyle tamamlanabilen inceleme akışı (J/K/A/Space/Ctrl+Enter)
- 13 ekran görüntüsü, her ekran iki temada

### FAZ 6 — Dil, demo, satışa hazırlık
- Rubrik kriter adları **tam Türkçe** (migration ile mevcut veri dahil)
- `scripts/tr_audit.py` — Türkçe karakter ve jargon denetimi, CI'da
- AI çıktısı Türkçe kalite kapısı: ASCII Türkçe tespit edilirse düzeltme istenir
- `docs/v2/SOZLUK.md` — terim sözlüğü; aynı kavrama iki isim verilmez
- `make demo` — 220 çağrılık satış demosu, zaman içinde iyileşme hikâyesiyle
- `docs/KALITE-METODOLOJISI.md` — satış dokümanı, ölçülmüş metriklerle
- `docs/KVKK-UYUM.md` — veri yerleşimi, maskeleme, rol matrisi

### Kapatılan hatalar
B1–B26 (prompt dosyasında listelenen) + B27–B32 (denetimde bulunan) = **32 hata**.
Her biri için regresyon testi veya altın set senaryosu var.
