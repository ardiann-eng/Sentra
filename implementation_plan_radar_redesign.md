# Redesign Radar Pasar Sentra

This plan outlines the complete redesign of the **Radar Pasar Sentra** section to create a modern, premium, and highly readable dashboard experience tailored for UMKM owners. The design prioritizes visual hierarchy and instantly highlights the "hottest" sectors using a unified dark theme with vibrant, sector-specific accents.

## Proposed Strategy & Layout

### 1. Typography & Colors
*   **Background:** True deep dark (`#0F0F0F`) with subtle grid patterns.
*   **Primary Accent:** Gold/Yellow (`#FACC15`) for unifying highlights.
*   **Sector Accents:**
    *   **Fashion (FSH):** Vibrant Pink (`#EC4899`)
    *   **Beauty (BTY):** Deep Purple (`#A855F7`)
    *   **Food & Beverage (FNB):** Warm Orange (`#F97316`)
    *   **Gadget (GDT):** Electric Blue (`#3B82F6`)
    *   **Home & Living (HME):** Teal/Cyan (`#14B8A6`)
    *   **Hobby (HBY):** Rose/Red (`#EF4444`)
    *   **Seasonal (SSN):** Classic Gold (`#EAB308`)

### 2. Grid Structure (Responsive)
*   **Desktop (`xl`):** 7 columns (`grid-cols-7`). All cards displayed side-by-side.
*   **Tablet (`md`, `lg`):** 3-4 columns (`grid-cols-3` or `grid-cols-4`).
*   **Mobile:** 2 columns (`grid-cols-2`), with the option for horizontal scrolling if vertical real estate is tight.

### 3. Sector Card Anatomy
*   **Header:**
    *   Left: Sector Code Badge (e.g., `FSH`) with the sector's specific accent color (text + low opacity background).
    *   Right: Flame Icon / Blinking Dot for the "Hottest" sector.
*   **Body:**
    *   Sector Name (e.g., "Fashion & Apparel").
    *   YoY Growth: Huge typography (`text-4xl` or `text-5xl`), colored Green (Positive +) or Red (Negative -).
*   **Visualizer:**
    *   Large, smooth Chart.js sparkline filled with a semi-transparent gradient of the sector's accent color.
*   **Footer:**
    *   Competition Status Badge: Merah (Tinggi), Kuning (Sedang), Hijau (Rendah).
    *   Optional mini-text for news teaser.

### 4. Interactive & Animation Details
*   **GSAP Viewport Trigger:** When user scrolls to the section, cards stagger in from the bottom with an opacity fade. Numbers will count up.
*   **Hover state:** Card gently lifts up (`-translate-y-2`), adds a deeper drop shadow utilizing the sector accent hue, and the sparkline tooltip activates.

## Proposed Changes

### [HTML Structure]

#### [MODIFY] [index.html](file:///d:/Vibe%20Coding/SENTRA/index.html)
*   Completely replace the existing `<section class="radar-section" id="sector-dashboard">`.
*   Implement the new responsive grid.
*   Update to the new card structure.

### [CSS Styles]

#### [MODIFY] [index.html](file:///d:/Vibe%20Coding/SENTRA/index.html) (or connected css)
*   Inject the custom Tailwind/CSS rules for the `.radar-card-premium` wrappers.
*   Add custom glow/shadows based on the predefined accent color variables.

### [JavaScript Logic]

#### [MODIFY] [static/app.js](file:///d:/Vibe%20Coding/SENTRA/static/app.js)
*   Write a dynamic rendering function that takes dummy/live data to build the 7 cards.
*   Integrate `Chart.js` for each sparkline, tuning the `tension` to 0.4 for smooth, curvy lines, hiding axes, and using sector-specific colors.
*   Implement GSAP `ScrollTrigger` to handle the staggered intro animation and number counting.

## Open Questions

> [!WARNING]
> 1.  Did you want to use static/dummy data for the YoY growth and sparkline charts initially, or should we hook this directly into the existing `sentra_engine` output if available?
> 2.  Do we want to maintain the "Click to select" functionality on these cards that updates a different section, or is this radar section purely a dashboard display?
> 3.  Are there specific styling classes (like a Tailwind config file or `styles.css`) that we should put the custom CSS in, or should it remain inline `<style>` within `index.html`?

## Verification Plan

### Automated Tests
*   Syntax checking HTML and JS.

### Manual Verification
*   Check responsiveness across Mobile, Tablet, and Desktop resolutions.
*   Verify GSAP animations trigger correctly on scroll.
*   Confirm the custom colors perfectly match the unified dark dashboard look.
