"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api, wsUrl } from "@/lib/api";
import type { Alert } from "@/lib/types";
import { useAuth } from "./AuthProvider";

interface LiveAlertsCtx {
  unread: number;
  /** En son gelen CANLI alarm (toast icin); okundugunda temizlenir. */
  incoming: Alert | null;
  dismissIncoming: () => void;
  connected: boolean;
  refresh: () => void;
}

const Ctx = createContext<LiveAlertsCtx>({
  unread: 0,
  incoming: null,
  dismissIncoming: () => {},
  connected: false,
  refresh: () => {},
});

export const useLiveAlerts = () => useContext(Ctx);

/** WebSocket kopukken kullanilan yedek yoklama araligi. */
const POLL_MS = 30_000;
const MAX_BACKOFF_MS = 30_000;

/**
 * Kac basarisiz denemeden sonra vazgecilir.
 *
 * Neden gerekli: sunucu yetkisiz baglantiyi accept() ETMEDEN kapatir; ASGI bunu
 * HTTP 403 handshake reddine cevirir ve ozel kapanis kodumuz (4401/4403) hicbir
 * zaman istemciye ULASMAZ — tarayici yalnizca 1006 (anormal kapanma) gorur.
 * Yani "yetki hatasi" ile "ag koptu" ayirt EDILEMEZ. Sonsuz yeniden deneme
 * yerine sayiyi sinirliyoruz; vazgectigimizde yedek yoklama devreye girer ve
 * token gercekten gecersizse REST 401 doner, AuthProvider da login'e atar.
 */
const MAX_ATTEMPTS = 6;

export default function LiveAlertsProvider({ children }: { children: React.ReactNode }) {
  const { me } = useAuth();
  const [unread, setUnread] = useState(0);
  const [incoming, setIncoming] = useState<Alert | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(1000);
  const attemptsRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const closedByUsRef = useRef(false);

  const refresh = useCallback(() => {
    if (!me || me.role === "agent") return;
    api.listAlerts(true).then((a) => setUnread(a.length)).catch(() => {});
  }, [me]);

  // Ilk sayim + WebSocket kopukken yedek yoklama.
  // WS bagliysa yoklamaya gerek yok — sayim zaten anlik guncelleniyor.
  useEffect(() => {
    if (!me || me.role === "agent") return;
    refresh();
    if (connected) return;
    const id = setInterval(refresh, POLL_MS);
    return () => clearInterval(id);
  }, [me, connected, refresh]);

  useEffect(() => {
    // Temsilciler alarm akisini gormez (backend de 4403 ile reddeder).
    if (!me || me.role === "agent") return;

    closedByUsRef.current = false;
    attemptsRef.current = 0;

    const connect = () => {
      const url = wsUrl("/ws/alerts");
      if (!url) return;
      let ws: WebSocket;
      try {
        ws = new WebSocket(url);
      } catch {
        scheduleReconnect();
        return;
      }
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        backoffRef.current = 1000;
        attemptsRef.current = 0; // basarili baglanti sayaci sifirlar
      };

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type !== "alert") return;
          setUnread((n) => n + 1);
          setIncoming(msg.data as Alert);
        } catch {
          /* bozuk mesaj — yok say */
        }
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        scheduleReconnect();
      };

      ws.onerror = () => {
        // onclose zaten arkasindan gelir; yeniden baglanmayi orada yonetiyoruz.
      };
    };

    const scheduleReconnect = () => {
      if (closedByUsRef.current) return;
      if (attemptsRef.current >= MAX_ATTEMPTS) return; // yedek yoklamaya birak
      attemptsRef.current += 1;
      timerRef.current = setTimeout(connect, backoffRef.current);
      backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);
    };

    connect();

    return () => {
      closedByUsRef.current = true;
      if (timerRef.current) clearTimeout(timerRef.current);
      wsRef.current?.close();
      wsRef.current = null;
      setConnected(false);
    };
  }, [me]);

  return (
    <Ctx.Provider
      value={{ unread, incoming, dismissIncoming: () => setIncoming(null), connected, refresh }}
    >
      {children}
    </Ctx.Provider>
  );
}
