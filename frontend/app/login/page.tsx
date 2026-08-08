"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ssoLoginUrl, fetchPublicBranding } from "@/lib/api";
import type { AuthConfig, Branding } from "@/lib/types";
import { useAuth } from "@/components/AuthProvider";
import { useI18n, useT } from "@/components/I18nProvider";
import { useTheme, type Theme } from "@/components/ThemeProvider";
import { LANGS } from "@/lib/i18n";

const DEMO_ROLES = [
  { role: "admin", icon: "🛠️", labelKey: "role.admin", descKey: "login.role.admin" },
  { role: "supervisor", icon: "📊", labelKey: "role.supervisor", descKey: "login.role.supervisor" },
  { role: "quality", icon: "🎯", labelKey: "role.quality", descKey: "login.role.quality" },
  { role: "agent", icon: "🎧", labelKey: "role.agent", descKey: "login.role.agent" },
];

export default function LoginPage() {
  const router = useRouter();
  const { refresh } = useAuth();
  const t = useT();
  const [cfg, setCfg] = useState<AuthConfig | null>(null);
  const [brand, setBrand] = useState<Branding | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  // Kurum olustur formu
  const [org, setOrg] = useState({ org_name: "", admin_name: "", admin_email: "", password: "" });
  // Giris formu
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [forgotOpen, setForgotOpen] = useState(false);
  const [forgotEmail, setForgotEmail] = useState("");

  useEffect(() => {
    api.authConfig().then((c) => {
      setCfg(c);
      // Gercek kurumun markasini (org_slug) cek — login ekraninda sirket markasi gorunsun
      fetchPublicBranding(c?.org_slug ?? "demo").then(setBrand).catch(() => {});
    }).catch(() => setCfg(null));
  }, []);

  async function afterAuth() {
    await refresh();
    router.replace("/");
  }

  async function createOrg(e: React.FormEvent) {
    e.preventDefault();
    setBusy("org"); setError("");
    try { await api.registerOrg(org); await refresh(); router.replace("/onboarding"); }
    catch (err) { setError(err instanceof Error ? err.message : String(err)); setBusy(""); }
  }

  async function formLogin(e: React.FormEvent) {
    e.preventDefault();
    setBusy("login"); setError("");
    try { await api.login(email, password, cfg?.org_slug ?? "demo"); await afterAuth(); }
    catch (err) { setError(err instanceof Error ? err.message : String(err)); setBusy(""); }
  }

  async function demoLogin(role: string) {
    setBusy(role); setError("");
    try { await api.demoLogin(role); await afterAuth(); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); setBusy(""); }
  }

  async function sendForgot(e: React.FormEvent) {
    e.preventDefault();
    setBusy("forgot"); setError("");
    try {
      const r = await api.forgotPassword(forgotEmail, cfg?.org_slug ?? undefined);
      setInfo(r.message || t("login.forgotSent"));
      setForgotOpen(false);
    } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { setBusy(""); }
  }

  const needsSetup = cfg?.needs_setup ?? false;
  const showDemo = (cfg?.demo_mode ?? true);
  const orgName = brand?.brand_name ?? cfg?.org_name ?? t("app.name");

  return (
    <div className="min-h-screen">
      <div className="absolute right-4 top-4 flex gap-2">
        <ThemeToggle />
        <LangToggle />
      </div>

      <div className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-4 py-10">
        {/* Marka */}
        <div className="mb-6 text-center">
          <div className="flex items-center justify-center gap-3 text-2xl font-bold">
            {brand?.logo_data_url ? (
              <img src={brand.logo_data_url} alt="logo" className="h-10 max-w-48 object-contain" />
            ) : (
              <span aria-hidden className="grid h-10 w-10 place-items-center rounded-xl text-xl text-white"
                style={{ background: brand?.brand_color ?? "var(--series)" }}>
                {orgName.slice(0, 1)}
              </span>
            )}
            {orgName}
          </div>
          <p className="mt-2 text-sm text-ink2">{t("app.tagline")}</p>
        </div>

        {error && (
          <p className="card mb-4 border-l-4 p-3 text-sm" style={{ borderLeftColor: "var(--status-critical)" }}>
            {error}
          </p>
        )}
        {info && (
          <p className="card mb-4 border-l-4 p-3 text-sm" style={{ borderLeftColor: "var(--status-good)" }}>
            {info}
          </p>
        )}

        {cfg === null && <p className="text-center text-sm text-muted">…</p>}

        {/* ---- KURUM OLUSTUR (ilk kurulum) ---- */}
        {cfg && needsSetup && (
          <div className="card p-5">
            <h2 className="text-lg font-semibold">{t("setup.title")}</h2>
            <p className="mt-1 text-sm text-ink2">{t("setup.subtitle")}</p>
            <form onSubmit={createOrg} className="mt-4 space-y-3">
              <Field label={t("setup.orgName")}>
                <input className="input w-full" value={org.org_name} required
                  onChange={(e) => setOrg({ ...org, org_name: e.target.value })}
                  placeholder="Örn. Netix İletişim" />
              </Field>
              <Field label={t("setup.adminName")}>
                <input className="input w-full" value={org.admin_name} required
                  onChange={(e) => setOrg({ ...org, admin_name: e.target.value })} />
              </Field>
              <Field label={t("setup.email")}>
                <input className="input w-full" type="email" value={org.admin_email} required
                  onChange={(e) => setOrg({ ...org, admin_email: e.target.value })} />
              </Field>
              <Field label={t("setup.password")}>
                <input className="input w-full" type="password" value={org.password} required minLength={8}
                  onChange={(e) => setOrg({ ...org, password: e.target.value })} />
              </Field>
              <button className="btn btn-primary w-full" disabled={busy === "org"}>
                {busy === "org" ? t("setup.submitting") : t("setup.submit")}
              </button>
            </form>
          </div>
        )}

        {/* ---- GIRIS (kurum kuruluysa) ---- */}
        {cfg && !needsSetup && (
          <div className="card p-5">
            <h2 className="text-lg font-semibold">{t("login.title")}</h2>
            {!forgotOpen ? (
              <form onSubmit={formLogin} className="mt-4 space-y-3">
                <input className="input w-full" type="email" placeholder={t("login.emailPlaceholder")}
                  value={email} onChange={(e) => setEmail(e.target.value)} required />
                <input className="input w-full" type="password" placeholder={t("login.passwordPlaceholder")}
                  value={password} onChange={(e) => setPassword(e.target.value)} required />
                <button className="btn btn-primary w-full" disabled={busy === "login"}>
                  {busy === "login" ? t("login.submitting") : t("login.submit")}
                </button>
                <button type="button" className="text-xs text-series hover:underline"
                  onClick={() => { setForgotOpen(true); setForgotEmail(email); }}>
                  {t("login.forgot")}
                </button>
              </form>
            ) : (
              <form onSubmit={sendForgot} className="mt-4 space-y-3">
                <p className="text-sm text-ink2">{t("login.forgotHint")}</p>
                <input className="input w-full" type="email" placeholder={t("login.emailPlaceholder")}
                  value={forgotEmail} onChange={(e) => setForgotEmail(e.target.value)} required />
                <button className="btn btn-primary w-full" disabled={busy === "forgot"}>{t("login.forgotSend")}</button>
                <button type="button" className="text-xs text-series hover:underline"
                  onClick={() => setForgotOpen(false)}>{t("login.backToLogin")}</button>
              </form>
            )}
            {cfg.sso_enabled && (
              <a href={ssoLoginUrl()} className="btn mt-3 flex w-full items-center justify-center gap-2">
                <span aria-hidden>🔐</span> {t("sso.button")}
              </a>
            )}
          </div>
        )}

        {/* ---- DEMO (parolasiz deneme) ---- */}
        {cfg && showDemo && (
          <details className="card mt-4 p-0" open={needsSetup ? false : false}>
            <summary className="cursor-pointer list-none px-5 py-3 text-sm font-semibold text-ink2">
              🧪 {needsSetup ? t("setup.orDemo") : t("login.demoTitle")}
            </summary>
            <div className="grid gap-2 border-t border-hairline p-4 sm:grid-cols-2">
              {DEMO_ROLES.map((r) => (
                <button key={r.role} onClick={() => demoLogin(r.role)} disabled={!!busy}
                  className="card flex items-start gap-3 p-3 text-left transition hover:border-series disabled:opacity-50">
                  <span className="text-xl" aria-hidden>{r.icon}</span>
                  <span className="min-w-0">
                    <span className="block text-sm font-semibold">{t(r.labelKey)}</span>
                    <span className="block text-xs text-muted">{t(r.descKey)}</span>
                  </span>
                </button>
              ))}
            </div>
            <p className="px-4 pb-3 text-center text-xs text-muted">{t("login.demoNote")} <code>demo1234</code></p>
          </details>
        )}
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink2">{label}</span>
      {children}
    </label>
  );
}

