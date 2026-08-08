"use client";

import { useState } from "react";
import type { CriterionAvg } from "@/lib/types";
import { useT } from "@/components/I18nProvider";

const BAR_H = 16;
const ROW_H = 34;
const LABEL_W = 190;
const W = 640;
const PAD_R = 44;

/**
 * Kriter bazinda ortalama puan (0-10) — tek renkli yatay barlar.
 * Deger her barin ucunda dogrudan etiketli; hover'da adet bilgisiyle tooltip.
 * Bar ucu 4px yuvarlak, taban (sol) kose.
 */
export default function CriteriaBars({ items, title }: { items: CriterionAvg[]; title: string }) {
  const t = useT();
  const [hover, setHover] = useState<number | null>(null);

  if (items.length === 0) {
    return (
      <div className="card p-4">
        <h3 className="text-sm font-semibold text-ink2">{title}</h3>
        <p className="py-10 text-center text-sm text-muted">{t("common.noData")}</p>
      </div>
    );
  }

  const H = items.length * ROW_H + 8;
  const trackW = W - LABEL_W - PAD_R;

  const barPath = (yTop: number, w: number) => {
    const r = Math.min(4, w);
    const x0 = LABEL_W;
    // taban kose, uc 4px yuvarlak
    return `M${x0},${yTop} H${x0 + w - r} Q${x0 + w},${yTop} ${x0 + w},${yTop + r}
            V${yTop + BAR_H - r} Q${x0 + w},${yTop + BAR_H} ${x0 + w - r},${yTop + BAR_H}
            H${x0} Z`;
  };

  return (
    <div className="card p-4">
      <h3 className="text-sm font-semibold text-ink2">{title}</h3>
      <svg viewBox={`0 0 ${W} ${H}`} className="mt-2 w-full" role="img" aria-label={title}>
        {/* taban cizgisi */}
        <line x1={LABEL_W} x2={LABEL_W} y1={0} y2={H} stroke="var(--baseline)" strokeWidth={1} />
        {items.map((item, i) => {
          const yTop = i * ROW_H + (ROW_H - BAR_H) / 2;
          const w = Math.max(2, (item.avg_score / 10) * trackW);
          return (
            <g
              key={item.criterion_name}
              opacity={hover === null || hover === i ? 1 : 0.55}
              onPointerEnter={() => setHover(i)}
              onPointerLeave={() => setHover(null)}
            >
              {/* buyuk hit alani */}
              <rect x={0} y={i * ROW_H} width={W} height={ROW_H} fill="transparent" />
              <text
                x={LABEL_W - 8} y={yTop + BAR_H / 2 + 3.5} textAnchor="end"
                fontSize={11.5} fill="var(--ink-2)"
              >
                {item.criterion_name.length > 26
                  ? item.criterion_name.slice(0, 25) + "…"
                  : item.criterion_name}
              </text>
              <path d={barPath(yTop, w)} fill="var(--series-1)" />
              <text
                x={LABEL_W + w + 6} y={yTop + BAR_H / 2 + 3.5}
                fontSize={11.5} fontWeight={600} fill="var(--ink)"
                style={{ fontVariantNumeric: "tabular-nums" }}
              >
                {item.avg_score.toFixed(1)}
              </text>
              <title>{`${item.criterion_name}: ${item.avg_score.toFixed(2)} / 10 (${item.count} değerlendirme)`}</title>
            </g>
          );
        })}
      </svg>
      <p className="mt-1 text-xs text-muted">{t("cb.scaleNote")}</p>
    </div>
  );
}
