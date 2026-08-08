# KaliteGöz — Entegrasyon Rehberi (API v1)

Tam referans: **http://localhost:8000/docs** (OpenAPI/Swagger, otomatik üretilir).
Bu doküman entegrasyon senaryolarını anlatır.

Taban adres: `http://<host>:8000/api/v1`

---

## 1. Kimlik doğrulama

JWT: kısa ömürlü **access** + uzun ömürlü **refresh** token.

```bash
# Parola ile giriş
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@demo.local","password":"demo1234","tenant_slug":"demo"}'
# -> {"access_token":"...","refresh_token":"...","token_type":"bearer"}
```

Sonraki tüm isteklerde:
```
Authorization: Bearer <access_token>
```

Access token dolduğunda (varsayılan 30 dk):
```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H 'Content-Type: application/json' -d '{"refresh_token":"..."}'
```

> **Demo modu:** `DEMO_MODE=true` iken `POST /auth/demo-login` ile
> `{"role":"admin"}` göndererek parolasız giriş yapılabilir.
> **Production'da `DEMO_MODE=false` yapın.**

## 2. Roller ve görünürlük (RBAC)

| Rol | Görebildiği |
|---|---|
| `admin` | Tenant'ın her şeyi + kullanıcı/kampanya/yasaklı kelime yönetimi |
| `supervisor` | Kendi takımının çağrıları, kokpit, alarmlar, koçluk atama |
| `quality` | Tüm çağrılar, puan override, kalibrasyon, itiraz kararı |
| `agent` | **Yalnızca kendi çağrıları**, kendi karnesi, itiraz açma |

Her istek, kullanıcının `tenant_id`'si ile kapsanır — tenant'lar arası erişim
yoktur (testle doğrulanmıştır).

## 3. Çağrı gönderme (ingest)

### 3a. Sesli çağrı — REST upload

```bash
curl -X POST http://localhost:8000/api/v1/calls/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@cagri.wav" \
  -F "agent_name=ayse.yilmaz" \
  -F "campaign_id=1"
```

- İzinli tipler: `.wav .mp3 .m4a .ogg .flac` · Maks. **200 MB**
- `agent_name` verilmezse dosya adından çıkarılır: `ayse.yilmaz_fatura_01.wav` → `ayse.yilmaz`
- **Stereo** dosyalarda sol kanal müşteri, sağ kanal temsilci kabul edilir
  (bedava diarization). Mono dosyalarda `HF_TOKEN` varsa pyannote kullanılır.

### 3b. Sesli çağrı — toplu klasör aktarımı (watch-folder)

Dosyaları `data/inbox/` klasörüne bırakın (SFTP/rsync/batch kopya). `watcher`
servisi dosya boyutu sabitlenince otomatik alır ve depoya taşır. Dosya adı
kuralı yukarıdaki ile aynıdır.

### 3c. Chat / yazışma

```bash
curl -X POST http://localhost:8000/api/v1/chats \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{
    "filename": "chat_12345.json",
    "agent_name": "elif.arslan",
    "campaign_id": 2,
    "messages": [
      {"speaker":"temsilci","ts_sec":2,"text":"Merhaba, nasıl yardımcı olabilirim?"},
      {"speaker":"musteri","ts_sec":15,"text":"Faturamı alamıyorum."}
    ]
  }'
```

`speaker`: `musteri` | `temsilci` · `ts_sec`: görüşme başından saniye.
Chat'te STT çalışmaz; doğrudan puanlamaya girer.

## 4. Sonuçları çekme

```bash
# Filtreli liste
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/calls?status=done&channel=voice&min_score=0&max_score=60&only_crisis=true&page=1&page_size=20"

# Detay: segmentler + puanlar + ihlaller + metrikler
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/calls/42

# Ses (Range destekli)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/calls/42/audio -o cagri.wav

# CSV (Excel uyumlu, BOM'lu, ; ayraçlı)
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/calls/export.csv?date_from=2026-07-01" -o rapor.csv
```

