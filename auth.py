"""
auth.py — Authentication module for MallOS (MongoDB Version for Vercel)
- MongoDB-based users collection
- Password hashing with werkzeug
- Session management helpers
- login_required decorator
"""

import os
from functools import wraps
from flask import session, redirect, url_for, flash, render_template
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient

# ── MongoDB Setup ─────────────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "mall_management")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
users_col = db["users"]


# ── Database setup & Seeding ──────────────────────────────────────────────────

def init_auth_db():
    """Seed default accounts if users collection is empty."""
    try:
        count = users_col.count_documents({})
        if count == 0:
            defaults = [
                ('admin',   'admin123',   'admin'),
                ('manager', 'manager123', 'manager'),
                ('cashier', 'cashier123', 'cashier'),
            ]
            for username, password, role in defaults:
                users_col.insert_one({
                    'username': username.strip(),
                    'password': generate_password_hash(password),
                    'role': role
                })
            print("[MallOS] Default users created in MongoDB — admin/admin123, manager/manager123, cashier/cashier123")
    except Exception as e:
        print(f"[MallOS] Error initializing auth DB: {e}")


# ── Auth helpers ──────────────────────────────────────────────────────────────

def verify_user(username, password):
    """Return user dict if credentials valid, else None."""
    user = users_col.find_one({'username': username.strip()})
    if user and check_password_hash(user['password'], password):
        # Convert ObjectId to string id for compatibility
        return {
            'id': str(user['_id']),
            'username': user['username'],
            'role': user['role']
        }
    return None


def get_all_users():
    users = []
    for u in users_col.find().sort('_id', 1):
        users.append({
            'id': str(u['_id']),
            'username': u['username'],
            'role': u['role'],
            'created_at': str(u.get('_id').generation_time) if '_id' in u else ''
        })
    return users


def create_user(username, password, role):
    """Returns (True, None) or (False, error_message)."""
    cleaned_username = username.strip()
    existing = users_col.find_one({'username': cleaned_username})
    if existing:
        return False, f"Username '{cleaned_username}' already exists."
    
    users_col.insert_one({
        'username': cleaned_username,
        'password': generate_password_hash(password),
        'role': role
    })
    return True, None


def delete_user(user_id):
    from bson.objectid import ObjectId
    try:
        users_col.delete_one({'_id': ObjectId(user_id)})
    except Exception:
        pass


def update_password(user_id, new_password):
    from bson.objectid import ObjectId
    try:
        users_col.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {'password': generate_password_hash(new_password)}}
        )
    except Exception:
        pass


# ── Session helpers ───────────────────────────────────────────────────────────

def login_user(user):
    session['user_id']   = str(user['id'])
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
                return render_template('access_denied.html',
                    required_roles=roles,
                    user_role=user_role,
                    route=f.__name__
                ), 403
            return f(*args, **kwargs)
        return decorator
    return decorator