# KaliteGöz — FAZ 0 AUDIT

**Tarih:** 2026-07-14
**Amaç:** Mevcut v1.0 (tek kanallı QA aracı) → Hedef (kurumsal, multi-tenant, satılabilir kalite yönetim platformu) gap analizi.

---

## 1. Mevcut mimari (v1.0 — bu depoda çalışan hal)

### Backend (FastAPI + Celery/Redis + PostgreSQL)
| Katman | Dosya | Durum |
|---|---|---|
| Config | `app/config.py` | pydantic-settings, .env; STT/LLM/chunk ayarları |
| DB | `app/db.py` | SQLAlchemy 2.0, `create_all` (migration YOK) |
| Modeller | `app/models.py` | `Agent, Call, Segment, Criterion, Score` |
| Pipeline | `app/tasks/pipeline.py` | `process_call`, `rescore_call` |
| Servisler | `app/services/*` | `audio`(ffmpeg), `stt`(faster-whisper), `diarization`(stereo/pyannote), `metrics`(deterministik), `llm`(Ollama/Gemini), `scoring`(rubrik+map-reduce), `ingest` |
| API | `app/api/*` | `calls, criteria, agents, stats` — hepsi `/api/...` (versiyonsuz) |
| Watch-folder | `app/watcher.py` | PollingObserver |

### Frontend (Next.js 14 + Tailwind)
- Sayfalar: `/` (çağrı listesi + filtreler + trend + kategori), `/calls/[id]` (player + senkron transkript + puan kartları + metrikler + duygu + koçluk), `/agents`, `/agents/[id]`, `/rubric`.
- Auth YOK, rol YOK, admin panel YOK.

### Veri modeli (mevcut)
- `Agent(id, name)` — tek alan, takım/kampanya/kullanıcı bağı yok.
- `Call(...)` — voice-only; tenant_id yok.
- `Criterion(name, description, weight, is_active)` — grup yok, kritik/sıfırlayıcı bayrak yok, kuyruk eşleşmesi yok.
- `Score(...)` — snapshot'lı, insan override alanı yok.

### Doğrulanan çalışan yetenekler
- Stereo kanal ayrımı ile bedava diarization; mono'da pyannote fallback.
- Deterministik akustik-benzeri metrikler (talk ratio, söz kesme, sessizlik, wpm).
- LLM rubrik puanlama: JSON şema zorlama + repair + map-reduce (>15dk).
- Duygu değişimi + koçluk önerisi.
- 10 çağrılık demo (tek TR sesi `dfki`, pitch shift), watch-folder, CSV export.
- Uçtan uca test edildi: 10/10 çağrı işlendi, 2 kötü çağrı düşük puan aldı.

---

## 2. Hedef durum (5 fazlık kurumsal spec)

Çok kanallı denetim (voice+chat+görsel), yönetilebilir rubrik & uyum motoru (grup, sıfırlayıcı ihlal, kuyruk-rubrik eşleşmesi, script semantik, yasaklı kelime motoru, RAG bilgi doğruluğu, kriz), insan katmanı (RBAC 4 rol, kalibrasyon/itiraz, gamification, süpervizör kokpiti), kurumsal (multi-tenant, KVKK/PII maskeleme, retention, audit log, raporlama/webhook), production (pgvector, testler, CI, observability, güvenlik, satış dokümanları).

---

## 3. GAP LİSTESİ (mevcut → hedef)

