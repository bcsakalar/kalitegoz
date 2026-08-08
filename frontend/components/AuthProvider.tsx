"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api, tokenStore } from "@/lib/api";
import type { Me, Role } from "@/lib/types";

interface AuthCtx {
  me: Me | null;
  loading: boolean;
  logout: () => void;
  refresh: () => Promise<void>;
}

const Ctx = createContext<AuthCtx>({ me: null, loading: true, logout: () => {}, refresh: async () => {} });

export const useAuth = () => useContext(Ctx);

export function can(role: Role | undefined, ...allowed: Role[]): boolean {
  return !!role && allowed.includes(role);
}

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  async function load() {
    if (!tokenStore.get()) {
      setMe(null);
      setLoading(false);
      return;
    }
    try {
      setMe(await api.me());
    } catch {
      setMe(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Route koruması: token yoksa login'e yönlendir
  useEffect(() => {
    if (loading) return;
    const isLogin = pathname === "/login";
    // Oturumsuz erisilen sayfalar: /sso (SSO geri donusu), /accept-invite ve
    // /reset-password (e-posta linkinden gelen kullanici parolasini belirler).
    const isPublic = isLogin || pathname === "/sso"
      || pathname === "/accept-invite" || pathname === "/reset-password";
    if (!me && !isPublic) router.replace("/login");
    if (me && isLogin) router.replace("/");
  }, [me, loading, pathname, router]);

  function logout() {
    tokenStore.clear();
    setMe(null);
    router.replace("/login");
  }

  return (
    <Ctx.Provider value={{ me, loading, logout, refresh: load }}>{children}</Ctx.Provider>
  );
}
