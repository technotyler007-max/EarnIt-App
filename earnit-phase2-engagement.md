# EarnIt — Phase 2: Engagement Features

> Full feature detail lives in `earnit-spec_base.md`. This file tracks just
> what's in scope for Phase 2, and progress against it.
>
> **Depends on Phase 1** (`earnit-phase1-mvp.md`) being done — the XP/level
> engine needs to exist before any of this makes sense.

**Goal:** the app becomes fun to keep using, not just functional.

**Legend:** `[ ]` not started · `[~]` in progress · `[x]` done

---

## Achievements (repeatable)
- [x] "Good Rating" — 4–5 star average for a week → +5 XP
- [x] "All Chores Finished" — full week completed → +5 XP

## Milestones (repeatable, tied to 5-star streaks)
- [x] 7-day 5-star streak → +15 XP
- [x] 1-month 5-star streak → +50 XP
- [x] 1-year 5-star streak → instant +1 Level

## Badge Wall
- [x] Gallery screen showing earned achievements + milestones

## XP Claim Mechanic
- [x] XP granted but sits "unclaimed" until kid taps to claim it
- [x] Unclaimed XP expires after 7 days
- [x] Split kid XP into `xp` (lifetime, drives Level) and `spendable_xp` (Store balance) — resolves the Phase 1 `[TBD]` about lifetime vs. spendable XP

## Store
- [x] Kid-side: browse rewards, see XP cost, redeem
- [x] Store redemption requires parent approval (via Kid Rewarding)
- [x] Parent-side: add/edit/remove reward items + XP cost

## Kid Rewarding Enhancements
- [x] Live activity feed (chore done, report filed, badge earned, requests)

## Notifications
- [x] 5pm daily report reminder — implemented as an **in-app banner** on
      Kids Accounts (not a real push notification — a locally-run Streamlit
      script has no way to notify you when the app isn't open; that needs
      a real backend/server, which is out of scope for now)
- [x] Notification when kid earns XP badges — implemented as an in-app toast

## Bonus fix (found via testing)
- [x] Duplicate-kid guard — adding a kid with a name that already exists now
      warns and requires an explicit confirmation checkbox. This directly
      addresses the real "parents accidentally duped a kid profile" incident
      that also prompted the Phase 1 delete-profile feature.

---

## Open Decisions — Resolved for This Phase
- [x] "A full week" = the 7 calendar days ending today
- [x] "1 month" streak = 30 days, "1 year" streak = 365 days
- [x] Achievements/milestones only re-award once per fresh cycle (not every day the condition holds)
- [x] Concrete example Store reward items — left as an empty list; parent adds their own (format is fully flexible, per spec)
- [x] Cost limits/categorization for Store items — none added; any positive XP cost is allowed
