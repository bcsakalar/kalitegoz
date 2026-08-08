"""Uçtan uca duman testi (smoke test): sistem gerçekten ayakta mı?

Playwright gibi ağır bir tarayıcı otomasyonu yerine, gerçek bir kullanıcının
yapacağı akışı HTTP seviyesinde doğrular:
  1. Tüm frontend sayfaları 200 dönüyor mu (Next.js render)
  2. API sağlıklı mı
  3. Demo-login çalışıyor + JWT alınıyor mu
  4. Yeni özellik endpoint'leri (analitik/inceleme/gamification/uyum/vision) çalışıyor mu
  5. RBAC: temsilci personel-only endpoint'lerde 403 alıyor mu
  6. Agent assist önerileri gerçekten üretiliyor mu

Kullanım:
    python scripts/smoke_test.py                 # localhost varsayılan
    python scripts/smoke_test.py --api http://localhost:8000 --web http://localhost:3000

Çıkış kodu 0 = hepsi geçti, 1 = en az bir hata. CI'da da çalışır.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

PASS, FAIL = "PASS", "FAIL"


def _req(url, token=None, method="GET", body=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:  # baglanti hatasi
        return 0, str(e).encode()


class Smoke:
    def __init__(self, api, web):
        self.api = api.rstrip("/")
        self.web = web.rstrip("/")
        self.results = []

    def check(self, name, ok, detail=""):
        self.results.append((PASS if ok else FAIL, name, detail))

    def login(self, role):
        st, body = _req(f"{self.api}/api/v1/auth/demo-login", method="POST", body={"role": role})
        if st == 200:
            return json.loads(body)["access_token"]
        return None

    def run(self):
        # 1. Frontend sayfaları
        pages = ["", "login", "analytics", "assist", "cockpit", "agents",
                 "leaderboard", "workflow", "calibration", "rubric", "admin", "search"]
        for p in pages:
            st, _ = _req(f"{self.web}/{p}")
            self.check(f"web /{p or '(home)'}", st == 200, f"HTTP {st}")

        # 2. API sağlık
        st, _ = _req(f"{self.api}/api/health")
        self.check("api /health", st == 200, f"HTTP {st}")

        # 3. Demo-login
        admin = self.login("admin")
        agent = self.login("agent")
        self.check("demo-login admin", admin is not None)
        self.check("demo-login agent", agent is not None)
        if not admin:
            return

        # 4. Yeni özellik endpoint'leri (admin)
        endpoints = [
            "/api/v1/analytics/timeseries", "/api/v1/analytics/voc",
            "/api/v1/analytics/emotions", "/api/v1/analytics/cohort",
            "/api/v1/review/stats", "/api/v1/review/coaching-effectiveness",
            "/api/v1/challenges", "/api/v1/compliance-packs",
            "/api/v1/vision/status", "/api/v1/reports/email/status",
        ]
        for ep in endpoints:
            st, _ = _req(f"{self.api}{ep}", token=admin)
            self.check(f"api {ep}", st == 200, f"HTTP {st}")

        # 5. RBAC: temsilci personel-only'de 403
        if agent:
            st, _ = _req(f"{self.api}/api/v1/analytics/voc", token=agent)
            self.check("rbac agent->analytics 403", st == 403, f"HTTP {st}")
            st, _ = _req(f"{self.api}/api/v1/me/gamification", token=agent)
            self.check("agent self-service 200", st == 200, f"HTTP {st}")

        # 6. Agent assist önerileri
        st, body = _req(f"{self.api}/api/v1/assist/suggest", token=admin, method="POST",
                        body={"partial_text": "Merhaba, hattımı iptal etmek istiyorum"})
        ok = st == 200 and len(json.loads(body)) > 0
        self.check("assist suggestions", ok, f"HTTP {st}")

    def report(self):
        failed = [r for r in self.results if r[0] == FAIL]
        for status, name, detail in self.results:
            mark = "OK " if status == PASS else ">>>"
            line = f"  {mark} {name}"
            if detail and status == FAIL:
                line += f"  ({detail})"
            print(line)
        print(f"\n{len(self.results) - len(failed)}/{len(self.results)} gecti"
              + (f", {len(failed)} BASARISIZ" if failed else " — HEPSI GECTI"))
        return 0 if not failed else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--web", default="http://localhost:3000")
    args = ap.parse_args()
    s = Smoke(args.api, args.web)
    s.run()
    sys.exit(s.report())


if __name__ == "__main__":
    main()
