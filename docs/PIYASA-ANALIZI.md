# Piyasa Analizi — KaliteGöz nerede duruyor?

> Araştırma tarihi: 2026-08-10 · Kaynaklar dokümanın sonunda.
> Bu doküman satış broşürü değil; **eksiklerimizi de yazar.**

İncelenenler: MaestroQA (yeni adı **Rippit**), Klaus / **Zendesk QA**,
Scorebuddy, Level AI, Playvox, Observe.AI, Kaizo, Enthu.ai, EvaluAgent,
Convin, Solidroad + Türkiye'den Sonitel, Verimor, FGS, Zeno, VOİSCOPE.

---

## 1. Piyasanın 2026'daki ortak dili

Beş yıl önce QA yazılımı "elektronik değerlendirme formu" demekti. 2026'da
kategori ikiye ayrılmış durumda:

| | **QA iş akışı platformları** | **Konuşma zekâsı suit'leri** |
|---|---|---|
| Kimler | Zendesk QA, Scorebuddy, EvaluAgent, Kaizo | Observe.AI, Level AI, Cresta |
| Odak | İnceleme, kalibrasyon, koçluk, itiraz | %100 otomatik puanlama, gerçek zamanlı asist |
| Fiyat | Koltuk başı ~$20-60/ay | Kurumsal, teklife bağlı; **$100-500/ay/koltuk** aralığı raporlanıyor (Level AI için $185/temsilci/ay alıntılanmış) |

**KaliteGöz ikisinin arasında duruyor** ve bu bilinçli: otomatik puanlama +
insan onayı iş akışı bir arada, ama gerçek zamanlı asist yok.

### Herkeste standart olan sekiz şey

1. **AutoQA / %100 kapsam** — artık ayırt edici değil, giriş bileti.
2. **Özel skorkart** (ağırlık, kritik kriter, otomatik sıfırlama).
3. **Kalibrasyon oturumları** ve değerlendiriciler arası uyum takibi.
4. **Koçluk döngüsü** — bulgu → oturum → takip.
5. **İtiraz / dispute** akışı.
6. **Risk sinyali** (Zendesk QA buna "Spotlight" diyor): churn riski, ölü hava,
   uyum ihlali, aykırı değer.
7. **Temsilci öz değerlendirmesi** ve kendi karnesini görmesi.
8. **SSO/SAML/OIDC + rol bazlı erişim.**

**Bunların hepsi KaliteGöz'de var.** Bu, ürünün kategoriye girdiği anlamına
gelir — üstünlük anlamına gelmez.

---

## 2. Bizde olup piyasada nadir olanlar

Bunlar ürünün gerçek ayrışma noktaları ve hepsi ölçülmüş:

### 2.1 Kanıt zorunluluğu — "kanıt yoksa ceza yok"

Rakiplerin AutoQA'sı bir puan üretir; gerekçe metnini de LLM yazar. Bu metnin
transkriptte gerçekten geçip geçmediği **doğrulanmaz**.

KaliteGöz'de modelin gösterdiği her alıntı sunucuda transkriptte **aranır**;
bulunamazsa kriter puan almaz, `yetersiz kanıt` olur ve insana gider. Ölçüm:
kanıt doğrulanabilirliği **%56.1 → %100**.

Bunun ticari karşılığı şu: temsilci "bunu ben demedim" dediğinde ekranda
zaman damgalı ses parçası açılıyor. İtirazların çoğu orada bitiyor.

### 2.2 Deterministik katmanın LLM'i ezmesi

Açılış, KVKK anonsu, kimlik doğrulama, kapanış, yasaklı kelime **kodla**
çözülüyor; dil modeline hiç sorulmuyor. Ölçüm: bu kriterlerde üç ayrı koşumda
**kuruşu kuruşuna aynı** sonuç (kappa 1.00 / 1.00 / 1.00 / 0.94).