**Filtreler:** `status, agent_id, category, channel, campaign_id, min_score,
max_score, only_crisis, only_zeroed, date_from, date_to, page, page_size`

### Çağrı detayındaki önemli alanlar

| Alan | Anlamı |
|---|---|
| `total_score` | Ağırlıklı toplam (0–100). Sıfırlayıcı ihlalde `0` |
| `zeroed` | Sıfırlayıcı ihlal tetiklendi mi |
| `is_crisis` | Kriz/eskalasyon sinyali var mı |
| `predicted_csat` | LLM'in müşteri memnuniyeti tahmini (1–5) |
| `sentiment_start` / `sentiment_end` | Müşteri duygusu (çağrı başı → sonu) |
| `metrics` | Konuşma oranı, söz kesme, sessizlik, hız (sesli) / yanıt süreleri (chat) |
| `violations[]` | Tespit edilen ihlaller: `kind, category, severity, term, speaker, evidence, ts_sec` |
| `scores[]` | Kriter kırılımı + `rationale`, `evidence`, `evidence_ts`, `override_score` |

## 5. Rubrik yönetimi

```bash
# Kriter ekle (sıfırlayıcı/kritik + kampanyaya özel)
curl -X POST http://localhost:8000/api/v1/criteria \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"Bekletme Yönetimi","description":"Müşteri bekletilirken bilgi verildi mi, 60 sn aşıldı mı?","group":"Iletisim Kalitesi","weight":1.0,"is_critical":false,"channel_scope":"voice","campaign_id":2}'

# Rubrik değişince mevcut çağrıyı STT'siz yeniden puanla
curl -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/calls/42/rescore
# STT dahil tam pipeline:
curl -X POST -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/calls/42/rescore?full=true"
```

`campaign_id: null` → kriter tüm kampanyalarda geçerli (global).
`is_critical: true` + `critical_threshold` → eşiğin altında çağrı puanı 0 + alarm.

## 6. Bilgi bankası (RAG) — yanlış bilgi tespiti

Şirket prosedür/SSS dokümanlarınızı yükleyin; puanlama sırasında temsilcinin verdiği
bilgi bu dokümanlarla karşılaştırılır. Aykırı bilgi **"Bilgi Doğruluğu"** kriterinde
düşük puanlanır ve gerekçede doğru bilgi + kaynak doküman belirtilir.

```bash
# Doküman yükle (PDF / DOCX / MD / TXT, maks 20 MB) — admin
curl -X POST http://localhost:8000/api/v1/knowledge/docs \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@iade_prosedur.pdf" -F "title=İade Prosedürü"
# -> {"id":1,"title":"İade Prosedürü","chunk_count":12,...}

# Neyin indeksli olduğunu gör
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/knowledge/docs
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/knowledge/stats
# -> {"documents":1,"chunks":12,"rag_active":true}

# RAG'in ne bulacağını önizle (anlamsal arama)
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/knowledge/search?q=iade%20suresi%20kac%20gun"

curl -X DELETE -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/knowledge/docs/1
```

- Embedding: Ollama `nomic-embed-text` (yerel, `EMBED_MODEL`) veya Gemini
  (`GEMINI_EMBED_MODEL`). Model yoksa (host Ollama): `ollama pull nomic-embed-text`
- Dokümanlar **tenant'a özeldir**; bir şirketin bilgisi diğerinin puanlamasına karışmaz.
- Bilgi bankası boşsa RAG otomatik devre dışı kalır, puanlama normal sürer.
- Doküman ekledikten sonra mevcut çağrıları güncellemek için **toplu yeniden puanlama** kullanın.

## 7. Toplu yeniden puanlama (rubrik/bilgi bankası değişince)

