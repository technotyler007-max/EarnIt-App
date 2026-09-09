"""
Handles reading and writing the app's data to a self-hosted MySQL database,
so every family — and every device that family uses — sees the same data.

Every family gets its own row in the `families` table. Each row's `data`
column holds one big JSON blob with everything that family's EarnIt
instance knows (kids, chores, reports, requests, avatar images, all of
it) — the exact same shape core.py has always worked with. That's the key
trick that makes multi-family support possible without changing any of
the game-logic code: core.py never finds out there's more than one
family, it just gets handed "a data dict" to work on. This file's only
job is figuring out *which* family's row that dict comes from.
"""

import base64
import json

import mysql.connector
import streamlit as st

# What a brand-new family's EarnIt data looks like before any kids/chores exist.
DEFAULT_DATA = {
    "kids": [],
    "chores": [],
    "chore_log": [],
    "chore_completion_requests": [],
    "daily_reports": [],
    "conversion_requests": [],
    "badges_earned": [],
    "xp_grants": [],
    "store_items": [],
    "redemption_requests": [],
    "parents": [],
    "disputes": [],
    "avatar_files": {},  # filename -> base64-encoded image bytes
    "next_id": 1,
}


def _connect():
    return mysql.connector.connect(
        host=st.secrets["mysql_host"],
        port=st.secrets["mysql_port"],
        user=st.secrets["mysql_user"],
        password=st.secrets["mysql_password"],
        database=st.secrets["mysql_database"],
    )


def _migrate(data):
    """If the app has grown new fields since this blob was last saved (e.g. we
    just added achievements), fill in the missing ones instead of crashing."""
    for key, default_value in DEFAULT_DATA.items():
        data.setdefault(key, default_value)
    for kid in data["kids"]:
        kid.setdefault("achievements_awarded", {})
        kid.setdefault("milestones_awarded", {})
        kid.setdefault("spendable_xp", kid.get("xp", 0))
        kid.setdefault("pin", "0000")  # kids created before PIN login existed
        kid.setdefault("avatar_file", None)
    for parent in data["parents"]:
        parent.setdefault("role", "admin")
        if "email" not in parent and "name" in parent:
            parent["email"] = parent.pop("name")  # parents used to have a chosen name, not email
        parent.setdefault("email", "unknown@example.com")
    return data


def find_family_by_name(name):
    """Look up a family by name (case-insensitive exact match).

    Used for both login (does this family exist?) and signup (is this name
    already taken?) — family names must be unique, since login works by
    typing your family's name directly rather than picking from a visible
    list of everyone using the app.
    """
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM families WHERE LOWER(name) = LOWER(%s)", (name,))
        row = cursor.fetchone()
        return {"id": row[0], "name": row[1]} if row else None
    finally:
        conn.close()


def create_family(name):
    """Start a brand-new, empty family and return its id.

    Deliberately doesn't add a first parent here — that's core.py's job
    (core.add_parent), done by the caller right after this, the same
    load-mutate-save pattern used everywhere else in the app.
    """
    fresh = json.loads(json.dumps(DEFAULT_DATA))  # a fresh copy
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO families (name, data) VALUES (%s, %s)",
            (name, json.dumps(fresh)),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def load(family_id):
    """Fetch one family's data blob and return it as a Python dict."""
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT data FROM families WHERE id = %s", (family_id,))
        row = cursor.fetchone()
        if row is None:
            raise ValueError(f"No family with id {family_id}.")
        data = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        return _migrate(data)
    finally:
        conn.close()


def save(family_id, data):
    """Write the given dict back out as this family's data blob."""
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE families SET data = %s WHERE id = %s",
            (json.dumps(data), family_id),
        )
        conn.commit()
    finally:
        conn.close()


def next_id(data, prefix):
    """Generate a simple unique id like 'kid_1', 'chore_2', etc."""
    new_id = f"{prefix}_{data['next_id']}"
    data["next_id"] += 1
    return new_id


def export_json(data):
    """A human-readable dump of everything a family's EarnIt knows, for a parent to download."""
    return json.dumps(data, indent=2)


def blank_slate():
    """A fresh copy of an empty family's data — used when a parent wipes their own family's data."""
    return json.loads(json.dumps(DEFAULT_DATA))


def save_avatar(data, kid_id, file_bytes, extension):
    """Store an uploaded avatar image (as base64 text) inside the data blob and return its filename."""
    filename = f"{kid_id}.{extension}"
    data["avatar_files"][filename] = base64.b64encode(file_bytes).decode("ascii")
    return filename


def avatar_bytes(data, filename):
    """Decode a stored avatar back into raw image bytes for st.image()."""
    encoded = data["avatar_files"].get(filename)
    return base64.b64decode(encoded) if encoded else None


def remove_avatar(data, filename):
    """Delete a stored avatar image from the data blob."""
    data["avatar_files"].pop(filename, None)
