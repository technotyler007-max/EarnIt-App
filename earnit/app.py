"""
EarnIt — the Streamlit app.

This file is just the screens/buttons — all the actual XP/level/credit
rules live in core.py, and all the saving/loading (plus avatar files) lives
in storage.py. Every time something changes, we save() the data and
st.rerun() so the screen reflects the new state.

Login is local-only PIN auth (no real passkeys/servers — see
earnit-phase3-polish.md for why): pick your name, enter your PIN. Parents
also have a role — "admin" can approve/add/delete things, "viewer" can only
look. The very first time the app runs, there are no parents yet, so it
walks you through creating the first (admin) one.
"""

from datetime import date, datetime

import streamlit as st

try:
    from earnit import core, mailer, storage
except ImportError:
    # allows `streamlit run app.py` to work when run from inside earnit/ too
    import core
    import mailer
    import storage

st.set_page_config(page_title="EarnIt", page_icon="⭐")


def save():
    storage.save(st.session_state["family_id"], data)


def show_badge_toasts(badge_names):
    """Pop up a little notification for each newly-earned badge."""
    for name in badge_names:
        info = core.BADGE_INFO[name]
        st.toast(f"{info['emoji']} New badge: {info['label']}!")


# ---------------------------------------------------------------------------
# Email verification — a small reusable "send a code, check a code" helper
# used by both family signup and adding a co-parent, so both spots prove
# someone really owns the email they typed before we trust it.
# ---------------------------------------------------------------------------

def request_email_verification(session_key, email):
    """Generate a code, email it, and remember it in session_state (tied to
    this browser session only) so verify_email_code() can check against it."""
    code = mailer.generate_code()
    mailer.send_verification_email(email, code)
    st.session_state[session_key] = {"email": email, "code": code, "sent_at": datetime.now()}


def verify_email_code(session_key, entered_code):
    """Check entered_code against the pending verification. Returns (ok, message)."""
    pending = st.session_state.get(session_key)
    if not pending:
        return False, "Nothing to verify — request a new code."
    age_minutes = (datetime.now() - pending["sent_at"]).total_seconds() / 60
    if age_minutes > mailer.CODE_EXPIRY_MINUTES:
        return False, "That code expired. Request a new one."
    if entered_code.strip() != pending["code"]:
        return False, "Wrong code."
    return True, "Verified!"


# ---------------------------------------------------------------------------
# Family gate — every family's data is completely separate (see storage.py:
# one row per family). Nothing else in this app runs until a family is
# chosen, the same way nothing in Kid/Parent mode runs until a PIN is
# entered below.
# ---------------------------------------------------------------------------

def family_gate():
    """Sign up a new family or log into an existing one.

    Returns True once a family is selected (and sets it in session_state).
    Shows a sign-up/log-in screen and returns False otherwise.
    """
    if st.session_state.get("family_id"):
        return True

    st.title("⭐ EarnIt")
    st.caption("Chores & rewards, for your whole family.")
    choice = st.radio("Get started", ["Log in to my family", "Sign up a new family"])

    if choice == "Sign up a new family":
        pending = st.session_state.get("signup_verification")

        if not pending:
            family_name = st.text_input("Family name (e.g. 'Parker')", key="signup_family_name")
            parent_email = st.text_input("Your email", key="signup_parent_email")
            parent_pin = st.text_input("Choose a PIN", type="password", key="signup_parent_pin")
            if (
                st.button("Send verification code")
                and family_name.strip() and parent_email.strip() and parent_pin.strip()
            ):
                if not core.is_valid_email(parent_email):
                    st.error("That doesn't look like a valid email address.")
                elif storage.find_family_by_name(family_name.strip()):
                    st.error(
                        f"A family named '{family_name.strip()}' already exists. "
                        "Try logging in instead, or pick a different family name."
                    )
                else:
                    try:
                        request_email_verification("signup_verification", parent_email.strip())
                        st.session_state["signup_draft"] = {
                            "family_name": family_name.strip(),
                            "email": parent_email.strip(),
                            "pin": parent_pin.strip(),
                        }
                        st.rerun()
                    except Exception:
                        st.error(
                            "Couldn't send the verification email. The app's email setup "
                            "might not be configured yet — see earnit-phase4-platform.md."
                        )
        else:
            draft = st.session_state["signup_draft"]
            st.info(f"We emailed a 6-digit code to {draft['email']}. Enter it below to finish signing up.")
            code_input = st.text_input("Verification code", key="signup_code_input")
            cols = st.columns(2)
            if cols[0].button("Verify & create family"):
                ok, message = verify_email_code("signup_verification", code_input)
                if not ok:
                    st.error(message)
                else:
                    family_id = storage.create_family(draft["family_name"])
                    new_data = storage.load(family_id)
                    parent = core.add_parent(new_data, draft["email"], draft["pin"], "admin")
                    storage.save(family_id, new_data)
                    st.session_state["family_id"] = family_id
                    st.session_state["family_name"] = draft["family_name"]
                    st.session_state["authenticated_parent_id"] = parent["id"]
                    st.session_state.pop("signup_verification", None)
                    st.session_state.pop("signup_draft", None)
                    st.rerun()
            if cols[1].button("Resend code"):
                request_email_verification("signup_verification", draft["email"])
                st.rerun()
            if st.button("Start over"):
                st.session_state.pop("signup_verification", None)
                st.session_state.pop("signup_draft", None)
                st.rerun()
    else:
        family_name_input = st.text_input("Your family's name")
        if st.button("Continue") and family_name_input.strip():
            match = storage.find_family_by_name(family_name_input.strip())
            if match is None:
                st.error("No family found with that name. Check the spelling, or sign up if you're new.")
            else:
                st.session_state["family_id"] = match["id"]
                st.session_state["family_name"] = match["name"]
                st.rerun()

    return False


