"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useT } from "@/components/I18nProvider";
import type { RoiInputs, RoiResult } from "@/lib/types";

const DEFAULTS: RoiInputs = {
  agents: 50,
  calls_per_agent_day: 40,
  minutes_per_manual_review: 8,
  qa_hourly_cost: 120,
  manual_coverage_pct: 3,
  working_days_month: 22,
};

const FIELDS: { key: keyof RoiInputs; labelKey: string; step?: number }[] = [
  { key: "agents", labelKey: "roi.agents" },
  { key: "calls_per_agent_day", labelKey: "roi.callsPerDay" },
  { key: "minutes_per_manual_review", labelKey: "roi.minutesPerReview" },
  { key: "qa_hourly_cost", labelKey: "roi.qaCost", step: 10 },
  { key: "manual_coverage_pct", labelKey: "roi.coverage", step: 0.5 },
  { key: "working_days_month", labelKey: "roi.workingDays" },
];

function fmt(n: number): string {
  return n.toLocaleString("tr-TR", { maximumFractionDigits: 0 });
}

export default function RoiPage() {
  const t = useT();
  const [inp, setInp] = useState<RoiInputs>(DEFAULTS);
  const [res, setRes] = useState<RoiResult | null>(null);
  const [busy, setBusy] = useState(false);

  async function calc() {
    setBusy(true);
    try {
      setRes(await api.computeRoi(inp));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">{t("roi.title")}</h1>
          <p className="text-sm text-ink2">{t("roi.subtitle")}</p>
        </div>
        {res && (
          <button className="btn print:hidden" onClick={() => window.print()}>🖨 {t("roi.print")}</button>
        )}
      </div>

      <div className="card grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3 print:hidden">
        {FIELDS.map((f) => (
          <label key={f.key} className="block">
            <span className="mb-1 block text-xs text-ink2">{t(f.labelKey)}</span>
            <input
              type="number" className="input w-full" step={f.step ?? 1} min={0}
              value={inp[f.key]}
              onChange={(e) => setInp({ ...inp, [f.key]: Number(e.target.value) })}
            />
          </label>
        ))}
        <div className="flex items-end">
          <button className="btn btn-primary w-full" onClick={calc} disabled={busy}>
            {busy ? "…" : t("roi.calculate")}
          </button>
        </div>
      </div>

      {res && (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label={t("roi.totalCalls")} value={fmt(res.total_calls_month)} sub={t("roi.perMonth")} />
            <Stat label={t("roi.aiCoverage")} value="%100" accent="ok" />
            <Stat label={t("roi.coverageMult")} value={`${res.coverage_multiplier}×`} accent="ok" />
            <Stat label={t("roi.manualReviews")} value={fmt(res.manual_reviews_month)} sub={t("roi.perMonth")} />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="card p-5" style={{ borderLeft: "4px solid var(--status-ok)" }}>
              <p className="text-xs uppercase tracking-wide text-muted">{t("roi.annualSaving")}</p>
              <p className="mt-1 text-3xl font-bold tabular-nums">₺{fmt(res.est_annual_saving)}</p>
              <p className="mt-1 text-sm text-ink2">{t("roi.monthlySaving")}: ₺{fmt(res.est_monthly_saving)} {t("roi.perMonth")}</p>
            </div>
            <div className="card p-5">
              <p className="text-xs uppercase tracking-wide text-muted">{t("roi.equivHours")}</p>
              <p className="mt-1 text-3xl font-bold tabular-nums">{fmt(res.ai_equiv_hours_saved)} {t("roi.hours")}</p>
              <p className="mt-1 text-sm text-ink2">≈ ₺{fmt(res.ai_equiv_cost)} {t("roi.perMonth")}</p>
            </div>
          </div>

          <div className="card p-4">
            <p className="text-sm text-ink2"><strong>{t("roi.note")}:</strong> {res.payback_note}</p>
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: "ok" }) {
  return (
    <div className="card p-4">
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums" style={accent === "ok" ? { color: "var(--status-ok)" } : undefined}>
        {value} {sub && <span className="text-sm font-normal text-muted">{sub}</span>}
      </p>
    </div>
  );
}
