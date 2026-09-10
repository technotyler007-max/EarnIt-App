"""
The "engine" of EarnIt: all the rules for how XP, levels, credits, chores,
and daily reports work. This file has no UI code in it at all — it just
takes the data dict (loaded from storage.py) and updates it correctly.

Keeping the rules separate from the screens means we can test the math
(does 130 XP really give you Level 1 + 30 XP left over?) without needing
to click through the app.
"""

import re
from datetime import date as date_cls, timedelta

try:
    from earnit import storage
except ImportError:
    # allows `streamlit run app.py` to work when run from inside earnit/ too
    import storage

XP_PER_LEVEL = 100
ACHIEVEMENT_XP = 5
XP_CLAIM_WINDOW_DAYS = 7

# Not full RFC 5322 (that's a rabbit hole) -- just enough to catch obviously
# broken input: something@something.something, no spaces.
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def is_valid_email(email):
    return bool(EMAIL_PATTERN.match(email.strip()))

# Each milestone: (internal name, streak length needed, reward amount, "xp" or "level")
MILESTONE_TIERS = [
    ("streak_7", 7, 15, "xp"),
    ("streak_30", 30, 50, "xp"),
    ("streak_365", 365, 1, "level"),
]

# Display info for the badge wall — keyed by the internal names used above.
BADGE_INFO = {
    "good_rating": {"label": "Good Rating", "emoji": "🌟", "description": "4-5 star average for a full week"},
    "all_chores_finished": {"label": "All Chores Finished", "emoji": "🧹", "description": "Every chore done, every day, for a week"},
    "streak_7": {"label": "7-Day Streak", "emoji": "🔥", "description": "7 days in a row of 5-star ratings"},
    "streak_30": {"label": "1-Month Streak", "emoji": "🏅", "description": "30 days in a row of 5-star ratings"},
    "streak_365": {"label": "1-Year Streak", "emoji": "👑", "description": "365 days in a row of 5-star ratings"},
}


# ---------------------------------------------------------------------------
# Kids
# ---------------------------------------------------------------------------

def add_kid(data, name, pin):
    kid = {
        "id": storage.next_id(data, "kid"),
        "name": name,
        "pin": pin,
        "xp": 0,             # lifetime XP earned — only ever grows, drives level
        "spendable_xp": 0,   # currently available to spend in the Store
        "level": 0,
        "credits": 0,
        "avatar_file": None,
        "achievements_awarded": {},
        "milestones_awarded": {},
    }
    data["kids"].append(kid)
    return kid


def get_kid(data, kid_id):
    for kid in data["kids"]:
        if kid["id"] == kid_id:
            return kid
    return None


def verify_kid_pin(data, kid_id, pin):
    kid = get_kid(data, kid_id)
    return kid is not None and kid["pin"] == pin


def set_kid_pin(data, kid_id, new_pin):
    kid = get_kid(data, kid_id)
    if kid is None:
        raise ValueError("Kid not found.")
    kid["pin"] = new_pin


# ---------------------------------------------------------------------------
# Parents / Fam — local stand-in for real multi-device accounts. There's no
# real security here (anyone with access to this computer could edit the
# data file directly) — it's just enough structure to tell family members
# apart and to distinguish "can approve/manage things" from "view only."
# ---------------------------------------------------------------------------

PARENT_ROLES = ["admin", "viewer"]


def add_parent(data, email, pin, role="admin"):
    """Add a parent, identified by email rather than a chosen display name --
    email doubles as their login username and is how they're told apart in
    the Fam screen (there's no separate 'name' field for parents; multiple
    parents in one family are just 'a parent' in casual UI text, but need
    a real, unique identifier for login/admin purposes)."""
    if role not in PARENT_ROLES:
        raise ValueError(f"Role must be one of {PARENT_ROLES}.")
    if any(p["email"].strip().lower() == email.strip().lower() for p in data["parents"]):
        raise ValueError(f"A parent with email '{email}' already exists in this family.")
    parent = {
        "id": storage.next_id(data, "parent"),
        "email": email,
        "pin": pin,
        "role": role,
    }
    data["parents"].append(parent)
    return parent


def get_parent(data, parent_id):
    for parent in data["parents"]:
        if parent["id"] == parent_id:
            return parent
    return None


