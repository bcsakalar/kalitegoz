# data/

Docker Compose bu klasörü tüm backend servislerine `/data` olarak mount eder.

- `inbox/` — **watch-folder**: buraya düşen wav/mp3 dosyaları watcher servisi
  tarafından otomatik işlenir ve depoya taşınır. Dosya adı
  `temsilci_adi_serbest.wav` biçimindeyse temsilci otomatik atanır.
- `storage/audio/` — işlenen ses dosyaları
- `storage/transcripts/` — çağrı başına JSON transkript kopyası
- `voices/` — demo üreteci için indirilen Piper TTS ses modelleri
