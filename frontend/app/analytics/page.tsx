"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useT } from "@/components/I18nProvider";
import PageHeader from "@/components/PageHeader";
import type { TimeseriesPoint, VocTrend, CohortRow } from "@/lib/types";

const EMOTION_KEYS = ["ofke", "hayal_kirikligi", "endise", "memnuniyet", "notr", "saskinlik", "minnettarlik", "uzuntu"];

export default function AnalyticsPage() {
  const t = useT();
  const [metric, setMetric] = useState("score");
  const [ts, setTs] = useState<TimeseriesPoint[]>([]);
  const [voc, setVoc] = useState<VocTrend[]>([]);
  const [emotions, setEmotions] = useState<Record<string, number>>({});
  const [churn, setChurn] = useState<Record<string, number>>({});
  const [dimension, setDimension] = useState("team");
  const [cohort, setCohort] = useState<CohortRow[]>([]);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    try {
      const [tsData, vocData, emoData, cohortData] = await Promise.all([
        api.analyticsTimeseries(metric, 30, "day"),
        api.analyticsVoc(14),
        api.analyticsEmotions(30),
        api.analyticsCohort(dimension, 30),
      ]);
      setTs(tsData);
      setVoc(vocData.filter((v) => v.recent > 0 || v.prior > 0).slice(0, 12));
      setEmotions(emoData.emotions);
      setChurn(emoData.churn);
      setCohort(cohortData);
      setErr("");
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  }, [metric, dimension]);
  useEffect(() => { load(); }, [load]);

  const maxTs = Math.max(1, ...ts.map((p) => p.avg ?? 0));
  const totalEmotion = Math.max(1, Object.values(emotions).reduce((a, b) => a + b, 0));

  return (
    <div className="space-y-6">
      <PageHeader title={t("analytics.pageTitle")} subtitle={t("analytics.subtitle")} />
      {err && <p className="card p-3 text-sm text-[var(--status-critical)]">{err}</p>}

      {/* Zaman serisi */}
      <div className="card p-4">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <h2 className="text-sm font-semibold text-ink2">{t(`analytics.metric.${metric}`)}</h2>
          <div className="ml-auto flex gap-1">
            {["score", "csat", "effort"].map((m) => (
              <button key={m} onClick={() => setMetric(m)} data-active={metric === m}
                className="btn !px-2 !py-1 text-xs data-[active=true]:bg-series data-[active=true]:text-white">
                {t(`analytics.metric.${m}`)}
              </button>
            ))}
          </div>
        </div>
        {ts.length === 0 ? (
          <p className="text-sm text-muted">{t("analytics.noData")}</p>
        ) : (
          <div className="flex h-40 items-end gap-1 overflow-x-auto">
            {ts.map((p) => (
              <div key={p.date} className="flex min-w-[14px] flex-1 flex-col items-center justify-end gap-1"
                title={`${p.date}: ${p.avg ?? "—"} (${p.count})`}>
                <div className="w-full rounded-t bg-series" style={{ height: `${((p.avg ?? 0) / maxTs) * 100}%` }} />
                <span className="text-[9px] text-muted">{p.date.slice(5)}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* VoC trend */}
      <div className="card p-4">
        <h2 className="text-sm font-semibold text-ink2">{t("analytics.voc.title")}</h2>
        <p className="mb-2 text-xs text-muted">{t("analytics.voc.hint")}</p>
        {voc.length === 0 ? <p className="text-sm text-muted">{t("analytics.noData")}</p> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs text-muted">
                <tr className="border-b border-hairline text-left">
                  <th className="py-1">Konu</th><th>{t("analytics.voc.recent")}</th>
                  <th>{t("analytics.voc.prior")}</th><th>{t("analytics.voc.change")}</th>
                </tr>
              </thead>
              <tbody>
                {voc.map((v) => (
                  <tr key={v.kind + v.label} className="border-b border-hairline/50">
                    <td className="py-1.5">
                      <span className="badge badge-neutral text-[10px] mr-1">{v.kind === "intent" ? "🏷" : "📁"}</span>
                      {v.label}
                    </td>
                    <td className="tabular-nums">{v.recent}</td>
                    <td className="tabular-nums text-muted">{v.prior}</td>
                    <td className={`tabular-nums font-semibold ${v.change_pct > 0 ? "text-[var(--status-warn)]" : v.change_pct < 0 ? "text-[var(--status-ok)]" : "text-muted"}`}>
                      {v.change_pct > 0 ? "▲" : v.change_pct < 0 ? "▼" : ""} {v.change_pct > 0 ? "+" : ""}{v.change_pct}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Duygu dağılımı */}
        <div className="card p-4">
          <h2 className="mb-3 text-sm font-semibold text-ink2">{t("analytics.emotions.title")}</h2>
          <div className="space-y-1.5">
            {EMOTION_KEYS.filter((e) => emotions[e]).map((e) => (
              <div key={e} className="flex items-center gap-2 text-xs">
                <span className="w-28 shrink-0">{t(`emotion.${e}`)}</span>
                <div className="h-3 flex-1 overflow-hidden rounded bg-grid/40">
                  <div className="h-full bg-series" style={{ width: `${(emotions[e] / totalEmotion) * 100}%` }} />
                </div>
                <span className="w-8 text-right tabular-nums text-muted">{emotions[e]}</span>
              </div>
            ))}
            {Object.keys(emotions).length === 0 && <p className="text-sm text-muted">{t("analytics.noData")}</p>}
          </div>
          <h3 className="mb-2 mt-4 text-xs font-semibold text-ink2">{t("analytics.churn.title")}</h3>
          <div className="flex gap-2">
            {(["dusuk", "orta", "yuksek"] as const).map((r) => (
              <div key={r} className="flex-1 rounded-lg bg-grid/40 p-2 text-center">
                <div className={`text-lg font-bold ${r === "yuksek" ? "text-[var(--status-critical)]" : r === "orta" ? "text-[var(--status-warn)]" : ""}`}>{churn[r] ?? 0}</div>
                <div className="text-[10px] text-muted">{t(`risk.${r}`)}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Kohort */}
        <div className="card p-4">
          <div className="mb-3 flex items-center gap-2">
            <h2 className="text-sm font-semibold text-ink2">{t("analytics.cohort.title")}</h2>
            <div className="ml-auto flex gap-1">
              {["team", "campaign"].map((d) => (
                <button key={d} onClick={() => setDimension(d)} data-active={dimension === d}
                  className="btn !px-2 !py-1 text-xs data-[active=true]:bg-series data-[active=true]:text-white">
                  {t(`analytics.cohort.${d}`)}
                </button>
              ))}
            </div>
          </div>
          {cohort.length === 0 ? <p className="text-sm text-muted">{t("analytics.noData")}</p> : (
            <table className="w-full text-sm">
              <tbody>
                {cohort.map((c) => (
                  <tr key={c.label} className="border-b border-hairline/50">
                    <td className="py-1.5 font-medium">{c.label}</td>
                    <td className="tabular-nums text-muted">{c.count}</td>
                    <td className="tabular-nums font-semibold">{c.avg_score ?? "—"}</td>
                    <td className="tabular-nums text-muted">CSAT {c.avg_csat ?? "—"}</td>
                    {c.crisis > 0 && <td className="text-xs text-[var(--status-critical)]">🚨 {c.crisis}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