def verify_parent_pin(data, parent_id, pin):
    parent = get_parent(data, parent_id)
    return parent is not None and parent["pin"] == pin


def set_parent_pin(data, parent_id, new_pin):
    parent = get_parent(data, parent_id)
    if parent is None:
        raise ValueError("Parent not found.")
    parent["pin"] = new_pin


def remove_parent(data, parent_id):
    if len(data["parents"]) <= 1:
        raise ValueError("Can't remove the last remaining parent — add another admin first.")
    data["parents"] = [p for p in data["parents"] if p["id"] != parent_id]


def delete_kid(data, kid_id):
    """Remove a kid profile and everything tied to it (chores, history, requests)."""
    if get_kid(data, kid_id) is None:
        raise ValueError("Kid not found.")

    data["kids"] = [k for k in data["kids"] if k["id"] != kid_id]
    data["chores"] = [c for c in data["chores"] if c["assigned_to"] != kid_id]
    data["chore_log"] = [entry for entry in data["chore_log"] if entry["kid_id"] != kid_id]
    data["daily_reports"] = [r for r in data["daily_reports"] if r["kid_id"] != kid_id]
    data["conversion_requests"] = [r for r in data["conversion_requests"] if r["kid_id"] != kid_id]
    data["redemption_requests"] = [r for r in data["redemption_requests"] if r["kid_id"] != kid_id]
    data["chore_completion_requests"] = [r for r in data["chore_completion_requests"] if r["kid_id"] != kid_id]
    data["disputes"] = [d for d in data["disputes"] if d["kid_id"] != kid_id]
    data["xp_grants"] = [g for g in data["xp_grants"] if g["kid_id"] != kid_id]
    data["badges_earned"] = [b for b in data["badges_earned"] if b["kid_id"] != kid_id]


def _award_xp(kid, amount):
    """Add XP to a kid's real totals and grant credits for any level(s) just crossed.

    This updates TWO numbers: lifetime xp (which only ever grows and drives
    level — spending in the Store never touches it) and spendable_xp (which
    the Store draws down when the kid redeems something). Level is always
    xp // 100, so leftover XP automatically 'rolls over' into progress
    toward the next level — nothing is lost. This only touches the kid's
    CONFIRMED total — see grant_xp() for how XP gets here in the first
    place (it has to be claimed first).
    """
    old_level = kid["level"]
    kid["xp"] += amount
    kid["spendable_xp"] += amount
    new_level = kid["xp"] // XP_PER_LEVEL
    if new_level > old_level:
        kid["credits"] += new_level - old_level
        kid["level"] = new_level


# ---------------------------------------------------------------------------
# XP claiming — XP is earned immediately but sits "unclaimed" until the kid
# taps Claim. Unclaimed XP expires (is lost) after XP_CLAIM_WINDOW_DAYS days.
# ---------------------------------------------------------------------------

def grant_xp(data, kid_id, amount, source, on_date):
    """Record a newly-earned chunk of XP as unclaimed. Doesn't touch the
    kid's real total yet — that only happens when they claim it."""
    data["xp_grants"].append({
        "id": storage.next_id(data, "grant"),
        "kid_id": kid_id,
        "amount": amount,
        "source": source,
        "date_earned": on_date,
        "status": "unclaimed",
    })


def get_unclaimed_grants(data, kid_id):
    return [
        g for g in data["xp_grants"]
        if g["kid_id"] == kid_id and g["status"] == "unclaimed"
    ]


def get_unclaimed_total(data, kid_id):
    return sum(g["amount"] for g in get_unclaimed_grants(data, kid_id))


def days_until_expiry(grant, today=None):
    today = date_cls.fromisoformat(today) if today else date_cls.today()
    earned = date_cls.fromisoformat(grant["date_earned"])
    return XP_CLAIM_WINDOW_DAYS - (today - earned).days


def sweep_expired_grants(data, today=None):
    """Mark any unclaimed XP older than the claim window as expired (lost).
    Safe to call often — already-resolved grants are left alone."""
    today = today or date_cls.today().isoformat()
    expired_count = 0
    for grant in data["xp_grants"]:
        if grant["status"] == "unclaimed" and days_until_expiry(grant, today) < 0:
            grant["status"] = "expired"
            expired_count += 1
    return expired_count


