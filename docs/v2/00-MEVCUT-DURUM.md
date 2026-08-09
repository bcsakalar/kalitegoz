# 00 — Mevcut Durum Denetimi (FAZ 1.1)

> Ölçüm tarihi: 2026-08-08 · Ölçülen sürüm: `main` @ `0eb6ba2` (v2 öncesi anlık görüntü)
> Bu doküman **varsayım içermez.** Her sayı çalışan sistemden veya kaynak koddan okundu.

---

## 1. Sistem sınırları ve büyüklük

| Ölçü | Değer | Nasıl ölçüldü |
|---|---|---|
| Backend Python satırı | 12.924 | `find backend/app -name "*.py" \| xargs wc -l` |
| Frontend TS/TSX satırı | 9.655 | `find frontend/{app,components,lib} \| xargs wc -l` |
| API yolu / operasyonu | 128 yol / 148 operasyon | canlı `openapi.json` |
| Veritabanı tablosu | 27 | `information_schema.tables` |
| Aktif rubrik kriteri | 10 | `criteria` tablosu |
| Backend testi | 221 (hepsi yeşil) | `pytest -q` |
| `TODO/FIXME/placeholder/lorem` geçen satır | 54 | `grep -rniE` |
| Versiyon kontrolü | **yoktu** — FAZ 1'de kuruldu | `git rev-parse` hata veriyordu |

### Servis topolojisi (ölçülen, çalışan hâli)

```
                 ┌──────────── HOST (Docker DIŞI, native) ────────────┐
                 │  Ollama :11434   (LLM + embedding + vision)        │
                 │  run-host-worker.ps1  → Celery -Q voice (Whisper)  │
                 └────────────────────────┬───────────────────────────┘
                                          │ host.docker.internal:11434
┌─────────────────────────────────────────┴──────────────────────────┐
│ DOCKER                                                             │
│  frontend(3000) ─→ api(8000) ─┬─→ postgres(5432, pgvector)         │
│                                └─→ redis(6379) ─→ worker-fast (-Q fast)
│                                                 ─→ beat (zamanlanmış)
│                                                 ─→ watcher (klasör izleme)
└────────────────────────────────────────────────────────────────────┘
```

**Not:** `api`, `worker-fast`, `beat`, `watcher` aynı `./backend` bağlamından derlenir ama Compose
her biri için **ayrı imaj** üretir. Kod değişince dördü birden derlenmelidir; yalnızca `api`
derlemek worker'ı eski kodda bırakır (bu denetim sırasında bizzat yaşandı).

---

## 2. Veri modeli

27 tablo, beş kümede toplanıyor:

| Küme | Tablolar | Rol |
|---|---|---|
| **Kiracı / kimlik** | `tenants`, `users`, `teams`, `agents`, `auth_tokens`, `audit_logs` | çok kiracılı temel, RBAC, denetim |
| **Çağrı verisi** | `calls`, `segments`, `scores`, `violations`, `alerts`, `campaigns` | puanlamanın çekirdeği |
| **Rubrik** | `criteria`, `rubric_versions`, `banned_words` | değerlendirme tanımı |
| **İnsan döngüsü** | `manual_evaluations`, `calibration_sessions`, `review_assignments`, `appeals`, `self_assessments`, `coaching_tasks` | AŞAMA 2 altyapısı (kısmen kurulu) |
| **Yan sistemler** | `knowledge_docs`, `knowledge_chunks`, `ai_usage`, `badges`, `agent_badges`, `challenges`, `targets` | RAG, maliyet, oyunlaştırma |

### Çekirdek ilişkiler
```
tenants 1─n agents 1─n calls 1─n segments
                          calls 1─n scores    ─n criteria
                          calls 1─n violations
                          calls 1─n alerts
```

### Veri modelindeki somut boşluklar (FAZ 2/3'e girdi)

