"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { InviteInfo } from "@/lib/types";
import { useAuth } from "@/components/AuthProvider";
import { useT } from "@/components/I18nProvider";

export default function AcceptInvitePage() {
  const router = useRouter();
  const { refresh } = useAuth();
  const t = useT();
  const [token, setToken] = useState("");
  const [inv, setInv] = useState<InviteInfo | null>(null);
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const tk = new URLSearchParams(window.location.search).get("token") ?? "";
    setToken(tk);
    if (tk) api.inviteInfo(tk).then(setInv);
    else setInv({ valid: false, email: "", name: "", org_name: "" });
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== password2) { setError(t("reset.mismatch")); return; }
    setBusy(true); setError("");
    try {
      await api.acceptInvite(token, password);
      await refresh();
      router.replace("/");
    } catch (err) { setError(err instanceof Error ? err.message : String(err)); setBusy(false); }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4">
      <div className="card p-6">
        <h1 className="text-lg font-semibold">{t("invite.title")}</h1>
        {inv === null && <p className="mt-2 text-sm text-muted">…</p>}
        {inv && !inv.valid && (
          <p className="mt-3 text-sm" style={{ color: "var(--status-critical)" }}>{t("invite.invalid")}</p>
        )}
        {inv && inv.valid && (
          <>
            <p className="mt-1 text-sm text-ink2">
              {t("invite.welcome")} <b>{inv.org_name}</b> — {inv.email}
            </p>
            {error && <p className="mt-3 text-sm" style={{ color: "var(--status-critical)" }}>{error}</p>}
            <form onSubmit={submit} className="mt-4 space-y-3">
              <input className="input w-full" type="password" placeholder={t("reset.newPassword")}
                value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} />
              <input className="input w-full" type="password" placeholder={t("reset.confirm")}
                value={password2} onChange={(e) => setPassword2(e.target.value)} required minLength={8} />
              <button className="btn btn-primary w-full" disabled={busy}>
                {busy ? t("reset.saving") : t("invite.submit")}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