# ---------------------------------------------------------------------------
# Login gates — each returns the logged-in kid/parent dict, or None if a
# login form is currently being shown (caller should just stop rendering).
# ---------------------------------------------------------------------------

def kid_login_gate():
    if not data["kids"]:
        st.info("No kid profiles yet — ask a parent to add one in Parent mode.")
        return None

    kid_names = {k["name"]: k["id"] for k in data["kids"]}
    chosen_name = st.sidebar.selectbox("Which kid are you?", list(kid_names.keys()), key="kid_picker")
    chosen_id = kid_names[chosen_name]

    if st.session_state.get("authenticated_kid_id") != chosen_id:
        st.header(f"🔒 Enter {chosen_name}'s PIN")
        pin = st.text_input("PIN", type="password", key="kid_pin_input")
        if st.button("Log in", key="kid_login_button"):
            if core.verify_kid_pin(data, chosen_id, pin):
                st.session_state["authenticated_kid_id"] = chosen_id
                st.rerun()
            else:
                st.error("Wrong PIN.")
        return None

    if st.sidebar.button("Log out", key="kid_logout"):
        st.session_state["authenticated_kid_id"] = None
        st.rerun()

    return core.get_kid(data, chosen_id)


def parent_login_gate():
    if not data["parents"]:
        # Only reachable right after a full family data wipe (Fam > Danger
        # Zone) -- normally family_gate() already creates the first parent
        # at signup.
        st.header("👪 Set up the first parent account")
        st.caption("One-time setup for this family — this becomes an admin account.")
        email = st.text_input("Your email", key="setup_parent_email")
        pin = st.text_input("Choose a PIN", type="password", key="setup_parent_pin")
        if st.button("Create account", key="setup_parent_button") and email.strip() and pin.strip():
            parent = core.add_parent(data, email.strip(), pin.strip(), "admin")
            save()
            st.session_state["authenticated_parent_id"] = parent["id"]
            st.rerun()
        return None

    parent_emails = {p["email"]: p["id"] for p in data["parents"]}
    chosen_email = st.sidebar.selectbox("Which parent are you?", list(parent_emails.keys()), key="parent_picker")
    chosen_id = parent_emails[chosen_email]

    if st.session_state.get("authenticated_parent_id") != chosen_id:
        st.header(f"🔒 Enter {chosen_email}'s PIN")
        pin = st.text_input("PIN", type="password", key="parent_pin_input")
        if st.button("Log in", key="parent_login_button"):
            if core.verify_parent_pin(data, chosen_id, pin):
                st.session_state["authenticated_parent_id"] = chosen_id
                st.rerun()
            else:
                st.error("Wrong PIN.")
        return None

    if st.sidebar.button("Log out", key="parent_logout"):
        st.session_state["authenticated_parent_id"] = None
        st.rerun()

    return core.get_parent(data, chosen_id)


# ---------------------------------------------------------------------------
# KID MODE
# ---------------------------------------------------------------------------