| # | Boşluk | Etkisi |
|---|---|---|
| D1 | `calls.zeroed` (bool) var ama **`zeroing_reason` / `zeroing_evidence` kolonu YOK** | Sıfırlama gerekçesi hiçbir yerde saklanmıyor → **B5'in doğrudan kök nedeni** |
| D2 | `scores` tablosunda `(call_id, criterion_id)` **tekillik kısıtı yok** | Aynı kriter iki kez puanlanabiliyor → ağırlık iki kez sayılıyor (**B27**, aşağıda) |
| D3 | `alerts` tablosunda `evidence`, `evidence_ts`, `suggested_action`, `rule_id` kolonları **yok**; yalnız düz `message` metni var | Alarm şablonu kanıt taşıyamıyor → **B4**; tekillik kısıtı da yok → **B12** |
| D4 | `scores` `rubric_version_id` **taşımıyor** | Rubrik değişince geçmiş puanların hangi rubrikle üretildiği kaybolur |
| D5 | `scores` `confidence` ve `decision` (met/not_met/insufficient_evidence) alanı yok | "Kanıt yoksa ceza yok" kuralı veri modelinde ifade edilemiyor |
| D6 | `calls` durum makinesi yalnız `pending/processing/scoring/done/failed`; `ai_puanlandi → insan_kuyrugunda → kesinlesti` yok | FAZ 3'ün iki aşamalı akışı modellenemiyor |

---

## 3. Puanlama akışının adım adım izi

Bir sesli çağrının yüklemeden puana kadar izlediği **gerçek** yol
(`backend/app/tasks/pipeline.py::process_call`):

| # | Adım | Dosya / fonksiyon | Notlar |
|---|---|---|---|
| 1 | Dosya alınır (upload / watcher / ingest API) | `api/calls.py`, `app/watcher.py`, `api/ingest_api.py` | `calls` satırı `pending` |
| 2 | Kuyruğa atılır | `tasks/celery_app.py` — `voice` kuyruğu | STT worker **host'ta** çalışır |
| 3 | Süre/format ölçümü | `services/audio.py::probe` | ffprobe |
| 4 | **Diarizasyon + STT** | `services/diarization.py::diarize_and_transcribe` | ⚠️ **kritik hata burada** — §5 D-1 |
| 5 | Segmentler DB'ye | `pipeline.py:119-137` | `segments` tablosu |
| 6 | **Deterministik metrikler** | `services/metrics.py::compute_metrics` | söz kesme, sessizlik, konuşma oranı |
| 7 | **Akustik metrikler** | `services/acoustics.py` | pitch, bağırma, monotonluk |
| 8 | Nezaket/hitap kural motoru | `services/etiquette.py::analyze` | deterministik, Türkçe'ye özgü |
| 9 | RAG bağlamı | `services/knowledge.py::build_context` | bilgi bankası boşsa atlanır |
| 10 | **LLM değerlendirme** | `services/scoring.py::_evaluate_single` veya `_evaluate_map_reduce` | **tek dev prompt, 10 kriter birden** |
| 11 | Kriter kapsama garantisi | `scoring.py::_ensure_coverage` | eksik kriteri 1 kez tamamlatır, olmazsa **nötr 5 verir** |
| 12 | Yasaklı kelime tespiti | `services/compliance.py::detect_banned_words` | fuzzy eşleşme — §5 D-4 |
| 13 | Uyum paketleri (KVKK) | `services/compliance_packs.py::evaluate` | temsilci metninde kalıp arar |
| 14 | Kriz tespiti | `compliance.py::detect_crisis` | müşteri repliklerinde regex |
| 15 | **Sıfırlayıcı ihlal kararı** | `scoring.py:541-556` | gerekçe **kalıcılaştırılmıyor** — D1 |
| 16 | Toplam puan | `scoring.py::compute_total` | ✅ aritmetik kodda, LLM'de değil |
| 17 | Alarm üretimi | `pipeline.py::_apply_outcome` | dedup yok — D3 |
| 18 | Çağrı embedding'i | `scoring.py:590-602` | "benzer çağrı" araması için |

### Bu akışın mimari değerlendirmesi

