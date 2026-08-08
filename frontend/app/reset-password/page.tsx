"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";
import { useT } from "@/components/I18nProvider";

export default function ResetPasswordPage() {
  const router = useRouter();
  const { refresh } = useAuth();
  const t = useT();
  const [token, setToken] = useState("");
  const [ready, setReady] = useState(false);
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setToken(new URLSearchParams(window.location.search).get("token") ?? "");
    setReady(true);
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== password2) { setError(t("reset.mismatch")); return; }
    setBusy(true); setError("");
    try {
      await api.resetPassword(token, password);
      await refresh();
      router.replace("/");
    } catch (err) { setError(err instanceof Error ? err.message : String(err)); setBusy(false); }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4">
      <div className="card p-6">
        <h1 className="text-lg font-semibold">{t("reset.title")}</h1>
        {ready && !token && (
          <p className="mt-3 text-sm" style={{ color: "var(--status-critical)" }}>{t("reset.noToken")}</p>
        )}
        {error && <p className="mt-3 text-sm" style={{ color: "var(--status-critical)" }}>{error}</p>}
        {token && (
          <form onSubmit={submit} className="mt-4 space-y-3">
            <input className="input w-full" type="password" placeholder={t("reset.newPassword")}
              value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} />
            <input className="input w-full" type="password" placeholder={t("reset.confirm")}
              value={password2} onChange={(e) => setPassword2(e.target.value)} required minLength={8} />
            <button className="btn btn-primary w-full" disabled={busy}>
              {busy ? t("reset.saving") : t("reset.submit")}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
