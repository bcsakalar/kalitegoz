# KaliteGöz — Sistem & Test Rehberi (Uçtan Uca)

Bu belge; sistemin **ne yaptığını**, **her sayfanın ve butonun işlevini**, ve
**nasıl test edeceğini** baştan sona anlatır. Yeni başlayan biri bu rehberle
sistemi tanıyıp uçtan uca deneyebilir.

> **Hızlı başlangıç:** Sistemi çalıştırmak için kök dizindeki **`RUN.md`** yeterli.
> Bu rehber "ne var, nasıl test edilir"e odaklanır. Mimari için `README.md`.

**Erişim:** http://localhost:3000 · **API/Swagger:** http://localhost:8000/docs
**Demo hesapları** (parola: `demo1234`): `admin@demo.local` (Yönetici) ·
`sef.satis@demo.local` (Supervizör) · `kalite@demo.local` (Kalite) ·
`ayse.yilmaz@demo.local` (Temsilci)

---

## 1. Sistem ne yapıyor?

Çağrı merkezleri çağrıların yalnızca %2–3'ünü elle dinleyip puanlar. KaliteGöz
**%100'ünü** otomatik dinler/okur, rubriğe göre puanlar, ihlalleri yakalar, alarm
üretir ve raporlar — hem **sesli çağrı** hem **chat**, aynı kurallarla. Çok
kiracılı (multi-tenant), on-prem, KVKK uyumlu, kurumsal bir platformdur.

- **Sesli çağrı** → Whisper ile metne (STT) → konuşmacı ayrımı → akustik metrikler
  (konuşma oranı, sessizlik, ses yükseltme) → LLM ile rubrik bazında puanlama.
- **Chat** → doğrudan LLM ile puanlama (STT gerekmez).
- Her çağrı için: **kategori, özet, kriter puanları (gerekçe + kanıt), duygu seyri,
  tahmini CSAT, churn riski, müşteri eforu, niyet etiketleri, ihlaller
  (KVKK/yasaklı kelime/kriz), koçluk önerisi**.
- **KVKK:** Harici LLM'e giden metin daima maskelenir; saklanan transkriptler
  varsayılan maskelidir (yalnızca yetkili "ham veriyi göster" der, denetime yazılır).

**Yapay zekâ nerede?** LLM (Ollama), embedding ve Whisper STT **PC'de native**
çalışır (performans için Docker'da değil). Uygulama servisleri (API, Frontend,
Postgres, Redis, worker'lar) Docker'dadır.

---

## 2. Uçtan uca akış

```
Ses/Chat gelir → (ses ise) Whisper STT + diarization → akustik metrikler
   → LLM rubrik puanlama (Ollama/Gemini/OpenAI/OpenRouter, sağlayıcı fallback)
   → RAG bilgi doğruluğu (şirket dokümanlarıyla kıyas)
   → ihlal tespiti (KVKK/yasaklı kelime/kriz) + alarm
   → churn/emotion/CES/niyet + embedding (benzer çağrı için)
   → panolar, karneler, analitik, koçluk, kalibrasyon dolar
```

**İşleme duraklatma:** Demo kiracısı `processing_paused=true` gelir — ağır işler
kendiliğinden başlamaz; çağrılar "pending" birikir. **Yönetim > İşleme > "İşlemeyi
başlat"** denince işlenir. (Bu rehberdeki 28 hazır örnek çağrı zaten `done` — hemen
incelenebilir.)

---

## 3. Roller ve yetkileri (RBAC)

| Rol | Görebildiği | Yapabildiği |
|---|---|---|
| **admin** | Her şey (tenant geneli) | Kullanıcı/rubrik/AI ayarları, işleme kontrol, tüm veri |
| **quality** | Tenant geneli | Puan düzeltme (kalibrasyon), ham veri açma, itiraz çözme, örnekleme |
| **supervisor** | **Yalnızca kendi takımı** | Koçluk atama, kokpit, ekip analitiği |
| **agent** | **Yalnızca kendi** çağrıları/karnesi | Öz-değerlendirme, koçluk tamamlama, itiraz |

