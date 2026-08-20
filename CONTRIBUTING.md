# Katkı rehberi

<sub>Türkçe · <a href="#contributing">English below</a></sub>

Bu depoya katkıda bulunmayı düşündüğünüz için teşekkürler. Aşağıdakiler kural
değil, burada işlerin neden böyle yürüdüğünün açıklaması.

## Önce şunu bilin

KaliteGöz'ün iddiası hız değil, **doğruluğunu ölçebilmesi**. Bir çağrıya puan
veren her kod yolunun karşılığında `data/golden/` altında bir senaryo ve
`docs/eval/` altında ölçülmüş bir çıktı vardır. Puanlamaya dokunan bir değişiklik
gönderiyorsanız, `make eval` çıktısını da gönderin — sayı düştüyse bu tek başına
sorun değil, ama sessizce düşmesi sorun.

## Geliştirme ortamı

```bash
make setup      # sırları üret, bağımlılıkları kur
make up         # servisleri ayağa kaldır
make test       # birim + API testleri
make eval       # altın set üzerinde doğruluk ölçümü
make lint       # backend + frontend
```

Ollama **host makinede** çalışır, Docker içinde değil. Sebebi ve kurulumu
[docs/KURULUM.md](docs/KURULUM.md) içinde.

## Değişiklik gönderirken

1. **Dalınızı `main`'den açın**, açıklayıcı bir isim verin.
2. **Testleri çalıştırın.** Puanlama, uyum veya güvenlik katmanına
   dokunuyorsanız ilgili testi de yazın — bu üç alanda testsiz değişiklik
   birleştirilmiyor.
3. **Neden'i yazın.** Commit mesajı ve PR açıklaması *ne* yaptığınızı değil,
   *neden* öyle yaptığınızı anlatsın. Kodun kendisi zaten ne yaptığını söylüyor.
4. **Sır göndermeyin.** `.env`, `secrets/`, ses kaydı, gerçek transkript ve
   müşteri verisi depoya girmez; `.gitignore` bunları engelliyor ama gözden
   geçirin.

## Kod tarzı

- Python: `ruff` + `black` (`make lint` ikisini de çalıştırır).
- TypeScript/React: `eslint` + `prettier`.
- Türkçe terimler için [docs/SOZLUK.md](docs/SOZLUK.md) — aynı kavrama iki
  isim verilmemesi için.

## Güvenlik açığı bulduysanız

Issue açmayın. [SECURITY.md](SECURITY.md) içindeki yolu izleyin.

---

<a name="contributing"></a>

# Contributing

Thanks for considering a contribution. What follows is less a set of rules than
an explanation of why things work the way they do here.

## Read this first

KaliteGöz's claim is not speed — it is that **its accuracy is measurable**.
Every code path that scores a call has a matching scenario under `data/golden/`
and a measured result under `docs/eval/`. If your change touches scoring, send
the `make eval` output with it. A number going down is not automatically a
problem; a number going down *silently* is.

## Development environment

```bash
make setup      # generate secrets, install dependencies
make up         # bring services up
make test       # unit + API tests
make eval       # accuracy run against the golden set
make lint       # backend + frontend
```

Ollama runs **on the host**, not inside Docker. The reasoning and the setup are
in [docs/KURULUM.md](docs/KURULUM.md).

## Submitting a change

1. **Branch from `main`** with a descriptive name.
2. **Run the tests.** If you touch scoring, compliance or the security layer,
   write the test too — changes to those three areas are not merged untested.
3. **Explain the why.** Commit messages and PR descriptions should say why you
   made a choice, not what you changed. The diff already says what.
4. **Never send secrets.** `.env`, `secrets/`, audio, real transcripts and
   customer data stay out of the repository. `.gitignore` blocks them, but
   check anyway.

## Code style

- Python: `ruff` + `black` (`make lint` runs both).
- TypeScript/React: `eslint` + `prettier`.
- Terminology is fixed in [docs/SOZLUK.md](docs/SOZLUK.md) so one concept never
  ends up with two names.

## Found a vulnerability?

Do not open an issue. Follow [SECURITY.md](SECURITY.md).
