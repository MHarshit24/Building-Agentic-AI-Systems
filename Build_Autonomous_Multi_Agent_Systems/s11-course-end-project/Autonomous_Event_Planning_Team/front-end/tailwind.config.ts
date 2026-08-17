import type { Config } from "tailwindcss";
import defaultTheme from "tailwindcss/defaultTheme";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#FAF8F4",
        ink: {
          50: "#F5F5F7",
          100: "#E7E7EC",
          200: "#C7C8D3",
          300: "#9B9DAF",
          400: "#71738A",
          500: "#54566B",
          600: "#3D3F52",
          700: "#2B2C3C",
          800: "#1C1D29",
          900: "#121219",
        },
        brand: {
          50: "#F4F1FF",
          100: "#E9E3FF",
          200: "#D3C6FF",
          300: "#B49CFF",
          400: "#9370FF",
          500: "#7C4DFF",
          600: "#6D28D9",
          700: "#5B1FB8",
          800: "#481991",
          900: "#37146D",
        },
        // Each specialist agent gets a fixed, memorable hue reused
        // consistently across the live agent graph, badges, tags, and the
        // final blueprint's section headers — so "amber = logistics"
        // becomes a learnable visual language rather than arbitrary color.
        logistics: { DEFAULT: "#D97706", 50: "#FFFBEB", 100: "#FEF3C7", 500: "#F59E0B", 600: "#D97706" },
        budget: { DEFAULT: "#059669", 50: "#ECFDF5", 100: "#D1FAE5", 500: "#10B981", 600: "#059669" },
        marketing: { DEFAULT: "#C026D3", 50: "#FDF4FF", 100: "#FAE8FF", 500: "#D946EF", 600: "#C026D3" },
        schedule: { DEFAULT: "#0284C7", 50: "#F0F9FF", 100: "#E0F2FE", 500: "#0EA5E9", 600: "#0284C7" },
        risk: { DEFAULT: "#DC2626", 50: "#FEF2F2", 100: "#FEE2E2", 500: "#EF4444", 600: "#DC2626" },
        manager: { DEFAULT: "#6D28D9", 50: "#F4F1FF", 100: "#E9E3FF", 500: "#7C4DFF", 600: "#6D28D9" },
      },
      fontFamily: {
        sans: ["var(--font-inter)", ...defaultTheme.fontFamily.sans],
        display: ["var(--font-space-grotesk)", ...defaultTheme.fontFamily.sans],
      },
      backgroundImage: {
        "grid-fade":
          "radial-gradient(circle at 1px 1px, rgb(0 0 0 / 0.05) 1px, transparent 0)",
        "brand-radial": "radial-gradient(circle at top right, #E9E3FF 0%, transparent 60%)",
      },
      backgroundSize: {
        grid: "24px 24px",
      },
      keyframes: {
        "pop-in": {
          "0%": { transform: "scale(0.6)", opacity: "0" },
          "100%": { transform: "scale(1)", opacity: "1" },
        },
        "fade-slide-in": {
          "0%": { transform: "translateY(6px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "pulse-ring": {
          "0%": { transform: "scale(0.85)", opacity: "0.6" },
          "80%": { transform: "scale(1.6)", opacity: "0" },
          "100%": { transform: "scale(1.6)", opacity: "0" },
        },
        "flow-dash": {
          "0%": { strokeDashoffset: "24" },
          "100%": { strokeDashoffset: "0" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-4px)" },
        },
        "gradient-x": {
          "0%, 100%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
        },
      },
      animation: {
        "pop-in": "pop-in 300ms ease-out",
        "fade-slide-in": "fade-slide-in 350ms ease-out",
        "fade-in": "fade-in 400ms ease-out",
        "pulse-ring": "pulse-ring 1.8s cubic-bezier(0.2, 0.6, 0.4, 1) infinite",
        "flow-dash": "flow-dash 700ms linear infinite",
        shimmer: "shimmer 2.5s ease-in-out infinite",
        float: "float 3s ease-in-out infinite",
        "gradient-x": "gradient-x 6s ease infinite",
      },
    },
  },
  plugins: [],
};

export default config;