def claim_xp(data, kid_id, today=None):
    """Move all of a kid's still-valid unclaimed XP into their real total."""
    today = today or date_cls.today().isoformat()
    sweep_expired_grants(data, today)  # don't let an expired grant sneak in

    kid = get_kid(data, kid_id)
    grants = get_unclaimed_grants(data, kid_id)
    total = sum(g["amount"] for g in grants)
    if total > 0:
        _award_xp(kid, total)
        for grant in grants:
            grant["status"] = "claimed"
    return total


# ---------------------------------------------------------------------------
# Chores
# ---------------------------------------------------------------------------

def add_chore(data, name, xp_value, kid_id):
    chore = {
        "id": storage.next_id(data, "chore"),
        "name": name,
        "xp_value": xp_value,
        "assigned_to": kid_id,
    }
    data["chores"].append(chore)
    return chore


def get_chores_for_kid(data, kid_id):
    return [c for c in data["chores"] if c["assigned_to"] == kid_id]


def delete_chore(data, chore_id):
    """Remove a chore entirely, including its completion history."""
    data["chores"] = [c for c in data["chores"] if c["id"] != chore_id]
    data["chore_log"] = [log for log in data["chore_log"] if log["chore_id"] != chore_id]
    data["chore_completion_requests"] = [
        r for r in data["chore_completion_requests"] if r["chore_id"] != chore_id
    ]


def is_chore_done_on(data, chore_id, on_date):
    return any(
        log["chore_id"] == chore_id and log["date"] == on_date
        for log in data["chore_log"]
    )


def is_chore_request_pending(data, chore_id, on_date):
    return any(
        r["chore_id"] == chore_id and r["date"] == on_date and r["status"] == "pending"
        for r in data["chore_completion_requests"]
    )


def complete_chore(data, chore_id, on_date=None):
    """Actually log a chore as done and grant its (unclaimed) XP.

    This is the 'it really happened' step — called after a parent approves
    a kid's completion request, never directly from the kid's side. See
    request_chore_completion() for how a kid actually asks for this.
    """
    chore = next((c for c in data["chores"] if c["id"] == chore_id), None)
    if chore is None:
        raise ValueError("Chore not found.")

    kid = get_kid(data, chore["assigned_to"])
    if kid is None:
        raise ValueError("This chore isn't assigned to a valid kid.")

    on_date = on_date or date_cls.today().isoformat()
    if is_chore_done_on(data, chore_id, on_date):
        raise ValueError("This chore was already marked done today.")

    grant_xp(data, kid["id"], chore["xp_value"], f"Chore: {chore['name']}", on_date)
    data["chore_log"].append({
        "chore_id": chore_id,
        "kid_id": kid["id"],
        "date": on_date,
        "xp_awarded": chore["xp_value"],
    })
    badges = check_achievements_and_milestones(data, kid["id"], on_date)
    return {"xp_awarded": chore["xp_value"], "badges": badges}


def request_chore_completion(data, chore_id, on_date=None):
    """A kid says 'I did this chore' — creates a pending request. No XP yet;
    a parent has to approve it first (see approve_chore_completion)."""
    chore = next((c for c in data["chores"] if c["id"] == chore_id), None)
    if chore is None:
        raise ValueError("Chore not found.")

    on_date = on_date or date_cls.today().isoformat()
    if is_chore_done_on(data, chore_id, on_date):
        raise ValueError("This chore was already approved for today.")
    if is_chore_request_pending(data, chore_id, on_date):
        raise ValueError("Already waiting on parent approval for today.")

    request = {
        "id": storage.next_id(data, "chorereq"),
        "chore_id": chore_id,
        "kid_id": chore["assigned_to"],
        "date": on_date,
        "status": "pending",
        "date_requested": date_cls.today().isoformat(),
    }
    data["chore_completion_requests"].append(request)
    return request


def get_pending_chore_requests(data):
    return [r for r in data["chore_completion_requests"] if r["status"] == "pending"]


def approve_chore_completion(data, request_id):
    """Parent confirms a kid really did the chore — this is what actually
    logs it and grants the (still-unclaimed) XP, via complete_chore()."""
    request = next((r for r in data["chore_completion_requests"] if r["id"] == request_id), None)
    if request is None or request["status"] != "pending":
        raise ValueError("Request not found or already resolved.")

    result = complete_chore(data, request["chore_id"], request["date"])
    request["status"] = "approved"
    return result


