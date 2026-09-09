# EarnIt — Phase 3: Multi-user & Polish

> Full feature detail lives in `earnit-spec_base.md`. This file tracks just
> what's in scope for Phase 3, and progress against it.
>
> **Depends on Phase 1 and Phase 2** being done — this phase is about making
> an already-working app robust and ready for real, ongoing, multi-person use.

**Goal:** ready for real, ongoing, multi-person use — not just a single
parent testing it solo.

**Legend:** `[ ]` not started · `[~]` in progress · `[x]` done

---

## Architecture note (read this first)

EarnIt is a Python script running locally with one JSON data file — there's
no server, no hosting, no network access. That's perfect for Phases 1-2, but
a few Phase 3 spec items (real passkey login, true multi-device "Fam"
sharing, offline+cloud sync) assume a hosted backend that doesn't exist here.
Rather than skip them, we built **local-only substitutes**: simple PIN auth
for everyone (parents included), and a local family roster instead of
networked accounts. If EarnIt ever moves to a real hosted service, those
substitutes are exactly the pieces that'd get swapped for the real thing.

## Auth Upgrades
- [x] PIN login for kid accounts — enter a kid's name, then their PIN
- [x] Parent login — same idea, local PIN auth instead of real passkeys
      (passkeys need a server + HTTPS domain, which this app doesn't have)

## Fam (Multi-Parent Sharing)
- [x] Fam screen: add/remove parent profiles (local roster, not networked)
- [x] Permission levels — resolved as a simple 2-role system: **admin**
      (can add/approve/edit/delete anything) and **viewer** (can see
      everything but all action buttons are disabled). Enforced everywhere
      a parent can change data — Kids Accounts, Kid Rewarding, Store, Fam.

## Profile
- [x] Kid avatar upload (own screen: **My Account**, saved to
      `earnit/data/avatars/`)

## Reliability
- [x] Offline support — not applicable in the usual sense: since this is a
      local script with no network calls at all, it's always "offline
      capable" by construction. This item only makes sense once there's a
      real cloud sync to lose connection to.
- [x] Account recovery — no email/device recovery (no real backend to send
      a reset link from). Practical equivalent: any admin parent can reset
      any kid's or parent's PIN from Kids Accounts / Fam. If literally
      every parent forgets their PIN, the local data file itself is still
      just a JSON file you can inspect directly.
- [x] Edit/undo for a mistakenly logged chore or report — "Undo today's
      report" / "Undo today's chore" buttons in Kids Accounts. If the XP
      from that entry was already claimed, the log entry is still removed,
      but the XP itself isn't automatically clawed back (could send credits
      negative) — the app warns you when that happens.

## Trust & Fairness
- [x] Dispute flow — kid can dispute a report from their Rewards & Progress
      screen; parent sees + resolves it in Kid Rewarding's "Open Disputes."

## Compliance
- [x] Data retention / privacy stance — COPPA is a US law about
      *businesses* collecting data from children; it doesn't apply to a
      personal script you run for your own family. Documented instead as a
      plain-language note in the Fam screen: all data stays in the local
      JSON file, nothing is transmitted anywhere. Added an "Export all data
      as JSON" button and a "Delete ALL data" button (admin-only, requires
      a confirmation checkbox) as good practice regardless.

## Product Decisions
- [x] Multi-child comparison/visibility — decided **no**, to avoid
      resentment between siblings (the spec's own concern). No code change
      needed: a kid only ever sees their own selected profile, never
      another kid's data — this was already true by construction.

---

## Open Decisions — Resolved for This Phase
- [x] Co-parent permission levels — 2-role system (admin / viewer), see above
