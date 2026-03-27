# Elif Frontend Redesign Spec

## The Core Idea

Elif is a neighborhood companion, not a municipal dashboard. The app should feel like chatting with a friend who happens to know everything about Bahçeşehir — not like checking a government status page.

**One rule:** Infrastructure is invisible when working, loud when broken.

Nobody opens an app to confirm their water is running. Of course it is. The only time you want to know about water/electricity/gas is *before* a disruption or *during* one. Everything else is noise.

---

## Design System

Follow `DESIGN.md` (Civic Serenity / Bosphorus Morning). All fonts, colors, spacing are defined there. Key references:
- Font: Plus Jakarta Sans
- Primary: `#00595c` / `#0d7377`
- Surface: `#f7f4ef` / `#fcf9f4`
- No pure black, no hard corners, no 1px borders
- Ambient shadows, not drop shadows
- Tailwind CSS via CDN

---

## Page Structure (4 pages, down from 6)

### Page 1: `index.html` — The Homepage

This is the heart. Voice assistant + what's happening today.

#### Layout (top to bottom):

**1. Alert Strip (CONDITIONAL — usually hidden)**

A thin banner at the very top, below the nav. Only appears when there's an active or upcoming disruption. Fetch `/api/water`, `/api/electricity`, `/api/gas` — if any have outages, show the strip. If everything is fine, **render nothing**.

```
┌─────────────────────────────────────────────────────────────┐
│ ⚠️ Su kesintisi yarın 09:00-18:00 — Bahçeşehir 2. Kısım   │
└─────────────────────────────────────────────────────────────┘
```

- Background: `error-container` (`#ffdad6`) with `on-error-container` (`#93000a`) text
- Dismissible (X button, stores in sessionStorage)
- If multiple alerts: stack them or cycle
- If zero alerts: the div doesn't exist in the DOM. Not hidden, not collapsed — not rendered.

**How to decide what to show:**
```javascript
// Fetch all utility APIs in parallel
const [water, electricity, gas] = await Promise.allSettled([...]);

// Only show alerts for ACTIVE or UPCOMING outages
// Check: does the data have outages[] with length > 0?
// Check: is any outage's end_time in the future?
// If yes → show alert strip
// If no → don't render anything
```

**2. Greeting + Voice Card (existing, keep as-is)**

The "Günaydın" header, the assistant response card with action chips, the floating mic pill. This already works well. Don't touch `app.js` voice pipeline.

**3. Bento Grid (2 columns on desktop, 1 on mobile)**

Replace the current bento layout. Two cards:

| Left Card: Weather | Right Card: What's Nearby |
|---|---|
| Live weather from `/api/weather` | "3 nöbetçi eczane" → links to `eczaneler.html` |
| Current temp, description, wind | Next event title + date (if events exist) |
| Tomorrow forecast if rain > 50% | "Yakınımdaki yerler" map thumbnail |

The weather card already works. Keep it.

The "What's Nearby" card replaces the old pharmacy-only card. It combines:
- Pharmacy count (from `/api/pharmacies` → `pharmacies.length`)
- Next upcoming event title (from `/api/events` → first event, if any)
- A link to the map/eczaneler page

**4. REMOVE the "Bugünkü Durum" sidebar**

This is exactly the "dashboard" pattern we're killing. The sidebar with "Su kesintisi yok ✅" and "Deprem kaydı yok ✅" is the opposite of what we want. Delete the entire right sidebar (`lg:col-span-4`).

Make the left column full-width (`lg:col-span-12` or just remove the grid).

Replace the sidebar space with either:
- Nothing (let it breathe — "embrace Boşluk" per DESIGN.md)
- Or move the map widget inline, below the bento cards

**5. REMOVE the stock globe map image**

The map widget currently shows a random stock image. Either:
- Replace with a real Google Maps embed of Başakşehir (like eczaneler.html already has)
- Or remove it entirely from the homepage (the map lives on eczaneler.html anyway)

---

### Page 2: `eczaneler.html` — Pharmacies + Map

This page is already good. Real data, real map, real pharmacy cards fetched from `/api/pharmacies`. Minor fixes:

**Fix 1: Show freshness honestly**

The API now returns `_meta.status` and `_meta.age_days`. Use it:

```javascript
const data = await response.json();
const meta = data._meta || {};

if (meta.status === 'stale') {
    // Show a small warning under the header
    periodEl.textContent = `⚠️ Bu veriler ${meta.age_days} gün önce güncellendi — güncel olmayabilir.`;
    periodEl.classList.add('text-orange-600');
} else if (meta.status === 'unavailable') {
    periodEl.textContent = meta.note || 'Eczane verisi yüklenemedi.';
}
```

**Fix 2: Infrastructure alerts here too**

If there's an active water/electricity outage, show it as a small alert card at the top of the pharmacy list — because someone looking for a pharmacy at 2am probably also wants to know about the water cut. Same conditional logic: only show if there's an actual problem.

**No other changes needed.** The pharmacy page is the most functional page and it works.

---

### Page 3: `etkinlikler.html` — Events

Currently shows a loading spinner that resolves to an empty state because events.json has no real events.

**Make the empty state beautiful and honest:**

```html
<!-- When no events -->
<div class="text-center py-16 max-w-lg mx-auto">
    <span class="material-symbols-outlined text-6xl text-primary-fixed-dim mb-6">celebration</span>
    <h2 class="text-2xl font-bold text-on-secondary-fixed mb-3">Etkinlik verisi henüz eklenmedi</h2>
    <p class="text-secondary mb-6">
        Başakşehir'deki etkinlikleri yakında burada görebileceksiniz.
        Şimdilik belediye sitesini kontrol edebilirsiniz.
    </p>
    <a href="https://basaksehir.bel.tr" target="_blank"
       class="inline-flex items-center gap-2 px-6 py-3 bg-surface-container-low text-primary font-medium rounded-full hover:bg-surface-container transition-all">
        <span class="material-symbols-outlined text-base">open_in_new</span>
        basaksehir.bel.tr
    </a>
</div>
```