def deny_chore_completion(data, request_id):
    request = next((r for r in data["chore_completion_requests"] if r["id"] == request_id), None)
    if request is None or request["status"] != "pending":
        raise ValueError("Request not found or already resolved.")

    request["status"] = "denied"
    return request


def _remove_matching_grant(data, kid_id, source, on_date, amount):
    """Find the xp_grant created by a chore/report being undone and remove it.

    If it's still unclaimed, we can cleanly delete it — the XP just vanishes,
    as if it never happened. If it's already been claimed (or expired), the
    kid's real totals were already updated, and clawing that back could get
    weird (negative credits, etc.), so we leave it and tell the caller.
    Returns True if the undo was "clean" (nothing left dangling).
    """
    for grant in data["xp_grants"]:
        if (
            grant["kid_id"] == kid_id
            and grant["source"] == source
            and grant["date_earned"] == on_date
            and grant["amount"] == amount
        ):
            if grant["status"] == "unclaimed":
                data["xp_grants"].remove(grant)
                return True
            return False
    return True  # no grant found — nothing to clean up


def undo_chore_completion(data, chore_id, on_date):
    """Un-mark a chore as done for a given date (fixes a mistaken log)."""
    chore = next((c for c in data["chores"] if c["id"] == chore_id), None)
    if chore is None:
        raise ValueError("Chore not found.")
    log_entry = next(
        (log for log in data["chore_log"] if log["chore_id"] == chore_id and log["date"] == on_date),
        None,
    )
    if log_entry is None:
        raise ValueError("No completion logged for that chore on that date.")

    cleanly_removed = _remove_matching_grant(
        data, chore["assigned_to"], f"Chore: {chore['name']}", on_date, chore["xp_value"]
    )
    data["chore_log"].remove(log_entry)
    return cleanly_removed


# ---------------------------------------------------------------------------
# Daily reports
# ---------------------------------------------------------------------------

def has_report_for_date(data, kid_id, on_date):
    return any(
        r["kid_id"] == kid_id and r["date"] == on_date
        for r in data["daily_reports"]
    )


def get_kids_missing_report(data, on_date=None):
    """Which kids don't have a daily report filed yet for on_date (defaults to today)."""
    on_date = on_date or date_cls.today().isoformat()
    return [kid for kid in data["kids"] if not has_report_for_date(data, kid["id"], on_date)]


def file_daily_report(data, kid_id, stars, on_date=None):
    """Record a 1-5 star day for a kid. Star rating = XP awarded (1 star = 1 XP)."""
    if stars not in (1, 2, 3, 4, 5):
        raise ValueError("Stars must be between 1 and 5.")

    kid = get_kid(data, kid_id)
    if kid is None:
        raise ValueError("Kid not found.")

    on_date = on_date or date_cls.today().isoformat()
    if has_report_for_date(data, kid_id, on_date):
        raise ValueError(f"A report for {on_date} already exists for this kid.")

    grant_xp(data, kid_id, stars, f"Daily report: {stars}★", on_date)
    data["daily_reports"].append({
        "kid_id": kid_id,
        "date": on_date,
        "stars": stars,
        "xp_awarded": stars,
    })
    badges = check_achievements_and_milestones(data, kid_id, on_date)
    return {"xp_awarded": stars, "badges": badges}


def undo_daily_report(data, kid_id, on_date):
    """Delete a mistakenly-filed report (fixes a wrong star rating)."""
    report = next(
        (r for r in data["daily_reports"] if r["kid_id"] == kid_id and r["date"] == on_date),
        None,
    )
    if report is None:
        raise ValueError("No report found for that date.")

    cleanly_removed = _remove_matching_grant(
        data, kid_id, f"Daily report: {report['stars']}★", on_date, report["stars"]
    )
    data["daily_reports"].remove(report)
    return cleanly_removed


# ---------------------------------------------------------------------------
# Credit -> Buck conversion requests
# ---------------------------------------------------------------------------