Rakiplerin hiçbiri "uyum kriterlerini LLM'e sormuyoruz" demiyor. Bir uyum
denetiminde "modelimiz genelde doğru buluyor" ile "bu kural kodda, çıktısı
tekrarlanabilir" arasında hukuki fark var.

### 2.3 Sınırını bilen ürün

`docs/KALITE-METODOLOJISI.md` kriter kriter hangi kriterde güvenilir olmadığını
**yazıyor** ve ölçülen kappa'sı 0.40'ın altındaki kriterlerde güven skorunu
otomatik tavanlayıp çağrıyı garantili insan onayına düşürüyor.

Piyasada standart olan "%95 doğruluk" iddiasının arkasında genelde ölçüm
metodolojisi yok. Kurumsal alımda teknik değerlendirme yapan taraf bunu sorar.

### 2.4 Tam yerel çalışma (on-prem, veri hiç çıkmaz)

Rakiplerin tamamı SaaS. Self-hosted seçenek sunanlar bile modeli kendi
bulutlarında çalıştırıyor. KaliteGöz, Ollama ile **kurumun kendi donanımında**
çalışıyor; ses ve transkript hiçbir zaman dışarı çıkmıyor.

Türkiye'de bankacılık, sigorta, kamu ve savunma alımlarında bu tek başına
eleyici kriter olabiliyor — araştırmada Türk sağlayıcıların da en çok
vurguladığı nokta "Türkiye lokasyonlu veri merkezi" idi. **Bizimki bir adım
öteye gidiyor: veri merkezi bile bizim değil, müşterinin.**

### 2.5 Türkçe'nin birinci sınıf vatandaş olması

Rakiplerin çoğu çok dilli ama Türkçe onlar için "bir dil daha". Bizde
`text_tr.py` I/ı-İ/i dönüşümü, ASCII katlama, diakritik denetimi var;
`tr_audit.py` CI'da ASCII'ye düşmüş Türkçe'yi build kırarak engelliyor.

---

## 3. Bizde olmayan ve piyasada standart olanlar

Dürüst liste. Önem sırasına göre.

### 3.1 🔴 Gerçek CSAT/anket verisi — **UYGULANDI**

**Eksik neydi:** Sistem `predicted_csat` üretiyordu ama kurumun **gerçek**
müşteri anketi puanını hiç almıyordu. Yani tahminin doğru olup olmadığı
ölçülemiyordu — altın setteki döngüsellik sorununun iş seviyesindeki hali.

Rakiplerin hepsinde QA puanı ↔ CSAT korelasyonu var; çünkü satın alan tarafın
sorduğu asıl soru şu: *"Sizin puanınız müşterinin memnuniyetiyle ilgili mi?"*

**Ne yapıldı:** §5.1.

### 3.2 ✅ Kanal bazlı skorkart — **ZATEN VARDI**

Araştırma sırasında bunu eksik sandım. Koda bakınca **tam olarak uygulanmış**
olduğunu gördüm: `Criterion.channel_scope` alanı, `scoring.py`'de kriter
seçiminde filtre, rubrik editöründe kanal seçici.

Bunu burada bırakıyorum çünkü analizin kendisi de dürüst olmalı: **varsaydım,
ölçtüm, yanıldım.** Rakip incelemesinden çıkan her boşluk gerçek boşluk
değildir; koda bakmadan "bizde yok" demek, olmayan işi yapmaya kalkmaktır.

### 3.3 🟠 SCIM ile kullanıcı sağlama — **YAPILMADI**

Kurumsal alımda "SSO var mı?" sorusunun hemen ardından "SCIM var mı?" gelir:
çalışan işten ayrıldığında hesabın **otomatik** kapanması.

**Neden yapılmadı:** SCIM 2.0 doğru uygulanması ciddi bir yüzey (kullanıcı ve
grup kaynakları, PATCH semantiği, filtreleme, sayfalama) ve bu kurulumda hiçbir
kimlik sağlayıcıya karşı **test edilemez**. Test edilmemiş bir SCIM uçtan
uca çalışıyormuş gibi görünüp sessizce hesap açık bırakabilir — yokluğundan
daha tehlikelidir.

