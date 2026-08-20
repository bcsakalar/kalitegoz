# Güvenlik politikası

<sub>Türkçe · <a href="#security-policy">English below</a></sub>

## Açık bildirimi

Bir güvenlik açığı bulduysanız **issue açmayın.** Doğrudan yazın:

**bcan@berkecansakalar.com**

Şunları eklerseniz hızlanır: etkilenen sürüm veya commit, yeniden üretme
adımları, gözlemlediğiniz etki. İlk yanıtı 72 saat içinde vermeye çalışıyorum.

Tek kişilik bir proje olduğu için ödül programı yok; ama düzeltme yayınlandığında
— istemezseniz belirtmem — katkınızı yazıyorum.

## Bu sistemin güvenlik duruşu

KaliteGöz çağrı merkezi verisi işler: ses kaydı, transkript, temsilci ve müşteri
bilgisi. Tasarım kararları buna göre alındı.

- **Veri yerleşimi.** Ses, transkript ve puanlar kurumun donanımından çıkmaz.
  Dil modeli host makinede Ollama üzerinde çalışır; hiçbir bulut sağlayıcısına
  içerik gönderilmez.
- **Maskeleme.** Kişisel veri, analiz katmanına ulaşmadan önce maskelenir.
  Ayrıntı: [docs/KVKK-UYUM.md](docs/KVKK-UYUM.md).
- **Şifreleme ve anahtar rotasyonu.** Alan bazlı şifreleme ve kesintisiz
  anahtar rotasyonu aynı belgede anlatılıyor.
- **Model kararı sınır değildir.** Uyum kriterleri dil modeline sorulmaz;
  kural motorunda değerlendirilir. Modelin ürettiği hiçbir şey doğrudan bir
  yan etki tetiklemez.

## Kapsam dışı

- `secrets/` altındaki üretilmiş anahtarlar ve `.env` — bunlar zaten depoya
  girmez, kurulumda yerel olarak üretilir.
- Varsayılan parolayla çalıştırılan bir kurulum. `make setup` her kurulum için
  rastgele sır üretir; bunu atlayıp varsayılanla açmak yapılandırma hatasıdır.
- Ollama'nın kendi güvenlik yüzeyi — yukarı akış projeye bildirin.

---

<a name="security-policy"></a>

# Security Policy

## Reporting a vulnerability

If you find a security issue, **do not open an issue.** Write directly to:

**bcan@berkecansakalar.com**

It helps if you include the affected version or commit, reproduction steps and
the impact you observed. I aim to respond within 72 hours.

This is a one-person project, so there is no bounty programme — but I credit
reporters when a fix ships, unless you would rather I did not.

## Security posture

KaliteGöz processes call-centre data: audio, transcripts, agent and customer
information. The design follows from that.

- **Data residency.** Audio, transcripts and scores never leave the
  organisation's hardware. The language model runs on the host through Ollama;
  no content is sent to any cloud provider.
- **Masking.** Personal data is masked before it reaches the analysis layer.
  Detail in [docs/KVKK-UYUM.md](docs/KVKK-UYUM.md).
- **Encryption and key rotation.** Field-level encryption and zero-downtime key
  rotation are covered in the same document.
- **A model decision is not a boundary.** Compliance criteria are never asked
  of the language model; they are evaluated by a rule engine. Nothing the model
  produces triggers a side effect directly.

## Out of scope

- Generated keys under `secrets/` and `.env` — these never enter the
  repository; they are produced locally at setup time.
- An installation left running on default credentials. `make setup` generates
  random secrets per install; skipping it is a configuration error.
- Ollama's own security surface — report those upstream.
