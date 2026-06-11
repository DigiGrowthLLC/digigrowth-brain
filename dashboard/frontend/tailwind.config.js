/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        dg: {
          void:    "#080c14",
          abyss:   "#0d1626",
          depth:   "#111e36",
          navy:    "#1a2f52",
          cobalt:  "#1f3d70",
          royal:   "#2857a0",
          pulse:   "#3a7bd5",
          border:  "#1a2540",
          text1:   "#f0f4ff",
          text2:   "#c4d0e8",
          text3:   "#8a9dc0",
          text4:   "#5a6f8f",
          text5:   "#3a4f6f",
          success: "#14c882",
          warn:    "#f0a028",
          danger:  "#dc3c3c",
        },
      },
      fontFamily: {
        sans: ["Space Grotesk", "system-ui", "sans-serif"],
        mono: ["Share Tech Mono", "monospace"],
      },
    },
  },
  plugins: [],
};