**Şu an ne var:** OIDC ile giriş, panelden yapılandırılabilir. Kullanıcı
yaşam döngüsü elle veya davet akışıyla yönetiliyor. Denetim günlüğü her
giriş ve rol değişikliğini kaydediyor.

### 3.4 🟠 Hazır CCaaS / helpdesk entegrasyonları — **YAPILMADI**

Rakipler Zendesk, Salesforce Service Cloud, Intercom, Front, Genesys, Five9
ile hazır bağlantı sunuyor.

**Neden yapılmadı:** Her biri kendi kimlik doğrulaması, sayfalama ve hız
sınırı olan ayrı bir entegrasyondur; hiçbirine karşı gerçek bir hesapla test
edemem. **Test edilmemiş entegrasyon, olmayan entegrasyondan kötüdür.**

**Şu an ne var ve yeterli mi:** `POST /api/v1/ingest` (ses + metadata),
CSV metadata içe aktarma, giden webhook. Yani entegrasyon **mümkün** ama
müşterinin tarafında birkaç günlük iş demek. Satışta bunu "hazır konektör"
diye sunmak yanlış olur; "açık API + webhook" demek doğru.

### 3.5 🟡 Öğrenme yönetimi (LMS) / kısa sınav — **YAPILMADI**

Scorebuddy ve EvaluAgent, QA bulgusundan otomatik eğitim ataması yapıyor.

**Neden yapılmadı:** Bu ayrı bir ürün kategorisi (LMS). Kurumların çoğunda
zaten bir LMS var ve KaliteGöz'ün onun yerine geçmeye çalışması, iyi
yapamayacağı bir işe girmesi olurdu.

**Şu an ne var:** AI koçluk planı (temsilcinin en zayıf kriterlerinden kişisel
gelişim planı üretir), rozet/meydan okuma motoru, koçluk etkisi ölçümü
(`coaching_effect.py` — koçluk sonrası puan gerçekten yükseldi mi).

**Doğru yol:** LMS yazmak değil, webhook ile mevcut LMS'i tetiklemek.

### 3.6 🟡 Gerçek zamanlı temsilci asistanı — **BİLİNÇLİ KAPSAM DIŞI**

Observe.AI ve Cresta'nın ana satış argümanı. Bizim mimarimiz **çağrı sonrası**.

**Neden:** Gerçek zamanlı asist, akışa müdahale eden ayrı bir mimari
(streaming STT, düşük gecikme, canlı öneri) gerektirir. Yerel donanımda
7B/14B modelle gerçek zamanlı çalışmak, puanlama kalitesinden ödün vermek
demektir. İkisini aynı anda iyi yapamayız; puanlama doğruluğunu seçtik.

*(`assist.py` ve `assist_ws.py` çağrı sonrası özet/öneri üretir — canlı
suflör değildir, öyle sunulmamalıdır.)*

### 3.7 🟡 SOC 2 / ISO 27001 sertifikasyonu — **ORGANİZASYONEL**

Kurumsal alımda rutin olarak isteniyor. Bu bir kod işi değil; denetim ve
süreç işi.

**Kodun hazır olduğu kısım:** denetim günlüğü, rol matrisi, saklama süresi
otomasyonu, diskte şifreleme + anahtar rotasyonu, PII maskeleme, güvenlik
durum sayfası. Yani denetime girildiğinde kanıt üretilebilir.

**Kodun yapamayacağı kısım:** politika dokümanları, personel eğitim kayıtları,
sızma testi raporu, değişiklik yönetimi süreci.

---

## 4. Kurumsal alımda "blocker" maddeler — durum tablosu

Araştırmada tekrar eden eleyici kriterler:

