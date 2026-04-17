#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check existing users"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()

from api.database import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()
cursor.execute("SELECT id, email, name FROM employee_login_info")
users = cursor.fetchall()

print("Existing users:")
print("-" * 50)
if users:
    for u in users:
        name = u["name"] or ""
        if name:
            # Try to encode, if fails use repr
            try:
                name.encode("ascii")
            except UnicodeEncodeError:
                name = repr(name)[1:-1]  # Remove quotes
        print(f"  ID: {u['id']}, Email: {u['email']}, Name: {name}")
else:
    print("  No users found")
print("-" * 50)

conn.close()