Yetki backend'de zorlanır; yetkisiz erişim 401/403 döner.

---

## 4. Demo verisi

Sistemde **28 profesyonel örnek çağrı** hazır (sesli + chat, 30 güne yayılı, 12
temsilciye dağılı). Bilinçli olarak şunları içerir:
- **Mükemmel görüşmeler** (KVKK okundu, empati, net çözüm) — yüksek puan
- **KVKK ihlali** (kimlik doğrulama atlandı) — kritik **sıfırlama** (score=0)
- **Kriz çağrısı** (öfkeli müşteri, hukuki söylem) — `is_crisis`
- **Yanlış bilgi** (iade süresi 14 yerine 30 gün) — düşük Bilgi Doğruluğu
- **Kaba üslup / yasaklı kelime** ("anlamıyorsunuz") — düşük Üslup + ihlal
- **Zayıf elde tutma**, **robotik chat**, **başarılı elde tutma** vb.

> Yeniden üretmek: `docker exec kalitegoz-api-1 python scripts/seed_pro_calls.py`
> (idempotent) · Trend grafikleri için sentetik geçmiş: `make seed-history`.

---

## 5. Sayfa sayfa rehber (her buton ne yapar)

### 📋 Çağrılar — `/` (ana sayfa)
Çağrı listesi + istatistik kartları (toplam, ort. puan, CSAT, kriz, sıfırlanan) +
günlük trend & kategori dağılımı.
- **⬇ CSV:** filtreli listeyi dışa aktarır.
- **Çağrı yükle:** ses dosyası (.wav/.mp3/.m4a/.ogg/.flac) → işleme kuyruğu.
- **🔍 Filtreler:** tarih, kanal, temsilci, kategori, durum, kriz, sıfırlanan,
  **⭐ örnek çağrılar**, **etiket**. Aktif filtre rozetle gösterilir.
- **⭐ Kayıtlı görünümler:** mevcut filtreyi isimle kaydet, tek tıkla uygula.
- **Sırala:** en yeni/eski, **süreye göre**, puana göre.
- **Toplu seçim (staff):** çoklu seç → **toplu**: ⭐ örnek yap/kaldır, etiket
  ekle/kaldır, sil.
- Tabloda: **⭐** örnek, 🔴 kriz, ⛔ sıfırlanan, 🔁 tekrar, etiket rozetleri, **⏱** uzun çağrı.

### 🔍 Arama — `/search`
Tüm transkript/mesajlarda konuşma araması; sonuç çağrının ilgili saniyesine link verir.

### 📊 Kokpit — `/cockpit` (Supervizör/Admin)
- **İstatistik kartları:** kalite, CSAT, FCR, AHT, kriz, sıfırlanan, tekrar, alarm.
- **🧭 Yönetici özeti (LLM):** "Özet üret" → başlık + kazanım + risk + aksiyon.
- **🎯 Hedefler & takip:** kurum/temsilci hedefi koy; gerçekleşmeyi renkle izle.
- **🔗 Korelasyon içgörüleri:** hangi davranış puanla ilişkili (Pearson).
- **📈 Yükselen konular:** hızla artan kategori/etiket.
- **📉 Churn riski:** dağılım + yüksek riskli takip listesi.
- **⚖️ İtiraz analitiği:** sayı, overturn oranı, ort. çözüm süresi.
- **Konu keşfi (LLM):** "müşteriler neden arıyor?" kök-neden.
- **🎯 Koçluk etkinliği:** koçluk sonrası puan arttı mı.
- **🔍 QA inceleme:** örnekleme + uzmana atama.
- **İhlal dağılımı** + **ekip board**.

### 📈 Analitik — `/analytics`
Zaman serileri (puan/CSAT/efor), kohort, korelasyon, churn, itiraz, VoC temaları.

### 🎧 Asistan — `/assist`
Canlı agent asistanı + (etkinse) görsel denetim (ekran görüntüsü LLM vision).

