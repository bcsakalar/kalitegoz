# Test Rehberi — sistemi kendiniz deneyin

> Bu rehber, sistemi sıfırdan ayağa kaldırıp her önemli akışı adım adım
> denemeniz için yazıldı.
>
> Her adım üç parça: **[ne yapacağım]** → **[ne görmem gerekiyor]** →
> **[görmezsem sorun nedir]**.
>
> Sistem şu an **20 çağrı "bekliyor" durumunda**, hiçbiri işlenmemiş.
> Puanlamayı siz başlatacaksınız.

---

## Bölüm 0 — Giriş bilgileri

**Parola:** `.env` dosyanızdaki `ADMIN_PASSWORD` değeri. Tüm hesaplar aynı
parolayı kullanır.

```bash
grep ADMIN_PASSWORD .env
```

| Rol | E-posta | Ne görür |
|---|---|---|
| Yönetici | `admin@demo.local` | Her şey |
| Süpervizör | `sef.destek@demo.local` | Kokpit, ROI — yönetim yok |
| Kalite uzmanı | `kalite@demo.local` | İnceleme, kalibrasyon — kokpit yok |
| Temsilci | `ayse.yilmaz@demo.local` | Sadece kendi karnesi ve çağrıları |

---

## Bölüm 1 — Sistemi ayağa kaldırma

### 1.1 Servisleri başlat

**[ne yapacağım]**
```bash
docker compose up -d
docker compose ps
```

**[ne görmem gerekiyor]**
Yedi servis `running`: `api`, `frontend`, `postgres`, `redis`, `worker-fast`,
`beat`, `watcher`.

**[görmezsem sorun nedir]**
- `api` sürekli yeniden başlıyorsa: `docker compose logs api` bakın. En sık
  sebep eksik/bozuk `.env` — uygulama bunu **açık Türkçe hata** ile söyler.
  `./scripts/generate-secrets.sh --force` çalıştırın.
- `postgres` unhealthy ise disk dolu olabilir.

### 1.2 Sağlık kontrolü

