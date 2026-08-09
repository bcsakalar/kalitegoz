"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api, tokenStore } from "@/lib/api";
import type { Me, Role } from "@/lib/types";

interface AuthCtx {
  me: Me | null;
  loading: boolean;
  logout: () => void;
  refresh: () => Promise<Me | null>;
}

const Ctx = createContext<AuthCtx>({
  me: null, loading: true, logout: () => {}, refresh: async () => null,
});

export const useAuth = () => useContext(Ctx);

export function can(role: Role | undefined, ...allowed: Role[]): boolean {
  return !!role && allowed.includes(role);
}

/**
 * S14 — Giriş sonrası kullanıcı hangi ekrana düşer?
 *
 * Herkesi çağrı listesine düşürmek, "listeye bakıp ne yapacağını bulma"
 * işini her kullanıcıya her gün yeniden yaptırır. Oysa her rolün günü
 * belli bir ekranda geçer:
 *
 * - kaliteci  → İnceleme Kuyruğu: işi zaten orada, sırada bekleyen çağrılar
 * - süpervizör/yönetici → Kokpit: tek tek çağrı değil, takımın durumu
 * - temsilci  → Kendi karnesi: başkasının çağrısını görmesi zaten yasak
 *
 * Bu YALNIZCA giriş anında uygulanır. Kenar çubuğundaki "Çağrılar" bağlantısı
 * `/` adresine gider; `/` kendini yönlendirseydi o bağlantı çalışmazdı.
 */
export function landingFor(me: Me | null): string {
  if (!me) return "/";
  if (me.role === "quality") return "/review";
  if (me.role === "admin" || me.role === "supervisor") return "/cockpit";
  if (me.role === "agent" && me.agent_id) return `/agents/${me.agent_id}`;
  return "/";
}

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  // Me'yi DONDURUR: giris akisi rolu hemen bilmeli (setMe asenkron oldugu icin
  // cagiran taraf `me` state'ini o turda goremez).
  async function load(): Promise<Me | null> {
    if (!tokenStore.get()) {
      setMe(null);
      setLoading(false);
      return null;
    }
    try {
      const u = await api.me();
      setMe(u);
      return u;
    } catch {
      setMe(null);
      return null;
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
    if (me && isLogin) router.replace(landingFor(me));
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
