# KaliteGöz

**A call-centre quality management platform that scores every conversation, shows the evidence behind each decision, and knows where it is unreliable.** It runs entirely on-premise — audio, transcripts and scores never leave the organisation's hardware.

<sub><a href="README.md">Türkçe</a> · English</sub>

---

## Why it exists

Quality control in call centres is done by hand and covers **2–5% of calls**. The remaining 95% is never reviewed: compliance breaches, wrong information and churn signals pass unseen.

KaliteGöz scores every call, **puts a verbatim transcript quote next to every decision**, and routes to a human any criterion it knows it cannot judge reliably.

---

## Screens

### Supervisor cockpit
![Cockpit](docs/screens/03-kokpit-dark.png)

### Review queue — scoring with evidence
![Review queue](docs/screens/04-inceleme-kuyrugu-dark.png)

### Call list
![Calls](docs/screens/02-cagrilar-light.png)

### Security and compliance status
![Security](docs/screens/09-guvenlik-dark.png)

---

## Measured accuracy

Against a 50-scenario golden set, using the real scoring engine. **Reproducible** with `make eval`; raw outputs live under [`docs/eval/`](docs/eval/).

| Metric | v1 | v2 |
|---|---|---|
| Zeroing-violation false positives | 38.5% | **0.0%** |
| Zeroing-violation false negatives | 18.2% | **0.0%** |
| Mean absolute error per criterion (0–10) | 2.16 | **0.76–0.78** |
| Evidence verifiability | 56.1% | **100%** |
| Repeatability (3 runs, std dev) | 1.95 | **0.46** |
| Exact-match rate | 21.4% | **64.5–65.2%** |

### Broken out by criterion type, because a single average misleads

| | Objective criteria | Subjective criteria |
|---|---|---|
| What it measures | Greeting, GDPR/KVKK notice, identity verification, closing, tone | Active listening, needs analysis, resolution, factual accuracy |
| How it is resolved | **In code** — the language model is never asked | LLM with mandatory evidence |
| Cohen's kappa | Core four criteria: **0.94–1.00** | **0.09–0.18** |
| Coverage claim | 100%, score is final | **A suggestion** — a valid score requires human approval |

> **This table is the most honest part of the product.** On subjective criteria the system is not reliable and **it knows that**: where kappa falls below 0.40 the confidence score is automatically capped and the call is routed to guaranteed human review.
>
> The subjective kappa is written as a **range** rather than a single number: three consecutive runs on identical code and configuration measured **0.16 → 0.11 → 0.09**. Nothing in between touched the scoring code, so this movement has no known mechanism — run-to-run variance is **wider** than the 0.05 band previously assumed. Picking the best run would make the table look better and mislead. Objective kappa, by contrast, is identical across six runs to the fourth decimal (0.7639).
>
> How the reference set was produced and what is explicitly *not* proven: [KALITE-METODOLOJISI.md §4](docs/KALITE-METODOLOJISI.md)

---

## How it works — three layers

```
LAYER A — DETERMINISTIC PRE-CHECK    (code, no LLM)
   ↓ anything with a definite answer ends here and OVERRIDES the LLM
LAYER B — EVIDENCE-MANDATORY LLM     (per criterion group, temperature 0)
   ↓ every decision carries a verbatim quote from the transcript
LAYER C — SERVER-SIDE VERIFICATION   (code)
   ↓ does the quote actually appear in the transcript? score arithmetic IN CODE
```

**Three absolute rules**

1. **No evidence, no penalty.** A low score is never issued on an unverifiable quote; the criterion becomes "insufficient evidence" and goes to a human.
2. **The total is computed in code.** The language model is never asked to add anything up.
3. **A zeroing decision without evidence is a system fault** and raises an exception.

Detail: [MIMARI.md](docs/MIMARI.md)

---

## Features

**Scoring and compliance**
Three-layer hybrid engine · zeroing-violation detection · banned words and tone · crisis detection (lawyer, arbitration board) · GDPR/KVKK notice audit · script compliance · evidence-to-audio linking (click a quote, hear that second)

**Two-stage quality control**
Risk-based review queue (7 rules) · reviewer approval and correction · agent appeals · calibration sessions and inter-rater agreement · coaching plans and coaching-impact measurement · agent self-assessment

**Analytics**
Supervisor cockpit · topic discovery and root-cause clustering · trend and anomaly alerts · churn risk · true FCR · **quality score ↔ actual CSAT correlation** · ROI calculation · target tracking · league and badges

**Enterprise**
Multi-tenant · 4 roles with team scoping · OIDC/SSO (configured from the panel) · encryption at rest with key rotation and a KMS path · PII masking · audit log · retention automation · webhooks and an open API · Turkish/English interface · light and dark themes

Competitive comparison and **what we do not have**: [PIYASA-ANALIZI.md](docs/PIYASA-ANALIZI.md)

---

## Install in five minutes

**Requirements:** Docker Desktop, [Ollama](https://ollama.com) (on the host), 16 GB RAM (32 GB recommended).

```bash
git clone <repository-url> && cd KaliteGoz

# 1) Generate secrets — leaves no field to fill in by hand
./scripts/generate-secrets.sh

# 2) AI models — Ollama runs on the HOST, not in Docker
ollama pull qwen2.5:7b-instruct
ollama pull nomic-embed-text

# 3) Services
docker compose up -d --build

# 4) Verify
curl http://localhost:8000/health    # {"status":"ok"}
curl http://localhost:8000/ready     # {"status":"ready"}
```

Panel: **http://localhost:3000** · API: **http://localhost:8000/docs**

To walk through the system step by step: [TEST-REHBERI.md](docs/TEST-REHBERI.md)
Hardware, production hardening, troubleshooting: [KURULUM.md](docs/KURULUM.md)

---

## Technology

| Layer | What |
|---|---|
| Backend | Python 3.12 · FastAPI · SQLAlchemy 2 · Celery |
| Data | PostgreSQL 16 · Redis 7 |
| Frontend | Next.js 15 (App Router) · React 19 · TypeScript · Tailwind |
| AI | **Ollama** (local LLM and embeddings) · **Whisper** (STT) — both on the host |
| Deployment | Docker Compose · on-premise |

---

## Development

```bash
make test      # backend regression suite
make eval      # scoring accuracy against the golden set (CI fails below threshold)
make audit     # Turkish character and UI audit (sharp corners, defined colours)
```

Code and documentation guide: [CLAUDE.md](CLAUDE.md) · All documents: [docs/](docs/README.md)

---

## Licence

[AGPL-3.0](LICENSE) — rationale and detail: [docs/FINAL-RAPOR.md](docs/FINAL-RAPOR.md)

Interface language: Turkish and English. Documentation: primarily Turkish, with this English overview.
