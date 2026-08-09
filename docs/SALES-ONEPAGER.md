# KaliteGöz — Çağrı Merkezi Kalite Yönetim Platformu

## Bugün neredesiniz?

Çağrı merkezlerinin büyük çoğunluğu çağrıların **%2–3'ünü** elle dinleyerek
puanlar. Yani her 100 çağrının 97'si hiç denetlenmez. Kalite ekibiniz haftanın
yarısını çağrı dinlemekle geçirir; buna rağmen KVKK ihlali, kaba üslup veya
yanlış bilgi içeren çağrıların çoğu **hiç görülmez**. Şikayet size müşteriden,
bazen de düzenleyici kurumdan döner.

## KaliteGöz ne yapar?

**Her çağrının %100'ünü otomatik dinler, puanlar ve raporlar.** Sesli çağrılar ve
yazışma (chat) kanalı aynı rubrikle denetlenir.

> **Kapsamın anlamı — açıkça:** Uyum kriterlerinde (açılış, KVKK anonsu, kimlik
> doğrulama, kapanış, yasaklı üslup) kapsam **%100'dür ve puan kesindir**;
> bu kriterler kodla, tanımlı kuralla ölçülür. Yargı gerektiren kriterlerde
> (aktif dinleme, ihtiyaç analizi, çözüm) sistem **kanıtlı bir öneri** üretir;
> geçerli puan kalite uzmanının onayıyla oluşur. Bu ayrım ürünün zayıflığı
> değil tasarımıdır — ölçülen güvenilirlik `docs/KALITE-METODOLOJISI.md` §4'te.

| Elle denetim | KaliteGöz |
|---|---|
| Çağrıların %2–3'ü | **%100'ü taranır** |
| Çağrı başına 15–20 dk uzman zamanı | Otomatik, dakikalar içinde |
| Denetçiden denetçiye değişen puan | Tutarlı, kanıta dayalı, kalibre edilebilir |
| İhlal aylar sonra fark edilir | **Anında alarm** (kriz / KVKK / hakaret) |

## Öne çıkan yetenekler

- **Sıfırlayıcı ihlal motoru** — KVKK metni okunmadıysa, kimlik doğrulama
  atlandıysa veya hakaret varsa çağrı puanı otomatik **0** olur ve süpervizöre
  anında alarm düşer. Bu kuralları siz belirlersiniz.
- **Yönetilebilir rubrik** — Kriter ekleyin, ağırlıklandırın, gruplayın
  (Açılış / İhtiyaç Analizi / Çözüm / Kapanış / Uyum / İletişim Kalitesi).
  Satış hattı ile şikayet hattına **farklı rubrik** tanımlayın. Kod değişikliği yok.
- **Yasaklı kelime & davranış** — Hakaret, küçümseme, yasak vaat ("garanti
  ederim") listesi panelden yönetilir; yazım varyasyonları (fuzzy) yakalanır ve
  **kimin söylediği** ayrıştırılır — müşteri küfrederse temsilci cezalandırılmaz.
- **Kriz tespiti** — "Avukatıma gideceğim", "tüketici hakem heyeti" gibi
  eskalasyon sinyalleri işaretlenir, çağrı süpervizör kuyruğuna düşer.
- **Konuşma metrikleri** — Konuşma oranı, söz kesme sayısı, sessizlik/ölü hava,
  konuşma hızı. LLM'e nesnel dayanak olarak verilir; "aktif dinleme" artık
  tahmin değil, ölçüm.
- **Duygu değişimi + tahmini CSAT** — Müşteri çağrıya nasıl başladı, nasıl
  bitirdi? Anket beklemeden memnuniyet tahmini.
- **Kalibrasyon & itiraz** — Kalite uzmanı AI puanını düzeltir, sistem AI ile
  insan arasındaki sapmayı raporlar. Temsilci puanına **itiraz** edebilir; karar
  ve gerekçe denetim kaydında kalır.
- **Koçluk & lig** — Temsilci karnesi, haftalık otomatik gelişim özeti, koçluk
  görevi atama, takım/şirket liderlik tablosu ve rozetler.
- **KVKK paketi** — TC kimlik, telefon, kart, IBAN otomatik maskelenir. Harici
  LLM'e giden **her metin maskelenmiş gider** (kod seviyesinde garanti, testle
  doğrulanır). Kim hangi çağrıyı dinledi/indirdi — değiştirilemez denetim kaydı.
- **Veriniz sizde kalır** — Ollama ile **tamamen kendi sunucunuzda** çalışır;
  isterseniz tek ayarla Gemini'ye geçersiniz. Bulut zorunluluğu yok.

## Kurumsal hazırlık

- **Multi-tenant** — tek kurulumda birden fazla şirket/marka, tam veri izolasyonu.
- **4 rol (RBAC)** — Yönetici, Süpervizör, Kalite Uzmanı, Temsilci. Temsilci
  yalnızca kendi çağrılarını görür.
- **Entegrasyon** — REST API (OpenAPI/Swagger), webhook (CRM/Slack/Teams),
  klasör izleme ile toplu çağrı aktarımı, PDF/Excel rapor, CSV dışa aktarma.
- **Kurulum** — Docker Compose ile tek komut. Şirket içi (on-premise) veya bulut.

## Ne kazandırır?

- Kalite uzmanı zamanı **dinlemekten** koçluğa kayar (örnek: 3 uzman × günde
  4 saat dinleme ≈ haftada 60 saat geri kazanım).
- KVKK/mevzuat ihlali **aynı gün** yakalanır, aylar sonra değil.
- Her temsilci her hafta somut, kanıtlı geri bildirim alır — puanlar tartışma
  konusu olmaktan çıkar, kanıt cümlesi ve ses kaydıyla gösterilir.

---

**Demo:** `make demo` → http://localhost:3000 → rol seçip tek tıkla girin.
Gerçek sesli çağrılar, chat görüşmeleri ve 8 haftalık geçmiş veriyle dolu bir
platform açılır.