### 👥 Temsilciler — `/agents` ve karne `/agents/[id]`
Liste + karne (istatistik, trend, kriter kırılımı, rozet, son çağrılar).
- **✨ AI Koçluk Planı:** en zayıf kriterlerden Ollama ile kişisel gelişim planı.
- **PDF karne** indir.

### 🏆 Lig — `/leaderboard`
Liderlik tablosu + "Performansım".

### ✅ Görevler — `/workflow` 🔴
Alarmlar (rozetli), koçluk görevleri, örnekleme kuyruğu.

### ⚖️ Kalibrasyon — `/calibration`
Aynı çağrıyı birden fazla uzman bağımsız puanlar → uzmanlar arası uyum. Oturum
açıkken puanlar gizli; kapanınca karşılaştırma raporu.
- **📅 Planla (opsiyonel):** oturumu ileri tarihe planla → "Planlı" rozeti.

### 📐 Rubrik — `/rubric`
Kriter yönetimi (ağırlık, kritik eşik, kanal/kampanya kapsamı).
- **🧪 Simülasyon (what-if):** kaydetmeden geçmiş çağrılarda dene → önce/sonra.
- **🗂 Versiyonlama:** mevcut hali kaydet, geri yükle (puanlar isimle korunur).

### 💰 ROI — `/roi`
Yatırım getirisi hesaplayıcı.

### 🔒 Güvenlik — `/security`
KVKK maskeleme, şifreleme beyanı, denetim günlüğü durumu.

### ⚙️ Yönetim — `/admin` (yalnızca admin)
- **Kullanıcılar:** davet (self-service parola linki), rol yönetimi.
- **AI:** çoklu sağlayıcı — varsayılan yerel **Ollama**; panelden Gemini/OpenAI/
  OpenRouter anahtarı + model (LLM/Vision/Embedding ayrı). Ollama model **indir
  (pull)** + **Test et**. **📊 AI kullanım & maliyet** paneli.
- **Ayarlar:** marka/renk, kanal, kampanya.
- **İşleme:** STT/LLM işlemeyi başlat/durdur.

### 📞 Çağrı Detayı — `/calls/[id]`
- **Ses oynatıcı + senkron transkript** (KVKK maskeli; yetkili "👁 göster").
- **⭐ Örnek işaretle + etiketle** çubuğu.
- **Puan kartları:** kriter puanı + gerekçe + kanıt (kanıt anına atlar). Kalite/
  admin **"Puanı düzelt (kalibrasyon)"** ile override eder.
