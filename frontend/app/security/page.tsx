"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useT } from "@/components/I18nProvider";
import type { SecurityPosture } from "@/lib/types";

function Row({ label, ok, value }: { label: string; ok?: boolean; value?: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-hairline py-2.5 last:border-0">
      <span className="text-sm text-ink2">{label}</span>
      {value !== undefined ? (
        <span className="text-sm font-semibold tabular-nums">{value}</span>
      ) : (
        <span className={`badge ${ok ? "badge-good" : "badge-critical"}`}>
          <span className="dot" aria-hidden />
        </span>
      )}
    </div>
  );
}

export default function SecurityPage() {
  const t = useT();
  const [p, setP] = useState<SecurityPosture | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.securityPosture().then(setP).catch((e) => setErr(e.message ?? String(e)));
  }, []);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold">{t("sec.title")}</h1>
        <p className="text-sm text-ink2">{t("sec.subtitle")}</p>
      </div>

      {err && <p className="card border-l-4 p-3 text-sm" style={{ borderLeftColor: "var(--status-critical)" }}>{err}</p>}
      {!p && !err && <p className="card p-6 text-center text-sm text-muted">…</p>}

      {p && (
        <>
          {/* Satış vurgusu */}
          <div className="card border-l-4 p-4" style={{ borderLeftColor: "var(--status-ok)" }}>
            <div className="flex items-start gap-3">
              <span className="text-2xl" aria-hidden>🔒</span>
              <p className="text-sm text-ink">{t("sec.pitch")}</p>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="card p-4">
              <Row label={t("sec.deployment")} value={p.deployment === "on-premise" ? t("sec.onprem") : p.deployment} />
              <Row label={t("sec.dataResidency")} value={p.data_leaves_premises ? t("sec.dataLeaves") : t("sec.dataStays")} />
              <Row label={t("sec.llm")} value={p.llm_provider === "ollama" ? t("sec.llmLocal") : p.llm_provider} />
              <Row label={t("sec.retention")} value={`${p.retention_days} ${t("sec.days")}`} />
              <Row label={t("sec.rbac")} value={`${p.rbac_roles.length} ${t("sec.roles")}`} />
              <Row label={t("sec.auditEvents30d")} value={String(p.audit_events_30d)} />
            </div>
            <div className="card p-4">
              <Row label={t("sec.pii")} ok={p.pii_masking_enabled} />
              <Row label={t("sec.audit")} ok={p.audit_log_enabled} />
              <Row label={t("sec.tenantIsolation")} ok={p.multi_tenant_isolation} />
              <Row label={t("sec.kvkkPack")} ok={p.kvkk_pack_active} />
              <Row label={t("sec.sso")} ok={p.sso_enabled} />
              <Row label={t("sec.encryption")} ok={p.encryption_at_rest} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
