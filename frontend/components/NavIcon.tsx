/**
 * Gezinme ikonları — inline SVG.
 *
 * Önceki sidebar emoji kullanıyordu (📋 🔍 📊 …). `ui-ux-pro-max` bunu açık bir
 * anti-patern olarak listeliyor ("Emoji as icons"): emoji platformdan platforma
 * farklı çizilir, renk token'ına uymaz, boyutu kontrol edilemez ve ekran
 * okuyucuda "clipboard" gibi anlamsız bir ad okunur.
 *
 * Bu ikonlar dekoratiftir — yanlarında her zaman metin etiketi vardır. Bu
 * yüzden `aria-hidden` ve `focusable="false"`.
 */

type IconName =
  | "cockpit" | "analytics" | "calls" | "queue" | "calibration" | "search"
  | "agents" | "leaderboard" | "coaching" | "rubric" | "knowledge"
  | "banned" | "users" | "security" | "roi" | "audit" | "assist";

const PATHS: Record<IconName, string> = {
  // İzleme
  cockpit: "M3 13h4v7H3zM10 4h4v16h-4zM17 9h4v11h-4z",
  analytics: "M3 17l5-6 4 4 6-8 3 3M3 21h18",
  // Çalışma
  calls: "M4 5h16M4 10h16M4 15h10M4 20h7",
  queue: "M4 6h16M4 12h16M4 18h9M17 16l2 2 4-4",
  calibration: "M12 3v18M5 8l7-4 7 4M4 8l-2 6a3 3 0 006 0L6 8M18 8l-2 6a3 3 0 006 0l-2-6",
  search: "M11 4a7 7 0 107 7 7 7 0 00-7-7zM20 20l-4-4",
  // Ekip
  agents: "M8 11a3 3 0 100-6 3 3 0 000 6zM2 20a6 6 0 0112 0M17 11a3 3 0 100-6M16 20h6a5 5 0 00-4-4.9",
  leaderboard: "M8 21h8M12 17v4M6 4h12v4a6 6 0 01-12 0zM6 6H3v2a3 3 0 003 3M18 6h3v2a3 3 0 01-3 3",
  coaching: "M12 3l9 5-9 5-9-5zM6 11v5c0 1.7 2.7 3 6 3s6-1.3 6-3v-5",
  assist: "M4 12a8 8 0 0116 0v5a3 3 0 01-3 3h-1M4 12v4a2 2 0 002 2h1v-6H6a2 2 0 00-2 2zM20 12v4a2 2 0 01-2 2h-1v-6h1a2 2 0 012 2z",
  // Kurulum
  rubric: "M4 4h16v16H4zM8 8h8M8 12h8M8 16h5",
  knowledge: "M4 5a2 2 0 012-2h13v18H6a2 2 0 01-2-2zM8 7h8M8 11h8",
  banned: "M12 3a9 9 0 109 9 9 9 0 00-9-9zM6 6l12 12",
  // Sistem
  users: "M9 11a3 3 0 100-6 3 3 0 000 6zM3 20a6 6 0 0112 0M17 8h5M19.5 5.5v5",
  security: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6zM9 12l2 2 4-4",
  roi: "M12 3v18M8 7h6a2.5 2.5 0 010 5h-4a2.5 2.5 0 000 5h6",
  audit: "M6 3h9l4 4v14H6zM15 3v4h4M9 13h6M9 17h4",
};

export default function NavIcon({ name, className = "" }: { name: IconName; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={`h-[18px] w-[18px] shrink-0 ${className}`}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}

export type { IconName };
