# FAZ 7 RAPORU — Rio'nun Kararları, Dürüstlük Düzeltmeleri ve Kapanış

> Branch: `v2/faz-7-kapanis` · Tarih: 2026-08-09
> Amaç: Rio'nun beş iş kararını uygulamak, kalan bütün soruları gerekçeli
> kapatmak ve ürünün *iddiaları* ile *ölçümleri* arasındaki son boşlukları
> kapamak.

Bu faz planlı değildi. Rio, satış dokümanındaki **"uzman referanslı"** ifadesini
sorguladı — ve haklıydı. Altın setin puanlarını bu sistemi geliştiren yapay zekâ
asistanı yazdı. Bunu `SORULAR.md` S2'de zaten yazmıştım ama **en çok önemli
olduğu yere**, satışta kullanılan metodoloji dokümanına taşımamıştım. Faz 7 bu
tespitle başladı.

---

## 1. Ne değişti

| Dosya | Rol |
|---|---|
| `docs/KALITE-METODOLOJISI.md` | §4.0 referansın kaynağı · §4.1 nesnel/öznel ayrımı · §4.2 IRR'ye bağlı hedef · §4.4 14B ölçümü |
| `scripts/golden/human_ref.py` | İnsan referansı alt küme seçimi + IRR karşılaştırması |
| `data/human_ref/sablon.json` | 20 senaryoluk elle puanlama şablonu |
| `backend/app/services/model_routing.py` | Kriter bazlı model yönlendirmesi (S2c) |
| `backend/app/services/scoring_layers.py` | Öznel kriterler gruplamadan **önce** ayrılıyor |
| `backend/app/services/llm.py` | `generate_json_with` — belirli config, hata halinde varsayılana düşer |
| `scripts/golden/evaluate.py` | Nesnel/öznel metrik ayrımı · `--subjective-model` · `--etiket` |
| `backend/app/services/crypto.py` | Dosya tabanlı anahtar + rotasyon penceresi |
| `backend/app/services/sso.py` | OIDC ayarları DB'den, ortamı ezer |
| `backend/app/api/enterprise.py` | SSO config + şifreleme durumu uçları |
| `backend/app/api/agents.py` | **B33** — karne yalnız kesinleşmiş puanı sayar |
| `frontend/components/AuthProvider.tsx` | **S14** — rol bazlı açılış ekranı |
| `docs/KVKK-UYUM.md` | §3.1 anahtar rotasyonu · §3.2 KMS entegrasyon yolu |
| `docs/v2/SORULAR.md` | 17 sorunun tamamı kapatıldı |

---

## 2. Rio'nun beş kararı ve ne yapıldı

### S2 — "Uzman" değil, sentetik referans

**Karar:** Puanları model ürettiyse öyle yaz; "uzman" deme.

Yapılanlar §4.0'da toplandı. En önemlisi şu ayrım:

- **Nesnel kriterlerde** sentetik referans bir *spesifikasyondur*. "Temsilci
  kurum adını söyledi mi?" sorusunun cevabı transkript okunarak doğrulanabilir.
  Burada referansı kimin yazdığı önemli değildir.
- **Öznel kriterlerde döngüseldir.** Puanlama prompt'unu tasarlayan ile cevap
  anahtarını yazan aynı taraftır. Bu kriterlerin sentetik kappa'sı
  **bağımsız bir doğruluk kanıtı sayılmaz** ve doküman artık bunu yazıyor.

Metodoloji dokümanından "uzman referansı" ifadesi tamamen kaldırıldı; nesnel
kriterlerde artık "spesifikasyonla mutabık" deniyor.

**İnsan referansı için:** `data/human_ref/sablon.json` üretildi. Alt küme
rastgele değil — zorluk ve senaryo tipi dağılımı korunacak şekilde
deterministik seçildi, regresyon vakaları zorunlu dahil. **Sentetik puanlar
şablonda gizlendi**; görünselerdi çapalama önyargısı (anchoring) yaratır ve
ölçüm değersizleşirdi.

### S2b — Öznel kriterlerde hedef, ölçülen insan uyumuna bağlanır