- **Akustik**, **duygu+koçluk+CSAT**, **🧠 AI Analizi** (churn/emotion/CES/niyet).
- **🧩 Benzer çağrılar** (semantik/embedding).
- **🎯 Koçluk görevleri:** temsilci yorum yazıp **tamamlar**; yönetici görür.
- **İhlaller** (kanıt + zaman) · **Rescore** (LLM'i tekrarla) · **İtiraz/koçluk ata**.

### 🔔 Bildirim zili (her sayfada, sol üst)
Birleşik akış: alarm + sana atanan inceleme + açık koçluğun + açık itirazlar.
Rozet sayacı + dropdown + "tümünü okundu".

### 🔐 Diğer
`/account` (parola) · `/onboarding` (yeni kurum sihirbazı) · `/login`.

---

## 6. Nasıl test ederim? (adım adım)

### Adım 0 — Ayakta mı?
```powershell
docker compose ps
curl http://localhost:8000/api/health/ready
```

### Adım 1 — Hazır veriyle gez
1. http://localhost:3000 → `admin@demo.local` / `demo1234`.
2. **Çağrılar**'da 28 örneği gör; birine tıkla → transkript, puan, ihlal, AI analiz, benzer çağrılar.
3. **Kokpit** → yönetici özeti üret, hedef ekle, churn/korelasyon/itiraz panelleri.
4. **Rubrik** → simülasyon çalıştır, versiyon kaydet.
5. **Yönetim > AI** → sağlayıcı/model + kullanım paneli.
6. Bir karnede **AI Koçluk Planı** üret.

### Adım 2 — Kendi çağrını işle (uçtan uca AI)
1. STT worker açık: `powershell -ExecutionPolicy Bypass -File scripts\run-host-worker.ps1`
2. **Çağrılar > Çağrı yükle** ile ses yükle.
3. **Yönetim > İşleme > "İşlemeyi başlat"**.
4. `pending → processing → done`; detayında transkript + puan.

### Adım 3 — Rol rol dene
| Rol | Dene |
|---|---|
| admin | Yönetim (AI/kullanıcı/işleme), hedef koy |
| quality | Puan düzelt (kalibrasyon), ham veri "göster", itiraz çöz |
| supervisor | Kokpit; yalnızca kendi takımı; koçluk ata |
| agent | Yalnızca kendi çağrıları; öz-değerlendirme, koçluk tamamla |

---

## 7. Kabul kriterleri (checklist)

- [ ] `docker compose ps` → 7 konteyner Up (api/postgres/redis **healthy**)
- [ ] `/api/health/ready` → `status: ready`
- [ ] 4 rolle giriş; agent yalnızca kendini görür
- [ ] 28 örnek çağrı; filtre/sıralama/kayıtlı görünüm/toplu aksiyon çalışıyor
- [ ] Çağrı detayı: transkript + puan+gerekçe+kanıt + ihlal + AI analiz + benzer çağrı
- [ ] Kokpit panelleri dolu (özet/hedef/korelasyon/churn/itiraz/konu)
- [ ] Rubrik simülasyon + versiyonlama
- [ ] AI Koçluk Planı + Yönetici Özeti gerçek LLM çıktısı
- [ ] Bildirim zili birleşik akış gösteriyor
- [ ] Yönetim > AI: sağlayıcı/model/pull/test + kullanım
- [ ] Güvenlik başlıkları yanıtlarda (`X-Frame-Options: DENY`)
- [ ] Yeni ses yüklenip işlenebiliyor (STT worker açıkken)

---

## 8. Sorun giderme

| Belirti | Çözüm |
|---|---|
| `docker info` hata | Docker Desktop'ı başlat, bekle |
| Panolar boş | `docker exec kalitegoz-api-1 python scripts/seed_pro_calls.py` |
| AI yanıtı yok / takılı | `ollama list` (Ollama + model var mı) |
| Ses işlenmiyor | `scripts\run-host-worker.ps1` açık mı? → İşleme > başlat |
| Çağrı "pending" | Yönetim > İşleme > "İşlemeyi başlat" |
| Sıfırdan temiz | `docker compose down -v; docker compose up -d` (otomatik seed) |
| Prod'a çıkış | `.env`: `ENVIRONMENT=production`, güçlü `JWT_SECRET`, `DEMO_MODE=false`, gerçek `CORS_ORIGINS` |

---

## 9. Öne çıkan özellikler (tam liste)

Rubrik kalite skorlama (kritik/sıfırlama) · çok kanallı (sesli+chat) · çoklu AI
sağlayıcı (Ollama/Gemini/OpenAI/OpenRouter + **fallback**) · RAG bilgi doğruluğu ·
KVKK maskeleme · örnek/altın çağrı + etiketleme · yükselen konular · rubrik
what-if simülasyonu · rubrik versiyonlama · AI mikro-koçluk planı · AI
maliyet/kullanım takibi · korelasyon içgörüleri · hedefler & takip · LLM yönetici
özeti · churn/retention panosu · itiraz analitiği · kayıtlı görünümler · toplu
aksiyonlar · semantik benzer çağrı · bildirim merkezi · koçluk kapanış-döngüsü ·
kalibrasyon (zamanlama dahil) · rozet/lig · ROI · denetim günlüğü · RBAC · çoklu
kiracı · SSO/OIDC (ops.) · webhook/Slack/Teams · sağlık/readiness + güvenlik
başlıkları + otomatik şema migrasyonu (self-heal).
