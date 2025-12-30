# VIDPS — Subscription Model & Value Definition

**Version**: 0.1.0
**Last Updated**: 2025-12-29

---

## Purpose

This document defines **what a customer is paying for** when they subscribe to VIDPS.

The goal is to ensure:
- Predictable costs
- High margins
- Clear value exchange
- Simple commercial packaging

This is not usage-based billing for compute.
It is subscription access to a **decision-support asset**.

---

## Core Principle

Customers are **not** paying for:
- API calls
- Data volume
- AI models

They **are** paying for:
- Consistent prioritisation decisions
- Explainable rankings
- Institutional memory
- Reduced internal friction

---

## Subscription Unit of Value

The subscription is defined around **decision scope**, not raw usage.

### Core Dimensions

| Dimension | Description | Cost Driver |
|-----------|-------------|-------------|
| **Brands** | Each brand has its own relevance profile and scoring configuration | Configuration complexity |
| **Markets / Cities** | Each city represents a distinct decision environment | API costs per refresh |
| **Refresh Frequency** | How often venue intelligence is updated | Direct variable cost |

---

## Subscription Tiers

### Tier 1 — Individual / Pilot

| Feature | Included |
|---------|----------|
| Brands | 1–2 |
| Cities | Up to 3 |
| Refresh | Quarterly |
| Output | CSV / Excel export |
| Support | Email |

**Target Price**: £100–300 / month

**Use Case**: Single-market pilot, individual contributor, proof of value

---

### Tier 2 — Regional Team

| Feature | Included |
|---------|----------|
| Brands | 3–5 |
| Cities | Up to 10 |
| Refresh | Monthly |
| Output | Web UI + exports |
| Features | Basic audit trail |

**Target Price**: £500–1,500 / month

**Use Case**: Regional commercial team, multi-brand portfolio

---

### Tier 3 — Enterprise

| Feature | Included |
|---------|----------|
| Brands | Unlimited |
| Cities | Custom coverage |
| Refresh | Monthly or on-demand (capped) |
| Output | Full UI + API access |
| Features | Full audit trail, SLA, procurement-friendly terms |

**Target Price**: £3k–10k+ / year per brand (contracted)

**Use Case**: Global beverage company, central commercial operations

---

## Unit Economics

### Why This Model Works

| Factor | Benefit |
|--------|---------|
| Controlled refresh cadence | Predictable API spend |
| Cached city data | High reuse, high margin |
| Brand-based pricing | Maps to customer budget structure |
| No per-query billing | Reduces friction, increases trust |

### Cost Structure (Illustrative)

For Tier 2 customer (5 brands, 10 cities, monthly refresh):

| Cost Item | Monthly Est. |
|-----------|--------------|
| Google Places API | ~£130 (10 cities × £13/city) |
| Compute / hosting | ~£20–50 |
| **Total variable cost** | ~£150–180 |
| **Subscription revenue** | £500–1,500 |
| **Gross margin** | 70–90% |

---

## Explicit Non-Goals

- No per-search billing
- No per-API-call billing
- No "credits" model exposed to users
- No metered AI usage

These increase friction and reduce trust.

---

## Guiding Principle

> **The subscription buys confidence and repeatability — not compute.**