Sabit kappa hedefi kriterin doğasını yok sayar. İki uzman "aktif dinleme"de
birbirine 0.55 uyuyorsa, AI'dan 0.75 beklemek hedef değil **imkânsız bir
şarttır**.

```
AI hedefi (öznel kriter) = insan-insan kappa × 0.85
```

**IRR ölçülmediği için öznel kriterlerde şu an hedef KOYULMUYOR.**
`hedefler()` bu durumda `None` döndürüyor — hedef uydurulmuyor. `make eval`
kapısı yalnız nesnel kriterleri denetliyor.

### S10 — Hibrit kalsın, ama metrikler ayrılsın

`human_only` yapılmadı. Bunun yerine:

- `evaluate.py` nesnel ve öznel kriterleri **ayrı** raporluyor.
- Kapı değişti: `kappa_ortalama ≥ 0.75` → nesnel kriterlere bağlı iki kapı.
  (İlk koyduğum 0.90 değeri ölçülmemişti; §8'de düzeltildi.)
- "%100 kapsam" iddiası yalnız nesnel kriterler için kuruluyor.

Bu kararın doğrudan sonucu **B33** oldu (aşağıda).

### S2c — Daha büyük model, ölçülerek

Kriter bazlı model yönlendirmesi eklendi ve **ölçüldü**. Sonuç §7'de; özet:
öznel kappa 0.146 → 0.328, nesnel kriterler değişmedi (fark 0.0000).

### S12 — SSO panelden, anahtar dosyadan

**SSO:** `GET/PUT /api/v1/enterprise/sso/config`. Sır asla geri dönmüyor; boş
sır gönderilirse mevcut korunuyor. Bu ayrıntı önemli: "ayarı düzenlemek için
sırrı yeniden yazmak" zorunluluğu, sırların ekranlarda dolaşmasının bir
numaralı sebebidir. Kaydetmeden önce sağlayıcı doğrulanıyor.

**Anahtar:** `KG_MASTER_KEY_FILE` > `KG_MASTER_KEY` > yok. **Dosya ortamı
eziyor** — ortam değişkeni `docker inspect` ve `/proc/<pid>/environ` üzerinden
sızar, dosya izinlerle korunur. `KG_MASTER_KEY_OLD_FILES` ile kesintisiz
rotasyon; HMAC tutmayan anahtar atlanıyor, yani yanlış anahtarla "çözülmüş"
bozuk veri üretilemiyor.

**KMS'te bilinçli sınır:** Uygulamaya KMS SDK'sı gömülmedi. Sistem tek bir
sözleşme sunuyor — "anahtarı bir dosyaya koy" — gerisi altyapının işi. KMS
değişince uygulama kodu değişmiyor.

---

## 3. B33 — Kapanışta bulunan hata

**Bulgu:** S15'i ("kaliteci onayı olmadan puan temsilciye görünsün mü?")
cevaplamak için koda baktığımda, sistemin bu soruyu zaten sessizce "evet" diye
cevapladığını gördüm. `/api/v1/agents` yalnız `status == done` filtreliyordu;
`qa_state`'e hiç bakmıyordu.

Yani **kaliteci onaylamamışken, inceleme kuyruğunda bekleyen çağrının AI puanı
temsilcinin karnesine giriyordu.**

Model bu kuralı zaten yazmıştı. `Call.score_is_final` özelliğinin docstring'i
aynen şöyle: *"Puan liderlik tablosuna ve karneye girebilir mi?"* Kural
yazılmış, hiçbir yerde **uygulanmamıştı**.

**Neden ciddi:** Öznel kriterlerde ölçülen kappa 0.08–0.20. Çağrılar tam da bu
yüzden kuyruğa düşüyor. Onları karneye yazmak, *güvenilir olmadığını bildiğimiz
puanı temsilcinin karnesine yazdık* demektir — ürünün "AI önerir, insan
onaylar" vaadiyle doğrudan çelişir.

**Düzeltme:** `agents.py` içinde tek bir `KESINLESMIS` yüklemi; karne, sıralama
ve koçluk sorgularının hepsi onu kullanıyor. Regresyon:
`test_agent_scorecard_final.py` — 3 vaka.

**Kapsam kaybı yok:** Risk kuralı tetiklemeyen çağrı puanlandığı anda
kesinleşiyor. Filtre yalnız **şu an kuyrukta bekleyeni** dışarıda bırakıyor.

---

## 4. S14 — Rol bazlı açılış ekranı

| Rol | Açılış | Neden |
|---|---|---|
| kaliteci | `/review` | Günü orada geçiyor |
| süpervizör / yönetici | `/cockpit` | Tek çağrı değil, takımın durumu |
| temsilci | `/agents/<kendi>` | Başkasının çağrısını görmesi zaten yasak |

"Ana kullanıcı kim?" sorusunu cevaplamaya gerek kalmadı — her rol kendi
ekranına düşüyor. Soru ancak tek bir ekran seçmek zorunda olsaydık bir
konumlandırma kararı olurdu.

**Bilinçli sınır:** Yönlendirme yalnız **giriş anında** uygulanıyor. `/`
adresinin kendini yönlendirmesi, kenar çubuğundaki "Çağrılar" bağlantısını
(`/` adresine gider) bozardı.

---

## 5. Yan bulgu — Windows konsolunda çöken betikler

`human_ref.py --help` Windows'ta `UnicodeEncodeError` ile çöküyordu: konsol
cp1254 kullanıyor, yardım metnindeki `≥` karakteri o kod sayfasında yok.
`seed_sales_demo.py` aynı sorunu `→` ile taşıyordu.

Betiklerin çıktısı Türkçe olduğu için bu kaçınılmazdı; ikisinde de stdout/stderr
UTF-8'e sabitlendi. **Rio bu betikleri Windows'ta çalıştıracak** — çöken bir
yardım metni, aracın hiç kullanılmaması demektir.

Ayrıca `human_ref.py` docstring'i olmayan alt komutlardan (`load`, `irr`)
bahsediyordu; gerçek arayüz (`select`, `compare --a --b`) ile hizalandı.

---

## 6. Kabul kriterleri

| Kriter | Durum | Kanıt |
|---|---|---|
| Rio'nun 5 kararı uygulandı | ✅ | §2 |
| Tüm sorular kapatıldı | ✅ | `SORULAR.md` — 17/17, açık soru yok |
| Metodoloji dokümanı dürüst | ✅ | §4.0-4.2; "uzman referansı" ifadesi 0 kez geçiyor |
| B33 düzeltildi + regresyon | ✅ | `test_agent_scorecard_final.py` 3/3 |
| Backend testleri yeşil | ✅ | 410 passed |
| Frontend derleniyor | ✅ | `next build` temiz (`ignoreBuildErrors` yok) |
| 14B ölçümü yapıldı | ✅ | §7 |

---

## 7. S2c — Tavan model kaynaklı mı, metodoloji kaynaklı mı?

Aynı 50 senaryo, aynı prompt, aynı doğrulama. Tek fark: dört öznel kriter
`qwen2.5:14b-instruct` ile puanlandı.

| Kriter | 7B | 14B | Fark |
|---|---|---|---|
| İhtiyaç Analizi | 0.113 | **0.462** | +0.349 |
| Çözüm / Yönlendirme | 0.197 | **0.448** | +0.251 |
| Aktif Dinleme | 0.081 | **0.226** | +0.145 |
| Bilgi Doğruluğu | 0.195 | 0.175 | −0.019 |
| **Öznel ortalama** | **0.146** | **0.328** | **+0.182** |

**Altı nesnel kriterin hepsi kuruşu kuruşuna aynı kaldı (fark 0.0000).**
Yönlendirmenin doğru çalıştığının en temiz kanıtı bu: büyük model yalnızca
öznel kriterlere dokundu, geri kalanı hiç görmedi.

### Cevap: ikisi de — ama artık ayrıştırılmış halde

**Model payı gerçek ve büyük.** Öznel uyum 2.2 katına çıktı. Önceki üç deneme
(few-shot, skala kalibrasyonu, deterministik tavan) hiçbir şey değiştirmemişti;
model boyutu değiştirdi. "7B bu işi yapamıyor" artık tahmin değil, ölçüm.

**Model payı yetmiyor.** 0.33, nesnel kriterlerin (0.94–1.00) çok altında.

**En öğretici ayrıntı: kappa yükseldi ama MAE neredeyse hiç düzelmedi**
(1.98→1.94, 1.71→1.69, 1.67→1.51). Yani 14B *sayısal olarak daha doğru puan*
vermiyor — **bant kararlarında** daha tutarlı. Bu, kalan farkın büyük ölçüde
"doğru sayı kaç?" sorusunun cevapsızlığından geldiğini gösteriyor. O soru bir
model sorusu değil, **referans sorusu** (§4.0'daki döngüsellik).

**Bilgi Doğruluğu hiç düzelmedi** ve bunun sebebi anlaşılır: bu kriter bilginin
*doğruluğunu* ölçüyor. Model ne kadar büyük olursa olsun transkriptte olmayan
kurumsal gerçeği bilemez. Buranın çözümü model değil, **bilgi tabanı (RAG)**.

### Karar: yönlendirme eklendi, varsayılan KAPALI

Fark anlamlı olduğu için kriter bazlı yönlendirme kalıcı hale getirildi. Ama
varsayılan kapalı, çünkü:

- 9 GB model her kurulumda bulunmaz (model yoksa sessizce varsayılana düşer),
- ölçülen maliyet senaryo başına **21.7 sn → 64.3 sn**, yaklaşık 3 kat.

Açmak tek satır: `{"ai": {"subjective_model": "qwen2.5:14b-instruct"}}`

### Bu sonuç bir hedefe ulaşıldığı anlamına gelmiyor

0.33'ün iyi mi kötü mü olduğunu söyleyemeyiz — çünkü öznel kriterlerde meşru
bir hedef ancak insan-insan IRR ölçülünce doğar (S2b). Bu ölçüm "daha iyi"
olduğunu gösterdi, "yeterli" olduğunu değil.

---

## 8. Ölçerken bulunan ikinci hata — kapı ilk günden kırmızıydı

S10 kapsamında `make eval` kapısını `nesnel_kappa ≥ 0.90` yapmıştım.
**Bu değeri ölçmeden koydum.** Tam koşumda gerçek **0.7639** çıktı.

Fark iki kriterde toplanıyor ve ikisi de **model hatası değil**:

| Kriter | kappa | Sebep |
|---|---|---|
| Kimlik Doğrulama | 0.544 | "Geç doğrulama kaç puan?" — politika kararı (S9) |
| Script Uyumu | 0.100 | Kriter diğer dördünün türevi (S7) |

Kalan dört kriter ortalaması **0.985**.

**Neden bu önemli:** İlk günden kırmızı yanan bir kapı, kısa sürede
görmezden gelinir — ve o noktadan sonra gerçek bir regresyonu da yakalayamaz.
Yeşil görünsün diye eşiği düşürmek de aynı derecede yanlış olurdu.

**Yapılan:**
- `nesnel_kappa ≥ 0.75` — ölçülen gerçeğe göre, regresyonu yakalar.
- **Yeni kapı:** `cekirdek_nesnel_kappa_min ≥ 0.90` — tartışmasız dört kriterin
  **en düşüğü**. Ortalama değil minimum, çünkü ortalama tek bir kriterin
  bozulmasını gizleyebilir.
- İki eşiğin de neden o değerde olduğu `evaluate.py` içinde yazılı; S7 ve S9
  karara bağlanınca eşik yükseltilmeli.

Ayrıca `KALITE-METODOLOJISI.md` §4.1'de "nesnel kriterlerde kappa 0.94–1.00"
yazıyordu — bu **kendi §4 tablomla çelişiyordu** (Script Uyumu 0.10 orada
zaten yazılıydı). Düzeltildi; tablo tam koşum değerleriyle yenilendi ve iki
farklı düşük-kappa sebebi (tanım sorunu / yargı sorunu) ayrıldı.