| Madde | Durum | Not |
|---|---|---|
| Veri yerleşimi / on-prem | ✅ **Güçlü** | Tam yerel; veri hiç çıkmıyor |
| KVKK / GDPR uyumu | ✅ | `docs/KVKK-UYUM.md`, maskeleme, saklama, denetim izi |
| Diskte şifreleme + anahtar rotasyonu | ✅ | Dosya tabanlı anahtar, KMS yolu belgeli |
| SSO / OIDC | ✅ | Panelden yapılandırılabilir |
| Rol bazlı erişim (RBAC) | ✅ | 4 rol, tenant izolasyonu testli |
| Denetim günlüğü | ✅ | Giriş, PII görüntüleme, rol değişimi, ses indirme |
| Açık API + webhook | ✅ | `/api/v1/ingest`, giden webhook |
| **SCIM sağlama** | ❌ | §3.3 — gerekçeli yapılmadı |
| **Hazır CCaaS konektörleri** | ❌ | §3.4 — API var, konektör yok |
| **SOC 2 / ISO 27001** | ❌ | §3.7 — organizasyonel |
| Ölçülmüş doğruluk metodolojisi | ✅ **Nadir** | Rakiplerin çoğunda yok |

---

## 5. Bu turda uygulananlar

### 5.1 Gerçek CSAT verisi ve korelasyon

Ürünün en büyük dış doğrulama boşluğu kapatıldı.

- **Veri modeli:** `Call.actual_csat` (1-5) + `csat_source` (anket / manuel /
  içe aktarma) + `csat_comment`.
- **Giriş yolları:** `POST /api/v1/csat` (tek kayıt ve toplu), CSV içe aktarma.
  Çağrı `external_id` ile eşleşiyor — santral/CRM anket sonucu doğrudan
  bağlanabiliyor.
- **Korelasyon:** `analytics/csat-correlation` ucu, kesinleşmiş puanı olan ve
  gerçek CSAT'ı bulunan çağrılar üzerinde **Pearson r** ve tahmin hatası
  (MAE) üretiyor. Kokpitte tek kartta gösteriliyor.
- **Dürüstlük kuralı:** Örneklem 20'nin altındaysa korelasyon **sayı olarak
  gösterilmiyor**; "yeterli veri yok" deniyor. Az veriyle korelasyon yayımlamak,
  bu projede düzelttiğim hataların aynısı olurdu.

**Neden en yüksek etkili madde buydu:** QA puanının iş sonucuyla ilişkisini
gösteremeyen bir QA ürünü, "bize göre iyi çağrı" tanımını satmaya çalışır.
Gerçek CSAT bağlandığı anda ürün kendi iddiasını dışarıdan doğrulanabilir
hale getiriyor — ve korelasyon zayıf çıkarsa **rubriğin kendisi** sorgulanır,
ki doğrusu budur.

### 5.2 Araştırmanın kendi dersi

Bu turda uygulanan **tek** madde gerçek CSAT oldu. Sebebi şu: rakip
incelemesinden çıkardığım "eksik" listesinin yarısı, koda bakınca zaten
mevcut çıktı — kanal bazlı skorkart (`channel_scope`), rubrik sürümleme
(`rubric_versions`), inceleme ataması (`review_assignments`), temsilci öz
değerlendirmesi (`self_assessments`), hedef takibi (`targets`).

Bu, yazılmayan koddan daha değerli bir bulgu: **ürün, rakip listesindeki
sekiz standart maddenin sekizini de karşılıyor.** Gerçek boşluk özellik
sayısında değil, dış doğrulamadaydı.

---

## 6. Uygulanmayanlar ve gerekçeleri — özet

