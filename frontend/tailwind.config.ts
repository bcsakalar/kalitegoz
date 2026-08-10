import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    // KESKIN KOSE — tek kaynak.
    //
    // `extend` degil, dogrudan `borderRadius` EZILIYOR: boylece Tailwind'in
    // varsayilan olcegi (sm/md/lg/xl/full…) tamamen ortadan kalkar ve her
    // `rounded-*` yardimci sinifi `var(--radius)`e, yani 0'a cozulur.
    //
    // Neden sadece markup'tan silmek yetmiyor: markup temizlenebilir ama
    // yarin yazilacak bir bilesende `rounded-lg` yeniden belirir ve kimse
    // fark etmez. Olcegi tokena baglamak, kurali KODUN ICINE koyar.
    borderRadius: {
      none: "var(--radius)",
      sm: "var(--radius)",
      DEFAULT: "var(--radius)",
      md: "var(--radius)",
      lg: "var(--radius)",
      xl: "var(--radius)",
      "2xl": "var(--radius)",
      "3xl": "var(--radius)",
      full: "var(--radius)",
    },
    extend: {
      colors: {
        page: "var(--page)",
        surface: "var(--surface)",
        // `bg-surface2` markup'ta 10 yerde kullaniliyordu ama TANIMLI DEGILDI:
        // Tailwind bilinmeyen sinifi sessizce atlar, native <select> tarayici
        // varsayilanina duser ve KOYU TEMADA BEYAZ KUTU olarak gorunurdu.
        surface2: "var(--surface-2)",
        ink: "var(--ink)",
        ink2: "var(--ink-2)",
        muted: "var(--muted)",
        grid: "var(--grid)",
        baseline: "var(--baseline)",
        series: "var(--series-1)",
        hairline: "var(--border)",
        // `text-danger` de ayni sekilde tanimsizdi — hata metni renksiz kaliyordu.
        danger: "var(--status-critical)",
        warning: "var(--status-warning)",
        good: "var(--status-good)",
        "hairline-strong": "var(--border-strong)",
      },
    },
  },
  plugins: [],
};

export default config;
