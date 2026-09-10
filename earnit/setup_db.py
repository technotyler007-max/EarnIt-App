"""
One-time script to create the `families` table on a fresh MySQL database
(e.g. the Aiven cloud database used for deploying EarnIt). Run this once
after creating the database, before the app is used for the first time.

Prompts for the password at the terminal instead of taking it as an
argument, so it never ends up in shell history or anywhere else.
"""

import mysql.connector

host = input("Host: ").strip()
port = int(input("Port: ").strip())
user = input("User (e.g. avnadmin): ").strip()
password = input("Password: ").strip()
database = input("Database name (e.g. defaultdb): ").strip()

conn = mysql.connector.connect(host=host, port=port, user=user, password=password, database=database)
try:
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS families (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL UNIQUE,
            data JSON NOT NULL
        )
        """
    )
    conn.commit()
    print("Done -- 'families' table is ready.")
finally:
    conn.close()