| Madde | Neden yapılmadı |
|---|---|
| SCIM 2.0 | Hiçbir kimlik sağlayıcıya karşı test edilemez; sessizce açık hesap bırakma riski |
| Zendesk/Genesys/Five9 konektörleri | Gerçek hesap olmadan test edilemez; test edilmemiş entegrasyon zararlı |
| LMS / sınav modülü | Ayrı ürün kategorisi; kurumların LMS'i zaten var, webhook ile tetiklenmeli |
| Gerçek zamanlı asist | Farklı mimari; yerel donanımda puanlama kalitesinden ödün verdirir |
| SOC 2 / ISO 27001 | Kod işi değil; süreç ve denetim işi. Kod tarafı kanıt üretmeye hazır |
| Ekran kaydı | Masaüstü ajanı gerektirir; KVKK açısından ayrı bir aydınlatma yükümlülüğü doğurur |

---

## 7. Rio'nun karar vermesi gerekenler

1. **Hedef segment.** On-prem + KVKK + Türkçe üçlüsü bankacılık/sigorta/kamu
   için güçlü; SaaS hızı arayan e-ticaret için fazla ağır. İkisini aynı anda
   kovalamak ürünü bulanıklaştırır.
2. **Konektör yatırımı.** Türkiye pazarında hangi santral yaygınsa
   (Genesys? Alcatel? yerli santraller?) **önce ona** konektör yazılmalı.
   Bu bilgi bende yok, sende var.
3. **SOC 2'ye girilecek mi?** Girilecekse kod tarafı hazır; süreç 6-12 ay.

---

## Kaynaklar

- [10 Best Call Center Quality Assurance Software (2026) — Solidroad](https://solidroad.com/resources/call-center-quality-assurance-software)
- [Best Klaus (Zendesk QA) Alternatives — Solidroad](https://solidroad.com/resources/best-klaus-zendesk-qa-alternatives)
- [10 Best MaestroQA Alternatives in 2026 — Level AI](https://thelevel.ai/blog/best-maestroqa-alternatives)
- [5 Best MaestroQA Alternatives — Kaizo](https://kaizo.com/blog/maestroqa-alternatives/)
- [Zendesk QA: Complete guide to AI-powered quality assurance in 2026 — eesel AI](https://www.eesel.ai/blog/zendesk-qa-quality-assurance)
- [Zendesk QA scorecard criteria: A complete guide for 2026 — eesel AI](https://www.eesel.ai/blog/zendesk-qa-scorecard-criteria)
- [Contact Center QA Software for Agent Performance — Scorebuddy](https://www.scorebuddyqa.com/quality-assurance)
- [Boost Call Center Performance — Scorebuddy Learning & Development](https://www.scorebuddyqa.com/learning-and-development)
- [Observe AI Review, Features, Pricing — Level AI](https://thelevel.ai/observe-ai-alternative-new/)
- [Level AI vs. Observe.AI Comparison 2026 — G2](https://www.g2.com/compare/level-ai-vs-observe-ai)
- [Best AI Tools for Support QA & Coaching in 2026 — IrisAgent](https://irisagent.com/blog/best-ai-tools-for-support-qa-and-coaching/)
- [Enterprise AI Voice Agent Requirements Checklist: 2026 — CallSphere](https://callsphere.ai/blog/enterprise-ai-voice-agent-requirements-checklist)
- [SOC 2 Compliance Checklist — Drata](https://drata.com/learn/soc-2/checklist)
- [Çağrı Merkezi Programı: Nedir, Özellikleri ve Seçim Rehberi — Sonitel](https://sonitel.com.tr/cagri-merkezi-programi/)
- [Görüşme Kaydı Analizi — Verimor Telekom](https://www.verimor.com.tr/makaleler/gorusme-kaydi-analizi-cagri-kalitesini-olcmek/)
- [Yapay Zekâ Destekli Çağrı Analizi — FGS](https://fgs.com.tr/yapay-zeka-destekli-cagri-analizi/)
- [Çağrı Merkezi Kalite Skorları — Zeno Bilişim](https://zenobilisim.com/cagri-merkezi-kalite-skorlarini-zeno-speech-to-text-ile-otomatiklestirmek/)
