import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#050507",
        panel: "#0d1016",
        ember: "#ff2d55",
        flare: "#ffc247",
        haze: "#141b27",
        calm: "#6dc7ff"
      },
      fontFamily: {
        display: ["'Bricolage Grotesque'", "sans-serif"],
        body: ["'IBM Plex Sans'", "sans-serif"],
        mono: ["'Fira Code'", "monospace"]
      },
      boxShadow: {
        glow: "0 0 30px rgba(255,45,85,0.25)",
        card: "0 16px 40px rgba(0,0,0,0.35)"
      },
      backgroundImage: {
        grain: "radial-gradient(circle at 1px 1px, rgba(255,255,255,0.08) 1px, transparent 0)",
        mesh: "radial-gradient(circle at 20% 20%, rgba(255,45,85,0.22), transparent 45%), radial-gradient(circle at 80% 30%, rgba(109,199,255,0.2), transparent 45%), radial-gradient(circle at 60% 80%, rgba(255,194,71,0.16), transparent 45%)"
      }
    }
  },
  plugins: []
};

export default config;