**When events DO exist** (after manual scrape), the current card layout is fine. Just add the `_meta` freshness label:

```
Etkinlikler · Son güncelleme: 28 Mart 2026
```

Small text under the page header, only shown when `_meta.last_updated` exists.

---

### Page 4: `ayarlar.html` — Settings

Low priority. The neighborhoods are already fixed to Bahçeşehir. This page is a placeholder for future user preferences (notification settings, language, etc). No changes needed for this spec.

---

## What to DELETE

1. **The "Bugünkü Durum" sidebar** from `index.html` — the whole `lg:col-span-4` right column with the daily summary and map widget
2. **The `loadDailySummary()` function** from `index.html` — it fetches water/earthquake status to show "everything is fine" checkmarks. Kill it.
3. **The "Su kesintisi yok ✅" / "Deprem kaydı yok ✅" pattern** — never show "X is working" for infrastructure. Only show "X is broken."

---

## What to ADD

1. **Alert strip component** — a reusable conditional banner for disruptions
2. **Freshness labels** — use `_meta` from API responses to show "Son güncelleme: X" where appropriate
3. **Honest empty states** — every page handles "no data" with a clear message + alternative action (not a spinner, not fake data)

---

## The Alert Strip — Detailed Spec

This is the single most important new component. It replaces all the infrastructure status displays.

### Where it appears
- `index.html` — below nav, above greeting
- `eczaneler.html` — below nav, above pharmacy header (optional, same component)

### Data sources
Fetch these three in parallel on page load:
```javascript
const apis = ['/api/water', '/api/electricity', '/api/gas'];
```

### Logic
```javascript
function getActiveAlerts(waterData, electricityData, gasData) {
    const alerts = [];

    // Water outages
    if (waterData.outages && waterData.outages.length > 0) {
        for (const outage of waterData.outages) {
            // Only show if end_time is in the future
            if (new Date(outage.end_time) > new Date()) {
                alerts.push({
                    type: 'water',
                    icon: 'water_drop',
                    text: `Su kesintisi: ${outage.affected_area}`,
                    detail: `${outage.start_time} — ${outage.end_time}`,
                    emergency: 'İSKİ: 185'
                });
            }
        }
    }

    // Same pattern for electricity (BEDAŞ: 186) and gas (İGDAŞ: 187)
    // ...

    return alerts;
}

// If alerts.length === 0 → don't render anything
// If alerts.length > 0 → inject the alert strip into the DOM
```

### Visual
```html
<!-- Only rendered when alerts exist -->
<div id="alert-strip" class="bg-error-container border-b border-error/10 px-6 py-3">
    <div class="max-w-[1200px] mx-auto flex items-center justify-between">
        <div class="flex items-center gap-3">
            <span class="material-symbols-outlined text-on-error-container">warning</span>
            <div>
                <p class="text-on-error-container text-sm font-medium">{alert.text}</p>
                <p class="text-on-error-container/70 text-xs">{alert.detail} · {alert.emergency}</p>
            </div>
        </div>
        <button onclick="this.parentElement.parentElement.remove(); sessionStorage.setItem('dismissed-alert', Date.now())"
                class="text-on-error-container/50 hover:text-on-error-container">
            <span class="material-symbols-outlined text-sm">close</span>
        </button>
    </div>
</div>
```

---

## API Reference (for frontend)

All endpoints return `_meta` with freshness info.

| Endpoint | Returns | `_meta.status` |
|----------|---------|----------------|
| `/api/weather` | Live weather | `"live"` always |
| `/api/earthquakes` | Live earthquakes | `"live"` always |
| `/api/pharmacies` | Pharmacy list | `"fresh"` / `"stale"` / `"unavailable"` |
| `/api/events` | Events list | `"fresh"` / `"stale"` / `"unavailable"` |
| `/api/water` | Water outages | `"fresh"` / `"stale"` / `"unavailable"` |
| `/api/electricity` | Electricity outages | `"fresh"` / `"stale"` / `"unavailable"` |
| `/api/gas` | Gas outages | `"fresh"` / `"stale"` / `"unavailable"` |

When `_meta.status === "unavailable"`, the `_meta.note` field contains the Turkish fallback message with the relevant emergency number.

When `_meta.status === "stale"`, `_meta.age_days` tells you how old the data is.

---

## IMPORTANT: Don't Break These

- `app.js` — voice pipeline (mic → record → /api/voice → play). Don't touch.
- `shared.js` — nav highlighting, branding fetch. Don't touch.
- The floating mic pill at the bottom — this is the core interaction.
- The recording state (`state-recording`) and loading state (`state-loading`).
- The responsive layout — all pages work on both desktop and mobile.
- Material Symbols icons (used everywhere via `<span class="material-symbols-outlined">`).

---

## Execution Order

1. `index.html` — Remove daily summary sidebar, add alert strip, simplify to full-width
2. `etkinlikler.html` — Fix empty state to be honest and beautiful
3. `eczaneler.html` — Add `_meta` freshness label, optional alert strip
4. Test all pages — verify no broken elements, voice still works
5. Push

---

## The Philosophy (for reference)

> "The only time infrastructure matters is when it's NOT working. Then you want to know — a day before, two days before. But you don't want to know that it IS working. Of course it is."

The app should be fun. Weather, events, nearby places — that's the interesting stuff. Infrastructure alerts are a conditional interruption, not a permanent fixture.
