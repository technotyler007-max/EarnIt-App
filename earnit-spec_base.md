# EarnIt — Chore & Behavior Rewards System

> Status: 🚧 WIP spec — built up conversationally. Confirmed details are stated plainly. Anything not yet decided is flagged as `[TBD]` — these are suggestions/placeholders, not locked decisions.

## 1. Overview
Web app (phone, tablet, and computer, all through a browser — **no native mobile app / app store**) for parents to track kids' chores and daily behavior, and reward them through an XP-based progression system that ultimately converts into real-world money. Built as a **multi-family platform**: any family can sign up and use it, and every family's data is completely private from every other family's.

**Core concept:** kids do chores and get rated on daily behavior → earn XP → level up → earn credits → convert credits to real cash (parent-approved) → parent hands over the money in real life. There's also a secondary in-app economy where raw XP can be spent directly on in-app rewards without ever touching real money.

### Account Structure
- **The platform hosts many independent families** — anyone can sign up to create a new family
- **1 family → 1+ parent accounts → N kid profiles** underneath it
- A parent account is a "root" of its own family — creates and manages all kid profiles within that family only
- **Multiple parents can share access to the same family** (e.g. mom + dad both linked to the same kids) — ties into how "Fam" works
- **Families are fully isolated** — the Dubey family can never see or affect the Sharma family's kids, chores, XP, or anything else, and vice versa

### Auth
- **PIN-based login** for both parent and kid accounts — type your family's name, pick your name from that family, enter your PIN. Lightweight and appropriate for a kid; also avoids needing a full backend for real passkeys/passwords for now. Deliberately no visible list of every family on the app — you have to already know your own family's name.
- **Signing up creates a new family** — a family name plus the first parent's email and PIN. That first parent becomes an **admin** for the family (see Fam section for roles).
- **Email verification** — a 6-digit code is emailed and must be entered before the account is created, both for the initial family signup and for adding a co-parent later via Fam. Confirms whoever's signing up actually controls that email address.
- **Parents are identified by email, not a chosen display name** — since multiple parents (e.g. Dad + Mom) share one family, there's no meaningful single "name" for casual UI text to use (it just says "Parent"), but email still uniquely tells separate parent accounts apart for login and for Fam management (add/reset/remove). Kids keep display names, since a family can have several kids who do need to be told apart by name.
- `[TBD]` Passkey-based login is a possible future upgrade once the platform has a real hosted backend + domain, but is not the near-term plan.

### Hosting & Multi-Tenancy
- **Multi-tenant**: one running app instance serves every signed-up family, with data kept fully separate per family
- **Self-hosted, low-cost infrastructure** — no paid managed services (e.g. no Supabase/managed DB). The app (Python/Streamlit) talks to a self-hosted, **open-source database (MySQL)** — open source so it can be hosted on any cloud provider later without vendor lock-in or licensing cost
- **Stage 1 (now):** app + database both run locally, for development and testing
- **Stage 2 (future):** app + database both run together on one small, low-cost cloud server — since traffic is expected to be low early on, this keeps hosting cost minimal rather than paying for separate managed services
- **No native mobile app** — reached entirely through a browser; "Add to Home Screen" gives an app-like icon on a phone without needing an app store, Apple/Google developer fees, or app review

### Navigation Structure
- **Kid-side:** 4 sections — intentionally minimal/simple
- **Adult-side:** 5 sections — more admin/control surface
- The asymmetry is deliberate: kids get a clean, low-complexity experience focused on progress and spending; parents get the full management toolkit.

---

## 2. Main Screens

### Kid-side (4 sections)

**1. My Account**
- Kid's own profile: avatar, display name, basic settings
- Kid-friendly, minimal — no admin controls, no editing of chores/rewards themselves
- **Kids can upload their own avatar image** — full custom upload, not limited to preset options

**2. Rewards/Progress**
- Central hub for the kid to see their own standing:
  - Current XP total and progress toward next level (e.g. a progress bar: 63/100 XP)
  - Current level
  - Current credit balance (earned, not-yet-converted)
  - Achievements and milestones earned (see Section 3)
  - Recent daily reports, with the option to dispute one
  - Credit → Buck conversion requests
  - `[TBD]` Streak tracker — visual display of current 5-star rating streak, since streaks feed into milestones
