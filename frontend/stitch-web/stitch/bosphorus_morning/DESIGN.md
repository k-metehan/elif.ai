# Design System Document: Civic Serenity

## 1. Overview & Creative North Star
**Creative North Star: "The Bosphorus Horizon"**

This design system rejects the cluttered, high-density aesthetic of traditional civic tools in favor of "The Bosphorus Horizon"—a philosophy rooted in clarity, vastness, and the soft, diffused light of an Istanbul morning. 

To move beyond the "standard" voice assistant template, we utilize **Intentional Asymmetry** and **Tonal Depth**. By leaning into the "Limestone" warmth of the background and the "İznik" vibrancy of the accents, we create a digital environment that feels like a trusted public space rather than a cold government database. The layout should breathe; we prioritize generous negative space (8.5rem margins where possible) to ensure the user’s "civic voice" is the most important element on the screen.

---

## 2. Colors & Surface Philosophy
The palette is a sophisticated interplay between the warmth of weathered stone (`#f7f4ef`) and the deep, authoritative navy of the Marmara Sea (`#1a2a3a`).

### Surface Hierarchy & The "No-Line" Rule
**Explicit Instruction:** Do not use 1px solid borders to define sections. 
Boundaries must be created through background shifts. For example, a `surface-container-low` (`#f6f3ee`) component should sit directly on a `surface` (`#fcf9f4`) background. 

*   **Nesting:** Treat the UI as layers of fine Turkish paper. Use `surface-container-lowest` (`#ffffff`) for interactive cards to make them "pop" against the `surface-container` (`#f0ede9`) page sections.
*   **The Glass & Gradient Rule:** For floating navigation or headers, use a "Frosted İznik" effect: `primary-container` (`#0d7377`) at 85% opacity with a `20px` backdrop-blur. 
*   **Signature Texture:** Main Action Buttons (CTAs) should utilize a subtle linear gradient from `primary` (`#00595c`) to `primary-container` (`#0d7377`) at a 135-degree angle to provide a "jeweled" depth.

---

## 3. Typography: Editorial Authority
We utilize **Plus Jakarta Sans** for its geometric clarity and modern humanist touch. Our hierarchy mimics a high-end editorial journal.

*   **Display (The Statement):** `display-lg` (3.5rem) is reserved for brief, welcoming Turkish greetings (e.g., "Günaydın"). Use `on-secondary-fixed` (`#0c1d2c`) to ensure a deep, soft contrast.
*   **Headline (The Context):** `headline-md` (1.75rem) guides the user through civic processes.
*   **Body (The Conversation):** `body-lg` (1rem) is the workhorse. Increase line-height to `1.6` to evoke a relaxed, readable pace.
*   **Labels (The Utility):** `label-md` (0.75rem) in `secondary` (`#506072`) for metadata, ensuring they never compete with the primary voice interaction.

---

## 4. Elevation & Depth: Tonal Layering
Traditional drop shadows are too "digital." We use **Ambient Shadows** and **Tonal Stacking**.

*   **The Layering Principle:** Instead of a shadow, place a `surface-container-highest` (`#e5e2dd`) element behind a `surface-container-lowest` (`#ffffff`) element to create a natural "lift."
*   **Ambient Shadows:** For the main voice card, use a custom shadow: `0px 24px 48px -12px rgba(26, 42, 58, 0.08)`. The shadow is tinted with our "Deep Navy" to mimic natural light diffraction.
*   **The Ghost Border:** If a boundary is required for accessibility, use `outline-variant` (`#bec9c9`) at **15% opacity**. It should be felt, not seen.
*   **Glassmorphism:** Use `backdrop-filter: blur(12px)` on voice-overlay modals to maintain the "Morning Light" transparency, letting the background limestone color bleed through the active UI.

---

## 5. Components

### The Pill Microphone (Signature Component)
The core of the experience. A pill-shaped button (`rounded-full`) using the `primary` to `primary-container` gradient.
*   **The Glow:** While active, apply a `0px 0px 30px` spread using `primary-fixed-dim` (`#81d4d8`) at 50% opacity. This "İznik Glow" signals the assistant is listening without using intrusive animations.

### Chat Bubbles (The "Asymmetric Soft" Style)
*   **User Bubble:** `surface-container-highest` (`#e5e2dd`). Radius: `24px 24px 6px 24px`.
*   **Assistant Bubble:** `surface-container-lowest` (`#ffffff`). Radius: `24px 24px 24px 6px`. 
*   **Rule:** No dividers between messages. Use `spacing-3` (1rem) for grouped messages and `spacing-6` (2rem) between different speakers.

### Cards & Civic Lists
*   **Container:** Use `surface-container-lowest` with a `2rem` (`lg`) corner radius.
*   **Separation:** Prohibit divider lines. Use `spacing-4` (1.4rem) of vertical white space to separate list items.
*   **Interaction:** On hover, transition the background to `surface-container-low` (`#f6f3ee`)—a whisper of movement.

### Input Fields
*   **Style:** Minimalist. No bottom line or box. Use a `surface-container-low` fill with a `1rem` radius.
*   **Focus State:** The background stays consistent, but the "İznik Turquoise" (`primary`) appears as a `2px` "Ghost Border" at 40% opacity.

---

## 6. Do’s and Don’ts

### Do:
*   **Embrace "Boşluk" (Whitespace):** Let elements float. If in doubt, add more padding from the `spacing-10` or `spacing-12` scales.
*   **Use Soft Transitions:** All hover and active states should have a `300ms cubic-bezier(0.4, 0, 0.2, 1)` transition for a "fluid" feel.
*   **Turkish Typographic Nuance:** Ensure "İ" and "ı" are handled correctly in the Plus Jakarta Sans weight scales.

### Don't:
*   **Don't use pure black:** Never use `#000000`. It breaks the Bosphorus morning light metaphor. Use `on-secondary-fixed` for high-contrast text.
*   **Don't use "Floating Action Buttons" (FABs):** These are too standard. Integrate the microphone pill into a dedicated, grounded bottom-bar using `surface-container-lowest`.
*   **Don't use hard corners:** The minimum radius is `sm` (0.5rem); the standard is `DEFAULT` (1rem). Civic engagement should feel welcoming, not sharp.