### Omurga (her şeyin bağlı olduğu)
- [G1] API versiyonlama yok → `/api/v1`.
- [G2] Multi-tenancy yok → `tenant_id` her tabloda + service-layer scoping.
- [G3] Auth/RBAC yok → JWT + refresh, 4 rol (admin/supervisor/quality/agent).
- [G4] Migration yok → Alembic (mevcut DB'yi kırmadan additive migration).
- [G5] pgvector yok → RAG için `pgvector` imajı + extension.
- [G6] Kullanıcı/Takım/Kampanya(Kuyruk) modeli yok.

### FAZ 1 — Çok kanallı
- [G7] Akustik analiz katmanı deterministik ama librosa/praat değil (pitch/bağırma yok) → gerçek akustik metrikler.
- [G8] Chat kanalı yok → `POST /api/v1/chats`, chat metrikleri, chat puanlama.
- [G9] Görsel denetim yok → vision (llava/Gemini) ile ek dosya analizi.

### FAZ 2 — Rubrik & uyum motoru
- [G10] Kriter grubu + puan aralığı + sıfırlayıcı bayrak yok.
- [G11] Kuyruk/kampanya bazlı rubrik eşleştirme yok.
- [G12] Script semantik uyum modülü (LLM) yok.
- [G13] Yasaklı kelime motoru (regex+fuzzy+LLM bağlam, kim söyledi) yok.
- [G14] Bilgi bankası + RAG (pgvector) + yanlış bilgi tespiti yok.
- [G15] Kriz & eskalasyon alt-rubriği + etiket + süpervizör kuyruğu yok.

### FAZ 3 — İnsan & operasyon
- [G16] RBAC 4 rol (yukarıda G3).
- [G17] Kalibrasyon (AI vs insan override + sapma raporu) yok.
- [G18] İtiraz akışı yok.
- [G19] Gamification (lig, rozet, radar, haftalık AI koçluk) yok.
- [G20] Süpervizör kokpiti (KPI duvarı, alarm kuyruğu WebSocket, koçluk görevi) yok.

### FAZ 4 — Kurumsal & satış
- [G21] Multi-tenant (G2).
- [G22] PII maskeleme (harici LLM'e maskeli gitme garantisi) yok.
- [G23] Retention (scheduled silme) + audit log (append-only) yok.
- [G24] Raporlama PDF/Excel + zamanlanmış e-posta yok.
- [G25] Webhook sistemi yok.
- [G26] Toplu içe aktarma + CSV metadata eşleştirme kısmi (watch-folder var).
- [G27] `make demo` + landing/rol seçim demo girişi + zengin demo (30+ çağrı, kadın ses, chat, görsel, 8 haftalık trend) yok.

### FAZ 5 — Production
- [G28] pgvector'lı compose (G5), healthcheck var.
- [G29] pytest (rubrik, maskeleme, RBAC, tenant izolasyonu) + frontend smoke + CI yok.
- [G30] Retry/dead-letter + başarısız işler ekranı yok.
- [G31] Observability (JSON log, süre metrikleri, /metrics) yok.
- [G32] Güvenlik sertleştirme (rate limit, upload doğrulama tip/boyut) kısmi.
- [G33] Satış dokümanları (SALES-ONEPAGER, DEMO-SCRIPT, API.md) yok.

---

## 4. Kritik kararlar (audit sonucu, sabitlenen)

1. **Tenant izolasyonu:** Service-layer scoping (her sorgu `tenant_id` ile filtrelenir; ortak `TenantQuery` yardımcı + dependency). PostgreSQL RLS yerine bu seçildi — Alembic ve test edilebilirlik daha basit, tek DB kullanıcısı yeterli.
2. **Auth:** JWT access (kısa) + refresh (uzun), bcrypt (passlib). Rol enum kullanıcı üstünde.
3. **Migration:** Alembic; mevcut tablolar için "additive" ilk migration (drop yok). `create_all` bırakılıp Alembic'e geçilir; ilk revizyon mevcut şemayı da kapsar ki temiz DB'de de kurar.
4. **Vector:** `pgvector/pgvector:pg16` imajı; `vector` extension; embedding Ollama (`nomic-embed-text`) veya Gemini embeddings.
5. **API sözleşmesi:** Yeni her şey `/api/v1`. Eski `/api/*` route'ları geriye dönük kırılmasın diye v1'e taşınır; frontend `NEXT_PUBLIC_API_URL` + `/api/v1` kullanır.
6. **Kapsam gerçekçiliği:** Tek oturumda tüm 5 faz "production-satış" kalitesinde bitmez. Omurga + en yüksek değerli, test edilebilir farklılaştırıcılar önce; kalan maddeler ROADMAP'te dürüst statüyle işaretlenir. Placeholder/TODO bırakılmaz — yazılan her modül çalışır.