def get_pending_credits_requested(data, kid_id):
    """Credits already tied up in this kid's pending conversion requests --
    not yet deducted from kid['credits'], but already spoken for."""
    return sum(
        r["credits_requested"] for r in data["conversion_requests"]
        if r["kid_id"] == kid_id and r["status"] == "pending"
    )


def request_conversion(data, kid_id, credits_requested):
    kid = get_kid(data, kid_id)
    if kid is None:
        raise ValueError("Kid not found.")
    if credits_requested < 1:
        raise ValueError("Must request at least 1 credit.")
    already_pending = get_pending_credits_requested(data, kid_id)
    if credits_requested > kid["credits"] - already_pending:
        raise ValueError(
            "Not enough credits for that request "
            f"(you already have {already_pending} credits tied up in other pending requests)."
        )

    request = {
        "id": storage.next_id(data, "req"),
        "kid_id": kid_id,
        "credits_requested": credits_requested,
        "status": "pending",
        "date_requested": date_cls.today().isoformat(),
    }
    data["conversion_requests"].append(request)
    return request


def get_pending_requests(data):
    return [r for r in data["conversion_requests"] if r["status"] == "pending"]


def approve_conversion(data, request_id):
    request = next((r for r in data["conversion_requests"] if r["id"] == request_id), None)
    if request is None or request["status"] != "pending":
        raise ValueError("Request not found or already resolved.")

    kid = get_kid(data, request["kid_id"])
    if kid["credits"] < request["credits_requested"]:
        raise ValueError("Kid no longer has enough credits for this request.")

    kid["credits"] -= request["credits_requested"]
    request["status"] = "approved"
    return request


def deny_conversion(data, request_id):
    request = next((r for r in data["conversion_requests"] if r["id"] == request_id), None)
    if request is None or request["status"] != "pending":
        raise ValueError("Request not found or already resolved.")

    request["status"] = "denied"
    return request


# ---------------------------------------------------------------------------
# Achievements & Milestones
# ---------------------------------------------------------------------------

