"use client";

import { useEffect, useRef, useState } from "react";
import { wsUrl } from "@/lib/api";
import { useT } from "@/components/I18nProvider";
import type { AssistSuggestion } from "@/lib/types";

const SEV_COLOR: Record<string, string> = {
  kritik: "var(--status-critical)", uyari: "var(--status-warning)", bilgi: "var(--series-1)",
};

/* Web Speech API tarayici tipleri (TS'de standart degil) */
type SR = {
  lang: string; continuous: boolean; interimResults: boolean;
  start: () => void; stop: () => void;
  onresult: ((e: { resultIndex: number; results: ArrayLike<{ 0: { transcript: string } }> }) => void) | null;
  onerror: ((e: unknown) => void) | null;
  onend: (() => void) | null;
};

function getRecognition(): SR | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { webkitSpeechRecognition?: new () => SR; SpeechRecognition?: new () => SR };
  const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
  return Ctor ? new Ctor() : null;
}

/** Canlı sufle: mikrofonu dinler (tarayıcı STT), metni WS'e akıtır, öneri alır. */
export default function LiveAssist() {
  const t = useT();
  const [supported, setSupported] = useState(true);
  const [listening, setListening] = useState(false);
  const [connected, setConnected] = useState(false);
  const [text, setText] = useState("");
  const [suggestions, setSuggestions] = useState<AssistSuggestion[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const recRef = useRef<SR | null>(null);
  const textRef = useRef("");

  useEffect(() => { setSupported(getRecognition() !== null); }, []);

  function stop() {
    recRef.current?.stop();
    wsRef.current?.close();
    recRef.current = null;
    wsRef.current = null;
    setListening(false);
    setConnected(false);
  }
  useEffect(() => () => stop(), []);

  function start() {
    const url = wsUrl("/ws/assist");
    const rec = getRecognition();
    if (!url || !rec) { setSupported(false); return; }

    const ws = new WebSocket(url);
    wsRef.current = ws;
    ws.onopen = () => setConnected(true);
    ws.onmessage = (ev) => {
      try {
        const m = JSON.parse(ev.data);
        if (m.type === "suggestions") setSuggestions(m.data);
      } catch { /* yok say */ }
    };
    ws.onclose = () => setConnected(false);

    rec.lang = "tr-TR";
    rec.continuous = true;
    rec.interimResults = true;
    rec.onresult = (e) => {
      let chunk = "";
      for (let i = e.resultIndex; i < e.results.length; i++) chunk += e.results[i][0].transcript;
      const full = (textRef.current + " " + chunk).trim().slice(-4000);
      setText(full);
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ text: full }));
    };
    rec.onerror = () => {};
    rec.onend = () => { if (recRef.current) rec.start(); }; // otomatik yeniden başlat
    recRef.current = rec;
    rec.start();
    setListening(true);
  }

  if (!supported) {
    return (
      <div className="bg-[var(--status-warning)]/10 p-3 text-sm text-ink2">
        Tarayıcınız canlı ses tanımayı (Web Speech API) desteklemiyor. Chrome/Edge deneyin
        veya yukarıdaki metin kutusunu kullanın.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        {!listening ? (
          <button className="btn btn-primary" onClick={start}>{t("assist.startLive")}</button>
        ) : (
          <button className="btn" onClick={stop}>⏹ Durdur</button>
        )}
        {listening && (
          <span className="flex items-center gap-1 text-xs text-muted">
            <span className={`h-2 w-2 ${connected ? "bg-[var(--status-good)] animate-pulse" : "bg-[var(--muted)]"}`} />
            {connected ? t("assist.listening") : t("assist.connecting")}
          </span>
        )}
      </div>
      {text && <p className="bg-grid/40 p-2 text-xs text-ink2">{text}</p>}
      <div className="space-y-2">
        {suggestions.map((s, i) => (
          <div key={i} className="bg-grid/40 p-2 text-sm" style={{ borderLeft: `3px solid ${SEV_COLOR[s.severity] ?? "var(--muted)"}` }}>
            <div className="flex items-center gap-2 text-[10px] uppercase text-muted">
              <span style={{ color: SEV_COLOR[s.severity] }}>{t(`sev.${s.severity}`)}</span>
              <span>{t(`kind.${s.kind}`)}</span>
            </div>
            <p className="mt-0.5">{s.text}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
