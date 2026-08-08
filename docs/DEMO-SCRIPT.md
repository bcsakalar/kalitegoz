# KaliteGöz — Canlı Demo Senaryosu

**Süre:** ~12 dakika · **Hedef kitle:** Çağrı merkezi müdürü, kalite yöneticisi

## Demodan önce (15 dk önce yapın)

```bash
make demo          # stack + model + demo verisi
make logs          # sesli çağrıların işlenmesini izleyin
```

Sesli çağrılar CPU'da birkaç dakikada işlenir. **Demodan önce çağrı listesinin
"Tamamlandı" durumunda olduğunu doğrulayın.** Tarayıcıda http://localhost:3000
açık, çıkış yapılmış (login ekranı) halde bekletin.

---

## 1. Açılış — problemi çerçevele (1 dk)

> "Bugün çağrılarınızın yüzde kaçını dinliyorsunuz?"

Cevap genelde %2–5'tir. Ardından:

> "KaliteGöz %100'ünü dinliyor. Üstelik sadece sesli çağrıları değil, chat
> yazışmalarını da. Size üç şey göstereceğim: kaçırdığınız ihlaller, kalite
> ekibinizin kazandığı zaman, ve temsilcilerin nihayet itiraz edebildiği
> şeffaf bir puanlama."

## 2. Rol seçimi — "herkes kendi penceresinden görür" (30 sn)

Login ekranını gösterin: 4 rol kartı.

> "Aynı platform, dört farklı pencere. Temsilci yalnızca kendi çağrılarını
> görür — bu KVKK açısından da, ekip huzuru açısından da kritik."

**Süpervizör** ile girin.

## 3. Kokpit — yönetici penceresi (2 dk)

`/cockpit`

Gösterilecekler:
- Ortalama kalite puanı, **tahmini CSAT** (anket beklemeden), **tahmini FCR**, AHT
- **Kriz çağrısı** ve **sıfırlayıcı ihlal** sayaçları
- İhlal dağılımı grafiği
- Ekip liderlik tablosu

> "Bu ekranı sabah kahvenizle açıyorsunuz. Dün gece kaç kriz çağrısı olmuş, kaç
> KVKK ihlali var — hepsi burada. Şu 'sıfırlayıcı ihlal' rakamına tıklayalım."

## 4. Kötü çağrı — ürünün kalbi (4 dk) ⭐

Çağrılar sayfasında **"Sadece ihlal"** filtresini işaretleyin →
`zeynep.demir_sikayet_09.wav` çağrısını açın.

Sırayla gösterin:

1. **Puan 0 + "Sıfırlayıcı ihlal" rozeti**
   > "Bu çağrı ortalama 40 puan alacaktı. Ama KVKK metni okunmadığı için puan
   > otomatik sıfırlandı. Bu kuralı siz koyuyorsunuz — panelden."

2. **Tespit edilen ihlaller** bölümü
   > "'Saçmalamayın' — hakaret, yüksek şiddet. Ve dikkat: sistem **kimin**
   > söylediğini biliyor. Müşteri küfretseydi temsilci ceza almazdı."

3. **▶ butonuna basın** → ses tam o saniyeye atlar, cümle vurgulanır
   > "Kanıt tartışmaya kapalı. Temsilci 'ben öyle demedim' diyemiyor, kayıt burada."

4. **Konuşma metrikleri**
   > "Söz kesme sayısı 2. Bu bir tahmin değil, ses analizinden gelen ölçüm.
   > LLM'in 'aktif dinleme' puanı bu ölçüme dayanıyor."

5. **Müşteri duygusu: Olumsuz → Olumsuz** + koçluk önerisi
   > "Müşteri öfkeli geldi, öfkeli gitti. Ve sistem temsilciye ne yapması
   > gerektiğini yazmış — kalite uzmanınızın yazmak zorunda kalmadığı geri bildirim."

## 5. İyi çağrı — kontrast (1 dk)

Kriz çağrısını açın (`emre.sahin_sikayet_*`):
> "Aynı öfkeli müşteri profili. Ama burada temsilci sakin kaldı, sorumluluğu
> kabul etti, somut çözüm sundu. Duygu **olumsuzdan olumluya** döndü. Bu çağrı
> sizin 'örnek çağrı' arşiviniz olur — yeni başlayanlara bunu dinletirsiniz."

## 6. Rubrik editörü — "kod yok, panel var" (1.5 dk)

`/rubric`

> "En sık gelen soru: 'Bizim rubriğimiz farklı.' Sorun değil."

- Bir kriterin ağırlığını değiştirin
- **Kritik (sıfırlayıcı)** kutusunu gösterin
- **Kampanya** seçicisini gösterin
  > "Satış hattı ile şikayet hattı aynı kriterlerle ölçülemez. Kampanya
  > seçiyorsunuz, o kriter yalnızca o kuyrukta çalışıyor."

Çağrı detayına dönüp **"Yeniden puanla"** → yeni rubrikle anında yeniden puanlanır.

## 7. Chat kanalı (1 dk)

Kanal filtresi → **Chat** → `burak.ozturk_sikayet_chat`:
> "Aynı motor yazışmayı da denetliyor. Burada ilk yanıt süresi 83 saniye ve
> temsilci aynı şablonu iki kez yapıştırmış — robotik yanıt. Sesli çağrıda
> yakaladığımız her şeyi burada da yakalıyoruz."

## 8. Kalite uzmanı & temsilci — güven döngüsü (1.5 dk)

Çıkış → **Kalite Uzmanı** ile girin → bir çağrıda **"Puanı düzelt"**:
> "AI son söz değil. Uzmanınız düzeltir, gerekçe yazar — ve sistem AI ile insan
> arasındaki sapmayı ölçer." → `/workflow` → **Kalibrasyon** sekmesi.

Çıkış → **Temsilci** ile girin:
> "Temsilci yalnızca kendi çağrılarını görüyor. Puanını haksız buluyorsa
> **itiraz** ediyor — kalite uzmanının kuyruğuna düşüyor, karar ve gerekçe
> denetim kaydına yazılıyor. Kalite puanı artık dayatma değil, süreç."

`/leaderboard` gösterin — kendi sırası vurgulu.

## 9. Kapanış (1 dk)

> "Özetle: çağrılarınızın %100'ü denetleniyor, ihlaller aynı gün yakalanıyor,
> kalite ekibiniz dinlemek yerine koçluk yapıyor. Veriniz kendi sunucunuzda
> kalıyor — Ollama ile tamamen offline çalışıyor. Kurulum tek komut.
>
> Bir sonraki adım: bize 20 gerçek çağrı kaydı verin, kendi rubriğinizle
> puanlayıp sonuçları yan yana koyalım."

---

## Sık gelen sorular

| Soru | Cevap |
|---|---|
| "Veriler dışarı çıkıyor mu?" | Hayır. Ollama ile tamamen şirket içinde. Gemini seçerseniz de PII maskelenerek gider — testle garanti altında. |
| "AI yanılırsa?" | Kalite uzmanı düzeltir, sapma raporlanır. Ayrıca her puanın kanıt cümlesi ve ses zamanı var. |
| "Kendi rubriğimiz var" | Panelden tanımlanır; kampanya bazlı farklı rubrik desteklenir. |
| "Mevcut santralimizle çalışır mı?" | Kayıtları klasöre bırakın (watch-folder) veya REST API ile gönderin. |
| "Kaç dilde?" | Şu an Türkçe'ye optimize (STT + rubrik + prompt'lar Türkçe). |