def _last_n_dates(end_date_str, n):
    """Return the last n calendar dates (as ISO strings), oldest first, ending on end_date_str."""
    end = date_cls.fromisoformat(end_date_str)
    return [(end - timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]


def get_five_star_streak(data, kid_id, end_date_str):
    """Count consecutive calendar days of 5-star reports, ending on end_date_str.

    Walks backward one day at a time from end_date_str: as long as that day has
    a 5-star report, the streak keeps growing. The first day that isn't a
    5-star report stops the count.
    """
    reports_by_date = {
        r["date"]: r["stars"] for r in data["daily_reports"] if r["kid_id"] == kid_id
    }
    streak = 0
    current = date_cls.fromisoformat(end_date_str)
    while reports_by_date.get(current.isoformat()) == 5:
        streak += 1
        current -= timedelta(days=1)
    return streak


def _has_good_rating_week(data, kid_id, end_date_str):
    """A report was filed every day for the last 7 days, averaging 4-5 stars."""
    reports_by_date = {
        r["date"]: r["stars"] for r in data["daily_reports"] if r["kid_id"] == kid_id
    }
    week_stars = [reports_by_date.get(d) for d in _last_n_dates(end_date_str, 7)]
    if any(stars is None for stars in week_stars):
        return False
    return sum(week_stars) / len(week_stars) >= 4


def _has_all_chores_week(data, kid_id, end_date_str):
    """Every chore currently assigned to the kid was done on each of the last 7 days."""
    chores = get_chores_for_kid(data, kid_id)
    if not chores:
        return False
    for d in _last_n_dates(end_date_str, 7):
        for chore in chores:
            if not is_chore_done_on(data, chore["id"], d):
                return False
    return True


def _award_badge(data, kid_id, name, amount, unit, on_date):
    data["badges_earned"].append({
        "kid_id": kid_id,
        "name": name,
        "amount": amount,
        "unit": unit,
        "date": on_date,
    })


def check_achievements_and_milestones(data, kid_id, on_date):
    """Look at a kid's history around on_date and award any newly-earned
    achievements/milestones. Safe to call after any chore completion or
    daily report — it just won't find anything new most of the time.

    Returns a list of badge names newly awarded (empty if none).
    """
    kid = get_kid(data, kid_id)
    if kid is None:
        return []

    achievements_awarded = kid.setdefault("achievements_awarded", {})
    milestones_awarded = kid.setdefault("milestones_awarded", {})
    newly_awarded = []
    end = date_cls.fromisoformat(on_date)

    # --- Achievements: re-earnable, but only once per 7-day cycle ---
    achievement_checks = [
        ("good_rating", _has_good_rating_week(data, kid_id, on_date)),
        ("all_chores_finished", _has_all_chores_week(data, kid_id, on_date)),
    ]
    for name, condition_met in achievement_checks:
        last_awarded = achievements_awarded.get(name)
        cycle_elapsed = (
            last_awarded is None
            or (end - date_cls.fromisoformat(last_awarded)).days >= 7
        )
        if condition_met and cycle_elapsed:
            grant_xp(data, kid_id, ACHIEVEMENT_XP, f"Achievement: {BADGE_INFO[name]['label']}", on_date)
            achievements_awarded[name] = on_date
            _award_badge(data, kid_id, name, ACHIEVEMENT_XP, "xp", on_date)
            newly_awarded.append(name)

    # --- Milestones: tied to the CURRENT 5-star streak ---
    streak_length = get_five_star_streak(data, kid_id, on_date)
    if streak_length > 0:
        streak_start = (end - timedelta(days=streak_length - 1)).isoformat()
        for name, threshold, amount, unit in MILESTONE_TIERS:
            already_awarded_this_streak = milestones_awarded.get(name) == streak_start
            if streak_length >= threshold and not already_awarded_this_streak:
                if unit == "xp":
                    grant_xp(data, kid_id, amount, f"Milestone: {BADGE_INFO[name]['label']}", on_date)
                else:  # instant level(s) — spec calls this out as NOT xp, so it applies right away
                    kid["level"] += amount
                    kid["credits"] += amount
                milestones_awarded[name] = streak_start
                _award_badge(data, kid_id, name, amount, unit, on_date)
                newly_awarded.append(name)

    return newly_awarded


# ---------------------------------------------------------------------------
# Store — kids spend spendable_xp here; every redemption needs parent approval
# ---------------------------------------------------------------------------

def add_store_item(data, name, description, xp_cost):
    item = {
        "id": storage.next_id(data, "item"),
        "name": name,
        "description": description,
        "xp_cost": xp_cost,
    }
    data["store_items"].append(item)
    return item


def update_store_item(data, item_id, name, description, xp_cost):
    item = next((i for i in data["store_items"] if i["id"] == item_id), None)
    if item is None:
        raise ValueError("Store item not found.")
    item["name"] = name
    item["description"] = description
    item["xp_cost"] = xp_cost
    return item


def delete_store_item(data, item_id):
    data["store_items"] = [i for i in data["store_items"] if i["id"] != item_id]


def get_pending_xp_requested(data, kid_id):
    """Spendable XP already tied up in this kid's pending Store redemption
    requests -- not yet deducted, but already spoken for."""
    return sum(
        r["xp_cost"] for r in data["redemption_requests"]
        if r["kid_id"] == kid_id and r["status"] == "pending"
    )


def request_redemption(data, kid_id, item_id):
    kid = get_kid(data, kid_id)
    item = next((i for i in data["store_items"] if i["id"] == item_id), None)
    if kid is None or item is None:
        raise ValueError("Kid or store item not found.")
    already_pending = get_pending_xp_requested(data, kid_id)
    if kid["spendable_xp"] - already_pending < item["xp_cost"]:
        raise ValueError(
            "Not enough XP for that reward "
            f"(you already have {already_pending} XP tied up in other pending requests)."
        )

    request = {
        "id": storage.next_id(data, "redeem"),
        "kid_id": kid_id,
        "item_id": item_id,
        "item_name": item["name"],     # snapshot in case the item changes/is deleted later
        "xp_cost": item["xp_cost"],
        "status": "pending",
        "date_requested": date_cls.today().isoformat(),
    }
    data["redemption_requests"].append(request)
    return request


def get_pending_redemptions(data):
    return [r for r in data["redemption_requests"] if r["status"] == "pending"]


def approve_redemption(data, request_id):
    request = next((r for r in data["redemption_requests"] if r["id"] == request_id), None)
    if request is None or request["status"] != "pending":
        raise ValueError("Request not found or already resolved.")

    kid = get_kid(data, request["kid_id"])
    if kid["spendable_xp"] < request["xp_cost"]:
        raise ValueError("Kid no longer has enough XP for this request.")

    kid["spendable_xp"] -= request["xp_cost"]
    request["status"] = "approved"
    return request


def deny_redemption(data, request_id):
    request = next((r for r in data["redemption_requests"] if r["id"] == request_id), None)
    if request is None or request["status"] != "pending":
        raise ValueError("Request not found or already resolved.")

    request["status"] = "denied"
    return request


# ---------------------------------------------------------------------------
# Activity feed — pulls a human-readable event out of every kind of record
# ---------------------------------------------------------------------------

def get_activity_feed(data, limit=20):
    """Combine chores, reports, badges, and requests into one feed,
    newest first. Each source list already exists for its own reason
    (chore_log, daily_reports, ...) — this just describes each entry
    in plain English so parents can see everything in one place."""
    events = []

    for log in data["chore_log"]:
        chore = next((c for c in data["chores"] if c["id"] == log["chore_id"]), None)
        kid = get_kid(data, log["kid_id"])
        chore_name = chore["name"] if chore else "a chore"
        kid_name = kid["name"] if kid else "A kid"
        events.append({"date": log["date"], "text": f"{kid_name} completed '{chore_name}' (+{log['xp_awarded']} XP)"})

    for report in data["daily_reports"]:
        kid = get_kid(data, report["kid_id"])
        kid_name = kid["name"] if kid else "A kid"
        events.append({"date": report["date"], "text": f"{kid_name} got a {report['stars']}★ day (+{report['xp_awarded']} XP)"})

    for badge in data["badges_earned"]:
        kid = get_kid(data, badge["kid_id"])
        kid_name = kid["name"] if kid else "A kid"
        info = BADGE_INFO[badge["name"]]
        reward = f"+{badge['amount']} XP" if badge["unit"] == "xp" else f"+{badge['amount']} Level"
        events.append({"date": badge["date"], "text": f"{kid_name} earned {info['emoji']} {info['label']} ({reward})"})

    for req in data["conversion_requests"]:
        kid = get_kid(data, req["kid_id"])
        kid_name = kid["name"] if kid else "A kid"
        events.append({
            "date": req["date_requested"],
            "text": f"{kid_name} requested to convert {req['credits_requested']} credits ({req['status']})",
        })

    for req in data["redemption_requests"]:
        kid = get_kid(data, req["kid_id"])
        kid_name = kid["name"] if kid else "A kid"
        events.append({
            "date": req["date_requested"],
            "text": f"{kid_name} requested '{req['item_name']}' from the Store ({req['status']})",
        })

    for req in data["chore_completion_requests"]:
        kid = get_kid(data, req["kid_id"])
        kid_name = kid["name"] if kid else "A kid"
        chore = next((c for c in data["chores"] if c["id"] == req["chore_id"]), None)
        chore_name = chore["name"] if chore else "a chore"
        events.append({
            "date": req["date_requested"],
            "text": f"{kid_name} asked for approval on '{chore_name}' ({req['status']})",
        })

    events.sort(key=lambda e: e["date"], reverse=True)
    return events[:limit]


# ---------------------------------------------------------------------------
# Disputes — a kid can flag a report rating they disagree with
# ---------------------------------------------------------------------------

def file_dispute(data, kid_id, report_date, note):
    if not has_report_for_date(data, kid_id, report_date):
        raise ValueError("No report exists for that date.")
    if any(
        d["kid_id"] == kid_id and d["report_date"] == report_date and d["status"] == "open"
        for d in data["disputes"]
    ):
        raise ValueError("There's already an open dispute for that report.")

    dispute = {
        "id": storage.next_id(data, "dispute"),
        "kid_id": kid_id,
        "report_date": report_date,
        "note": note,
        "status": "open",
        "date_filed": date_cls.today().isoformat(),
    }
    data["disputes"].append(dispute)
    return dispute


def get_open_disputes(data):
    return [d for d in data["disputes"] if d["status"] == "open"]


def resolve_dispute(data, dispute_id):
    dispute = next((d for d in data["disputes"] if d["id"] == dispute_id), None)
    if dispute is None:
        raise ValueError("Dispute not found.")
    dispute["status"] = "resolved"
    return dispute