- This is the "scoreboard" screen — where the kid checks how they're doing

**3. Chores**
- The kid's own chore checklist, separate from the scoreboard screen
- Marking a chore "done" sends a request to the parent — **no XP is granted until a parent approves it** in Kid Rewarding, matching the same approve-before-it-counts pattern as conversions and Store redemptions

**4. Store**
- Where kids spend **XP** (not bucks — bucks never live in-app, see Section 3)
- Browse available rewards, see XP cost, redeem
- **Redemption requires parent approval** — kid requests a reward, parent confirms before it's granted (mirrors the credit→buck approval flow, keeps parent in the loop on spending)
- **Store item structure:** each reward has a **name**, a **description**, and an **XP cost/amount** — simple, flexible format that lets a parent define any reward they want
- `[TBD]` Any concrete example reward categories worth listing (e.g. extra screen time, picking dinner, staying up late)? Not required to lock down now since the format is flexible either way.

### Adult-side (5 sections)

**1. Kids Accounts**
- Manage individual kid profiles: add a new kid, edit existing profiles, file/undo daily reports, reset PIN, delete profile
- `[TBD]` A parent "My Account" (own profile/settings, notification preferences) isn't built yet — not required so far since a parent's identity is just their email/PIN/role (see Auth above)

**2. Chores**
- Separate from Kids Accounts — per-kid chore list management (add/delete a chore, undo today's completion) plus the **Pending Chore Completions** approval queue (a kid marks a chore done → it lands here → a parent approves or denies before any XP is granted)
- **Chore model:** every kid gets the same shared default chore set (family-wide template), but individual chores can also be **directly assigned** to a specific kid on top of/instead of the shared list

**3. Kid Rewarding**
- **Live activity feed** — every event (chore completed, report filed, achievement/milestone earned) shows up here in real time
- This is also where the other parent-facing approval actions happen:
  - Kid requests to convert credits → bucks → parent approves/denies here
  - Store redemption requests needing approval
  - Open disputes a kid has filed against a report rating
- **XP claim mechanic:** XP is granted immediately when earned, but sits as **unclaimed** until the kid actively claims it in the app. **If unclaimed for 7 days, that XP expires and is lost.** This creates a "use it or lose it" incentive to keep the kid actively checking in.

**4. Fam**
- Family-wide **management of who has access** — shows all parents/managers linked to this family only (not the kids themselves, that's Kids Accounts)
- This is where the multi-parent sharing (mom + dad both linked to the same kids) gets managed — adding/removing co-parent access
- **Resolved:** each parent has a role — **admin** (can add/approve/edit/delete anything) or **viewer** (can see everything, can't change anything). This applies regardless of the platform's multi-family structure — roles are scoped to one family.
- **A kid can never approve/grant their own rewards, no matter what** — reward-granting (credit→buck conversions, Store redemptions, chore completions) is always a parent-only action, enforced separately from the admin/viewer role split.

**5. Store**
- Parent-facing store management: add/edit/remove reward items, set their XP cost
- Controls exactly what shows up in the kid-side Store
- `[TBD]` Any limits — e.g. max XP cost, category tagging (privilege vs. item vs. activity)?

---

## 3. Progression System (XP → Levels → Credits → Bucks)

This is the core economic engine of the app. Four currencies, each with a distinct role:

| Currency | Earned via | Spent/Converted via | Real money? |
|---|---|---|---|
| XP | Chores, reports, achievements, milestones | Store (kid-side) or accumulates toward Levels | No |
| Levels | 100 XP accumulated | N/A (grants Credits) | No |
| Credits | Leveling up | Converted to Bucks (1:1, parent-approved) | No |
| Bucks | Credit conversion | Handed over IRL by parent | **Yes — real cash** |

### 3.1 XP — Sources

**Chores**
- **XP value scales by difficulty** — parent sets the XP value when creating/assigning a chore, rather than a flat rate for everything
- Base example still holds for simple chores (1 XP), but bigger/harder chores can be worth more at the parent's discretion

**Parent Daily Reports**
- Parent rates the kid's overall behavior for the day on a **1–5 star scale**
- Star rating = direct XP: **1 star = 1 XP**, up to **5 XP** for a perfect day
- **Filed daily**, with an **automatic reminder at 5pm** nudging the parent to submit it
- **If missed, a parent can file late/backdated** — the report still applies to the intended day rather than being lost or skipped

**Achievements** (repeatable — can be earned again every time the condition is met)
- **Good Rating** — maintaining a **4–5 star average** across daily reports for a full week → **+5 XP** bonus
- **All Chores Finished** — completing every assigned chore for a full week → **+5 XP** bonus
- Both are weekly check-ins layered on top of the base chore/report XP — designed to reward *consistency*, not just individual good days
- `[TBD]` Any other achievements planned beyond these two? Room to expand later (e.g. streak-based smaller achievements, chore-variety bonuses, etc.)
- **Achievements/milestones display visually to the kid via a badge wall/gallery** — not just silent XP additions. This gives the kid something tangible to show off/collect, separate from the raw XP number.

**Milestones** (repeatable — tied to streaks of 5-star ratings specifically, not just 4-5 star averages)
- **7-day streak** of 5-star ratings → **+15 XP**
- **1-month streak** of 5-star ratings → **+50 XP**
- **1-year streak** of 5-star ratings → **instant +1 Level** (not XP — a full level, regardless of current XP progress)
- **Milestones can repeat** — if a kid breaks a streak and builds it back up, they earn the bonus again each time they hit the threshold (not a once-ever unlock)

### 3.2 Levels
- **100 XP = 1 Level**
- Flat threshold — same 100 XP required for every level (not scaling upward like some XP games)
- Each level-up grants exactly **+1 Credit**
- **XP rolls over** past 100 into the next level's progress (e.g. 130 XP → Level 1 + 30 XP already toward Level 2) — nothing is lost when leveling up

### 3.3 Credits → Bucks
- **Conversion rate: 1 Credit = 1 Buck** (i.e. 1 Credit = $1, since Bucks are real currency — see below)
- Kid initiates the conversion request from their side; it lands in the parent's **Kid Rewarding** tab
- **Requires parent approval** before it's finalized
- **Whole numbers only** — no partial/fractional credit conversion

### 3.4 Bucks — Real Money
- Bucks represent **actual real-world cash** — this is effectively a chore-based allowance system, not a fake in-app points economy
- Once a conversion is approved, the parent **hands over the cash in real life**
- **The app does not track bucks after conversion.** No in-app wallet, no balance, no spend history — once it becomes cash, it's fully outside the app's scope. What the kid buys with it is not the app's concern.
- This significantly simplifies the build: **no payment processing, no financial account integration needed** — the app's job ends at "conversion approved," everything after is real-world and untracked

### 3.5 XP Spending (separate from leveling)
- XP is **not exclusively** fuel for leveling up — it can also be **spent directly** in the kid-side Store
- This means a kid has to make a strategic choice: **save XP toward the next level** (→ credit → real money) **or spend it now** on smaller in-app rewards
- This tension is a nice design lever — it's the classic "save vs. spend" tradeoff that makes progression systems engaging
- `[TBD]` Once XP is spent in the Store, does it still count toward the kid's all-time XP total (for stats/bragging rights) even though it's no longer "available" to spend or level with? Worth deciding whether to track **lifetime XP earned** separately from **current spendable XP balance**.

---

## 4. Full Currency Flow (summary diagram)

```
Chore completed ──────────┐
Parent daily report (1-5★)─┼──> XP ──> spendable directly in Store (kid-side)
Achievements (+5 XP) ──────┤       │
Milestones (+15/+50 XP,  ──┘       └──> 100 XP = Level Up ──> +1 Credit
  or instant +1 Level)                                             │
                                                       Credit → Buck (1:1)
                                                    [requires parent approval
                                                     via Kid Rewarding tab]
                                                                     │
                                                       Bucks = real cash
                                                    (handed over IRL, untracked
                                                       by the app after this point)
```

**Worked example:** A kid does 80 chores (80 XP) and gets a perfect week of 5-star reports for 4 weeks (4 weeks × 5 XP/day × 7 days = 140 XP from reports alone, plus 4× "Good Rating" achievement bonuses = +20 XP, plus the 1-month streak milestone = +50 XP). That's roughly 290 XP total — enough for 2 full levels (200 XP) with 90 XP left over, meaning **2 Credits earned** (worth $2 if converted), plus 90 XP still available to either save toward the 3rd level or spend in the Store.

---

## 5. Open Questions / TODO

**Foundational (not yet touched):**
- [ ] Core daily loop — the exact moment-to-moment flow of what a parent and kid each do in the app on a normal day
- [x] Data sync — **resolved:** self-hosted MySQL database, one shared instance for all families (see Hosting & Multi-Tenancy above)
- [x] Tech stack — **resolved:** Python + Streamlit, web-only, no React Native/Flutter/native mobile

**Account/Auth:**
- [x] Multi-family signup — **resolved:** family name + first parent's email/PIN creates a new, fully isolated family. Email is used purely as a login identifier (no verification email or password-reset link is sent — no email-sending infrastructure exists), matching the low-cost/simple approach — consistent with how kid/parent PIN reset already works (an admin resets it).
- [x] Family name uniqueness — **resolved: names must be unique.** Login works by typing your own family's name directly rather than picking from a visible list of every family on the app (a deliberate privacy choice — the app never shows anyone a directory of who else uses it), so two families can't share a name with no way to tell them apart. Signup blocks a name that's already taken.

**Screens:**
- [x] Kid Rewarding shows a live activity feed of everything (chores, reports, badges, requests) — resolved in Phase 2
- [x] Can a co-parent have full admin rights, or view-only/limited permissions? — **resolved**, see Fam section above

**Chores & Reports:**

**Progression System:**
- [ ] Minimum credit amount required before conversion is allowed?
- [ ] Track lifetime XP earned separately from current spendable balance?

**Achievements/Milestones:**
- [ ] More achievements planned beyond "Good Rating" and "All Chores Finished"?

**Store:**
- [x] Concrete example reward items — **resolved:** left as an empty list; each family's parent adds their own (the name/description/cost format is fully flexible on purpose)
- [x] Any cost limits or categorization for store items? — **resolved:** none; any positive XP cost is allowed

**Product/UX Gaps:**
- [x] Notifications — **resolved:** in-app only (toasts for badges, a banner for the 5pm report reminder). No real push notifications, since that needs a backend that can reach a device even when the app/tab is closed — revisit once the platform has one.
- [ ] Shared chores — if two kids share a chore, does XP split between them or does each need it assigned individually? (currently: each chore belongs to exactly one kid)
- [x] Editing/undo — **resolved:** a parent can undo today's logged chore or report from Kids Accounts. If its XP was already claimed, the log entry is still removed, but the XP itself isn't clawed back (avoids weird negative-credit edge cases) — the app warns when that happens.
- [ ] Onboarding flow — what's the first-time setup path from download to fully configured (kids, chores, store items)? Now also needs a **family signup** step ahead of this (see Account/Auth above).

**System/Business Gaps:**
- [x] Dispute handling — **resolved:** a kid can dispute a specific report from their Rewards & Progress screen with a note; the parent sees + resolves it in Kid Rewarding.
- [x] Data retention/privacy — **resolved for personal/local use:** COPPA applies to *businesses* collecting data from children, not a personal tool run for one's own family — documented in-app. **Now that the platform is multi-family and may go public, this needs revisiting** — once other families' children's data is involved, this stops being purely personal and a real privacy/COPPA stance is worth taking seriously before public sign-ups open.
- [x] Multi-child comparison — **resolved:** no, siblings never see each other's data — true by construction, since a kid only ever sees their own selected profile.

**Technical Gaps:**
- [ ] Offline behavior — can a parent log a chore with no internet connection, and does it sync later? Now relevant for real once the app is hosted remotely rather than run locally.
- [x] Backup/account recovery — **resolved, and updated for PIN-based (not passkey) login:** no email/device recovery flow exists (no backend to send a reset link from). An admin parent can reset any kid's or parent's PIN. `[TBD]` What happens if a family's *only* admin parent forgets their PIN, once the app is hosted remotely and the data file isn't something they can just open themselves?

## 6. Notes
(misc ideas dumped here as we go)