function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const t = useT();
  const opts: { v: Theme; icon: string; key: string }[] = [
    { v: "light", icon: "☀️", key: "common.light" },
    { v: "dark", icon: "🌙", key: "common.dark" },
    { v: "system", icon: "🖥️", key: "common.system" },
  ];
  return (
    <div className="flex gap-0.5 rounded-lg bg-[var(--surface-2)] p-1">
      {opts.map((o) => (
        <button key={o.v} onClick={() => setTheme(o.v)} title={t(o.key)} aria-pressed={theme === o.v}
          className={`rounded-md px-2 py-1 text-xs ${theme === o.v ? "bg-[var(--surface)] shadow-sm" : "opacity-60"}`}>
          <span aria-hidden>{o.icon}</span>
        </button>
      ))}
    </div>
  );
}

function LangToggle() {
  const { lang, setLang } = useI18n();
  return (
    <div className="flex gap-0.5 rounded-lg bg-[var(--surface-2)] p-1">
      {LANGS.map((l) => (
        <button key={l.code} onClick={() => setLang(l.code)} title={l.label} aria-pressed={lang === l.code}
          className={`rounded-md px-2 py-1 text-xs font-semibold ${lang === l.code ? "bg-[var(--surface)] shadow-sm" : "opacity-60"}`}>
          {l.flag} {l.code.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
