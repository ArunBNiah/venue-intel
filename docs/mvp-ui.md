# VIDPS — Minimal Viable Product UI Definition

**Version**: 0.1.0
**Last Updated**: 2025-12-29

---

## Purpose

This document defines the **smallest possible UI** that makes VIDPS feel like a real, paid product — not a data science tool or internal dashboard.

The goal is to:
- Support the core use case
- Build trust
- Avoid premature UX investment

---

## Core User Job

A commercial user wants to:

1. **Select** a market and brand
2. **See** which venues to prioritise
3. **Understand** why
4. **Export** the list and act

Nothing else is required for v1.

---

## Required UI Components (v1)

### 1. Input Panel

**Location**: Left sidebar or top bar

| Control | Type | Purpose |
|---------|------|---------|
| City | Dropdown | Select target market |
| Brand | Dropdown | Select brand/category profile |
| Venue types | Multi-select (optional) | Filter by bar, restaurant, hotel |
| Min. rating | Slider (optional) | Floor for quality |
| Min. reviews | Slider (optional) | Floor for data confidence |
| Max venues | Number input | Limit results (default: 50) |

**Design Principles**:
- Inputs are structured and constrained
- Business-native terminology
- **No free-text prompts**

---

### 2. Results Table (Primary View)

**This table is the product.**

| Column | Description |
|--------|-------------|
| Rank | Position in prioritised list |
| Venue name | Clickable → opens detail drawer |
| Score | Distribution Fit Score (0–100) |
| Confidence | High / Medium / Low with visual indicator |
| Rationale | 1–2 sentence explanation |

**Interactions**:
- Sortable by any column
- Click row → open detail drawer
- Bulk select for export

**Visual Design**:
- Confidence tiers colour-coded (green/amber/red or similar)
- Clean, minimal chrome
- No charts or graphs in table view

---

### 3. Venue Detail Drawer (Secondary)

**Triggered by**: Clicking a venue row

| Section | Content |
|---------|---------|
| Header | Venue name, address, Google Maps link |
| Score breakdown | V, R, M scores with visual bars |
| Key signals | Types, price level, review count, rating |
| Review themes | Theme labels with supporting quotes |
| Data freshness | "Last updated: 15 Dec 2025" |
| Confidence explanation | Why this tier was assigned |

**Purpose**: Supports trust and internal justification ("I can explain why we're targeting this venue").

---

### 4. Export & Share

| Action | Implementation |
|--------|----------------|
| Download CSV | All visible columns + score breakdown |
| Download Excel | Formatted with headers, ready for internal use |
| Copy link | Read-only shareable URL (if authenticated) |

**No collaboration features** required for v1 (comments, assignments, etc.).

---

## Information Architecture

```
┌─────────────────────────────────────────────────────────┐
│  [City ▼]  [Brand ▼]  [Filters...]      [Export ▼]      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Rank  Venue              Score  Confidence  Rationale  │
│  ────  ─────              ─────  ──────────  ─────────  │
│  1     The Connaught Bar   92    ●● High     Premium... │
│  2     Swift Soho          88    ●● High     Strong...  │
│  3     Nightjar            85    ●● High     Speake...  │
│  ...                                                    │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  Showing 50 of 847 venues │ Data as of: 15 Dec 2025     │
└─────────────────────────────────────────────────────────┘

                    ┌─────────────────────┐
                    │  DETAIL DRAWER      │
                    │  ───────────────    │
                    │  The Connaught Bar  │
                    │  London W1          │
                    │                     │
                    │  Score: 92/100      │
                    │  ├─ Volume: 0.85    │
                    │  ├─ Quality: 0.92   │
                    │  └─ Relevance: 0.94 │
                    │                     │
                    │  Themes:            │
                    │  ✓ cocktail_focus   │
                    │  ✓ spirits_depth    │
                    │  ✓ upscale_atmos    │
                    │                     │
                    │  Data: 15 Dec 2025  │
                    │  Confidence: High   │
                    └─────────────────────┘
```

---

## Explicitly Out of Scope (v1)

| Feature | Reason |
|---------|--------|
| Dashboards | No aggregate analytics needed for decision |
| Charts | Visual decoration without decision value |
| Map visualisation | Nice-to-have, not core to job |
| User customisation | Beyond input filters |
| Notifications / alerts | Not a monitoring tool |
| Comments / collaboration | Adds complexity, unclear demand |
| Saved views / presets | Can add if requested |

These can come later **if demand exists**.

---

## Technology Choice

### Why Streamlit Is Acceptable (Initially)

| Benefit | Detail |
|---------|--------|
| Fast to build | Days, not weeks |
| Python-native | No frontend/backend split |
| Easy iteration | Change and redeploy in minutes |
| Good enough | For early customers validating value |

### When to Rebuild

Rebuild in Next.js (or similar) **if and only if**:
- Users engage consistently
- Someone is willing to pay
- UI friction becomes a concrete blocker
- Specific features require it (e.g., offline, mobile)

Until then, Streamlit is fine.

---

## Product Feel Test

VIDPS v1 UI is good enough if:

| Criterion | Test |
|-----------|------|
| Self-service | Client can use it without explanation |
| Trust | They believe the outputs |
| Defensibility | They can justify decisions internally |
| Willingness to pay | They would subscribe for continued access |

---

## Guiding Principle

> **The UI exists to enable decisions — not to impress.**
