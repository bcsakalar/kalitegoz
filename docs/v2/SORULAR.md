# Rio'nun Karar Vermesi Gereken İş Kararları

> Bu defter fazlar ilerledikçe büyür. **Hiçbiri beklemede değil** — her biri için
> en makul varsayımla ilerlendi, varsayım burada ve ilgili faz raporunda yazılı.
> Rio farklı karar verirse ilgili varsayım tek yerden değiştirilebilir.

**Durum kodları:** 🟡 varsayımla ilerlendi · 🟢 Rio karar verdi · ⚪ henüz sırası gelmedi

---

## FAZ 1 — Denetim ve doğruluk temeli

### S1. Altın set ses seviyesinde mi, transkript seviyesinde mi olmalı? 🟡

**Varsayım:** Transkript seviyesinde.

**Gerekçe:** Puanlama motorunun doğruluğunu ölçmek istiyoruz. Ses hattını (Whisper +
kanal ayrımı) karıştırırsak ölçülen sapmanın ne kadarının STT'den, ne kadarının
yargıdan geldiğini ayıramayız — bunlar ayrı ayrı düzeltilmesi gereken iki şey.
Ayrıca `01-KOK-NEDEN.md` §D'de ölçüldüğü gibi mevcut ses hattı zaman damgalarını
bozuyor; bozuk çıktıyı referans almak hatayı altın sete gömerdi.

**Etkisi:** Ses hattının doğruluğu ayrı bir diarizasyon regresyonuyla ölçülecek
(FAZ 2). Altın set STT hatalarını yakalamaz — bu bilinçli bir sınır.

**Rio hayır derse:** 50 senaryo için TTS ses üretilir; `make eval` süresi ~35 dk'dan
birkaç saate çıkar ve STT gürültüsü metriklere karışır.

---

### S2. Uzman referans puanlarını kim veriyor? 🟡

**Varsayım:** Prompt dosyasının verdiği "15 yıllık çağrı merkezi QA uzmanı"
şapkasıyla ben verdim. Her senaryonun `expected.json`'ında puanın neden o olduğu
`notes` alanında yazılı.

**Gerekçe:** Prompt dosyası bu rolü açıkça bana verdi ve "teknik detay sorma"
dedi. Referans puanlar 4C çerçevesi ve "10 puan neye benzer / 0 puan neye benzer"
çapası kullanılarak verildi.

**Rio'nun yapması gereken:** Altın seti gözden geçirip katılmadığı puanları
düzeltmesi. Bu, ürünün **kalibrasyon zeminini** belirler — sistemin "doğru" saydığı
şey budur. Özellikle şu 3 senaryodaki puanlar tartışmaya açık:
- `orta-03-kimlik-gec` — kimlik doğrulama işlem SONRASI yapıldı. Ben 4 verdim
  (ciddi eksik ama sıfırlamayı hak etmiyor). Uyum politikası katıysa 0-2 olmalı ve
  çağrı sıfırlanmalı.
- `orta-06-acilis-yarim` — kurum adı var, temsilci adı yok. Ben 6 verdim (kısmen
  karşılandı). Bazı merkezler bunu 0/10 ikili puanlar.
- `dusuk-03-yanlis-bilgi` — yanlış bilgi kritik sayılmalı mı? Ben 1 verdim ama
  sıfırlayıcı yapmadım.

---

### S3. Sıfırlayıcı ihlal eşiği 3/10 kalsın mı? 🟡

**Varsayım:** Şimdilik 3/10 (mevcut değer) korundu.

**Gerekçe:** FAZ 1 ölçüm fazı; eşiği değiştirmek taban çizgisini kirletirdi.
FAZ 2'de altın set verisiyle **ölçülerek** ayarlanacak: eşik, sıfırlayıcı
yanlış-pozitifi %0'a indirirken yanlış-negatifi en aza indiren değer olacak.

---

### S4. FAZ 1'de bulunan 6 yeni hata (B27–B32) kapsama dahil mi? 🟢

**Karar:** Rio "ekle, her birine regresyon vakası yaz" dedi (2026-08-09). Yapıldı:
- B29, B30, B32 → altın set senaryosu (`reg-b29-*`, `reg-b30-*`, `reg-b32-*`)
- B27, B28, B31 → motor değişmezi, birim test (`test_scoring_invariants.py`),
  `xfail(strict=True)` ile şu an kırmızı

---

### S5. Git deposu yoktu — kuruldu 🟡

**Varsayım:** Prompt dosyası faz başına branch + mantıksal adım başına commit
istiyordu ama proje versiyon kontrolü altında değildi. `git init` yapıldı,
mevcut durum `chore:` commit'i olarak dondurulup `v2/faz-1-denetim` branch'i açıldı.

**Etkisi:** v2 öncesi geçmiş yok; `0eb6ba2` sıfır noktası.

---

## FAZ 2 — Puanlama motoru

*(faz başında doldurulacak)*

## FAZ 3 — İki aşamalı kalite kontrol

⚪ Kaliteci onayı olmadan puan temsilciye görünsün mü?
⚪ Rastgele örneklem oranı %5 uygun mu?

## FAZ 5 — Arayüz

⚪ Ana hedef kullanıcı kim — kaliteci mi süpervizör mü? (varsayılan açılış ekranı)

## FAZ 6 — Dil ve demo

⚪ Hazır rubrik şablonları hangi sektörler için olsun?

---

## FAZ 2 — Puanlama motoru

