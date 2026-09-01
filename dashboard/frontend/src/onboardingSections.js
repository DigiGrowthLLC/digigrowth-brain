// Shared source of truth for the client-portal onboarding questionnaire —
// used by pages/ClientPortal.jsx (the form itself) and panels/ClientsPanel.jsx
// (the admin read-only view of submitted answers) so the two never drift.
export const SECTIONS = [
  {
    key: "practice_snapshot",
    title: "Practice Snapshot",
    questions: [
      { key: "name_website", label: "Practice name & website" },
      { key: "service_area", label: "City/metro you serve, and do you treat multiple locations?" },
      { key: "top_conditions", label: "Top 3–5 conditions or complaints you treat most" },
      { key: "insurance", label: "Do you accept insurance, cash-pay, or both? If insurance, which panels?" },
    ],
  },
  {
    key: "ideal_patient",
    title: "Ideal Patient",
    questions: [
      { key: "best_patient", label: "Describe your best patient — age range, what brought them in, why they stuck with the full plan of care" },
      { key: "drop_off_reason", label: "What's the #1 reason a good-fit patient doesn't book after inquiring?" },
    ],
  },
  {
    key: "offer_economics",
    title: "Offer & Economics",
    questions: [
      { key: "avg_visits", label: "Average number of visits per plan of care" },
      { key: "avg_revenue", label: "Average revenue per patient over a full plan of care, roughly" },
      { key: "specials", label: "Do you currently run any specials, free screens, or intro offers?" },
    ],
  },
  {
    key: "differentiation_voice",
    title: "Differentiation & Voice",
    questions: [
      { key: "why_you", label: "Why do patients choose you over the PT practice or chiro down the street?" },
      { key: "avoid", label: "Any phrases, claims, or tone you want us to avoid (regulatory, brand, or personal preference)?" },
      { key: "reviews", label: "Link to your best Google/FB reviews, or a couple of patient quotes we can use" },
    ],
  },
  {
    key: "current_marketing",
    title: "Current Marketing & Assets",
    questions: [
      { key: "past_marketing", label: "What marketing have you tried before, and what worked or flopped?" },
      { key: "assets", label: "Do you have existing photo/video of the clinic, staff, or patient sessions we can use?" },
      { key: "inquiry_volume", label: "Roughly how many new patient inquiries are you getting a month right now, from any source?" },
    ],
  },
  {
    key: "ops",
    title: "Ops",
    questions: [
      { key: "booking_software", label: "What do you currently book appointments with (software/system)?" },
      { key: "handoff", label: "Who on staff should the AI booking agent hand off to for anything it can't answer?" },
      { key: "no_show_rate", label: "Rough no-show rate today, if you know it" },
    ],
  },
];
