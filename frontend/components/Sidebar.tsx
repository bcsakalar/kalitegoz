"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { ROLE_LABEL_KEYS } from "@/lib/api";
import type { Role } from "@/lib/types";
import { useAuth } from "./AuthProvider";
import { useLiveAlerts } from "./LiveAlertsProvider";
import NotificationBell from "./NotificationBell";
import { useI18n, useT } from "./I18nProvider";
import { useTheme, type Theme } from "./ThemeProvider";
import { LANGS } from "@/lib/i18n";

export const COLLAPSE_KEY = "kg_sidebar_collapsed";

interface NavLink {
  href: string;
  labelKey: string;
  icon: string;
  roles: Role[];
  badge?: "alerts";
}

const LINKS: NavLink[] = [
  { href: "/", labelKey: "nav.calls", icon: "📋", roles: ["admin", "supervisor", "quality", "agent"] },
  { href: "/search", labelKey: "nav.search", icon: "🔍", roles: ["admin", "supervisor", "quality", "agent"] },
  { href: "/cockpit", labelKey: "nav.cockpit", icon: "📊", roles: ["admin", "supervisor"] },
  { href: "/analytics", labelKey: "nav.analytics", icon: "📈", roles: ["admin", "supervisor", "quality"] },
  { href: "/assist", labelKey: "nav.assist", icon: "🎧", roles: ["admin", "supervisor", "quality", "agent"] },
  { href: "/agents", labelKey: "nav.agents", icon: "👥", roles: ["admin", "supervisor", "quality"] },
  { href: "/leaderboard", labelKey: "nav.leaderboard", icon: "🏆", roles: ["admin", "supervisor", "quality", "agent"] },
  { href: "/workflow", labelKey: "nav.workflow", icon: "✅", roles: ["admin", "supervisor", "quality", "agent"], badge: "alerts" },
  { href: "/calibration", labelKey: "nav.calibration", icon: "⚖️", roles: ["admin", "supervisor", "quality"] },
  { href: "/rubric", labelKey: "nav.rubric", icon: "📐", roles: ["admin", "supervisor", "quality"] },
  { href: "/roi", labelKey: "nav.roi", icon: "💰", roles: ["admin", "supervisor"] },
  { href: "/security", labelKey: "nav.security", icon: "🔒", roles: ["admin", "supervisor", "quality"] },
  { href: "/admin", labelKey: "nav.admin", icon: "⚙️", roles: ["admin"] },
];