### S6. Yasak vaat çağrıyı sıfırlamalı mı? 🟡

**Varsayım:** Evet. `banned_words.severity` `orta`→`yuksek` çekildi ve
"Yasaklı Kelime / Üslup" kriteri kritik yapıldı (eşik 3).

**Gerekçe:** Prompt dosyasının altın set spesifikasyonu 6 sıfırlayıcı senaryodan
birini "yasak vaat" olarak tanımlıyor. Sektör pratiğinde tutulamayan vaat,
itiraz ve tüketici şikâyetinin bir numaralı kaynağıdır.

**Rio hayır derse:** Panelden `banned_words` şiddeti `orta`ya çekilir; kriter
kritikliği rubrik editöründen kapatılır. Kod değişikliği gerekmez.

---

### S7. "Script Uyumu" nasıl tanımlansın? 🟡

**Varsayım:** Zorunlu akış = açılış + KVKK anonsu + kimlik doğrulama + kapanış.
Kriter bu dördünün bileşimi; LLM'e ayrıca sorulmuyor.

**Gerekçe:** Ölçüldü — 50 senaryonun 15'inde model bu kriter için kanıt
bulamayıp "yetersiz kanıt" döndü. Muğlaklığın kaynağı kriterin kendisiydi;
"script" hiçbir yerde tanımlı değildi.

**Rio'nun yapması gereken:** Kurumun gerçek script'i bu dört adımdan farklıysa
(örn. "işlem özeti tekrarı" veya "kampanya anonsu" da zorunluysa) kriterin
tanımı ve `deterministic.check_script` genişletilmeli.

---

### S8. Sıfırlayıcı eşik 3/10 ölçüldü mü? 🟡

**Varsayım:** 3/10 korundu.

**Gerekçe:** FAZ 2 sonunda sıfırlayıcı yanlış-pozitif **%0** ve yanlış-negatif
**%0** — yani mevcut eşik altın sette hatasız çalışıyor. Değiştirmek için bir
sebep ölçülmedi.

---

### S9. Kimlik doğrulama geç yapılırsa kaç puan? 🟡

**Varsayım:** 4/10 (`partially_met`) — yapılmış ama işlemden sonra.

**Gerekçe:** Uyum açısından ciddi eksik, ama tamamen atlanmış değil; sıfırlama
haksız olurdu. Bu kriterin kappa'sı 0.544 ile deterministik kriterler arasında
en düşüğü — uzman beklentisiyle ayrıştığı yer burası.

**Rio'nun yapması gereken:** Kurum politikası "işlem öncesi doğrulama zorunlu,
sonrası geçersiz" ise puan 0-2 olmalı ve çağrı sıfırlanmalı. Bu bir **politika
kararıdır**, teknik değil.

---

## FAZ 3 — İki aşamalı kalite kontrol

### S10. Öznel kriterler AI tarafından puanlansın mı? 🟡 ÖNEMLİ

**Varsayım:** Evet, puanlansın — ama **düşük güvenle işaretlenip insana gönderilsin**.

**Ölçüm (altın set sınav altkümesi, n=25, qwen2.5:7b-instruct):**

| Kriter | kappa | AI güvenilir mi? |
|---|---|---|
| KVKK / Aydinlatma | 1.00 | evet |
| Yasaklı Kelime / Üslup | 1.00 | evet |
| Açılış | 1.00 | evet |
| Kapanış | 0.90 | evet |
| Kimlik Doğrulama | 0.49 | sınırda |
| Bilgi Doğruluğu | 0.19 | **hayır** |
| Script Uyumu | 0.19 | **hayır** |
| Çözüm / Yönlendirme | 0.12 | **hayır** |
| İhtiyaç Analizi | 0.03 | **hayır** |
| Aktif Dinleme | 0.03 | **hayır** |

Üç mekanizma denendi ve **ölçüldü**: few-shot geri besleme (+0.007), skala
kalibrasyonu, deterministik tavan. Hiçbiri kappa'yı taşımadı.

**Seçenekler:**
- **(a) Mevcut varsayım** — puanlanır, güven 0.60 ile tavanlanır, çağrı insan
  kuyruğuna düşer. Kapsam %100 kalır ama o kriterlerin puanı fiilen "insan
  onayına kadar geçici"dir.
- **(b) `evaluation_mode='human_only'`** — AI hiç puanlamaz, kriter doğrudan
  kaliteciye gider. Prompt dosyasının kendi önerisi ("öznel sorular insana
  işaretlensin"). Daha dürüst ama kapsam iddiası zayıflar.
- **(c) Daha büyük model** — o dört kriter için 14B/32B ya da bulut modeli.
  Maliyet ve gecikme artar; ölçüm tekrarlanmalı.

**Rio'nun kararı gereken:** Satış hikâyesi "%100 kapsam" üzerine kurulu.
(b) seçeneği kapsamı %60'a düşürür ama savunulabilirliği artırır. Bu bir
konumlandırma kararıdır, teknik değil.

---

### S11. Yeni temsilci örneklem oranı %20 uygun mu? 🟡

**Varsayım:** Evet, ve bu oran kiracının genel oranını **yalnızca yükseltir**.

**Gerekçe:** İlk uygulamada yeni temsilci oranı genel oranın yerine geçiyordu;
kiracı %50 ayarlasa bile yeni temsilciler %20'ye düşüyordu — "daha sıkı takip"
ayarı yeni temsilciyi daha az denetler hale getiriyordu. Test ile kilitlendi.