def kid_screen(kid):
    st.header("⭐ My Rewards & Progress")

    xp_into_level = kid["xp"] % core.XP_PER_LEVEL
    st.subheader(f"Level {kid['level']}")
    st.progress(xp_into_level / core.XP_PER_LEVEL)
    st.caption(f"{xp_into_level} / {core.XP_PER_LEVEL} XP to next level")

    col1, col2, col3 = st.columns(3)
    col1.metric("Lifetime XP", kid["xp"])
    col2.metric("Spendable XP", kid["spendable_xp"])
    col3.metric("Credits", kid["credits"])
    st.caption("Spendable XP is what you can use in the Store — spending it doesn't affect your Level.")

    st.divider()
    st.subheader("📬 Unclaimed XP")
    unclaimed = core.get_unclaimed_grants(data, kid["id"])
    if not unclaimed:
        st.caption("Nothing waiting — go earn some XP!")
    else:
        st.caption("XP you've earned but haven't claimed yet. Claim it before it expires!")
        for grant in sorted(unclaimed, key=lambda g: g["date_earned"]):
            days_left = core.days_until_expiry(grant)
            warning = " ⚠️ expires today!" if days_left <= 0 else f" (expires in {days_left} day{'s' if days_left != 1 else ''})"
            st.write(f"+{grant['amount']} XP — {grant['source']}{warning}")
        total_unclaimed = core.get_unclaimed_total(data, kid["id"])
        if st.button(f"Claim {total_unclaimed} XP"):
            core.claim_xp(data, kid["id"])
            save()
            st.rerun()

    st.divider()
    st.subheader("🏅 Badge Wall")
    kid_badges = [b for b in data["badges_earned"] if b["kid_id"] == kid["id"]]
    if not kid_badges:
        st.caption("No badges yet — keep it up!")
    else:
        for b in sorted(kid_badges, key=lambda x: x["date"], reverse=True):
            info = core.BADGE_INFO[b["name"]]
            reward = f"+{b['amount']} XP" if b["unit"] == "xp" else f"+{b['amount']} Level"
            st.write(f"{info['emoji']} **{info['label']}** — {reward}  ({b['date']})")

    st.divider()
    st.subheader("My Recent Reports")
    my_reports = sorted(
        [r for r in data["daily_reports"] if r["kid_id"] == kid["id"]],
        key=lambda r: r["date"], reverse=True,
    )[:7]
    if not my_reports:
        st.caption("No reports filed yet.")
    open_dispute_dates = {
        d["report_date"] for d in data["disputes"]
        if d["kid_id"] == kid["id"] and d["status"] == "open"
    }
    for report in my_reports:
        cols = st.columns([3, 1])
        cols[0].write(f"{report['date']} — {'⭐' * report['stars']}")
        if report["date"] in open_dispute_dates:
            cols[1].caption("Dispute pending")
        elif cols[1].button("Dispute", key=f"dispute_{report['date']}"):
            st.session_state["disputing_date"] = report["date"]
    if st.session_state.get("disputing_date"):
        with st.form(key="dispute_form"):
            st.write(f"Why do you disagree with the rating on {st.session_state['disputing_date']}?")
            note = st.text_area("Explain here")
            if st.form_submit_button("Send to parent") and note.strip():
                core.file_dispute(data, kid["id"], st.session_state["disputing_date"], note.strip())
                save()
                st.session_state["disputing_date"] = None
                st.success("Sent!")
                st.rerun()

    st.divider()
    st.subheader("Convert Credits to Bucks")
    st.caption("This sends a request to your parent for approval.")
    already_pending_credits = core.get_pending_credits_requested(data, kid["id"])
    available_credits = kid["credits"] - already_pending_credits
    if already_pending_credits:
        st.caption(f"({already_pending_credits} credits already tied up in a pending request)")
    if available_credits < 1:
        st.caption("You don't have any credits available to convert right now.")
    else:
        amount = st.number_input(
            "How many credits?", min_value=1, max_value=available_credits, step=1
        )
        if st.button("Request conversion"):
            core.request_conversion(data, kid["id"], amount)
            save()
            st.success("Request sent! Waiting for parent approval.")
            st.rerun()


