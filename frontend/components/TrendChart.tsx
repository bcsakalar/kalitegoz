"use client";

import { useRef, useState } from "react";
import type { TrendPoint } from "@/lib/types";
import { useT } from "@/components/I18nProvider";

const W = 640;
const H = 220;
const PAD = { top: 16, right: 48, bottom: 28, left: 36 };
const TICKS = [0, 25, 50, 75, 100];

/**
 * Gunluk ortalama puan trendi — tek seri cizgi grafik.
 * Tek seri oldugu icin legend yok (baslik seriyi adlandirir);
 * crosshair + tooltip ile her noktanin degeri okunabilir.
 */
/** Eğilim çizmek için gereken asgari nokta — backend `stats_honesty` ile aynı. */
const MIN_POINTS = 7;

export default function TrendChart({ data, title }: { data: TrendPoint[]; title: string }) {
  const t = useT();
  const wrapRef = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<{ i: number; px: number; py: number } | null>(null);

  // B10 + B19: BOŞ GRAFİK ÇİZİLMEZ ve "Veri yok" denmez.
  //
  // Çizgi grafik bir "değişim" iddiasıdır; tek nokta değişim göstermez ve
  // bomboş bir kutu çizilir. Kullanıcı "Veri yok" görünce sistemin bozuk
  // olduğunu sanıyordu — oysa veri VAR, sadece eğilim için yetmiyor.
  // Bu yüzden: tekil değer kartı + ne gerektiğinin açıkça söylenmesi.
  if (data.length < MIN_POINTS) {
    const degerler = data.map((d) => d.avg_score).filter((v): v is number => v != null);
    const ortalama = degerler.length
      ? Math.round((degerler.reduce((a, b) => a + b, 0) / degerler.length) * 10) / 10
      : null;
    const toplamCagri = data.reduce((a, d) => a + (d.call_count ?? 0), 0);

    return (
      <div className="card p-4">
        <h3 className="text-sm font-semibold text-ink2">{title}</h3>
        <div className="flex flex-col items-center justify-center gap-1.5 py-8 text-center">
          {ortalama != null ? (
            <>
              <p className="text-3xl font-bold tabular-nums">{ortalama.toFixed(1)}</p>
              <p className="text-xs text-ink2">
                {toplamCagri} çağrının ortalaması ({data.length} gün)
              </p>
            </>
          ) : (
            <p className="text-sm font-semibold">Henüz puanlanmış çağrı yok.</p>
          )}
          <p className="mt-1 max-w-xs text-xs leading-relaxed text-muted">
            Eğilim grafiği için en az {MIN_POINTS} günlük veri gerekir
            {data.length > 0 && ` (şu an ${data.length} gün)`}. O zamana kadar
            tekil değer gösteriliyor.
          </p>
        </div>
      </div>
    );
  }

  const iw = W - PAD.left - PAD.right;
  const ih = H - PAD.top - PAD.bottom;
  const x = (i: number) =>
    PAD.left + (data.length === 1 ? iw / 2 : (i / (data.length - 1)) * iw);
  const y = (v: number) => PAD.top + ih - (v / 100) * ih;

  const linePath = data
    .map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.avg_score).toFixed(1)}`)
    .join(" ");
  const areaPath =
    `${linePath} L${x(data.length - 1).toFixed(1)},${y(0)} L${x(0).toFixed(1)},${y(0)} Z`;

  const last = data[data.length - 1];

  function onMove(e: React.PointerEvent<SVGRectElement>) {
    const svg = e.currentTarget.ownerSVGElement;
    const wrap = wrapRef.current;
    if (!svg || !wrap) return;
    const svgRect = svg.getBoundingClientRect();
    const relX = ((e.clientX - svgRect.left) / svgRect.width) * W;
    let best = 0;
    let bestDist = Infinity;
    data.forEach((_, i) => {
      const d = Math.abs(x(i) - relX);
      if (d < bestDist) {
        bestDist = d;
        best = i;
      }
    });
    const wrapRect = wrap.getBoundingClientRect();
    setHover({
      i: best,
      px: (x(best) / W) * svgRect.width + (svgRect.left - wrapRect.left),
      py: (y(data[best].avg_score) / H) * svgRect.height + (svgRect.top - wrapRect.top),
    });
  }

  const fmtDay = (iso: string) =>
    new Date(iso + "T00:00:00").toLocaleDateString("tr-TR", { day: "2-digit", month: "2-digit" });

  return (
    <div className="card p-4">
      <h3 className="text-sm font-semibold text-ink2">{title}</h3>
      <div ref={wrapRef} className="relative">
        <svg viewBox={`0 0 ${W} ${H}`} className="mt-2 w-full" role="img" aria-label={title}>
          {/* hairline gridlines */}
          {TICKS.map((t) => (
            <g key={t}>
              <line
                x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)}
                stroke="var(--grid)" strokeWidth={1}
              />
              <text
                x={PAD.left - 6} y={y(t) + 3.5} textAnchor="end"
                fontSize={10} fill="var(--muted)" style={{ fontVariantNumeric: "tabular-nums" }}
              >
                {t}
              </text>
            </g>
          ))}
          {/* alan yikamasi (%10) + 2px cizgi */}
          <path d={areaPath} fill="var(--series-1)" opacity={0.1} />
          <path
            d={linePath} fill="none" stroke="var(--series-1)"
            strokeWidth={2} strokeLinejoin="miter" strokeLinecap="butt"
          />
          {/* crosshair */}
          {hover && (
            <line
              x1={x(hover.i)} x2={x(hover.i)} y1={PAD.top} y2={H - PAD.bottom}
              stroke="var(--baseline)" strokeWidth={1}
            />
          )}
          {/* hover noktasi + son nokta (yuzey halkali) */}
          {hover && (
            <circle
              cx={x(hover.i)} cy={y(data[hover.i].avg_score)} r={4.5}
              fill="var(--series-1)" stroke="var(--surface)" strokeWidth={2}
            />
          )}
          <circle
            cx={x(data.length - 1)} cy={y(last.avg_score)} r={4.5}
            fill="var(--series-1)" stroke="var(--surface)" strokeWidth={2}
          />
          {/* son degere dogrudan etiket */}
          <text
            x={x(data.length - 1) + 8} y={y(last.avg_score) + 4}
            fontSize={12} fontWeight={600} fill="var(--ink)"
          >
            {last.avg_score.toFixed(1)}
          </text>
          {/* x ekseni: ilk/orta/son gun */}
          {[0, Math.floor((data.length - 1) / 2), data.length - 1]
            .filter((v, i, a) => a.indexOf(v) === i)
            .map((i) => (
              <text
                key={i} x={x(i)} y={H - 8} textAnchor="middle"
                fontSize={10} fill="var(--muted)"
              >
                {fmtDay(data[i].date)}
              </text>
            ))}
          {/* hit alani */}
          <rect
            x={PAD.left} y={PAD.top} width={iw} height={ih} fill="transparent"
            onPointerMove={onMove} onPointerLeave={() => setHover(null)}
          />
        </svg>
        {hover && (
          <div
            className="chart-tooltip"
            style={{ left: hover.px + 10, top: Math.max(0, hover.py - 40) }}
          >
            <div className="text-base font-semibold">
              {data[hover.i].avg_score.toFixed(1)}
            </div>
            <div className="text-muted">
              {fmtDay(data[hover.i].date)} · {data[hover.i].call_count} çağrı
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
