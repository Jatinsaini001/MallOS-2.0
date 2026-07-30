"""
auth.py — Authentication module for MallOS
- SQLite-based users table (separate from MongoDB)
- Password hashing with werkzeug
- Session management helpers
- login_required decorator
"""

import sqlite3
import os
from functools import wraps
from flask import session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash

AUTH_DB = os.path.join(os.path.dirname(__file__), 'users.db')


# ── Database setup ────────────────────────────────────────────────────────────

def init_auth_db():
    """Create users table and seed default accounts if empty."""
    conn = sqlite3.connect(AUTH_DB)
    conn.row_factory = sqlite3.Row
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT    NOT NULL UNIQUE,
            password TEXT    NOT NULL,
            role     TEXT    NOT NULL DEFAULT 'cashier'
                             CHECK(role IN ('admin', 'manager', 'cashier')),
            created_at TEXT  DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

    # Seed default users only if table is empty
    count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    if count == 0:
        defaults = [
            ('admin',   'admin123',   'admin'),
            ('manager', 'manager123', 'manager'),
            ('cashier', 'cashier123', 'cashier'),
        ]
        for username, password, role in defaults:
            conn.execute(
                'INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                (username, generate_password_hash(password), role)
            )
        conn.commit()
        print("[MallOS] Default users created — admin/admin123, manager/manager123, cashier/cashier123")

    conn.close()


def get_db():
    conn = sqlite3.connect(AUTH_DB)
    conn.row_factory = sqlite3.Row
    return conn


# ── Auth helpers ──────────────────────────────────────────────────────────────

def verify_user(username, password):
    """Return user row if credentials valid, else None."""
    conn = get_db()
    user = conn.execute(
        'SELECT * FROM users WHERE username = ?', (username.strip(),)
    ).fetchone()
    conn.close()
    if user and check_password_hash(user['password'], password):
        return user
    return None


def get_all_users():
    conn = get_db()
    users = conn.execute('SELECT id, username, role, created_at FROM users ORDER BY id').fetchall()
    conn.close()
    return users


def create_user(username, password, role):
    """Returns (True, None) or (False, error_message)."""
    try:
        conn = get_db()
        conn.execute(
            'INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
            (username.strip(), generate_password_hash(password), role)
        )
        conn.commit()
        conn.close()
        return True, None
    except sqlite3.IntegrityError:
        return False, f"Username '{username}' already exists."


def delete_user(user_id):
    conn = get_db()
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()


def update_password(user_id, new_password):
    conn = get_db()
    conn.execute(
        'UPDATE users SET password = ? WHERE id = ?',
        (generate_password_hash(new_password), user_id)
    )
    conn.commit()
    conn.close()


# ── Session helpers ───────────────────────────────────────────────────────────

def login_user(user):
    session['user_id']   = user['id']
    session['username']  = user['username']
    session['role']      = user['role']
    session.permanent    = True


def logout_user():
    session.clear()


def current_user():
    if 'user_id' in session:
        return {
            'id':       session['user_id'],
            'username': session['username'],
            'role':     session['role'],
        }
    return None


def is_logged_in():
    return 'user_id' in session


# ── Decorators ────────────────────────────────────────────────────────────────

def login_required(f):
    """Redirect to /login if not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_logged_in():
            flash('Please log in to continue.', 'info')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    """
    Restrict route to specific roles.
    Usage: @role_required('admin', 'manager')
    - Not logged in → redirect to /login
    - Logged in but wrong role → render 403 access_denied.html
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not is_logged_in():
                flash('Please log in to continue.', 'info')
                return redirect(url_for('login'))
            user_role = session.get('role')
            if user_role not in roles:
                from flask import render_template
                return render_template('access_denied.html',
                    required_roles=roles,
                    user_role=user_role,
                    route=f.__name__
                ), 403
            return f(*args, **kwargs)
        return decorated
    return decorator