def kid_chores_screen(kid):
    st.header("🧹 Chores")
    st.caption("Marking a chore done sends it to your parent for approval before you get any XP.")

    today = date.today().isoformat()
    chores = core.get_chores_for_kid(data, kid["id"])
    if not chores:
        st.caption("No chores assigned yet.")
    for chore in chores:
        done = core.is_chore_done_on(data, chore["id"], today)
        pending = core.is_chore_request_pending(data, chore["id"], today)
        cols = st.columns([3, 1])
        if done:
            status = "✅"
        elif pending:
            status = "⏳"
        else:
            status = "⬜"
        cols[0].write(f"{status} {chore['name']} — {chore['xp_value']} XP")
        if pending:
            cols[1].caption("Waiting on parent")
        elif not done:
            if cols[1].button("Mark done", key=f"done_{chore['id']}"):
                core.request_chore_completion(data, chore["id"], today)
                save()
                st.success("Sent to your parent for approval!")
                st.rerun()


def kid_store_screen(kid):
    st.header("🛍️ Store")

    st.metric("Spendable XP", kid["spendable_xp"])
    already_pending_xp = core.get_pending_xp_requested(data, kid["id"])
    available_xp = kid["spendable_xp"] - already_pending_xp
    if already_pending_xp:
        st.caption(f"({already_pending_xp} XP already tied up in pending requests)")
    st.divider()

    if not data["store_items"]:
        st.caption("No rewards in the Store yet — ask a parent to add some.")
    else:
        for item in data["store_items"]:
            cols = st.columns([3, 1])
            with cols[0]:
                st.write(f"**{item['name']}** — {item['xp_cost']} XP")
                st.caption(item["description"])
            can_afford = available_xp >= item["xp_cost"]
            if cols[1].button("Redeem", key=f"redeem_{item['id']}", disabled=not can_afford):
                core.request_redemption(data, kid["id"], item["id"])
                save()
                st.success("Requested! Waiting for parent approval.")
                st.rerun()

    st.divider()
    st.subheader("🛒 My Purchases")
    my_purchases = sorted(
        [
            r for r in data["redemption_requests"]
            if r["kid_id"] == kid["id"] and r["status"] == "approved"
        ],
        key=lambda r: r["date_requested"],
        reverse=True,
    )
    if not my_purchases:
        st.caption("Nothing bought yet.")
    else:
        for r in my_purchases:
            st.write(f"✅ **{r['item_name']}** — {r['xp_cost']} XP ({r['date_requested']})")


def kid_account_screen(kid):
    st.header("🙂 My Account")

    st.subheader("Avatar")
    if kid.get("avatar_file"):
        st.image(storage.avatar_bytes(data, kid["avatar_file"]), width=150)
        if st.button("Remove avatar"):
            storage.remove_avatar(data, kid["avatar_file"])
            kid["avatar_file"] = None
            save()
            st.rerun()
    else:
        st.caption("No avatar yet.")
    uploaded = st.file_uploader("Upload a new avatar", type=["png", "jpg", "jpeg"])
    if uploaded is not None and st.button("Save avatar"):
        extension = uploaded.name.rsplit(".", 1)[-1].lower()
        filename = storage.save_avatar(data, kid["id"], uploaded.getvalue(), extension)
        kid["avatar_file"] = filename
        save()
        st.rerun()

    st.divider()
    st.subheader("Change My PIN")
    with st.form(key="change_kid_pin"):
        current = st.text_input("Current PIN", type="password")
        new = st.text_input("New PIN", type="password")
        confirm = st.text_input("Confirm new PIN", type="password")
        if st.form_submit_button("Change PIN"):
            if not core.verify_kid_pin(data, kid["id"], current):
                st.error("Current PIN is wrong.")
            elif new != confirm or not new.strip():
                st.error("New PINs don't match (or are empty).")
            else:
                core.set_kid_pin(data, kid["id"], new.strip())
                save()
                st.success("PIN changed!")


# ---------------------------------------------------------------------------
# PARENT MODE
# ---------------------------------------------------------------------------

