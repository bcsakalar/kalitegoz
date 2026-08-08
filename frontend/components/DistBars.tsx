"use client";

import { useT } from "@/components/I18nProvider";

/**
 * Adet dagilimi — tek renkli yatay barlar (orn. kategori dagilimi).
 * Deger her barin ucunda dogrudan etiketli; uc 4px yuvarlak, taban kose.
 */
export default function DistBars({
  items,
  title,
}: {
  items: { label: string; value: number }[];
  title: string;
}) {
  const t = useT();
  if (items.length === 0) {
    return (
      <div className="card p-4">
        <h3 className="text-sm font-semibold text-ink2">{title}</h3>
        <p className="py-10 text-center text-sm text-muted">{t("common.noData")}</p>
      </div>
    );
  }
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <div className="card p-4">
      <h3 className="text-sm font-semibold text-ink2">{title}</h3>
      <div className="mt-3 space-y-2.5">
        {items.map((item) => (
          <div key={item.label} className="flex items-center gap-3 text-sm">
            <span className="w-24 shrink-0 text-right text-ink2">{item.label}</span>
            <div className="flex flex-1 items-center gap-2 border-l border-baseline pl-px">
              <div
                className="h-4 rounded-r bg-series"
                style={{ width: `${(item.value / max) * 100}%`, minWidth: 2 }}
              />
              <span className="font-semibold tabular-nums">{item.value}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
