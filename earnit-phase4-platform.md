# EarnIt — Phase 4: Multi-Family Platform & Hosting

> Full feature detail lives in `earnit-spec_base.md`. This file tracks just
> what's in scope for Phase 4, and progress against it.
>
> **Depends on Phases 1-3** being done — this phase turns an already-working
> single-family app into a platform many families can sign up for.

**Goal:** any family can sign up and use EarnIt, with data fully isolated
per family, self-hosted on infrastructure cheap enough to run for free (or
near-free) at low traffic.

**Legend:** `[ ]` not started · `[~]` in progress · `[x]` done

---

## Supersedes an earlier attempt

Partway through this phase, an earlier plan (Streamlit Community Cloud +
Supabase, single family only) was started and then dropped in favor of
this one, because the requirements changed to: multi-family, and an
open-source self-hostable database instead of a managed one. Any
Supabase-specific code from that earlier attempt gets replaced.

## Family Signup & Login
- [x] Sign-up flow: family name + first parent's name/PIN → creates a new,
      fully isolated family with that parent as its first admin, auto-logged in
- [x] Login flow: type your family's name (no visible directory of every
      family, for privacy) → existing parent/kid name+PIN picker, now
      scoped to that family only
- [x] A kid/parent from one family can never see or affect another
      family's data — verified live with two real families (Dubey, Sharma)
- [x] Family names must be unique — signup blocks a name already taken

## Data & Storage
- [x] Each family's data (kids, chores, reports, XP, everything) stored as
      its own blob, keyed by family, in a **MySQL** database — this keeps
      `core.py` (all the tested game-logic functions) unchanged, since each
      family's blob has the exact same shape as the single-family data
      always has
- [x] `storage.py` rewritten to talk to MySQL instead of a local JSON file
- [x] Avatars stored inside each family's own blob (not local disk files)
- [x] "Delete ALL data" now correctly scoped to only the current family —
      verified live: wiping Dubey's data left Sharma's completely untouched

## Hosting
- [x] **Stage 1 (now):** MySQL + the app both run locally on this laptop —
      MySQL installed via winget, database/table/app-user created directly
      via terminal, app connects via `.streamlit/secrets.toml`
- [ ] **Stage 2 (future):** MySQL + the app run together on one small,
      low-cost cloud server — chosen specifically to minimize cost at low
      traffic, rather than paying for separate managed services. Same code;
      just point `secrets.toml` at the server instead of `localhost`.
- [ ] Keeping the app running as a proper background service (survives
      closing the terminal / laptop reboot) — not yet done; currently it
      only runs while a terminal has `streamlit run` active

## Bonus fixes (found/requested during this phase)
- [x] Chore completion now requires parent approval — previously a kid
      could mark any chore done and get XP with zero parent check, which
      was inconsistent with how reports/conversions/redemptions already
      work. Kid marks it → parent approves/denies in Kid Rewarding → only
      then does XP appear as unclaimed (still requires the normal Claim
      step). Verified live end-to-end.
- [x] "My Purchases" section added to the kid Store screen — shows the
      history of approved Store redemptions.
- [x] Parent identity switched from a chosen display name to **email** —
      email is the login username and how parents are told apart in Fam;
      casual UI text just says "Parent" since a shared family account
      doesn't need a name. Signup asks for family name + email + PIN only.
- [x] **Parent login is pick-from-list + PIN again** (not typed email) —
      after adding the Kid → Parent re-auth requirement above, retyping a
      full email every time felt heavier than it needed to be. Parent
      login now mirrors kid login exactly: pick your email from a dropdown
      of this family's parents, then just enter the PIN. Typed email is
      still used for *signup* and *adding* a new parent (where the email
      doesn't exist in the system yet), just not for logging back in as
      one that already does.
- [x] **Parents can see spendable XP** — Kids Accounts previously only
      showed lifetime XP; the header now shows both
      (`250 lifetime XP (15 spendable)`), since spendable XP is what
      actually matters for Store spending/conversions.
- [x] **Conversion/redemption request spam fixed** — requesting a
      credit→buck conversion or a Store item didn't reserve anything, so
      rapid-clicking could create several pending requests that together
      exceeded the kid's real balance (only caught, confusingly, if a
      parent tried approving all of them). Fixed: both now check pending
      requests already tied up in other requests against the current
      balance, block new requests that would overcommit, and the Store's
      Redeem button disables itself once nothing's left to spend. Verified
      live with real over-commit attempts.
- [x] **Real email format validation** — signup and Add-a-parent used to
      only check for an "@" character; now uses a proper pattern
      (`core.is_valid_email`) and shows a clear error for junk input.
- [x] **Re-auth on Kid → Parent switch** — previously, once a parent's PIN
      had been verified anywhere in a browser session, flipping the "I am
      a..." toggle to Parent skipped straight past login (session state
      persisted). Fixed: switching *into* Parent mode from something else
      now always clears the parent auth and re-shows the normal email+PIN
      login (no new verification code involved) — so a kid handing the
      device back can't tap into an already-authenticated parent session.
      Staying within Parent mode, or the auto-login right after signup,
      are both unaffected. Verified live.
- [x] **Email verification** — signing up, and adding a co-parent in Fam,
      now both require entering a 6-digit code emailed to that address
      before the account is created. Sent via Gmail SMTP (`earnit/mailer.py`,
      Python's built-in `smtplib` — no new dependency). Codes expire after
      10 minutes; wrong codes are rejected; tested end-to-end (including a
      wrong-code rejection) with a temporary local stub in place of real
      Gmail sending, since sending real mail needs Gmail credentials only
      you can create (below).

### Setting up the Gmail app password (one-time, you)
1. Use a Gmail account (existing or new — doesn't need to be fancy, this
   is just the "from" address for verification codes).
2. Turn on **2-Step Verification** on that Google account, if it isn't
   already on: [myaccount.google.com/security](https://myaccount.google.com/security).
3. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords),
   sign in again if asked, and create a new app password (name it
   something like "EarnIt").
4. Google shows a 16-character password **once** — copy it immediately.
5. In `.streamlit/secrets.toml` (already git-ignored), set:
   ```
   smtp_email = "your-gmail-address@gmail.com"
   smtp_app_password = "the 16-character app password, no spaces"
   ```
6. Tell me once that's in place and I'll do one real end-to-end send to
   confirm delivery actually works before you rely on it.

**Gotcha hit during setup:** the App Passwords page doesn't reliably show
up by clicking through the Google Account UI (it's not listed under
2-Step Verification's "Second steps," even though that's where you'd
expect it). Go directly to
[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
instead. Also, a password generated once and never appearing in that
page's list afterward means it didn't actually save — generate a fresh
one and confirm it's listed before using it.

**Status:** done — real send confirmed working with `earnit.support@gmail.com`.

## Explicitly Dropped
- Native mobile app / Apple App Store / Google Play Store listings
- Supabase (replaced by self-hosted MySQL)
- Real passkey auth (still PIN-based for now — see spec's Auth section)

---

## Open Decisions
- [x] Family name uniqueness — **resolved: names must be unique.** Login
      works by typing your own family's name directly (no visible list of
      every family using the app, for privacy), so two families can't
      safely share a name with no way to disambiguate. Signup checks for
      an existing match and blocks it with an error.
- [ ] Account recovery if a family's only admin forgets their PIN, now that
      the data won't be a file they can just open and edit themselves
- [ ] Data retention/privacy stance now that other families' children's
      data may be involved (COPPA-style considerations become real once
      this isn't just personal use) — worth a real answer before public
      sign-ups open
