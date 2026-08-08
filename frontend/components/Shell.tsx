"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import Sidebar, { COLLAPSE_KEY } from "./Sidebar";
import { useAuth } from "./AuthProvider";
import { useT } from "./I18nProvider";

export default function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { me, loading } = useAuth();
  const t = useT();
  const [mobileOpen, setMobileOpen] = useState(false);
  // Sidebar genisligini Shell biliyor ki icerik bosluğu ona gore ayarlansin
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    setCollapsed(localStorage.getItem(COLLAPSE_KEY) === "1");
  }, []);

  useEffect(() => { setMobileOpen(false); }, [pathname]);

  function toggleCollapse() {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
  }

  // Oturumsuz, tam ekran (sidebar'siz) sayfalar
  if (["/login", "/accept-invite", "/reset-password"].includes(pathname)) {
    return <>{children}</>;
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted">
        {t("common.loading")}
      </div>
    );
  }
  if (!me) return null; // AuthProvider login'e yonlendiriyor

  return (
    <div className="min-h-screen">
      <Sidebar
        mobileOpen={mobileOpen}
        onClose={() => setMobileOpen(false)}
        collapsed={collapsed}
        onToggleCollapse={toggleCollapse}
      />

      <div
        className="transition-[padding] duration-200 lg:pl-[var(--pad)]"
        style={{ "--pad": collapsed ? "var(--sidebar-w-collapsed)" : "var(--sidebar-w)" } as React.CSSProperties}
      >
        {/* Mobil ust bar (sidebar mobilde gizli) */}
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-hairline bg-surface px-4 lg:hidden">
          <button className="btn !px-2.5 !py-1" onClick={() => setMobileOpen(true)} aria-label="Menu">
            ☰
          </button>
          <span className="font-bold">{t("app.name")}</span>
        </header>

        <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">{children}</main>
      </div>
    </div>
  );
}
