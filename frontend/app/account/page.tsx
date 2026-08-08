"use client";

import { useState } from "react";
import { api, ROLE_LABEL_KEYS } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";
import { useT } from "@/components/I18nProvider";

export default function AccountPage() {
  const { me } = useAuth();
  const t = useT();
  const [old, setOld] = useState("");
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  if (!me) return null;

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setErr(""); setMsg("");
    if (pw !== pw2) { setErr(t("reset.mismatch")); return; }
    setBusy(true);
    try {
      await api.changePassword(old, pw);
      setMsg(t("account.changed")); setOld(""); setPw(""); setPw2("");
    } catch (e2) { setErr(e2 instanceof Error ? e2.message : String(e2)); }
    finally { setBusy(false); }
  }

  return (
    <div className="max-w-md space-y-4">
      <h1 className="text-xl font-bold">{t("account.title")}</h1>

      <div className="card space-y-1.5 p-4 text-sm">
        <Row k={t("org.name")} v={me.name} />
        <Row k={t("org.email")} v={me.email} />
        <Row k={t("usr.colRole")} v={t(ROLE_LABEL_KEYS[me.role] ?? me.role)} />
        <Row k={t("account.org")} v={me.tenant_name} />
      </div>

      <div className="card space-y-3 p-4">
        <h2 className="text-sm font-semibold text-ink2">🔑 {t("account.changePw")}</h2>
        {msg && <p className="text-sm" style={{ color: "var(--status-good)" }}>{msg}</p>}
        {err && <p className="text-sm" style={{ color: "var(--status-critical)" }}>{err}</p>}
        <form onSubmit={submit} className="space-y-3">
          <input className="input w-full" type="password" placeholder={t("account.oldPw")} value={old} onChange={(e) => setOld(e.target.value)} required />
          <input className="input w-full" type="password" placeholder={t("reset.newPassword")} value={pw} onChange={(e) => setPw(e.target.value)} required minLength={8} />
          <input className="input w-full" type="password" placeholder={t("reset.confirm")} value={pw2} onChange={(e) => setPw2(e.target.value)} required minLength={8} />
          <button className="btn btn-primary" disabled={busy}>{busy ? t("reset.saving") : t("account.changePw")}</button>
        </form>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-ink2">{k}</span>
      <span className="truncate font-medium">{v}</span>
    </div>
  );
}
