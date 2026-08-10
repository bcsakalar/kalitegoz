# KaliteGoz — kurulum ve demo komutlari
# Kullanim: make demo   (tek komutla dolu, satisa hazir platform)

SHELL := /bin/sh
API   := http://localhost:8000
MODEL := $(shell grep -E '^OLLAMA_MODEL=' .env 2>/dev/null | cut -d= -f2)
MODEL := $(if $(MODEL),$(MODEL),qwen2.5:7b)
EMBED := $(shell grep -E '^EMBED_MODEL=' .env 2>/dev/null | cut -d= -f2)
EMBED := $(if $(EMBED),$(EMBED),nomic-embed-text)

.PHONY: help demo up down clean logs test test-scripts seed-history pull-model wait-api demo-data rebuild eval eval-build eval-baseline demo-reset tr-audit ui-audit audit perf

help:
	@echo "KaliteGoz komutlari:"
	@echo "  make eval      - Altin set regresyon kosumu (puanlama dogrulugu)"
	@echo "  make demo-reset- Demo verisini temizler"
	@echo "  make tr-audit  - Turkce karakter ve jargon denetimi"
	@echo "  make perf      - Kokpit performans olcumu (1000 cagri)"
	@echo "  make demo      - Her seyi ayaga kaldirir, modeli indirir, demo veriyi uretir"
	@echo "  make up        - Servisleri baslatir"
	@echo "  make down      - Servisleri durdurur (veri kalir)"
	@echo "  make clean     - Servisleri durdurur ve TUM veriyi siler"
	@echo "  make test      - Backend testlerini calistirir (pytest, Docker icinde)"
	@echo "  make test-scripts - Demo/TTS betik testlerini calistirir (host'ta)"
	@echo "  make logs      - Worker loglarini izler"
	@echo "  make demo-data - Sadece demo veriyi uretir (stack ayakta olmali)"

.env:
	@cp .env.example .env
	@echo ".env olusturuldu (.env.example kopyalandi)"

up: .env
	docker compose up -d --build

down:
	docker compose down

clean:
	docker compose down -v
	@rm -rf data/storage data/inbox

rebuild: .env
	docker compose build --no-cache

# --- Altin set / regresyon -------------------------------------------------
# eval-build : senaryolari data/golden/ altina yazar (tutarlilik denetimi dahil)
# eval       : gercek puanlama motorunu altin sette kosar, metrikleri raporlar
#              ve esikler saglanmazsa 1 doner (CI build'i kirar)
# eval-baseline : ayni kosum ama esik kapisi kapali (FAZ 1 taban cizgisi icin)

eval-build:
	python -m scripts.golden.build

