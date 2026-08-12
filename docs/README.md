# Dokümantasyon

| Doküman | Ne zaman okunur |
|---|---|
| [KURULUM.md](KURULUM.md) | Sistemi ayağa kaldıracaksanız. Donanım, Ollama, Docker, üretim sertleştirmesi, sorun giderme. |
| [MIMARI.md](MIMARI.md) | Sistemin nasıl çalıştığını anlamak için. Servis topolojisi, üç katmanlı puanlama, veri modeli, dizin haritası. |
| [KALITE-METODOLOJISI.md](KALITE-METODOLOJISI.md) | **Ürünün en önemli dokümanı.** Puanlamanın nasıl ölçüldüğü, hangi kriterde ne kadar güvenilir olduğu, neyin ölçülmediği. Satışta da bu kullanılır. |
| [TEST-REHBERI.md](TEST-REHBERI.md) | Sistemi kendiniz denemek için. Numaralı adımlar, her adımda ne görmeniz gerektiği. |
| [KVKK-UYUM.md](KVKK-UYUM.md) | Uyum ve güvenlik incelemesi için. Veri yerleşimi, maskeleme, saklama, şifreleme, anahtar rotasyonu, KMS. |
| [PIYASA-ANALIZI.md](PIYASA-ANALIZI.md) | Rakiplerle karşılaştırma. Neyimiz var, neyimiz yok, neden yok. |
| [API.md](API.md) | Entegrasyon yazacaksanız. |
| [SOZLUK.md](SOZLUK.md) | Terim karşılıkları — aynı kavrama iki isim verilmemesi için. |
| [ROADMAP.md](ROADMAP.md) | Ne bitti, ne bilerek yapılmadı. |
| [FINAL-RAPOR.md](FINAL-RAPOR.md) | Son turda ne değişti, ne bulundu, ne karar bekliyor. |

## Ölçüm çıktıları

`eval/` altındaki JSON dosyaları **ürünün kanıtıdır** ve bilinçli olarak
depoda tutulur. Her biri `make eval` ile yeniden üretilebilir.

| Dosya | Ne |
|---|---|
| `2026-08-09-faz1-taban.json` | v1 taban çizgisi — iyileştirme öncesi |
| `2026-08-09-faz7-final.json` | Güncel ölçüm, tüm eşikler yeşil |
| `2026-08-09-14b.json` | 14B model karşılaştırması (S2c) |

## Ekran görüntüleri

`screens/` — 16 sayfa × 2 tema. `node scripts/shots.mjs` ile yeniden üretilir.

---

## İç dokümanlar

`internal/` altındaki faz raporları, karar defteri ve arayüz denetim
raporu **depoya dahil değildir** (`.gitignore`). Bunlar geliştirme sürecinin
kaydıdır; ürünü kullanmak veya kurmak için gerekli değildir.

Depoyu klonlayan biri onları görmez — bu bilinçli bir tercihtir: ara faz
raporları, ürünün bugünkü halini anlatan dokümanlarla çelişebilecek eski
ölçümler içerir.
