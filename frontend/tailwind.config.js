/** @type {import('tailwindcss').Config} */

// Bridge a CSS custom property (RGB channels, space-separated) to a Tailwind color
// so `<alpha-value>` opacity modifiers keep working (e.g. `bg-surface/60`).
const token = (name) => `rgb(var(${name}) / <alpha-value>)`;

export default {
  // `.dark` on <html>/<body> flips the token set (DESIGN_SYSTEM §2 dark mode).
  darkMode: "class",
  content: [
    "../templates/**/*.html",
    "../apps/**/templates/**/*.html",
    "../themes/**/*.html",
    // Plugins can emit utility classes from Python (e.g. reading_time's badge).
    "../plugins/**/*.{py,html}",
    "./src/**/*.{js,ts}",
  ],
  theme: {
    extend: {
      colors: {
        // Full semantic token set (DESIGN_SYSTEM §2). All values are CSS variables
        // defined in styles.css (:root light, .dark dark); themes re-scope them.
        bg: token("--bg"),
        surface: token("--surface"),
        "surface-2": token("--surface-2"),
        text: token("--text"),
        "text-muted": token("--text-muted"),
        "text-subtle": token("--text-subtle"),
        primary: token("--primary"),
        "primary-hover": token("--primary-hover"),
        "primary-contrast": token("--primary-contrast"),
        highlight: token("--accent"), // secondary highlight (badges) — DESIGN_SYSTEM accent
        border: token("--border"),
        "border-strong": token("--border-strong"),
        ring: token("--ring"),
        success: token("--success"),
        "success-bg": token("--success-bg"),
        warning: token("--warning"),
        "warning-bg": token("--warning-bg"),
        error: token("--error"),
        "error-bg": token("--error-bg"),

        // Legacy aliases — existing templates use paper/ink/accent utilities. Mapped
        // onto the new tokens (paper→bg, ink→text, accent→primary, since templates use
        // `accent` as the CTA/link emphasis colour, which is `--primary` in the canon)
        // so the palette shifts to the canon without a big-bang template rewrite.
        // Migrate utilities to semantic names in the U3–U6 UI slices, then drop these.
        paper: token("--bg"),
        ink: token("--text"),
        accent: token("--primary"),
      },
      fontFamily: {
        // UI / body — Inter (DESIGN_SYSTEM §3), self-hosted variable font.
        sans: [
          "Inter Variable",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "sans-serif",
        ],
        // Display / headings / prose — Newsreader, the editorial serif signature.
        display: [
          "Newsreader Variable",
          "ui-serif",
          "Georgia",
          "Cambria",
          "Times New Roman",
          "serif",
        ],
        // Metadata, eyebrows, code.
        mono: [
          "Geist Mono Variable",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "monospace",
        ],
      },
      borderRadius: {
        // DESIGN_SYSTEM §4 radius tokens.
        sm: "6px",
        md: "10px",
        lg: "16px",
        xl: "24px",
      },
    },
  },
  plugins: [],
};