eval: eval-build
	@docker compose cp scripts/golden/evaluate.py api:/tmp/evaluate.py
	@docker compose exec -T api python /tmp/evaluate.py $(EVAL_ARGS)
	@mkdir -p docs/eval && cp -f data/eval/*.json docs/eval/ 2>/dev/null || true
	@echo "Rapor: docs/eval/"

eval-baseline:
	@$(MAKE) eval EVAL_ARGS="--no-gate"

# --- FAZ 6: demo, dil denetimi, performans -------------------------------
# demo-data hedefi (asagida) gercek ses uretir ve uctan uca isler — yavas.
# `make demo` ise SATIS demosu icin hazir puanli veri uretir (saniyeler).

demo-reset:
	@docker compose cp scripts/seed_sales_demo.py api:/tmp/seed_sales_demo.py
	@docker compose exec -T api python /tmp/seed_sales_demo.py --reset

tr-audit:
	python scripts/tr_audit.py

# Keskin kose kurali: border-radius her yerde 0, tek tokendan yonetilir.
ui-audit:
	python scripts/ui_audit.py

# Tum statik denetimler tek komutta (CI bunu kosar)
audit: tr-audit ui-audit

perf:
	@docker compose cp scripts/perf_check.py api:/tmp/perf_check.py
	@docker compose exec -T api python /tmp/perf_check.py --calls 1000

wait-api:
	@echo "API hazir bekleniyor..."
	@i=0; while [ $$i -lt 60 ]; do \
		if curl -sf $(API)/api/health >/dev/null 2>&1; then echo "API hazir."; exit 0; fi; \
		i=$$((i+1)); sleep 3; \
	done; echo "API 3 dk icinde hazir olmadi"; exit 1

# Ollama artik PC'de (host) NATIVE calisir; modeller HOST Ollama'ya cekilir.
# On kosul: Ollama for Windows kurulu ve calisir durumda (ollama serve / uygulama).
pull-model:
	@echo "LLM modeli indiriliyor ($(MODEL)) — host Ollama'ya, ilk seferde ~4.7 GB..."
	@ollama pull $(MODEL) || curl -s http://localhost:11434/api/pull -d '{"name":"$(MODEL)"}' >/dev/null
	@echo "Embedding modeli indiriliyor ($(EMBED), ~270 MB) — RAG bilgi bankasi icin..."
	@ollama pull $(EMBED) || curl -s http://localhost:11434/api/pull -d '{"name":"$(EMBED)"}' >/dev/null
	@echo "Modeller hazir (host Ollama)."

demo-data:
	@echo "Demo verisi uretiliyor (TTS + chat + 8 haftalik gecmis)..."
	python scripts/generate_demo.py --upload $(API) || python3 scripts/generate_demo.py --upload $(API)

# Tek komutla: stack + model + demo verisi
demo: up wait-api
	@docker compose cp scripts/seed_sales_demo.py api:/tmp/seed_sales_demo.py
	@docker compose exec -T api python /tmp/seed_sales_demo.py
	@echo ""
	@echo "Panel: http://localhost:3000  ·  admin@demo.local / demo1234"

# Uctan uca demo: gercek ses uretir ve STT+LLM ile isler (yavas, host worker ister)
demo-full: up wait-api pull-model demo-data
	@echo ""
	@echo "============================================================"
	@echo " KaliteGoz demo hazir!"
	@echo " Dashboard : http://localhost:3000  (rol secip tek tikla giris)"
	@echo " API/Swagger: $(API)/docs"
	@echo ""
	@echo " Demo hesaplari (parola: demo1234)"
	@echo "   admin@demo.local        - Yonetici"
	@echo "   sef.satis@demo.local    - Supervizor"
	@echo "   kalite@demo.local       - Kalite Uzmani"
	@echo "   ayse.yilmaz@demo.local  - Temsilci"
	@echo ""
	@echo " NATIVE AI: Ollama + Whisper STT PC'de calisir (Docker degil)."
	@echo "   1) Ollama for Windows kurulu + calisir olmali (modeller: make pull-model)"
	@echo "   2) Sesli cagri STT worker'ini host'ta baslatin:"
	@echo "      powershell -ExecutionPolicy Bypass -File scripts/run-host-worker.ps1"
	@echo "   3) Yonetim > Isleme > 'Islemeyi baslat' (demo tenant duraklatilmis gelir)"
	@echo "   Ayrinti: NATIVE-AI-KURULUM.md"
	@echo "============================================================"

# Sesli cagri worker'i artik host'ta; Docker'da chat/bakim worker'i (fast) var.
logs:
	docker compose logs -f worker-fast

test:
	docker compose run --rm --no-deps -e JWT_SECRET=test-secret-key-32-bytes-long-xx \
		-v "$(PWD)/backend:/srv" api sh -c "pip install -q pytest && cd /srv && python -m pytest -q"

# Betikler Docker imajinda degil (demo ureteci host'ta calisir), bu yuzden
# ayri hedef. Ag erisimi gerektirmez — edge-tts cagrilmaz.
test-scripts:
	python -m pytest scripts/tests -q

# Uctan uca duman testi: sistem ayakta mi, sayfalar/endpointler/RBAC calisiyor mu
smoke:
	python scripts/smoke_test.py

seed-history:
	@curl -s -X POST $(API)/api/v1/auth/demo-login -H 'Content-Type: application/json' \
		-d '{"role":"admin"}' | \
		python -c "import sys,json;print(json.load(sys.stdin)['access_token'])" > /tmp/kg_token
	@curl -s -X POST $(API)/api/v1/admin/seed-demo-history \
		-H "Authorization: Bearer $$(cat /tmp/kg_token)"