def parent_kids_accounts(can_edit):
    st.header("👪 Kids Accounts")

    if datetime.now().hour >= 17:
        missing = core.get_kids_missing_report(data)
        if missing:
            names = ", ".join(k["name"] for k in missing)
            st.warning(f"⏰ It's past 5pm — you still need to file today's report for: {names}")

    with st.expander("Add a new kid"):
        # Widget values can only be reset *before* the widget is created on a
        # given run, so this has to happen here, ahead of the text_inputs below.
        if st.session_state.pop("_clear_new_kid_form", False):
            st.session_state["new_kid_name"] = ""
            st.session_state["new_kid_pin"] = ""
            st.session_state["confirm_dup_kid"] = False

        new_name = st.text_input("Kid's name", key="new_kid_name")
        new_pin = st.text_input("Kid's PIN (they'll use this to log in)", key="new_kid_pin")
        existing_names = {k["name"].strip().lower() for k in data["kids"]}
        is_duplicate = bool(new_name.strip()) and new_name.strip().lower() in existing_names

        confirm_duplicate = True
        if is_duplicate:
            st.warning(
                f"A kid named '{new_name.strip()}' already exists. "
                "Adding another will create a second, separate profile."
            )
            confirm_duplicate = st.checkbox(
                "Yes, add another kid with this name anyway", key="confirm_dup_kid"
            )

        if not can_edit:
            st.caption("View-only — ask an admin parent to add kids.")
        if st.button("Add kid", disabled=not can_edit) and new_name.strip() and new_pin.strip() and confirm_duplicate:
            core.add_kid(data, new_name.strip(), new_pin.strip())
            save()
            st.session_state["_clear_new_kid_form"] = True
            st.rerun()

    if not data["kids"]:
        st.info("No kids yet — add one above.")
        return

    for kid in data["kids"]:
        unclaimed_total = core.get_unclaimed_total(data, kid["id"])
        unclaimed_note = f", {unclaimed_total} XP unclaimed" if unclaimed_total else ""
        with st.expander(
            f"{kid['name']} — Level {kid['level']}, {kid['xp']} lifetime XP "
            f"({kid['spendable_xp']} spendable), {kid['credits']} credits{unclaimed_note}"
        ):
            today = date.today().isoformat()
            st.write("**Today's Behavior Report**")
            if core.has_report_for_date(data, kid["id"], today):
                st.caption(f"Already filed for {today}.")
                if st.button("Undo today's report", key=f"undo_report_{kid['id']}", disabled=not can_edit):
                    clean = core.undo_daily_report(data, kid["id"], today)
                    save()
                    if not clean:
                        st.warning("That XP was already claimed, so it wasn't automatically removed.")
                    st.rerun()
            else:
                stars = st.slider(
                    "Stars for today", 1, 5, 3, key=f"stars_{kid['id']}"
                )
                if st.button("File today's report", key=f"file_{kid['id']}", disabled=not can_edit):
                    result = core.file_daily_report(data, kid["id"], stars, today)
                    save()
                    show_badge_toasts(result["badges"])
                    st.rerun()

            with st.expander("File a late/backdated report"):
                back_date = st.date_input(
                    "Date", value=date.today(), key=f"backdate_{kid['id']}"
                )
                back_stars = st.slider(
                    "Stars", 1, 5, 3, key=f"backstars_{kid['id']}"
                )
                if st.button("File backdated report", key=f"fileback_{kid['id']}", disabled=not can_edit):
                    try:
                        result = core.file_daily_report(
                            data, kid["id"], back_stars, back_date.isoformat()
                        )
                        save()
                        show_badge_toasts(result["badges"])
                        st.success("Filed.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

            st.divider()
            st.write("**Reset PIN**")
            new_kid_pin = st.text_input("New PIN", key=f"reset_pin_{kid['id']}")
            if st.button("Reset PIN", key=f"reset_pin_button_{kid['id']}", disabled=not can_edit) and new_kid_pin.strip():
                core.set_kid_pin(data, kid["id"], new_kid_pin.strip())
                save()
                st.success("PIN reset.")

            st.divider()
            st.write("**Delete this profile**")
            confirm = st.checkbox(
                f"Yes, permanently delete {kid['name']} and all their chores/history",
                key=f"confirm_del_{kid['id']}",
            )
            if confirm and st.button(f"Delete {kid['name']}", key=f"delete_{kid['id']}", disabled=not can_edit):
                core.delete_kid(data, kid["id"])
                save()
                st.rerun()


def parent_chores(can_edit):
    st.header("🧹 Chores")

    st.subheader("Pending Chore Completions")
    pending_chores = core.get_pending_chore_requests(data)
    if not pending_chores:
        st.caption("No chores waiting on approval.")
    for req in pending_chores:
        kid = core.get_kid(data, req["kid_id"])
        chore = next((c for c in data["chores"] if c["id"] == req["chore_id"]), None)
        cols = st.columns([3, 1, 1])
        cols[0].write(
            f"**{kid['name'] if kid else '?'}** says they did "
            f"**{chore['name'] if chore else 'a chore'}** ({req['date']})"
        )
        if cols[1].button("Approve", key=f"approve_chore_{req['id']}", disabled=not can_edit):
            result = core.approve_chore_completion(data, req["id"])
            save()
            show_badge_toasts(result["badges"])
            st.rerun()
        if cols[2].button("Deny", key=f"deny_chore_{req['id']}", disabled=not can_edit):
            core.deny_chore_completion(data, req["id"])
            save()
            st.rerun()

    st.divider()
    if not data["kids"]:
        st.info("No kids yet — add one in Kids Accounts.")
        return

    today = date.today().isoformat()
    for kid in data["kids"]:
        with st.expander(f"{kid['name']}'s chores"):
            chores = core.get_chores_for_kid(data, kid["id"])
            if chores:
                for c in chores:
                    cols = st.columns([3, 1, 1])
                    cols[0].write(f"- {c['name']} ({c['xp_value']} XP)")
                    if core.is_chore_done_on(data, c["id"], today):
                        if cols[1].button("Undo today", key=f"undo_chore_{c['id']}", disabled=not can_edit):
                            clean = core.undo_chore_completion(data, c["id"], today)
                            save()
                            if not clean:
                                st.warning("That XP was already claimed, so it wasn't automatically removed.")
                            st.rerun()
                    if cols[2].button("Delete", key=f"delete_chore_{c['id']}", disabled=not can_edit):
                        core.delete_chore(data, c["id"])
                        save()
                        st.rerun()
            else:
                st.caption("No chores assigned yet.")

            with st.form(key=f"add_chore_{kid['id']}", clear_on_submit=True):
                chore_name = st.text_input("New chore name")
                chore_xp = st.number_input("XP value", min_value=1, step=1, value=5)
                submitted = st.form_submit_button("Add chore", disabled=not can_edit)
                if submitted and chore_name.strip():
                    core.add_chore(data, chore_name.strip(), int(chore_xp), kid["id"])
                    save()
                    st.rerun()


def parent_kid_rewarding(can_edit):
    st.header("🏆 Kid Rewarding")

    st.subheader("Activity Feed")
    feed = core.get_activity_feed(data)
    if not feed:
        st.caption("Nothing has happened yet.")
    else:
        for event in feed:
            st.write(f"`{event['date']}` — {event['text']}")

    st.divider()
    st.subheader("Pending Conversion Requests")
    pending = core.get_pending_requests(data)
    if not pending:
        st.caption("No pending requests.")
    for req in pending:
        kid = core.get_kid(data, req["kid_id"])
        cols = st.columns([3, 1, 1])
        cols[0].write(
            f"**{kid['name']}** wants to convert **{req['credits_requested']} credits** "
            f"→ **${req['credits_requested']}** (requested {req['date_requested']})"
        )
        if cols[1].button("Approve", key=f"approve_{req['id']}", disabled=not can_edit):
            core.approve_conversion(data, req["id"])
            save()
            st.rerun()
        if cols[2].button("Deny", key=f"deny_{req['id']}", disabled=not can_edit):
            core.deny_conversion(data, req["id"])
            save()
            st.rerun()

    st.divider()
    st.subheader("Pending Store Redemptions")
    pending_redemptions = core.get_pending_redemptions(data)
    if not pending_redemptions:
        st.caption("No pending redemptions.")
    for req in pending_redemptions:
        kid = core.get_kid(data, req["kid_id"])
        cols = st.columns([3, 1, 1])
        cols[0].write(
            f"**{kid['name']}** wants to redeem **{req['item_name']}** "
            f"for **{req['xp_cost']} XP** (requested {req['date_requested']})"
        )
        if cols[1].button("Approve", key=f"approve_redeem_{req['id']}", disabled=not can_edit):
            core.approve_redemption(data, req["id"])
            save()
            st.rerun()
        if cols[2].button("Deny", key=f"deny_redeem_{req['id']}", disabled=not can_edit):
            core.deny_redemption(data, req["id"])
            save()
            st.rerun()

    st.divider()
    st.subheader("Open Disputes")
    open_disputes = core.get_open_disputes(data)
    if not open_disputes:
        st.caption("No open disputes.")
    for dispute in open_disputes:
        kid = core.get_kid(data, dispute["kid_id"])
        cols = st.columns([3, 1])
        cols[0].write(
            f"**{kid['name']}** disputes the report from {dispute['report_date']}: \"{dispute['note']}\""
        )
        if cols[1].button("Mark resolved", key=f"resolve_{dispute['id']}", disabled=not can_edit):
            core.resolve_dispute(data, dispute["id"])
            save()
            st.rerun()


def parent_store(can_edit):
    st.header("🛍️ Store Management")

    with st.expander("Add a new reward"):
        if st.session_state.pop("_clear_new_item_form", False):
            st.session_state["new_item_name"] = ""
            st.session_state["new_item_description"] = ""
            st.session_state["new_item_cost"] = 10

        name = st.text_input("Reward name", key="new_item_name")
        description = st.text_area("Description", key="new_item_description")
        xp_cost = st.number_input("XP cost", min_value=1, step=1, value=10, key="new_item_cost")
        if st.button("Add reward", disabled=not can_edit) and name.strip():
            core.add_store_item(data, name.strip(), description.strip(), int(xp_cost))
            save()
            st.session_state["_clear_new_item_form"] = True
            st.rerun()

    if not data["store_items"]:
        st.info("No rewards yet — add one above.")
        return

    for item in data["store_items"]:
        with st.expander(f"{item['name']} — {item['xp_cost']} XP"):
            new_name = st.text_input("Name", value=item["name"], key=f"edit_name_{item['id']}")
            new_desc = st.text_area("Description", value=item["description"], key=f"edit_desc_{item['id']}")
            new_cost = st.number_input(
                "XP cost", min_value=1, step=1, value=item["xp_cost"], key=f"edit_cost_{item['id']}"
            )
            cols = st.columns(2)
            if cols[0].button("Save changes", key=f"save_item_{item['id']}", disabled=not can_edit):
                core.update_store_item(data, item["id"], new_name.strip(), new_desc.strip(), int(new_cost))
                save()
                st.rerun()
            if cols[1].button("Delete reward", key=f"delete_item_{item['id']}", disabled=not can_edit):
                core.delete_store_item(data, item["id"])
                save()
                st.rerun()


def parent_fam(current_parent, can_edit):
    st.header("👨‍👩‍👧 Fam")
    st.caption(
        "Everyone with access to this family's EarnIt data — other families on this app "
        "can never see this list. Login is by email, so this is also how a parent is told "
        "apart from a co-parent; casual screens elsewhere just say 'Parent.' Roles separate "
        "'can approve/change things' (admin) from 'can only look' (viewer)."
    )

    for parent in data["parents"]:
        you_tag = " (you)" if parent["id"] == current_parent["id"] else ""
        st.write(f"**{parent['email']}**{you_tag} — {parent['role']}")

    st.divider()
    with st.expander("Add a parent"):
        pending_add = st.session_state.get("add_parent_verification")

        if not pending_add:
            if st.session_state.pop("_clear_new_parent_form", False):
                st.session_state["new_parent_email"] = ""
                st.session_state["new_parent_pin"] = ""
                st.session_state["new_parent_role"] = core.PARENT_ROLES[0]

            email = st.text_input("Email", key="new_parent_email")
            pin = st.text_input("PIN", type="password", key="new_parent_pin")
            role = st.selectbox("Role", core.PARENT_ROLES, key="new_parent_role")
            if st.button("Send verification code", key="send_add_parent_code", disabled=not can_edit) and email.strip() and pin.strip():
                if not core.is_valid_email(email):
                    st.error("That doesn't look like a valid email address.")
                elif any(p["email"].strip().lower() == email.strip().lower() for p in data["parents"]):
                    st.error(f"A parent with email '{email.strip()}' already exists in this family.")
                else:
                    try:
                        request_email_verification("add_parent_verification", email.strip())
                        st.session_state["add_parent_draft"] = {
                            "email": email.strip(), "pin": pin.strip(), "role": role,
                        }
                        st.rerun()
                    except Exception:
                        st.error("Couldn't send the verification email. Check the email setup.")
        else:
            draft = st.session_state["add_parent_draft"]
            st.info(f"We emailed a 6-digit code to {draft['email']}. Enter it below to finish adding them.")
            code_input = st.text_input("Verification code", key="add_parent_code_input")
            cols = st.columns(2)
            if cols[0].button("Verify & add parent", disabled=not can_edit):
                ok, message = verify_email_code("add_parent_verification", code_input)
                if not ok:
                    st.error(message)
                else:
                    try:
                        core.add_parent(data, draft["email"], draft["pin"], draft["role"])
                        save()
                        st.session_state.pop("add_parent_verification", None)
                        st.session_state.pop("add_parent_draft", None)
                        st.session_state["_clear_new_parent_form"] = True
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
            if cols[1].button("Resend code", key="resend_add_parent_code", disabled=not can_edit):
                request_email_verification("add_parent_verification", draft["email"])
                st.rerun()
            if st.button("Start over", key="cancel_add_parent"):
                st.session_state.pop("add_parent_verification", None)
                st.session_state.pop("add_parent_draft", None)
                st.session_state["_clear_new_parent_form"] = True
                st.rerun()

    with st.expander("Reset a parent's PIN"):
        parent_emails = {p["email"]: p["id"] for p in data["parents"]}
        chosen = st.selectbox("Parent", list(parent_emails.keys()), key="reset_parent_choice")
        new_pin = st.text_input("New PIN", type="password", key="reset_parent_pin")
        if st.button("Reset PIN", key="reset_parent_button", disabled=not can_edit) and new_pin.strip():
            core.set_parent_pin(data, parent_emails[chosen], new_pin.strip())
            save()
            st.success("PIN reset.")

    with st.expander("Remove a parent"):
        removable = [p for p in data["parents"] if p["id"] != current_parent["id"]]
        if not removable:
            st.caption("No other parents to remove.")
        else:
            names = {p["email"]: p["id"] for p in removable}
            chosen = st.selectbox("Parent", list(names.keys()), key="remove_parent_choice")
            if st.button("Remove", key="remove_parent_button", disabled=not can_edit):
                try:
                    core.remove_parent(data, names[chosen])
                    save()
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    st.divider()
    st.subheader("⚠️ Danger Zone")
    st.caption(
        "Data retention note: everything EarnIt stores for your family (kids, chores, "
        "reports, XP, badges) lives in this family's own database record — other families "
        "on this app can never see or affect it. Use these tools any time you want a copy "
        "or a clean start for **your family only**."
    )
    st.download_button(
        "Export all data as JSON",
        data=storage.export_json(data),
        file_name="earnit_data_export.json",
        mime="application/json",
        disabled=not can_edit,
    )
    confirm_wipe = st.checkbox(
        "Yes, permanently delete ALL of this family's data (every kid, chore, and record)",
        key="confirm_wipe",
    )
    if st.button("Delete ALL data", disabled=not (can_edit and confirm_wipe)):
        fresh = storage.blank_slate()
        data.clear()
        data.update(fresh)
        save()
        st.session_state.pop("authenticated_kid_id", None)
        st.session_state.pop("authenticated_parent_id", None)
        st.rerun()


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

if not family_gate():
    st.stop()

data = storage.load(st.session_state["family_id"])
if core.sweep_expired_grants(data):
    save()

st.sidebar.title("EarnIt")
st.sidebar.caption(f"Family: **{st.session_state['family_name']}**")
st.sidebar.divider()

mode = st.sidebar.radio("I am a...", ["Parent", "Kid"])
# Switching INTO Parent mode from something else always requires the PIN
# again (still just the normal email+PIN login, no verification code) --
# otherwise a kid handing the device back after using Kid mode could tap
# straight into an already-authenticated parent session.
previous_mode = st.session_state.get("_last_mode")
if previous_mode is not None and previous_mode != mode and mode == "Parent":
    st.session_state["authenticated_parent_id"] = None
st.session_state["_last_mode"] = mode
st.sidebar.divider()

if mode == "Kid":
    kid = kid_login_gate()
    if kid:
        kid_page = st.sidebar.radio("Kid screens", ["Rewards & Progress", "Chores", "Store", "My Account"])
        if kid_page == "Rewards & Progress":
            kid_screen(kid)
        elif kid_page == "Chores":
            kid_chores_screen(kid)
        elif kid_page == "Store":
            kid_store_screen(kid)
        else:
            kid_account_screen(kid)
else:
    parent = parent_login_gate()
    if parent:
        can_edit = parent["role"] == "admin"
        page = st.sidebar.radio("Parent screens", ["Kids Accounts", "Chores", "Kid Rewarding", "Store", "Fam"])
        if page == "Kids Accounts":
            parent_kids_accounts(can_edit)
        elif page == "Chores":
            parent_chores(can_edit)
        elif page == "Kid Rewarding":
            parent_kid_rewarding(can_edit)
        elif page == "Store":
            parent_store(can_edit)
        else:
            parent_fam(parent, can_edit)