```bash
# Tenant'ın TÜM tamamlanmış çağrıları (STT tekrar çalışmaz, hızlı kuyrukta)
curl -X POST http://localhost:8000/api/v1/calls/rescore-bulk \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}'

# Sadece belirli çağrılar
curl -X POST http://localhost:8000/api/v1/calls/rescore-bulk \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"call_ids":[42,43,44]}'
```

## 8. Kuyruk mimarisi

| Kuyruk | İşler | Worker |
|---|---|---|
| `voice` | `process_call` (STT — dakikalar sürer) | `worker` (concurrency 1) |
| `fast` | `process_chat`, `rescore_call`, `rescore_bulk`, `apply_retention` | `worker-fast` (concurrency 2) |

Ayrım sayesinde saniyeler süren bir chat puanlaması, sıradaki uzun STT işinin
arkasında beklemez.

## 9. KVKK saklama süresi (retention)

`beat` servisi her gece **03:15**'te `apply_retention` çalıştırır: tenant'ın
`retention_days` (varsayılan 365) süresini aşan çağrıların ses dosyası, transkript
dosyası ve DB kaydı silinir; işlem `audit_logs`'a `retention_delete` olarak yazılır.
`retention_days <= 0` → sınırsız saklama.

## 10. Webhook (dışa olay bildirimi)

`.env` → `WEBHOOK_URLS=https://crm.sirket.com/hook,https://hooks.slack.com/...`

İhlal/kriz/düşük puan olayları şu gövdeyle POST edilir:

```json
{
  "event": "zeroing",
  "data": {
    "call_id": 42, "tenant_id": 1, "agent": "zeynep.demir",
    "severity": "yuksek",
    "message": "Kritik kriter esik alti: KVKK / Aydinlatma (0/3)",
    "total_score": 0.0
  }
}
```

`event`: `zeroing` | `crisis` | `banned_word` | `low_score`
Gönderim best-effort'tur; webhook hatası pipeline'ı durdurmaz.

## 10b. Canlı alarm (WebSocket)

Webhook *dışa* bildirim içindir; panel içi canlı bildirim WebSocket'ledir.

```
ws://localhost:8000/api/v1/ws/alerts?token=<ACCESS_TOKEN>
```

**Neden query string?** Tarayıcının WebSocket API'si özel HTTP başlığı
göndermeye izin vermez — `Authorization` header kullanılamaz. Bu yüzden
yalnızca **kısa ömürlü access token** kabul edilir (refresh token reddedilir);
URL'ler erişim loglarına düz metin düşebilir.

Bağlanınca önce `{"type":"ready"}` gelir, sonra her alarm için:

```json
{
  "type": "alert",
  "data": {
    "id": 128, "tenant_id": 1, "team_id": 3, "call_id": 42,
    "type": "kritik_ihlal", "severity": "yuksek",
    "message": "Kritik kriter esik alti: KVKK / Aydinlatma (0/3)",
    "is_read": false, "created_at": "2026-07-16T00:00:00", "agent": "zeynep.demir"
  }
}
```

**Kapsam** `GET /api/v1/alerts` ile birebir aynıdır: tenant izolasyonu zorunlu,
süpervizör yalnızca kendi takımı + takımsız alarmları görür, temsilci bu akışa
bağlanamaz.

**Reddedilme davranışı:** yetkisiz bağlantı `accept()` edilmeden kapatılır; ASGI
bunu **HTTP 403 handshake reddine** çevirir — istemci özel kapanış kodu (4401/4403)
*görmez*, yalnızca başarısız handshake / 1006 görür. İstemci bu yüzden "yetki
hatası" ile "ağ koptu"yu ayırt edemez; yeniden deneme sayısı sınırlanmalıdır.

**Mimari:** alarmlar Celery worker'da (ayrı container) oluşur, WebSocket API'de
durur. Köprü **Redis pub/sub** (`kg:alerts` kanalı) — Celery broker'ı zaten Redis
olduğu için ek bağımlılık yoktur. Yayın best-effort'tur: Redis erişilemezse alarm
yine de veritabanına yazılır ve panel yoklama ile görür.

