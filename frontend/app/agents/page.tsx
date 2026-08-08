"use client";

import { useT } from "@/components/I18nProvider";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ScoreBadge } from "@/components/Badges";
import { api, authedDownload, fmtDate, reportUrls } from "@/lib/api";
import type { AgentSummary } from "@/lib/types";

export default function AgentsPage() {
  const t = useT();
  const [agents, setAgents] = useState<AgentSummary[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.listAgents().then(setAgents).catch((e) => setError(String(e)));
  }, []);

  if (error) return <p className="card p-6 text-sm">Hata: {error}</p>;
  if (!agents) return <p className="p-6 text-sm text-muted">{t("common.loading")}</p>;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">{t("agents.title")}</h1>
        <button className="btn" onClick={() => authedDownload(reportUrls.teamXlsx(), "ekip_raporu.xlsx")}>
          {t("agents.teamReport")}
        </button>
      </div>
      {agents.length === 0 ? (
        <p className="card p-8 text-center text-sm text-muted">{t("common.noData")}</p>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-hairline text-left text-xs uppercase tracking-wide text-muted">
                <th className="px-4 py-2.5">{t("calls.agent")}</th>
                <th className="px-4 py-2.5">{t("agents.evaluated")}</th>
                <th className="px-4 py-2.5">{t("stat.avgScore")}</th>
                <th className="px-4 py-2.5">{t("agents.lastCall")}</th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {agents.map((a) => (
                <tr key={a.id} className="border-b border-hairline last:border-0 hover:bg-grid/40">
                  <td className="px-4 py-2.5 font-medium">{a.name}</td>
                  <td className="px-4 py-2.5 tabular-nums">{a.call_count}</td>
                  <td className="px-4 py-2.5"><ScoreBadge score={a.avg_score} /></td>
                  <td className="px-4 py-2.5 text-ink2">{a.last_call_at ? fmtDate(a.last_call_at) : "—"}</td>
                  <td className="px-4 py-2.5 text-right">
                    <Link href={`/agents/${a.id}`} className="text-series hover:underline">{t("agents.openCard")}</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
