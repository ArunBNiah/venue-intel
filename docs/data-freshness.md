# VIDPS — Data Freshness & Refresh Strategy

**Version**: 0.1.0
**Last Updated**: 2025-12-29

---

## Purpose

This document defines how "fresh" VIDPS data needs to be — and just as importantly, how fresh it does **not** need to be.

The goal is to:
- Align with real-world decision cycles
- Control costs
- Avoid unnecessary reprocessing
- Maintain trust through transparency

---

## Core Insight

Venue characteristics change slowly.
Distribution decisions do not require real-time data.

**VIDPS is not a monitoring system.**
**It is a planning and prioritisation tool.**

---

## Freshness Model

### Default Cadence

| Tier | Refresh Frequency | Rationale |
|------|-------------------|-----------|
| Standard | Quarterly | Sufficient for annual planning cycles |
| Active | Monthly | For markets with active distribution efforts |
| On-demand | Manual trigger (capped) | For pre-meeting preparation or market entry |

### What "Refresh" Means

A refresh re-executes:
1. Stage 1: Discovery (new venues may appear)
2. Stage 2: Scoring (ratings/review counts may change)
3. Stage 3: Enrichment (for top N only)

Partial refresh (Stage 2 + 3 only) may be offered as a lighter option.

---

## Refresh Triggers

### Supported

| Trigger | Description |
|---------|-------------|
| Scheduled | Monthly or quarterly per subscription tier |
| Brand profile change | New relevance rubric requires re-scoring |
| Market expansion | New city added to subscription |
| Manual "Refresh Now" | User-initiated, capped per plan |

### Explicitly Not Supported

| Trigger | Reason |
|---------|--------|
| Real-time updates | Cost prohibitive, no decision value |
| Continuous monitoring | Out of scope for v1 |
| Event-driven (e.g., new review) | Complexity without proportional value |

---

## Confidence & Freshness Linkage

Confidence tiers now incorporate **two dimensions**:

| Dimension | High | Medium | Low |
|-----------|------|--------|-----|
| Data volume | ≥100 reviews | 30–99 reviews | <30 reviews |
| Data freshness | <30 days | 30–90 days | >90 days |

### Combined Confidence Logic

```
If data_volume = LOW → Confidence = LOW (regardless of freshness)
Else if data_freshness > 90 days → Confidence = max(MEDIUM, volume_tier)
Else → Confidence = volume_tier
```

**Example**:
- 500 reviews, refreshed 2 weeks ago → **HIGH**
- 500 reviews, refreshed 4 months ago → **MEDIUM** (freshness caps it)
- 25 reviews, refreshed yesterday → **LOW** (volume floor)

This ensures users don't over-trust stale data.

---

## User-Facing Transparency

Every output must display:

| Element | Example |
|---------|---------|
| Last refreshed | "Data as of: 15 Dec 2025" |
| Coverage note | "Based on 847 venues in London" |
| Confidence explanation | "Medium confidence: data is 45 days old" |

This avoids false precision and builds trust.

---

## Staleness Warnings

| Age | Treatment |
|-----|-----------|
| <30 days | No warning |
| 30–60 days | Subtle indicator ("Refresh available") |
| 60–90 days | Visible warning ("Data may be outdated") |
| >90 days | Prominent warning + confidence downgrade |

---

## Implementation Notes

### Caching Strategy

| Data Type | Cache Duration | Storage |
|-----------|----------------|---------|
| Place IDs (discovery) | 30 days | SQLite/Postgres |
| Venue details (Stage 2) | Per refresh cycle | SQLite/Postgres |
| Reviews (Stage 3) | Per refresh cycle | Ephemeral or short-term |
| Scored output | Until next refresh | Postgres |

### Cost Control

Refresh cadence is the primary cost lever:
- Monthly refresh: ~£13/city × 12 = ~£156/city/year
- Quarterly refresh: ~£13/city × 4 = ~£52/city/year

Subscription tiers are priced to cover worst-case refresh costs with margin.

---

## Commercial Benefit

| Benefit | Mechanism |
|---------|-----------|
| Predictable API spend | Controlled refresh cadence |
| Easier procurement | Clear data governance story |
| Tier differentiation | Refresh frequency as upgrade incentive |
| Margin protection | Cached data reused across sessions |

---

## Guiding Principle

> **Fresh enough to decide — not fresh enough to obsess.**