## 11. Raporlar

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/reports/team.xlsx -o ekip.xlsx
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/reports/agent/3.pdf -o karne.pdf
```

**Zamanlanmış e-posta raporu:** her Pazartesi 08:30'da haftalık ekip raporu (Excel)
e-postayla gönderilir. `.env` → `SMTP_HOST/PORT/USER/PASSWORD` + `REPORT_RECIPIENTS`.
SMTP tanımlı değilse rapor üretilir ama gönderilmez (özellik kimlik bilgisi olmadan da güvenli).

```bash
curl http://localhost:8000/api/v1/reports/email/status -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:8000/api/v1/reports/email/send-now -H "Authorization: Bearer $TOKEN"  # admin
```

## 11b. WFM / CRM entegrasyonu (bağlantı yolları)

KaliteGöz vendor'a özel konektör yerine **standart, açık entegrasyon yüzeyleri** sunar —
Genesys/Avaya/Salesforce dahil her sistem bunlardan biriyle bağlanır:

| Yön | Yöntem | Kullanım |
|---|---|---|
| **İçeri (çağrı besleme)** | Watch-folder | Santral ses kaydını `data/inbox/`'a bırakır → otomatik işlenir |
| **İçeri (çağrı besleme)** | REST upload | `POST /api/v1/calls` (multipart) — programatik yükleme |
| **İçeri (metadata)** | CSV eşleştirme | `POST /api/v1/admin/import-metadata` — temsilci/kampanya/müşteri-ref bağlar |
| **İçeri (chat)** | REST | `POST /api/v1/chats` — yazışma kanalı transkripti |
| **Dışarı (olay)** | Webhook | `WEBHOOK_URLS` — ihlal/kriz JSON POST (CRM'e ticket açma) |
| **Dışarı (bildirim)** | Slack/Teams | `SLACK_WEBHOOK_URL` / `TEAMS_WEBHOOK_URL` |
| **Dışarı (rapor)** | E-posta / Excel / PDF | SMTP + `/reports/*.xlsx` `.pdf` |

Örnek — santral gece toplu export'u:
```bash
# 1) Ses dosyalarını watch-folder'a kopyala (santral cron'u)
cp /pbx/recordings/*.wav /kalitegoz/data/inbox/
# 2) Metadata'yı eşleştir (temsilci/kampanya/müşteri-ref)
curl -X POST http://localhost:8000/api/v1/admin/import-metadata \
     -H "Authorization: Bearer $TOKEN" -F file=@export.csv
```

## 12. İzleme (observability)

```bash
curl http://localhost:8000/api/health    # {"status":"ok","version":"2.0.0"}
curl http://localhost:8000/metrics       # Prometheus formatı: istek/hata/gecikme
```

Loglar JSON formatındadır (`docker compose logs api`), log toplayıcıya doğrudan verilebilir.

## 13. Hata kodları

| Kod | Anlamı |
|---|---|
| 401 | Token yok/geçersiz/süresi dolmuş → `/auth/refresh` |
| 403 | Rol yetkisi yok (ör. temsilci kriter ekleyemez) |
| 404 | Kayıt yok **veya başka tenant'a ait** (izolasyon) |
| 409 | Çakışma (ör. çağrı işlenirken rescore, açık itiraz zaten var) |
| 413 | Dosya 200 MB'tan büyük |
| 429 | Rate limit (`RATE_LIMIT_PER_MIN`, varsayılan 120/dk/IP) |

## 14. İşleme durumları

`pending → transcribing → scoring → done` (hata: `failed`)

`failed` çağrılar Celery ile otomatik 2 kez yeniden denenir (üstel geri çekilme).
Kalıcı hatada `error` alanı doldurulur; `POST /calls/{id}/rescore?full=true` ile
manuel yeniden kuyruğa alınır.