export default function Sidebar({
  mobileOpen, onClose, collapsed, onToggleCollapse,
}: {
  mobileOpen: boolean;
  onClose: () => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
}) {
  const pathname = usePathname();
  const { me, logout } = useAuth();
  const t = useT();
  // Sayim canli: yeni alarm WebSocket ile aninda dusuyor. Sayfa degisiminde
  // yine de tazeleniyoruz — alarm baska bir sekmede okunmus olabilir.
  const { unread, connected, refresh } = useLiveAlerts();

  useEffect(() => { refresh(); }, [pathname, refresh]);

  if (!me) return null;
  const links = LINKS.filter((l) => l.roles.includes(me.role));

  return (
    <>
      {mobileOpen && (
        <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={onClose} aria-hidden />
      )}

      <aside
        className={`sidebar fixed inset-y-0 left-0 z-40 flex flex-col transition-all duration-200 lg:translate-x-0 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
        style={{ width: collapsed ? "var(--sidebar-w-collapsed)" : "var(--sidebar-w)" }}
      >
        {/* Logo */}
        <div className="flex h-14 shrink-0 items-center gap-2 border-b border-hairline px-3">
          <Link href="/" className="flex items-center gap-2 overflow-hidden font-bold">
            <span aria-hidden className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-series text-sm text-white">
              K
            </span>
            {!collapsed && <span className="truncate text-lg">{t("app.name")}</span>}
          </Link>
          <div className={collapsed ? "mx-auto" : "ml-auto"}>
            <NotificationBell collapsed={collapsed} />
          </div>
          {/* Canli baglanti gostergesi: kullanici alarmlarin aninda mi yoksa
              yoklama ile mi geldigini bilmeli. */}
          {me.role !== "agent" && !collapsed && (
            <span
              className="ml-auto flex items-center gap-1 text-[10px] text-muted"
              title={connected ? t("alerts.live.on") : t("alerts.live.off")}
            >
              <span
                aria-hidden
                className={`h-1.5 w-1.5 rounded-full ${
                  connected ? "bg-[var(--status-ok)]" : "bg-[var(--muted)]"
                }`}
              />
              {connected ? t("alerts.live.short") : ""}
            </span>
          )}
        </div>

        {/* Navigasyon */}
        <nav className="flex-1 space-y-0.5 overflow-y-auto p-2">
          {links.map((l) => {
            const active = l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                onClick={onClose}
                className={`nav-item ${collapsed ? "justify-center" : ""}`}
                data-active={active}
                title={collapsed ? t(l.labelKey) : undefined}
              >
                <span className="nav-icon" aria-hidden>{l.icon}</span>
                {!collapsed && <span className="truncate">{t(l.labelKey)}</span>}
                {l.badge === "alerts" && unread > 0 && (
                  <span
                    className={`rounded-full bg-[var(--status-critical)] px-1.5 text-[10px] font-bold text-white ${
                      collapsed ? "absolute right-0.5 top-0.5" : "ml-auto"
                    }`}
                  >
                    {unread}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* Alt panel */}
        <div className="shrink-0 space-y-1.5 border-t border-hairline p-2">
          <ThemeSwitch collapsed={collapsed} />
          <LangSwitch collapsed={collapsed} />

          <div className={`flex items-center gap-2 rounded-lg bg-[var(--surface-2)] p-2 ${collapsed ? "justify-center" : ""}`}>
            <span aria-hidden className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-series text-xs font-bold text-white">
              {me.name.slice(0, 1).toUpperCase()}
            </span>
            {!collapsed && (
              <>
                <Link href="/account" onClick={onClose} title={t("account.title")}
                  className="min-w-0 flex-1 leading-tight hover:opacity-80">
                  <span className="block truncate text-xs font-semibold">{me.name}</span>
                  <span className="block truncate text-[11px] text-muted">
                    {t(ROLE_LABEL_KEYS[me.role])}
                  </span>
                </Link>
                <button className="btn !px-2 !py-1 text-xs" onClick={logout} title={t("common.logout")}>
                  ⏻
                </button>
              </>
            )}
          </div>
          {collapsed && (
            <button className="btn w-full !px-2 !py-1 text-xs" onClick={logout} title={t("common.logout")}>
              ⏻
            </button>
          )}

          <button
            className="btn hidden w-full !py-1 text-xs lg:flex lg:justify-center"
            onClick={onToggleCollapse}
            title={collapsed ? t("nav.expand") : t("nav.collapse")}
            aria-label={collapsed ? t("nav.expand") : t("nav.collapse")}
          >
            {collapsed ? "»" : "«"}
          </button>
        </div>
      </aside>
    </>
  );
}

function ThemeSwitch({ collapsed }: { collapsed: boolean }) {
  const { theme, setTheme } = useTheme();
  const t = useT();
  const opts: { v: Theme; icon: string; key: string }[] = [
    { v: "light", icon: "☀️", key: "common.light" },
    { v: "dark", icon: "🌙", key: "common.dark" },
    { v: "system", icon: "🖥️", key: "common.system" },
  ];
  return (
    <div className={`flex gap-0.5 rounded-lg bg-[var(--surface-2)] p-1 ${collapsed ? "flex-col" : ""}`}>
      {opts.map((o) => (
        <button
          key={o.v}
          onClick={() => setTheme(o.v)}
          title={t(o.key)}
          aria-pressed={theme === o.v}
          className={`flex flex-1 items-center justify-center rounded-md py-1 text-xs font-medium ${
            theme === o.v ? "bg-[var(--surface)] text-ink shadow-sm" : "text-ink2 hover:text-ink"
          }`}
        >
          <span aria-hidden>{o.icon}</span>
        </button>
      ))}
    </div>
  );
}

function LangSwitch({ collapsed }: { collapsed: boolean }) {
  const { lang, setLang } = useI18n();
  return (
    <div className={`flex gap-0.5 rounded-lg bg-[var(--surface-2)] p-1 ${collapsed ? "flex-col" : ""}`}>
      {LANGS.map((l) => (
        <button
          key={l.code}
          onClick={() => setLang(l.code)}
          aria-pressed={lang === l.code}
          title={l.label}
          className={`flex flex-1 items-center justify-center gap-1 rounded-md py-1 text-xs font-semibold ${
            lang === l.code ? "bg-[var(--surface)] text-ink shadow-sm" : "text-ink2 hover:text-ink"
          }`}
        >
          <span aria-hidden>{l.flag}</span>
          {!collapsed && <span>{l.code.toUpperCase()}</span>}
        </button>
      ))}
    </div>
  );
}
