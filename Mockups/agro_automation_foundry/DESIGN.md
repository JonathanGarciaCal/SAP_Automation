# Design System Specification: Industrial Sophistication

## 1. Overview & Creative North Star: "The Digital Foreman"

This design system moves beyond the "utilitarian spreadsheet" aesthetic common in SAP environments. Our Creative North Star is **"The Digital Foreman"**—an interface that feels as robust as heavy machinery but as refined as a luxury editorial layout. 

We achieve this by breaking the rigid, boxed-in grid of traditional enterprise software. Instead of borders and lines, we use **Intentional Asymmetry** and **Tonal Depth**. The layout should feel like a series of precisely engineered layers. We utilize generous white space (inspired by high-end architectural journals) to ensure that even the most complex automation data feels breathable, authoritative, and premium.

---

## 2. Colors & Surface Philosophy

The palette honors a legacy of reliability while introducing a "Consumerized Enterprise" polish through sophisticated neutral layering.

### The Palette
*   **Primary (The Heritage):** `primary` (#1b6213) and `primary_container` (#367c2b). Use these for high-intent actions and brand anchors.
*   **Tertiary (The Alert):** `tertiary` (#6d5e00) and `tertiary_container` (#c4aa00). This John Deere Yellow derivative is used sparingly for highlights, status warnings, and critical path accents.
*   **Neutrals (The Anthracite):** `secondary` (#5f5e5e) and `on_surface` (#1b1c1c). These provide the structural "weight" of the system.

### The "No-Line" Rule
**Explicit Instruction:** Designers are prohibited from using 1px solid borders to section off content. Boundaries must be defined solely through background color shifts or elevation. 
*   *Example:* A `surface_container_low` sidebar sitting against a `surface` background provides all the definition needed without the "visual noise" of a stroke.

### Surface Hierarchy & Nesting
Treat the UI as a physical stack of materials. 
1.  **Base:** `surface` (#fbf9f8) - The "ground."
2.  **Sectioning:** `surface_container_low` (#f5f3f2) - For large layout blocks.
3.  **Floating Elements:** `surface_container_lowest` (#ffffff) - For cards and interactive modules to create a "lifted" feel.

### The "Glass & Gradient" Rule
To add soul to the industrial aesthetic, use subtle linear gradients (e.g., `primary` to `primary_container`) on large buttons or hero headers. For floating navigation or over-content modals, utilize **Glassmorphism**: use `surface` with 80% opacity and a `20px` backdrop-blur to keep the user grounded in their previous context.

---

## 3. Typography: Editorial Authority

We use **Plus Jakarta Sans** to bridge the gap between industrial sturdiness and modern tech.

*   **Display (lg/md/sm):** Used for high-level dashboard summaries. Use `display-md` (2.75rem) for primary KPIs to give them a "hero" feel.
*   **Headline (lg/md/sm):** These are your section anchors. Use `headline-sm` (1.5rem) with a tight letter-spacing (-0.02em) to mimic the bold branding of heavy equipment.
*   **Title (lg/md/sm):** Reserved for card headers and modal titles. `title-md` (1.125rem) is the workhorse for SAP object titles.
*   **Body (lg/md/sm):** Optimized for readability. Use `body-md` (0.875rem) for all data-dense tables to maximize information density without sacrificing legibility.
*   **Label (md/sm):** Used for micro-copy and metadata. Always in `on_surface_variant` (#41493c) to ensure hierarchy.

---

## 4. Elevation & Depth: Tonal Layering

We reject the "flat" trend in favor of a "Tactile Industrial" feel.

*   **The Layering Principle:** Depth is achieved by stacking. A `surface_container_highest` card placed on a `surface_container` background creates a natural, soft lift.
*   **Ambient Shadows:** For elements that truly float (Modals, Popovers), use extra-diffused shadows. 
    *   *Spec:* `0px 12px 32px rgba(27, 28, 28, 0.06)`. The shadow color is a tinted version of `on_surface` to look like natural light, never pure black.
*   **The "Ghost Border" Fallback:** If a border is required for accessibility (e.g., Input fields), use `outline_variant` at **20% opacity**. 100% opaque high-contrast borders are forbidden.

---

## 5. Components

### Buttons
*   **Primary:** `primary_container` background, `on_primary` text. 8px rounded corners. Use a subtle inner-glow (top-down) for a "machined" feel.
*   **Secondary:** `surface_container_highest` background. No border.
*   **Tertiary:** Text-only, using `primary` color. High-density, high-action areas only.

### Cards & Data Lists
*   **Forbid Divider Lines:** Separate list items using the Spacing Scale (e.g., `spacing-3` / 1rem) or subtle background alternates (`surface_container_low` vs `surface_container`).
*   **Corner Radius:** Consistently use `DEFAULT` (0.5rem/8px) for all container corners to maintain the "Robust" brand pillar.

### Form Inputs
*   **Style:** `surface_container_lowest` fill with a `Ghost Border`. 
*   **States:** On focus, the border transitions to `primary` (#1b6213) at 100% opacity with a 2px "soft glow" (spread).

### Custom Enterprise Components
*   **Process Trackers:** Use thick, 8px lines with `primary_fixed` for completed steps and `secondary_fixed` for upcoming, mirroring the heavy-duty piping found in industrial schematics.
*   **Status Badges:** Avoid "Traffic Light" defaults. Use `surface_tint` backgrounds with high-contrast `on_surface` text for a more sophisticated, "Consumerized" alert system.

---

## 6. Do’s and Don’ts

### Do:
*   **Do** use the `16` (5.5rem) spacing token for margins between major sections to emphasize the "High-End" feel.
*   **Do** use `tertiary` (Yellow) as a "surgical strike" color—only for things that need immediate attention or represent a "Gold Standard" status.
*   **Do** lean into asymmetry. Align a headline to the far left while keeping the primary action centered to create a sophisticated, editorial rhythm.

### Don’t:
*   **Don’t** use pure black (#000000). Use the Anthracite `on_surface` (#1b1c1c) for all "black" needs to maintain tonal warmth.
*   **Don’t** use 1px dividers to separate table rows. Use `0.7rem` (spacing-2) of vertical padding and a background hover state instead.
*   **Don’t** crowd the interface. If an SAP screen feels "busy," increase the surface nesting and add more `spacing-6` (2rem) gaps. Space is a sign of luxury and control.