# EarnIt — Phase 1: Core Loop (MVP)

> Full feature detail lives in `earnit-spec_base.md`. This file tracks just
> what's in scope for Phase 1, and progress against it.

**Goal:** the basic engine works end-to-end for one family — a parent can
set up chores, log a kid's day, and watch XP turn into real money.

**Legend:** `[ ]` not started · `[~]` in progress · `[x]` done

---

## Accounts
- [x] Parent account (mode toggle in sidebar, no real login yet — passkeys come in Phase 3)
- [x] Kid profile(s), selectable from a dropdown (real PIN auth comes in Phase 3)
- [x] Delete a kid profile (added after a real duplicate-profile mistake — requires a confirm checkbox first)

## Chores
- [x] Create a chore with a name + XP value (difficulty-based, parent sets it)
- [x] Assign a chore to a specific kid (shared/"all kids" chores deferred — see decisions below)
- [x] Mark a chore as done → grants XP (once per chore per day). **Updated in Phase 4:** a kid marking a chore done now creates a pending request; XP is only granted once a parent approves it in Kid Rewarding — matches how credit conversions and Store redemptions already require parent approval.

## Daily Reports
- [x] Parent rates the kid's day 1–5 stars → grants that many XP
- [x] Backdate a missed report (file it late, applies to the correct day)
- [x] *(5pm reminder notification pushed to Phase 2 — this phase uses a manual "file report" button)*

## Progression Engine
- [x] XP accumulates from chores + reports
- [x] 100 XP = 1 Level (flat threshold, rolls over, nothing lost)
- [x] Leveling up grants +1 Credit
- [x] Kid requests Credit → Buck conversion (1:1, whole numbers only)
- [x] Parent approves/denies the conversion request
- [x] Once approved, app stops tracking it (no in-app wallet for Bucks)

## Screens (minimum viable versions)
- [x] Kid: Rewards/Progress screen (XP total, progress bar, level, credit balance)
- [x] Parent: Kids Accounts (add kid, add/view chores, file reports)
- [x] Parent: Kid Rewarding (approve/deny conversion requests)

---

## Explicitly Deferred (not in this phase)
Achievements, milestones, badge wall, XP claim/expiry mechanic, Store
(both sides), Fam/multi-parent, notifications, avatar upload.

---

## Open Decisions — Resolved for This Phase
- [x] Tech stack — **Streamlit** (Python, browser-based, no HTML/CSS needed)
- [x] Data sync — **local-only**, single JSON file (`earnit/data/earnit_data.json`)
- [x] Minimum credit amount before conversion — **none**, any amount ≥ 1
- [x] Lifetime XP vs. spendable XP — **same field for now**; will split when Store spending arrives in Phase 2
- [x] Shared chores — **individually assigned only** for now; each chore belongs to one kid

## How to Run It
```
cd EarnIt-app
.venv\Scripts\python.exe -m streamlit run earnit\app.py
```
Opens at http://localhost:8501. Pick "Parent" or "Kid" in the sidebar — there's no real login yet, just a mode switch.