**[ne yapacağım]**
```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

**[ne görmem gerekiyor]**
```json
{"status":"ok","app":"KaliteGoz","version":"2.0.0"}
{"status":"ready","checks":{"database":"ok","redis":"ok"}}
```

**[görmezsem sorun nedir]**
`ready` içinde `database: error` varsa parola uyuşmuyordur — `.env` içindeki
`POSTGRES_PASSWORD` ile `DATABASE_URL` aynı parolayı taşımalı. Volume eskiyse
`docker compose down -v && docker compose up -d` gerekir (**veri siler**).

### 1.3 Yapay zekânın bağlı olduğunu doğrula

**[ne yapacağım]**
```bash
ollama list
docker compose exec api python -c "import httpx;print(len(httpx.get('http://host.docker.internal:11434/api/tags').json()['models']),'model')"
```

**[ne görmem gerekiyor]**
En az `qwen2.5:7b-instruct` ve `nomic-embed-text`. İkinci komut model sayısını
yazdırmalı.

**[görmezsem sorun nedir]**
Ollama **host'ta** çalışmalı, Docker'da değil. Kapalıysa başlatın. Konteynerden
erişilemiyorsa `extra_hosts: host.docker.internal` ayarı devre dışı kalmıştır.

---

## Bölüm 2 — Giriş ve rol bazlı erişim

### 2.1 Yönetici girişi

**[ne yapacağım]** <http://localhost:3000> → `admin@demo.local` + parola.

**[ne görmem gerekiyor]**
Giriş sonrası **Kokpit** açılır (rol bazlı açılış ekranı). Sol menüde:
İzleme, Çalışma, Ekip, Kurulum, Sistem grupları; en altta **Yönetim**.

**[görmezsem sorun nedir]**
401 alıyorsanız parola yanlıştır (`.env` → `ADMIN_PASSWORD`). "Kurumunuzu
oluşturun" ekranı çıkıyorsa veritabanı boş demektir; `docker compose logs api`
içinde seed hatası arayın.

### 2.2 Her rolle ayrı giriş — kritik test

**[ne yapacağım]** Sırayla çıkış yapıp dört hesapla da girin.

**[ne görmem gerekiyor]**

| Rol | Açılış ekranı | Menüde OLMAMASI gerekenler |
|---|---|---|
| Yönetici | Kokpit | — |
| Süpervizör | Kokpit | Yönetim |
| Kalite uzmanı | İnceleme Kuyruğum | Kokpit, ROI, Yönetim |
| Temsilci | Kendi karnesi | Kokpit, İnceleme, Kalibrasyon, Rubrik, Güvenlik, ROI, Yönetim |

**[görmezsem sorun nedir]**
Temsilci "İnceleme Kuyruğum"u görüyorsa **yetki sızıntısı** vardır — ciddi bir
hatadır, bildirin. Menüde görünmeyen bir sayfaya adresi elle yazarak
girebiliyorsanız, API tarafında da yetki kontrolü eksik demektir (menüyü
gizlemek yetmez).

### 2.3 Temsilci başkasının çağrısını göremez

**[ne yapacağım]** `ayse.yilmaz@demo.local` ile girin, Çağrılar'a bakın.

**[ne görmem gerekiyor]** Yalnızca kendi çağrıları.

**[görmezsem sorun nedir]** Başka temsilcilerin çağrılarını görüyorsa tenant/
takım kapsamı çalışmıyordur.

---

## Bölüm 3 — İşlemeyi başlatma ve takip

### 3.1 Başlangıç durumunu gör

**[ne yapacağım]** Yönetici ile **Çağrılar** ekranı.

**[ne görmem gerekiyor]**
20 çağrı, hepsi **Bekliyor**. Puan sütunu boş. Toplam çağrı 20, ortalama puan
boş.

**[görmezsem sorun nedir]**
Puanlı çağrı görüyorsanız sistem temiz başlamamıştır. 20'den az çağrı varsa
`data/inbox` klasörüne bakın; watcher dosyaları almış olmalı.

### 3.2 İşlemeyi başlat

**[ne yapacağım]** Yönetim → **İşleme** sekmesi → "İşlemeyi başlat".

**[ne görmem gerekiyor]**
Durum rozeti "Duraklatıldı" → "Çalışıyor". "Bekleyen" sayısı düşmeye,
"Şu an işleniyor" artmaya başlar.

**[görmezsem sorun nedir]**
Sayılar hiç değişmiyorsa **sesli çağrı worker'ı çalışmıyor** olabilir. STT
Docker'da değil host'ta koşar:

```powershell
.\scripts\run-host-worker.ps1
```

Bu pencere açık kalmalı. Açmazsanız çağrılar "bekliyor" durumunda kalır — bu
bir hata değil, mimarinin gereği (bkz. [MIMARI.md](MIMARI.md) §1).

### 3.3 İlerlemeyi izle

**[ne yapacağım]** Aynı ekranda "Yenile"ye basın veya Çağrılar'a dönüp bekleyin.

**[ne görmem gerekiyor]**
Çağrılar sırayla **Tamamlandı** olur ve puan alır. Bir çağrı yaklaşık **40-90
saniye** sürer (CPU'da; GPU varsa daha hızlı). 20 çağrı ~20-30 dakika.

**[görmezsem sorun nedir]**
- Çağrı **Hatalı** olursa: çağrı detayında hata mesajı görünür. En sık sebep
  Ollama'nın yanıt vermemesi (`ollama list` ile kontrol edin).
- Çok yavaşsa `.env` içinde `WHISPER_MODEL=small` yaparak hızlandırabilirsiniz
  (doğruluk biraz düşer).

---

## Bölüm 4 — Çağrı detayı ve kanıt–ses bağı

### 4.1 Bir çağrıyı aç

**[ne yapacağım]** Çağrılar → tamamlanmış bir çağrının referansına tıklayın.

**[ne görmem gerekiyor]**
Üstte toplam puan ve kategori; ses oynatıcı; transkript (konuşmacı ayrımlı:
temsilci / müşteri); altında kriter kriter puanlar, her birinin gerekçesi ve
**transkriptten birebir alıntı**.

**[görmezsem sorun nedir]**
Transkriptte herkes "bilinmeyen" görünüyorsa konuşmacı ayrımı çalışmamıştır.
Demo sesleri stereo (sol=müşteri, sağ=temsilci) olduğu için bu çalışmalı.

### 4.2 Kanıt–ses bağı — ürünün en önemli özelliği

**[ne yapacağım]** Bir kriterin altındaki **alıntıya tıklayın**.

**[ne görmem gerekiyor]**
Ses, o alıntının geçtiği **saniyeye atlar** ve oynatmaya başlar. Duyduğunuz
söz, ekrandaki alıntıyla aynı olmalı.

**[görmezsem sorun nedir]**
Ses başka bir yere atlıyorsa zaman damgaları kaymıştır. Duyduğunuz söz
alıntıdan **farklıysa** bu ciddi bir hatadır — sistemin tüm iddiası kanıtın
doğrulanabilir olmasına dayanır.

### 4.3 "Yetersiz kanıt" kriterini bul

**[ne yapacağım]** Birkaç çağrıda kriter listesini tarayın.

**[ne görmem gerekiyor]**
Bazı kriterlerde puan yerine **"Yetersiz kanıt"** yazar. Bu bir hata değil,
**tasarım**: model alıntı gösteremediyse ceza verilmez, kriter insana gider.

**[görmezsem sorun nedir]**
Hiç "yetersiz kanıt" görmüyorsanız ya çok şanslısınız ya da doğrulama
katmanı devre dışıdır. Tersine, çağrıların yarısından fazlasında görüyorsanız
ses kalitesi/STT sorunlu olabilir.

---

## Bölüm 5 — Kalite uzmanı akışı

### 5.1 İnceleme kuyruğu

**[ne yapacağım]** `kalite@demo.local` ile girin. Doğrudan **İnceleme
Kuyruğum** açılır.

**[ne görmem gerekiyor]**
Kuyrukta bekleyen çağrılar ve kaçının beklediği. Sol tarafta ses + özet, sağ
tarafta kriterler.

**[görmezsem sorun nedir]**
Kuyruk boşsa hiçbir çağrı risk kuralı tetiklememiştir. Sıfırlayıcı ve kriz
senaryoları mutlaka kuyruğa düşmeli — düşmüyorsa kuyruk kuralları çalışmıyor.

### 5.2 Klavye kısayolları

**[ne yapacağım]** Kuyrukta bir çağrı açıkken (imleç bir yazı alanında
**değilken**) şu tuşlara basın:

| Tuş | Ne yapar |
|---|---|
| `J` / `↓` | Sonraki kriter |
| `K` / `↑` | Önceki kriter |
| `A` | Aktif kriteri **onayla** |
| `Boşluk` | Sesi oynat / duraklat |
| `Ctrl+Enter` (Mac: `Cmd+Enter`) | **Kaydet ve sıradaki çağrıya geç** |

**[ne görmem gerekiyor]**
`J`/`K` ile vurgulanan kriter değişir. `A` ile o kriter onaylanır. Boşluk sesi
başlatır.

**[görmezsem sorun nedir]**
Bir metin kutusuna yazarken kısayollar **çalışmamalı** — çalışıyorsa yazı
yazamazsınız. Bu bilinçli olarak engellendi; kırılmışsa bildirin.

### 5.3 Puan düzeltme

**[ne yapacağım]** Bir kriterde "Düzelt" deyin, puanı değiştirin, gerekçe
yazın, kaydedin.

**[ne görmem gerekiyor]**
Toplam puan **anında** güncellenir. Çağrı "kesinleşti" durumuna geçer.
Düzeltme kalibrasyon verisi olarak saklanır.

**[görmezsem sorun nedir]**
Toplam puan değişmiyorsa aritmetik sunucuda yapılmıyordur — ciddi hata.

---

## Bölüm 6 — İtiraz ve kalibrasyon

### 6.1 Temsilci itirazı

**[ne yapacağım]** `ayse.yilmaz@demo.local` ile girin → kesinleşmiş bir
çağrısını açın → "İtiraz et", gerekçe yazın.

**[ne görmem gerekiyor]**
Çağrı "itiraz incelemede" durumuna geçer. Kalite uzmanının ekranında itiraz
görünür.

**[görmezsem sorun nedir]**
İtiraz butonu yoksa çağrı henüz kesinleşmemiştir (kuyrukta bekliyordur).

### 6.2 İtirazın karneye etkisi — önemli kontrol

**[ne yapacağım]** İtiraz açtıktan sonra temsilcinin karnesine bakın.

**[ne görmem gerekiyor]**
İtiraz edilen çağrı **ortalamaya dahil edilmez**. Çağrı sayısı bir azalır.

**[görmezsem sorun nedir]**
Hâlâ sayılıyorsa B33 regresyonu olmuştur: tartışmalı bir puan karneye
girmemeli.

### 6.3 Kalibrasyon oturumu

**[ne yapacağım]** Kalite uzmanı → **Kalibrasyon** → oturum oluşturun, aynı
çağrıyı iki farklı kullanıcıya puanlatın.

**[ne görmem gerekiyor]**
Değerlendiriciler arası uyum (kappa) hesaplanır, ayrıştıkları kriterler
listelenir.

**[görmezsem sorun nedir]**
Tek kişi puanladıysa uyum hesaplanamaz — bu doğrudur, uyum iki taraf gerektirir.

---

## Bölüm 7 — Alarmlar, kokpit, analitik

### 7.1 Alarmlar

**[ne yapacağım]** Yönetici veya süpervizör → **Görevler** (iş akışı).

**[ne görmem gerekiyor]**
Sıfırlayıcı ihlal ve kriz çağrıları için alarm. Her alarmda: başlık, açıklama,
**önerilen aksiyon** ve kanıt.

**[görmezsem sorun nedir]**
Serbest metin bir alarm görürseniz (şablonsuz) bildirin — alarm üretimi
şablona bağlıdır.

### 7.2 Kokpit

**[ne yapacağım]** Yönetici → **Kokpit**.

**[ne görmem gerekiyor]**
Ortalama kalite, tahmini CSAT, FCR, AHT, kriz sayısı, sıfırlayıcı ihlal.
Altında hedefler, **kalite ↔ müşteri memnuniyeti** paneli, churn riski,
yükselen konular, koçluk etkinliği.

CSAT panelinde şunu göreceksiniz: *"Korelasyon için yeterli veri yok
(0/20 çağrı)."* **Bu doğru davranıştır** — gerçek anket verisi girilmeden
korelasyon gösterilmez.

**[görmezsem sorun nedir]**
Az veriyle bir korelasyon sayısı gösteriliyorsa dürüstlük kapısı kırılmıştır.

### 7.3 Analitik ve ROI

**[ne yapacağım]** **Analitik** ve **ROI / Getiri** ekranları.

**[ne görmem gerekiyor]**
Analitik: kriter bazlı dağılım, temsilci karşılaştırması, trend.
ROI: elle denetimle kıyaslanan zaman/maliyet tasarrufu, girdileri
değiştirebilirsiniz.

**[görmezsem sorun nedir]**
20 çağrı istatistiksel olarak azdır; bazı paneller "yeterli veri yok" diyebilir.
Bu doğrudur.

---

## Bölüm 8 — Rubrik, simülasyon, arama

### 8.1 Rubrik düzenleme

**[ne yapacağım]** **Rubrik** → bir kriterin ağırlığını değiştirin, kaydedin.

**[ne görmem gerekiyor]**
Kaydedildi bildirimi. Kriter adlarının hepsi **tam Türkçe karakterli**
("Açılış", "İhtiyaç Analizi").

**[görmezsem sorun nedir]**
"Acilis" gibi ASCII bir ad görürseniz bildirin — `make audit` bunu build'de
engelliyor olmalı.

### 8.2 Simülasyon

**[ne yapacağım]** Rubrik ekranında simülasyon: ağırlık değişikliğinin geçmiş
çağrılara etkisini görün.

**[ne görmem gerekiyor]**
Kaydetmeden önce "bu değişiklik ortalamayı şu kadar değiştirir" özeti.

**[görmezsem sorun nedir]**
Puanlanmış çağrı yoksa simülasyon boş çıkar — önce Bölüm 3'ü tamamlayın.

### 8.3 Arama

**[ne yapacağım]** **Arama** → "fatura" yazın.

**[ne görmem gerekiyor]**
Transkript içinde geçen çağrılar, eşleşen cümle vurgulu.

**[görmezsem sorun nedir]**
Sonuç yoksa transkriptler henüz oluşmamıştır.

---

## Bölüm 9 — Sıfırlayıcı ihlal senaryosu (özel kontrol)

Bu, ürünün en kritik davranışıdır. İki çağrı bunun için hazırlandı.

### 9.1 KVKK anonsu olmayan çağrı

**[ne yapacağım]** `demo-17-sifirlayici-kvkk-yok` çağrısını açın.

**[ne görmem gerekiyor]**
- Toplam puan **0** ve "Sıfırlayıcı ihlal" rozeti
- "KVKK / Aydınlatma" kriteri düşük ve **gerekçesi kanıtlı**
- Alarm üretilmiş

**[görmezsem sorun nedir]**
Çağrı yüksek puan aldıysa deterministik KVKK kontrolü çalışmıyordur. Bu
kriter **kodla** çözülür, LLM'e sorulmaz — hata varsa `deterministic.py`
tarafındadır.

### 9.2 Hakaret içeren çağrı

**[ne yapacağım]** `demo-18-sifirlayici-hakaret` çağrısını açın.

**[ne görmem gerekiyor]**
Sıfırlanmış puan, "Yasaklı Kelime / Üslup" ihlali, alarm. Alıntıda temsilcinin
hangi cümlesinin sorunlu olduğu görünmeli.

**[görmezsem sorun nedir]**
Yasaklı kelime listesi Yönetim → Yasaklı Kelimeler'de görünüyor mu? Boşsa
tespit yapılamaz.

### 9.3 Kriz çağrıları

**[ne yapacağım]** `demo-19-kriz-avukat` ve `demo-20-kriz-hakem-heyeti`.

**[ne görmem gerekiyor]**
"Kriz" işareti ve alarm. **Ama puan düşük olmak zorunda değil** — bu
çağrılarda temsilci doğru davranıyor. Kriz, temsilcinin hatası değil
**durumun riski** demektir.

**[görmezsem sorun nedir]**
Kriz tespit edilmediyse hukuki söylem tespiti çalışmıyordur.

---

## Bölüm 10 — Tema ve dil

### 10.1 Tema geçişi

**[ne yapacağım]** Sol altta güneş / ay / ekran düğmeleri.

**[ne görmem gerekiyor]**
Anında geçiş. Sayfayı yenileyince seçim korunur. **Hiçbir yerde yuvarlak köşe
olmamalı** — kart, buton, input, rozet, hepsi keskin.

**[görmezsem sorun nedir]**
Koyu temada beyaz bir kutu görürseniz bildirin (bu tur bir tane vardı ve
düzeltildi). Yuvarlak köşe görürseniz `make audit` yakalamamış demektir.

### 10.2 Dil geçişi

**[ne yapacağım]** TR / EN düğmeleri.

**[ne görmem gerekiyor]**
Arayüz metinleri değişir. Veri (çağrı içeriği, kriter adları) Türkçe kalır —
bu doğrudur, veri çevrilmez.

**[görmezsem sorun nedir]**
`nav.cockpit` gibi ham anahtar görürseniz çeviri eksiktir.

---

## Bölüm 11 — Bilerek kırmayı deneyeceğiniz şeyler

Bu bölüm ürünü zorlamak içindir. Her maddede **beklenen davranış** yazılı;
farklı bir şey olursa bildirin.

### 11.1 Bozuk ve sınır girdiler

| Deneyin | Beklenen |
|---|---|
| Çağrılara **0 baytlık bir WAV** yükleyin | Açık hata mesajı; çağrı "Hatalı" olur, sistem çökmez |
| **Ses olmayan bir dosya** (PDF'i .wav yapın) | Reddedilir ya da "Hatalı" olur; kuyruk tıkanmaz |
| **Aynı dosyayı iki kez** yükleyin | İkincisi işlenmez (ses hash'i ile tespit) — LLM/STT maliyeti boşa gitmez |
| **Çok uzun bir çağrı** (>10 dk) | Parçalara bölünüp puanlanır; ortası atlanmaz |
| **Tamamen sessiz** bir kayıt | Transkript boş; kriterler "yetersiz kanıt" olur, uydurma puan verilmez |

### 11.2 Yetki sınırları

| Deneyin | Beklenen |
|---|---|
| Temsilci hesabıyla adres çubuğuna `/admin` yazın | Erişim engellenir (menüyü gizlemek yetmez, API de reddetmeli) |
| Temsilci hesabıyla `/cockpit` | Engellenir |
| Kalite uzmanı hesabıyla `/admin` | Engellenir |
| Süpervizör, **başka takımın** temsilcisini açsın | "Bu temsilci sizin takımınızda değil" |
| Tarayıcı konsolundan token'ı silin, sayfayı yenileyin | Giriş ekranına düşer |

### 11.3 Girdi doğrulama

| Deneyin | Beklenen |
|---|---|
| Puan düzeltmede **-5** veya **150** girin | Reddedilir; sessizce kırpılmaz |
| CSAT olarak **7** girin (ölçek 1-5) | Açık hata: "1-5 arasında olmalı… önce 1-5'e dönüştürün" |
| Rubrikte ağırlığı **0** yapın | Kabul edilir ama kriter ortalamaya girmez — beklenen |
| Kriter adına **çok uzun metin** girin | Sınır uygulanır |
| Gerekçe alanına `<script>alert(1)</script>` | Metin olarak görünür, **çalışmaz** |

### 11.4 Sistem dayanıklılığı

| Deneyin | Beklenen |
|---|---|
| İşleme sürerken **Ollama'yı kapatın** | Çağrı "Hatalı" olur ve **yeniden denenir**; diğerleri etkilenmez |
| İşleme sürerken **duraklat** deyin | Devam eden çağrı biter, yenileri başlamaz |
| `docker compose restart api` | Panel birkaç saniye sonra kendine gelir; veri kaybı olmaz |
| `docker compose restart redis` | Kuyruk toparlanır; işlenen çağrı yeniden denenir |
| **Aynı anda iki sekmede** aynı çağrıyı puanlayın | Son kayıt geçerli olur; çelişkili çift kayıt oluşmamalı |

### 11.5 Dürüstlük kapıları — bunlar kırılmamalı

Bu maddeler ürünün iddialarını korur. Kırılırsa **ciddi** hatadır.

| Deneyin | Beklenen |
|---|---|
| CSAT paneline **19 çağrı** için anket girin | Hâlâ "yeterli veri yok" der (eşik 20) |
| Kanıtı olmayan bir kriterin **puan almadığını** doğrulayın | "Yetersiz kanıt", ortalamaya girmez |
| Kuyrukta bekleyen çağrının **karneye girmediğini** doğrulayın | Temsilci ortalaması değişmez |
| Bir alıntıyı transkriptle karşılaştırın | **Birebir** aynı olmalı |

### 11.6 Yapılandırma hataları

| Deneyin | Beklenen |
|---|---|
| `.env`'den `JWT_SECRET` satırını silin, `docker compose up -d` | Uygulama **açık Türkçe hata** ile durur ve `generate-secrets.sh`'ı gösterir |
| `.env`'de `ENVIRONMENT=production` + `DEMO_MODE=true` | Başlamaz; "DEMO_MODE=false olmalı" der |
| `.env`'de `OLLAMA_BASE_URL`'i bozun | Puanlama başarısız olur ama **sistem ayakta kalır**; güvenlik/durum ekranları çalışır |

---

## Bölüm 12 — Ölçümü kendiniz doğrulayın

Ürünün doğruluk iddiaları yeniden üretilebilir.

**[ne yapacağım]**
```bash
make eval     # ~20-30 dk
make test
make audit
```

**[ne görmem gerekiyor]**
- `make eval`: "Tum esikler saglandi", çıkış kodu 0
- `make test`: tamamı geçti
- `make audit`: 0 ihlal

**[görmezsem sorun nedir]**
`make eval` eşik ihlali gösterirse hangi metriğin düştüğü yazılıdır. Eşiklerin
neden o değerde olduğu `scripts/golden/evaluate.py` içinde açıklanmıştır.

---

## Sistemi başlangıç durumuna döndürme

Denemeler bittikten sonra 20 bekleyen çağrıya dönmek için:

```bash
docker compose down -v          # veritabanini SILER
docker compose up -d
python scripts/seed_demo_calls.py --temizle
```

**Silinmez:** `data/golden/` (altın set), `data/human_ref/`, `docs/eval/` —
bunlar sürüm kontrolündedir.
