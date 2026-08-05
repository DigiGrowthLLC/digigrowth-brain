/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  // badge-* variants are assembled dynamically (`badge ${agent.badge_class}`
  // from agents_registry.json in AgentsPanel.jsx), so Tailwind's content
  // scanner never sees the literal class strings and purges them from the
  // production build unless explicitly safelisted here.
  safelist: [{ pattern: /^badge-/ }],
  theme: {},
  plugins: [],
};
