from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from database import shops_col, employees_col, products_col, orders_col, customers_col, suppliers_col, \
    expenses_col, maintenance_col, incidents_col, cctv_col, parking_col, events_col, foodcourt_col, cinema_col, \
    campaigns_col, coupons_col, feedback_col
from auth import (init_auth_db, verify_user, login_user, logout_user, current_user, create_user,
                  is_logged_in, login_required, role_required,
                  get_all_users, delete_user, update_password)
from bson import ObjectId
from dotenv import load_dotenv
from datetime import datetime, timedelta
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "mall_secret_2024")

app.permanent_session_lifetime = timedelta(minutes=30)
init_auth_db()

@app.context_processor
def inject_user():
    return dict(current_user=current_user())

@app.before_request
def make_session_permanent():
    session.permanent = True
    session.modified  = True

def fmt_currency(value):
    try:
        return f"₹{float(value):,.0f}"
    except:
        return "₹0"

app.jinja_env.filters['currency'] = fmt_currency

def gen_order_id():
    count = orders_col.count_documents({})
    return f"ORD-{1000 + count + 1}"

@app.route('/')
def index():
    if is_logged_in():
        return redirect(url_for('dashboard'))
    return render_template('landing.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/shops', methods=['GET', 'POST'])
@role_required('admin', 'manager')
def shops():
    if request.method == 'POST':
        shops_col.insert_one({
            "shop_name": request.form['shop_name'].strip(), "tenant_name": request.form['tenant_name'].strip(),
            "floor": request.form['floor'].strip(), "rent": float(request.form['rent'] or 0),
            "contact": request.form['contact'].strip(), "category": request.form['category'].strip(),
            "created_at": datetime.utcnow()
        })
        flash('Shop added successfully!', 'success')
        return redirect(url_for('shops'))
    search = request.args.get('search', '').strip()
    query = {"$or": [{"shop_name": {"$regex": search, "$options": "i"}}, {"tenant_name": {"$regex": search, "$options": "i"}}]} if search else {}
    return render_template('shops.html', shops=list(shops_col.find(query).sort("_id", -1)), search=search)

@app.route('/shops/delete/<shop_id>')
@role_required('admin', 'manager')
def delete_shop(shop_id):
    shops_col.delete_one({"_id": ObjectId(shop_id)})
    flash('Shop removed.', 'info')
    return redirect(url_for('shops'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if is_logged_in():
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = verify_user(username, password)
        if user:
            session.permanent = True
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)