**Doğru yapılmış olanlar** (v2'de korunacak):
- Toplam puan aritmetiği **kodda**, LLM'e hesaplatılmıyor (`compute_total`). Prompt dosyasının
  "asla yapma" listesindeki 2. madde zaten karşılanıyor.
- Müşteri ihlalleri temsilciyi cezalandırmıyor (`compliance.agent_violations`) — doğru ilke.
- Deterministik ölçümler (metrik + akustik + nezaket) zaten ayrı modüllerde; Katman A'nın
  iskeleti mevcut, sadece **karar yetkisi yok** (LLM'i ezmiyorlar, sadece ipucu veriyorlar).
- Sağlayıcı soyutlaması (`ai_config` + `llm.py`) temiz; Ollama/Gemini/OpenAI/OpenRouter geçişi çalışıyor.

**Mimari olarak yanlış olanlar** (FAZ 2'de yeniden yazılacak):
- **Tek dev prompt:** 10 kriter + 15 görev maddesi tek LLM çağrısında. Prompt dosyasının
  "asla yapma" 3. maddesinin ihlali. Kriter sayısı arttıkça bozulur.
- **Deterministik katman tavsiye niteliğinde:** `_metrics_hint` ölçümleri prompt'a "KESIN
  degerler" diye yazıyor ama LLM'in kararını **ezmiyor**. Katman A yok.
- **Kanıt doğrulanmıyor:** `LLMPuan.kanit` alanı DB'ye olduğu gibi yazılıyor; transkriptte
  gerçekten geçip geçmediği **hiç kontrol edilmiyor**. Katman C yok.
- **Kanıtsız ceza serbest:** kanıt boş olsa da düşük puan geçerli sayılıyor. `insufficient_evidence`
  diye bir kavram yok.
- **`temperature=0.1`, seed yok** (`llm.py:38`) — deterministik değil.
- **`_ensure_coverage` nötr 5 uyduruyor** (`scoring.py:341-349`): LLM bir kriteri değerlendiremezse
  sistem 5 puan uyduruyor ve bunu gerçek puan gibi ortalamaya katıyor. Bu, kanıtsız puan üretimidir.

---

## 4. Rubriğin mevcut hâli

| id | Ad | Grup | Ağırlık | Kritik | Eşik |
|---|---|---|---|---|---|
| 1 | Acilis | Acilis | 1.0 | hayır | 3 |
| 2 | KVKK / Aydinlatma | Uyum | 1.5 | **evet** | 3 |
| 3 | Kimlik Dogrulama | Uyum | 1.5 | **evet** | 3 |
| 4 | Aktif Dinleme | Iletisim Kalitesi | 1.0 | hayır | 3 |
| 5 | Ihtiyac Analizi | Ihtiyac Analizi | 1.0 | hayır | 3 |
| 6 | Cozum / Yonlendirme | Cozum | 2.0 | hayır | 3 |
| 7 | Yasakli Kelime / Uslup | Iletisim Kalitesi | 1.5 | hayır | 3 |
| 8 | Kapanis | Kapanis | 1.0 | hayır | 3 |
| 9 | Script Uyumu | Uyum | 1.0 | hayır | 3 |
| 10 | Bilgi Dogrulugu | Cozum | 2.0 | hayır | 3 |

**Bulgular:**
- Kriter sayısı **10** — sektör tatlı noktası olan 8-15 aralığında. ✅ Küçültme gerekmiyor.
- **Gruplama bozuk:** 7 farklı grup adı var ve 4'ü tek kriterlik ("Acilis" grubunda yalnız
  "Acilis" var). 4C çerçevesine (Uyum / İletişim / Yetkinlik / Müşteri Odağı) oturmuyor.
- **Kriter adları ASCII** (B15) — `criteria.name` doğrudan arayüzde gösteriliyor.
- Hiçbir kriterde `evaluation_mode` yok; 10 kriterin 10'u da LLM'e soruluyor. Hâlbuki
  Açılış / KVKK / Kimlik Doğrulama / Kapanış **deterministik olarak çözülebilir**.
- Kriter açıklamaları "10 puan neye benzer / 0 puan neye benzer" çapası içermiyor.

---

## 5. Ölü kod, çift implementasyon, hardcode değerler

| # | Bulgu | Yer | Değerlendirme |
|---|---|---|---|
| D-1 | **Çift Türkçe normalizasyon.** `compliance._normalize()` ve `schemas._fold_tr()` aynı işi farklı yapıyor (biri NFKD + combining temizliği, diğeri düz translate) | `services/compliance.py:34`, `schemas.py:12` | FAZ 2'de tek `normalize_tr()`'de birleşecek |
| D-2 | **`llm.py` içinde `temperature` üç yerde ayrı hardcode** (0.1) | `llm.py:38, 62, 87` | Ayarlanabilir olmalı, puanlama yolunda 0 |
| D-3 | `OVERLAP_TOLERANCE_SEC = 0.2` hardcode | `metrics.py:13` | Stereo kayıtta anlamsız — §6 |
| D-4 | **Fuzzy eşleşmede kök-önek kısayolu**: `stem = term_norm[:5]` + `partial_ratio >= 60` | `compliance.py:70-76` | Yanlış pozitif üretiyor → **B4** |
| D-5 | `compliance_packs.DEFAULT_ACTIVE` kodda sabit; kod yorumu "tenant ayarından gelmeli" diyor ama gelmiyor | `scoring.py:511-513`, `compliance_packs.py:90` | Yarım kalmış özellik |
| D-6 | `_transcript_outline()` uzun çağrıda transkriptin ortasını **atıyor** (head 25 + tail 25 satır) | `scoring.py:301-310` | Reduce aşaması çağrının ortasını hiç görmüyor |
| D-7 | `pyannote` opsiyonel bağımlılık, `HF_TOKEN` yok → mono kayıtlarda **tüm segmentler `bilinmeyen`** | `diarization.py:44-54` | Mono kayıtta "kim söyledi" bilgisi tamamen kayıp; uyum motoru çalışamaz |
| D-8 | `_ensure_coverage` içinde tekrarlanan `kriter_id` **elenmiyor** | `scoring.py:317-321` | → **B27** |
| D-9 | `scoring.py:592` gereksiz fonksiyon-içi import `knowledge`'ı yerel değişkene çeviriyordu | `scoring.py` | **FAZ 1'de düzeltildi** (aşağıda) |
| D-10 | 54 adet `TODO/FIXME/placeholder` geçen satır | proje geneli | FAZ 6 bitiş kriterinde sıfırlanacak |

---

## 6. En kritik yapısal bulgu — stereo transkripsiyon zaman damgalarını bozuyor

Bu, denetimin en önemli çıktısı ve **B1, B3, B6'nın ortak kök nedeni.** Ayrıntısı
`01-KOK-NEDEN.md` §D'de; burada özet:

`diarization._stereo()` sol ve sağ kanalı **bağımsız** olarak Whisper'a veriyor. Whisper her
kanalı kendi içinde sürekli segmentliyor — karşı taraf konuşurken oluşan sessizliği kendi
segmentinin **içine katıyor**. Sonuç: her repliğin `end` zamanı, o konuşmacının bir sonraki
repliğine kadar uzuyor.

Çağrı #24'ten ölçülen gerçek veri:

| idx | konuşmacı | başlangıç | bitiş | süre | metin |
|---|---|---|---|---|---|
| 3 | temsilci | 13.3 | **32.1** | 18.8 sn | "Bunun için gerçekten çok üzgünüm…" |
| 4 | musteri | 14.9 | 18.4 | 3.5 sn | "İyi günler ama hiç iyi değilim açıkçası." |
| 7 | musteri | 25.9 | **42.9** | 17.0 sn | "Hasan Yıldız 447821" (3 kelime) |
| 16 | musteri | 67.4 | **88.0** | 20.6 sn | "Tamam, not aldım." (3 kelime) |

Üç kelimelik bir replik 20 saniye sürüyor ve karşı tarafın 4 repliğini kapsıyor.

**Zincirleme sonuçlar (hepsi ölçüldü):**
1. `metrics.compute_metrics` her konuşmacı değişimini "söz kesme" sayıyor →
   çağrı #24 metrikleri: `temsilci_kesinti: 4, musteri_kesinti: 4`. **Sekizinin de gerçek karşılığı yok.**
2. Bu sahte sayı prompt'a **"OTOMATIK OLCUMLER (ses analizinden, KESIN degerler)"** başlığıyla
   giriyor ve prompt açıkça "söz kesme → Aktif Dinleme" diyor (`scoring.py:199-204`).
   → Temsilci, yapmadığı söz kesmeler yüzünden cezalandırılıyor = **B3**.
3. `temsilci_konusma_orani: 54.5`, `sessizlik_sn: 2.7` değerleri de aynı sebeple anlamsız.
4. Transkript LLM'e **mantıksal olarak bozuk sırada** gidiyor: temsilci 13.3'te özür diliyor,
   müşteri şikâyetini 18.4'te anlatıyor. LLM'in açılışı yanlış değerlendirmesi (**B1**) ve aynı
   senaryonun tekrarlarında farklı puan alması (**B6**) bu bozuk girdiyle doğrudan ilişkili.

---

## 7. FAZ 1'de yapılan tek kod düzeltmesi

Denetim sırasında **çalışır durumdaki sistemi kırmamak için** yalnız bir hata düzeltildi:

`services/scoring.py` — fonksiyon içinde tekrarlanan `from . import knowledge` importu,
`knowledge` adını tüm fonksiyon kapsamında yerele çevirip **RAG bağlamı çağrısını her
puanlamada `UnboundLocalError` ile düşürüyordu**. Hata `try/except` içinde yutulduğu için
sistem sessizce bilgi bankası olmadan puanlıyordu.

Kanıt (öncesi, worker günlüğü):
```
WARNING/ForkPoolWorker-1] RAG baglami olusturulamadi:
  cannot access local variable 'knowledge' where it is not associated with a value
```
Sonrası: bilgi bankasına 1 doküman/3 parça yüklendi (`rag_active: true`), çağrı #22 yeniden
puanlandı → uyarı yok, görev 40.8 sn'de başarılı, puan 93.3.

---

## 8. Ölçülen taban gerçekleri (FAZ 2 karşılaştırması için)

| Gerçek | Değer |
|---|---|
| Toplam çağrı | 24 (hepsi `done`) |
| Sıfırlanmış çağrı | 5 (#5, #7, #18, #23, #24) — **hiçbirinin gerekçesi DB'de saklı değil** |
| Toplam alarm | 27; **1 tanesi birebir kopya** (çağrı #22, aynı yasaklı kelime iki kez) |
| Aynı kriteri iki kez puanlanan çağrı | 1 (#24, KVKK / Aydinlatma) → **B27** |
| KVKK uyum kontrolü doğruluğu | 24/24 doğru (bkz. `01-KOK-NEDEN.md` §B) |
| Bir çağrının yeniden puanlanma süresi | 40-44 sn (qwen2.5:7b-instruct, RTX 3060) |

---

## 9. Bu denetimde ortaya çıkan, prompt listesinde OLMAYAN hatalar

| # | Hata | Kanıt |
|---|---|---|
| **B27** | **Aynı kriter iki kez puanlanıp ağırlığı iki kez sayılabiliyor.** Çağrı #24'te 11 puan satırı var, "KVKK / Aydinlatma" iki kez. `compute_total` bu kriterin ağırlığını (1.5) hem paya hem paydaya iki kez katıyor. | `select call_id,criterion_id,count(*) from scores group by 1,2 having count(*)>1` → `24 \| 2 \| 2` |
| **B28** | **`_ensure_coverage` kanıtsız "nötr 5" puan uyduruyor.** LLM bir kriteri atlarsa sistem 5 puan yazıp ortalamaya katıyor. Kanıtsız puan üretimi. | `scoring.py:341-349` |
| **B29** | **Mono kayıtta konuşmacı ayrımı tamamen kayboluyor** (`HF_TOKEN` yok → hepsi `bilinmeyen`). Bu durumda uyum motoru "temsilci ne dedi" sorusunu cevaplayamaz; KVKK/yasaklı kelime kontrolleri sessizce boşa düşer. | `diarization.py:48-54` + `compliance_packs` yalnız `speaker=='temsilci'` metnine bakıyor |
| **B30** | **Uzun çağrılarda transkriptin ortası hiç değerlendirilmiyor** — reduce aşamasına yalnız ilk 25 + son 25 satır gidiyor. | `scoring.py:301-310` |
| **B31** | **Alarmlar yeniden puanlamada temizlenmiyor.** `scores` ve `violations` siliniyor ama `alerts` birikiyor; eski/geçersiz alarm ekranda kalıyor. | `scoring.py:451,469` vs. `pipeline.py::_apply_outcome` |
| **B32** | **Deterministik uyum tespiti puana hiç etki etmiyor.** `compliance_packs` "KVKK anonsu yok" ihlalini doğru üretiyor ama sıfırlama kararı yalnız LLM puanına bakıyor. `dusuk-04-kvkk-yok` senaryosu anons hiç yapılmamasına rağmen **88.9** aldı ve sıfırlanmadı. | `scoring.py:514-546`, taban çizgisi koşumu |


### Kapanış turunda bulunan hata

| # | Bulgu | Kanıt |
|---|---|---|
| **B34** | **Opt-in model yönlendirmesi, kapalıyken bile gruplamayı değiştiriyor.** `scoring.py` `evaluate_all`'a her zaman bir `model_for` fonksiyonu geçiyor; `evaluate_all` ise `model_for is not None` ise kriterleri gruplamadan önce ayırıyor. Sonuç: yönlendirmeyi kullanmayan kurulumlarda da grup bileşimi değişti. (Şüpheyi bir kappa farkı uyandırdı ama o fark sonradan gürültü aralığında çıktı; kusurun kanıtı koddadır ve birim testle kilitlendi.) | `scoring.py:412`, `scoring_layers.py:253` |
| **B33** | **Temsilci karnesi onaylanmamış AI puanını sayıyor.** `/api/v1/agents` yalnız `status == done` filtreliyor, `qa_state`'e hiç bakmıyor. Kaliteci onaylamamışken inceleme kuyruğunda bekleyen çağrının AI puanı temsilcinin ortalamasına giriyor. Ürünün "AI önerir, insan onaylar" vaadiyle çelişiyor; üstelik `Call.score_is_final` özelliği bu kuralı zaten *yazmış* ama hiçbir yerde uygulanmamış. | `agents.py:94,136` vs. `models.py:328` |

**Nasıl bulundu:** S15 sorusunu ("kaliteci onayı olmadan puan temsilciye
görünsün mü?") cevaplamak için koda bakıldığında, sistemin bu soruyu zaten
sessizce "evet" diye cevapladığı görüldü. Soru bir tercih sanılıyordu; meğer
uygulanmamış bir kuralmış.

**Düzeltme:** `agents.py` içinde tek bir `KESINLESMIS` yüklemi; karne, sıralama
ve koçluk sorgularının hepsinde kullanılıyor. Regresyon:
`test_agent_scorecard_final.py` (3 vaka, yeşil).

---

Bunların hepsi FAZ 1 regresyon setine dahil edildi ve B1–B6 ile aynı statüde takip edilecek:

| Hata | Regresyon vakası | Tür | Durum |
|---|---|---|---|
| B27 | `test_b27_tekrarlanan_kriter_elenir`, `test_b27_toplam_puan_agirligi_iki_kez_saymaz` | birim test | 🔴 xfail |
| B28 | `test_b28_degerlendirilemeyen_kriter_uydurma_puan_almaz`, `test_b28_yetersiz_kanitli_kriter_ortalamaya_girmez` | birim test | 🔴 xfail |
| B29 | `data/golden/reg-b29-konusmaci-bilinmiyor` | altın set | 🔴 |
| B30 | `data/golden/reg-b30-uzun-cagri-orta-ihlal` | altın set | 🔴 |
| B31 | `test_b31_yeniden_puanlama_eski_alarmlari_gecersizler` | entegrasyon | 🔴 xfail |
| B32 | `data/golden/reg-b32-kvkk-yok-sifirlanmali` | altın set | 🔴 |
| B33 | `test_agent_scorecard_final.py` (3 vaka) | entegrasyon | 🟢 düzeltildi |
| B34 | `test_model_routing.py::test_yonlendirme_KAPALIYKEN_gruplama_degismez` | birim test | 🟢 düzeltildi |

`xfail(strict=True)` kullanıldı: hata düzeltilince test "beklenmedik şekilde geçti"
diye takımı kırar ve işaretçiyi kaldırmaya zorlar — düzeltme sessizce atlanamaz.
