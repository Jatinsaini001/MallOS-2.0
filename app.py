from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime, timedelta
from bson import ObjectId
import os
import random
import string
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
import functools

# ─── 1. MongoDB Connection & Database Setup ──────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client.get_database("mallos")

# Collections
shops_col       = db["shops"]
employees_col   = db["employees"]
products_col    = db["products"]
orders_col      = db["orders"]
customers_col   = db["customers"]
suppliers_col   = db["suppliers"]
expenses_col    = db["expenses"]
maintenance_col = db["maintenance"]
incidents_col   = db["incidents"]
parking_col     = db["parking"]
cctv_col        = db["cctv"]
events_col      = db["events"]
foodcourt_col   = db["foodcourt"]
cinema_col      = db["cinema"]
campaigns_col   = db["campaigns"]
coupons_col     = db["coupons"]
feedback_col    = db["feedback"]
users_col       = db["users"]

# ─── 2. Helper Functions ──────────────────────────────────────────────────────
def gen_order_id():
    chars = string.ascii_uppercase + string.digits
    return f"ORD-{''.join(random.choices(chars, k=6))}"

def fmt_currency(amount):
    try:
        return f"₹{float(amount):,.2f}"
    except (TypeError, ValueError):
        return "₹0.00"

# ─── 3. Authentication & User Management Helpers ──────────────────────────────
def init_auth_db():
    """Seeds a default admin user if no users exist in the database."""
    if users_col.count_documents({}) == 0:
        hashed_pw = generate_password_hash("admin123")
        users_col.insert_one({
            "username": "admin",
            "password": hashed_pw,
            "role": "admin",
            "created_at": datetime.utcnow()
        })

def verify_user(username, password):
    user = users_col.find_one({"username": username})
    if user and check_password_hash(user["password"], password):
        return user
    return None

def create_user(username, password, role="cashier"):
    if users_col.find_one({"username": username}):
        return False, "Username already exists."
    hashed_pw = generate_password_hash(password)
    users_col.insert_one({
        "username": username,
        "password": hashed_pw,
        "role": role,
        "created_at": datetime.utcnow()
    })
    return True, ""

def login_user(user):
    session['user_id'] = str(user['_id'])
    session['username'] = user['username']
    session['role'] = user['role']

def logout_user():
    session.clear()

def is_logged_in():
    return 'user_id' in session

def current_user():
    if not is_logged_in():
        return None
    user = users_col.find_one({"_id": ObjectId(session['user_id'])})
    if user:
        user['_id'] = str(user['_id'])
    return user

def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_logged_in():
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*roles):
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            if not is_logged_in():
                flash('Please log in to access this page.', 'error')
                return redirect(url_for('login', next=request.path))
            user_role = session.get('role')
            if user_role not in roles:
                flash('You do not have permission to access this page.', 'error')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_all_users():
    users = list(users_col.find())
    for u in users:
        u['_id'] = str(u['_id'])
    return users

def delete_user(user_id):
    users_col.delete_one({"_id": ObjectId(user_id)})

def update_password(user_id, new_password):
    hashed_pw = generate_password_hash(new_password)
    users_col.update_one({"_id": ObjectId(user_id)}, {"$set": {"password": hashed_pw}})

# ─── 4. Flask App Initialization ──────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "mall_secret_2024")

# Session timeout configuration
app.permanent_session_lifetime = timedelta(minutes=30)

# Initialise users check/seeding on startup (safe to call here since helpers are defined above)
init_auth_db()

# Inject current_user into every template automatically
@app.context_processor
def inject_user():
    return dict(current_user=current_user())

@app.before_request
def make_session_permanent():
    session.permanent = True

# ─── 5. App Routes ────────────────────────────────────────────────────────────
@app.route('/')
def index():
    if not is_logged_in():
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    now         = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    week_start  = today_start - timedelta(days=today_start.weekday())
    month_start = datetime(now.year, now.month, 1)

    total_shops     = shops_col.count_documents({})
    total_employees = employees_col.count_documents({})
    total_products  = products_col.count_documents({})
    total_orders    = orders_col.count_documents({})

    rent_agg     = list(shops_col.aggregate([{"$group": {"_id": None, "total": {"$sum": "$rent"}}}]))
    total_rent   = rent_agg[0]['total'] if rent_agg else 0
    salary_agg   = list(employees_col.aggregate([{"$group": {"_id": None, "total": {"$sum": "$salary"}}}]))
    total_salary = salary_agg[0]['total'] if salary_agg else 0
    revenue_agg  = list(orders_col.aggregate([{"$match": {"status": "completed"}}, {"$group": {"_id": None, "total": {"$sum": "$grand_total"}}}]))
    total_revenue = revenue_agg[0]['total'] if revenue_agg else 0

    def _sales_in_period(start):
        agg = list(orders_col.aggregate([
            {"$match": {"status": "completed", "created_at": {"$gte": start}}},
            {"$group": {"_id": None, "total": {"$sum": "$grand_total"}, "count": {"$sum": 1}}}
        ]))
        return (agg[0]['total'] if agg else 0, agg[0]['count'] if agg else 0)

    sales_today,    orders_today    = _sales_in_period(today_start)
    sales_weekly,   orders_weekly   = _sales_in_period(week_start)
    sales_monthly,  orders_monthly  = _sales_in_period(month_start)

    top_products = list(orders_col.aggregate([
        {"$match": {"status": "completed"}},
        {"$unwind": "$items"},
        {"$group": {"_id": "$items.product_name", "qty": {"$sum": "$items.qty"}, "revenue": {"$sum": "$items.line_total"}}},
        {"$sort": {"qty": -1}}, {"$limit": 5}
    ]))

    monthly_trend = list(orders_col.aggregate([
        {"$match": {"status": "completed"}},
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m", "date": "$created_at"}},
                    "revenue": {"$sum": "$grand_total"}, "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}, {"$limit": 6}
    ]))

    recent_shops     = list(shops_col.find().sort("_id", -1).limit(5))
    recent_employees = list(employees_col.find().sort("_id", -1).limit(5))
    recent_orders    = list(orders_col.find().sort("_id", -1).limit(5))
    dept_agg         = list(employees_col.aggregate([{"$group": {"_id": "$department", "count": {"$sum": 1}}}]))
    floor_agg        = list(shops_col.aggregate([{"$group": {"_id": "$floor", "count": {"$sum": 1}}}]))
    low_stock        = list(products_col.find({"$expr": {"$lte": ["$stock", "$low_stock_alert"]}}).limit(5))
    total_customers  = customers_col.count_documents({})
    total_suppliers  = suppliers_col.count_documents({})
    balance_agg      = list(suppliers_col.aggregate([{"$group": {"_id": None, "total": {"$sum": "$outstanding"}}}]))
    total_outstanding = balance_agg[0]['total'] if balance_agg else 0

    total_expense_agg = list(expenses_col.aggregate([{"$group": {"_id": None, "t": {"$sum": "$amount"}}}]))
    total_expenses    = total_expense_agg[0]['t'] if total_expense_agg else 0
    open_maintenance  = maintenance_col.count_documents({"status": "open"})
    open_incidents    = incidents_col.count_documents({"status": "open"})
    available_parking = parking_col.count_documents({"status": "available"})
    total_parking     = parking_col.count_documents({})

    net_profit = total_revenue - total_expenses

    return render_template('dashboard.html',
        total_shops=total_shops, total_employees=total_employees,
        total_products=total_products, total_orders=total_orders,
        total_rent=total_rent, total_salary=total_salary, total_revenue=total_revenue,
        total_customers=total_customers, total_suppliers=total_suppliers,
        total_outstanding=total_outstanding,
        total_expenses=total_expenses, open_maintenance=open_maintenance,
        open_incidents=open_incidents, available_parking=available_parking,
        total_parking=total_parking,
        recent_shops=recent_shops, recent_employees=recent_employees, recent_orders=recent_orders,
        dept_agg=dept_agg, floor_agg=floor_agg, low_stock=low_stock,
        sales_today=sales_today, orders_today=orders_today,
        sales_weekly=sales_weekly, orders_weekly=orders_weekly,
        sales_monthly=sales_monthly, orders_monthly=orders_monthly,
        top_products=top_products, monthly_trend=monthly_trend,
        net_profit=net_profit
    )

@app.route('/shops', methods=['GET', 'POST'])
@role_required('admin', 'manager')
def shops():
    if request.method == 'POST':
        shops_col.insert_one({
            "shop_name": request.form['shop_name'].strip(),
            "tenant_name": request.form['tenant_name'].strip(),
            "floor": request.form['floor'].strip(),
            "rent": float(request.form['rent'] or 0),
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

@app.route('/employees', methods=['GET', 'POST'])
@role_required('admin')
def employees():
    if request.method == 'POST':
        employees_col.insert_one({
            "name": request.form['name'].strip(), "department": request.form['department'].strip(),
            "salary": float(request.form['salary'] or 0), "contact": request.form['contact'].strip(),
            "role": request.form['role'].strip(), "join_date": request.form['join_date'],
            "created_at": datetime.utcnow()
        })
        flash('Employee added successfully!', 'success')
        return redirect(url_for('employees'))
    search = request.args.get('search', '').strip()
    query = {"$or": [{"name": {"$regex": search, "$options": "i"}}, {"department": {"$regex": search, "$options": "i"}}]} if search else {}
    return render_template('employees.html', employees=list(employees_col.find(query).sort("_id", -1)), search=search)

@app.route('/employees/delete/<id>')
@role_required('admin')
def delete_employee(id):
    employees_col.delete_one({"_id": ObjectId(id)})
    flash('Employee removed.', 'info')
    return redirect(url_for('employees'))

@app.route('/inventory', methods=['GET', 'POST'])
@role_required('admin', 'manager')
def inventory():
    if request.method == 'POST':
        sku = request.form['sku'].strip().upper()
        if sku and products_col.find_one({"sku": sku}):
            flash(f"SKU '{sku}' already exists!", 'error')
        else:
            products_col.insert_one({
                "name": request.form['name'].strip(), "sku": sku,
                "category": request.form['category'].strip(),
                "price": float(request.form['price'] or 0), "cost": float(request.form['cost'] or 0),
                "stock": int(request.form['stock'] or 0), "unit": request.form['unit'].strip(),
                "low_stock_alert": int(request.form.get('low_stock_alert') or 5),
                "created_at": datetime.utcnow()
            })
            flash('Product added!', 'success')
        return redirect(url_for('inventory'))

    search  = request.args.get('search', '').strip()
    filter_ = request.args.get('filter', 'all')
    query   = {}
    if search:
        query["$or"] = [{"name": {"$regex": search, "$options": "i"}}, {"sku": {"$regex": search, "$options": "i"}}]
    if filter_ == 'low':
        query["$expr"] = {"$lte": ["$stock", "$low_stock_alert"]}
    elif filter_ == 'out':
        query["stock"] = 0

    products  = list(products_col.find(query).sort("_id", -1))
    all_prods = list(products_col.find())
    total_val = sum(p.get('cost', 0) * p.get('stock', 0) for p in all_prods)
    low_count = products_col.count_documents({"$expr": {"$lte": ["$stock", "$low_stock_alert"]}})
    out_count = products_col.count_documents({"stock": 0})
    return render_template('inventory.html', products=products, search=search, filter=filter_,
                           total_val=total_val, low_count=low_count, out_count=out_count)

@app.route('/inventory/edit/<id>', methods=['GET', 'POST'])
@role_required('admin', 'manager')
def edit_product(id):
    product = products_col.find_one({"_id": ObjectId(id)})
    if not product:
        flash('Product not found.', 'error')
        return redirect(url_for('inventory'))
    if request.method == 'POST':
        products_col.update_one({"_id": ObjectId(id)}, {"$set": {
            "name": request.form['name'].strip(), "sku": request.form['sku'].strip().upper(),
            "category": request.form['category'].strip(),
            "price": float(request.form['price'] or 0), "cost": float(request.form['cost'] or 0),
            "stock": int(request.form['stock'] or 0), "unit": request.form['unit'].strip(),
            "low_stock_alert": int(request.form.get('low_stock_alert') or 5),
            "updated_at": datetime.utcnow()
        }})
        flash('Product updated!', 'success')
        return redirect(url_for('inventory'))
    return render_template('edit_product.html', product=product)

@app.route('/inventory/delete/<id>')
@role_required('admin', 'manager')
def delete_product(id):
    products_col.delete_one({"_id": ObjectId(id)})
    flash('Product deleted.', 'info')
    return redirect(url_for('inventory'))

@app.route('/pos')
@role_required('admin', 'cashier')
def pos():
    products   = list(products_col.find({"stock": {"$gt": 0}}).sort("name", 1))
    categories = products_col.distinct("category")
    return render_template('pos.html', products=products, categories=categories)

@app.route('/pos/get_products')
@role_required('admin', 'cashier')
def pos_get_products():
    category = request.args.get('category', '')
    search   = request.args.get('search', '')
    query    = {"stock": {"$gt": 0}}
    if category:
        query["category"] = category
    if search:
        query["$or"] = [{"name": {"$regex": search, "$options": "i"}}, {"sku": {"$regex": search, "$options": "i"}}]
    products = list(products_col.find(query, {"_id": 1, "name": 1, "price": 1, "stock": 1, "sku": 1, "unit": 1}))
    for p in products:
        p['_id'] = str(p['_id'])
    return jsonify(products)

@app.route('/pos/checkout', methods=['POST'])
@role_required('admin', 'cashier')
def pos_checkout():
    data             = request.get_json()
    cart             = data.get('cart', [])
    payment_method = data.get('payment_method', 'cash')
    discount_type  = data.get('discount_type', 'none')
    discount_value = float(data.get('discount_value', 0))
    customer_name  = data.get('customer_name', 'Walk-in Customer').strip() or 'Walk-in Customer'

    if not cart:
        return jsonify({"success": False, "message": "Cart is empty"}), 400

    line_items = []
    subtotal   = 0.0
    errors     = []

    for item in cart:
        product = products_col.find_one({"_id": ObjectId(item['product_id'])})
        if not product:
            errors.append("Product not found")
            continue
        qty = int(item['qty'])
        if product['stock'] < qty:
            errors.append(f"Insufficient stock for '{product['name']}' (only {product['stock']} left)")
            continue
        line_total = product['price'] * qty
        subtotal  += line_total
        line_items.append({
            "product_id": str(product['_id']), "product_name": product['name'],
            "sku": product.get('sku', ''), "qty": qty,
            "unit_price": product['price'], "line_total": line_total
        })

    if errors:
        return jsonify({"success": False, "message": "; ".join(errors)}), 400

    discount_amt = 0.0
    if discount_type == 'percent':
        discount_amt = round(subtotal * discount_value / 100, 2)
    elif discount_type == 'flat':
        discount_amt = min(discount_value, subtotal)

    grand_total = round(subtotal - discount_amt, 2)

    for item in line_items:
        products_col.update_one({"_id": ObjectId(item['product_id'])}, {"$inc": {"stock": -item['qty']}})

    customer_id     = data.get('customer_id', '')
    points_earned   = int(grand_total // 10)

    order = {
        "order_id":         gen_order_id(),
        "customer_name":  customer_name,
        "items":          line_items,
        "subtotal":       subtotal,
        "discount_type":  discount_type,
        "discount_value": discount_value,
        "discount_amt":   discount_amt,
        "grand_total":    grand_total,
        "payment_method": payment_method,
        "payment_status": "paid",
        "transaction_id": None,
        "gateway":        payment_method,
        "payment_time":   datetime.utcnow(),
        "status":         "completed",
        "customer_id":    customer_id,
        "points_earned":  points_earned,
        "created_at":     datetime.utcnow()
    }
    orders_col.insert_one(order)

    if customer_id:
        try:
            customer = customers_col.find_one({"_id": ObjectId(customer_id)})
            if customer:
                new_points = customer.get('points', 0) + points_earned
                new_tier   = get_tier(new_points)
                customers_col.update_one({"_id": ObjectId(customer_id)}, {"$set": {
                    "points":      new_points,
                    "tier":        new_tier,
                    "total_spent": round(customer.get('total_spent', 0) + grand_total, 2),
                    "visit_count": customer.get('visit_count', 0) + 1,
                    "last_visit":  datetime.utcnow()
                }})
        except:
            pass

    return jsonify({"success": True, "order_id": order['order_id'], "grand_total": grand_total,
                    "points_earned": points_earned,
                    "message": f"Sale completed! {order['order_id']}"})

@app.route('/orders')
@login_required
def orders():
    status  = request.args.get('status', 'all')
    search  = request.args.get('search', '').strip()
    query   = {}
    if status != 'all':
        query['status'] = status
    if search:
        query['$or'] = [{"order_id": {"$regex": search, "$options": "i"}}, {"customer_name": {"$regex": search, "$options": "i"}}]

    orders_list     = list(orders_col.find(query).sort("created_at", -1))
    total_orders    = orders_col.count_documents({})
    completed_count = orders_col.count_documents({"status": "completed"})
    pending_count   = orders_col.count_documents({"status": "pending"})
    returned_count  = orders_col.count_documents({"status": "returned"})
    revenue_agg     = list(orders_col.aggregate([{"$match": {"status": "completed"}}, {"$group": {"_id": None, "total": {"$sum": "$grand_total"}}}]))
    total_revenue   = revenue_agg[0]['total'] if revenue_agg else 0

    return render_template('orders.html', orders=orders_list, status=status, search=search,
        total_orders=total_orders, completed_count=completed_count,
        pending_count=pending_count, returned_count=returned_count, total_revenue=total_revenue)

@app.route('/orders/update_status/<id>', methods=['POST'])
@role_required('admin', 'manager')
def update_order_status(id):
    new_status = request.form.get('status')
    if new_status not in ['pending', 'completed', 'returned']:
        flash('Invalid status.', 'error')
        return redirect(url_for('orders'))
    order = orders_col.find_one({"_id": ObjectId(id)})
    if not order:
        flash('Order not found.', 'error')
        return redirect(url_for('orders'))
    if new_status == 'returned' and order['status'] != 'returned':
        for item in order.get('items', []):
            try:
                products_col.update_one({"_id": ObjectId(item['product_id'])}, {"$inc": {"stock": item['qty']}})
            except:
                pass
    orders_col.update_one({"_id": ObjectId(id)}, {"$set": {"status": new_status, "updated_at": datetime.utcnow()}})
    flash(f"Order marked as '{new_status}'.", 'success')
    return redirect(url_for('orders'))

@app.route('/orders/detail/<id>')
@login_required
def order_detail(id):
    order = orders_col.find_one({"_id": ObjectId(id)})
    if not order:
        flash('Order not found.', 'error')
        return redirect(url_for('orders'))
    return render_template('order_detail.html', order=order)

@app.route('/orders/view/<order_id>')
@login_required
def order_view(order_id):
    order = orders_col.find_one({"order_id": order_id})
    if not order:
        flash(f'Order {order_id} not found.', 'error')
        return redirect(url_for('orders'))
    return render_template('order_detail.html', order=order)

TIERS = [
    ("Platinum", 5000, "#e2e8f4", "#a78bfa"),
    ("Gold",     1500, "#fef9c3", "#fbbf24"),
    ("Silver",   500,  "#f1f5f9", "#94a3b8"),
    ("Bronze",   0,    "#fdf4ec", "#f97316"),
]

def get_tier(points):
    for name, threshold, _, color in TIERS:
        if points >= threshold:
            return name
    return "Bronze"

def get_tier_color(tier):
    colors = {"Platinum": "#a78bfa", "Gold": "#fbbf24", "Silver": "#94a3b8", "Bronze": "#f97316"}
    return colors.get(tier, "#6b7a99")

def next_tier_info(points):
    thresholds = [("Bronze", 0), ("Silver", 500), ("Gold", 1500), ("Platinum", 5000)]
    for i, (name, threshold) in enumerate(thresholds):
        if points < threshold:
            prev = thresholds[i - 1][0] if i > 0 else "Bronze"
            prev_thresh = thresholds[i - 1][1] if i > 0 else 0
            needed = threshold - points
            progress = int((points - prev_thresh) / (threshold - prev_thresh) * 100) if threshold > prev_thresh else 100
            return {"next": name, "needed": needed, "progress": progress}
    return {"next": None, "needed": 0, "progress": 100}

app.jinja_env.globals['get_tier_color'] = get_tier_color
app.jinja_env.globals['next_tier_info'] = next_tier_info
app.jinja_env.globals['get_tier'] = get_tier

@app.route('/customers', methods=['GET', 'POST'])
@role_required('admin', 'manager')
def customers():
    if request.method == 'POST':
        phone = request.form['phone'].strip()
        if customers_col.find_one({"phone": phone}):
            flash(f"Phone {phone} already registered!", 'error')
        else:
            customers_col.insert_one({
                "name":       request.form['name'].strip(),
                "phone":      phone,
                "email":      request.form['email'].strip(),
                "address":    request.form['address'].strip(),
                "points":     0,
                "tier":       "Bronze",
                "total_spent": 0.0,
                "visit_count": 0,
                "created_at": datetime.utcnow()
            })
            flash('Customer registered!', 'success')
        return redirect(url_for('customers'))

    search = request.args.get('search', '').strip()
    tier_f = request.args.get('tier', 'all')
    query  = {}
    if search:
        query["$or"] = [
            {"name":  {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}}
        ]
    if tier_f != 'all':
        query["tier"] = tier_f

    customers_list   = list(customers_col.find(query).sort("points", -1))
    total_customers  = customers_col.count_documents({})
    tier_counts      = {t: customers_col.count_documents({"tier": t}) for t, *_ in TIERS}
    total_points_agg = list(customers_col.aggregate([{"$group": {"_id": None, "total": {"$sum": "$points"}}}]))
    total_points     = total_points_agg[0]['total'] if total_points_agg else 0

    return render_template('customers.html',
        customers=customers_list, search=search, tier_filter=tier_f,
        total_customers=total_customers, tier_counts=tier_counts,
        total_points=total_points, tiers=TIERS
    )

@app.route('/customers/detail/<id>')
@role_required('admin', 'manager')
def customer_detail(id):
    customer = customers_col.find_one({"_id": ObjectId(id)})
    if not customer:
        flash('Customer not found.', 'error')
        return redirect(url_for('customers'))
    cust_orders = list(orders_col.find({"customer_id": str(id)}).sort("created_at", -1))
    tier_info   = next_tier_info(customer.get('points', 0))
    return render_template('customer_detail.html', customer=customer,
                           orders=cust_orders, tier_info=tier_info)

@app.route('/customers/delete/<id>')
@role_required('admin', 'manager')
def delete_customer(id):
    customers_col.delete_one({"_id": ObjectId(id)})
    flash('Customer removed.', 'info')
    return redirect(url_for('customers'))

@app.route('/customers/adjust_points/<id>', methods=['POST'])
@role_required('admin', 'manager')
def adjust_points(id):
    action = request.form.get('action')
    amount = int(request.form.get('amount', 0))
    customer = customers_col.find_one({"_id": ObjectId(id)})
    if not customer:
        flash('Customer not found.', 'error')
        return redirect(url_for('customers'))

    new_points = customer.get('points', 0)
    if action == 'add':
        new_points += amount
    elif action == 'deduct':
        new_points = max(0, new_points - amount)

    new_tier = get_tier(new_points)
    customers_col.update_one({"_id": ObjectId(id)}, {"$set": {"points": new_points, "tier": new_tier}})
    flash(f"Points updated! Now {new_points} pts — {new_tier} tier.", 'success')
    return redirect(url_for('customer_detail', id=id))

@app.route('/customers/search_ajax')
@login_required
def customers_search_ajax():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    results = list(customers_col.find(
        {"$or": [{"name": {"$regex": q, "$options": "i"}}, {"phone": {"$regex": q, "$options": "i"}}]},
        {"_id": 1, "name": 1, "phone": 1, "points": 1, "tier": 1}
    ).limit(8))
    for r in results:
        r['_id'] = str(r['_id'])
    return jsonify(results)

@app.route('/suppliers', methods=['GET', 'POST'])
@role_required('admin', 'manager')
def suppliers():
    if request.method == 'POST':
        suppliers_col.insert_one({
            "name":        request.form['name'].strip(),
            "contact":     request.form['contact'].strip(),
            "email":       request.form['email'].strip(),
            "category":    request.form['category'].strip(),
            "address":     request.form['address'].strip(),
            "rating":      float(request.form.get('rating') or 3),
            "outstanding": float(request.form.get('outstanding') or 0),
            "notes":       request.form.get('notes', '').strip(),
            "created_at":  datetime.utcnow()
        })
        flash('Supplier added!', 'success')
        return redirect(url_for('suppliers'))

    search = request.args.get('search', '').strip()
    query  = {}
    if search:
        query["$or"] = [
            {"name":       {"$regex": search, "$options": "i"}},
            {"category": {"$regex": search, "$options": "i"}},
            {"contact":  {"$regex": search, "$options": "i"}}
        ]

    suppliers_list   = list(suppliers_col.find(query).sort("name", 1))
    total_suppliers  = suppliers_col.count_documents({})
    balance_agg      = list(suppliers_col.aggregate([{"$group": {"_id": None, "total": {"$sum": "$outstanding"}}}]))
    total_balance    = balance_agg[0]['total'] if balance_agg else 0
    avg_rating_agg   = list(suppliers_col.aggregate([{"$group": {"_id": None, "avg": {"$avg": "$rating"}}}]))
    avg_rating       = round(avg_rating_agg[0]['avg'], 1) if avg_rating_agg else 0

    return render_template('suppliers.html',
        suppliers=suppliers_list, search=search,
        total_suppliers=total_suppliers, total_balance=total_balance, avg_rating=avg_rating
    )

@app.route('/suppliers/detail/<id>')
@role_required('admin', 'manager')
def supplier_detail(id):
    supplier = suppliers_col.find_one({"_id": ObjectId(id)})
    if not supplier:
        flash('Supplier not found.', 'error')
        return redirect(url_for('suppliers'))
    linked_products = list(products_col.find({"supplier_id": str(id)}))
    return render_template('supplier_detail.html', supplier=supplier, products=linked_products)

@app.route('/suppliers/edit/<id>', methods=['GET', 'POST'])
@role_required('admin', 'manager')
def edit_supplier(id):
    supplier = suppliers_col.find_one({"_id": ObjectId(id)})
    if not supplier:
        flash('Supplier not found.', 'error')
        return redirect(url_for('suppliers'))
    if request.method == 'POST':
        suppliers_col.update_one({"_id": ObjectId(id)}, {"$set": {
            "name":        request.form['name'].strip(),
            "contact":     request.form['contact'].strip(),
            "email":       request.form['email'].strip(),
            "category":    request.form['category'].strip(),
            "address":     request.form['address'].strip(),
            "rating":      float(request.form.get('rating') or 3),
            "outstanding": float(request.form.get('outstanding') or 0),
            "notes":       request.form.get('notes', '').strip(),
            "updated_at":  datetime.utcnow()
        }})
        flash('Supplier updated!', 'success')
        return redirect(url_for('supplier_detail', id=id))
    return render_template('edit_supplier.html', supplier=supplier)

@app.route('/suppliers/delete/<id>')
@role_required('admin', 'manager')
def delete_supplier(id):
    suppliers_col.delete_one({"_id": ObjectId(id)})
    flash('Supplier removed.', 'info')
    return redirect(url_for('suppliers'))

@app.route('/suppliers/pay/<id>', methods=['POST'])
@role_required('admin', 'manager')
def pay_supplier(id):
    amount = float(request.form.get('amount', 0))
    supplier = suppliers_col.find_one({"_id": ObjectId(id)})
    if not supplier:
        flash('Supplier not found.', 'error')
        return redirect(url_for('suppliers'))
    new_balance = max(0, supplier.get('outstanding', 0) - amount)
    suppliers_col.update_one({"_id": ObjectId(id)}, {"$set": {"outstanding": new_balance}})
    flash(f'Payment of {fmt_currency(amount)} recorded. Balance: {fmt_currency(new_balance)}', 'success')
    return redirect(url_for('supplier_detail', id=id))

@app.route('/finance', methods=['GET', 'POST'])
@role_required('admin')
def finance():
    if request.method == 'POST':
        expenses_col.insert_one({
            "title":      request.form['title'].strip(),
            "amount":     float(request.form['amount'] or 0),
            "category":   request.form['category'].strip(),
            "paid_to":    request.form.get('paid_to', '').strip(),
            "note":       request.form.get('note', '').strip(),
            "date":       request.form.get('date') or datetime.utcnow().strftime('%Y-%m-%d'),
            "created_at": datetime.utcnow()
        })
        flash('Expense recorded!', 'success')
        return redirect(url_for('finance'))

    expenses  = list(expenses_col.find().sort("date", -1))
    total_expense_agg = list(expenses_col.aggregate([{"$group": {"_id": None, "t": {"$sum": "$amount"}}}]))
    total_expense = total_expense_agg[0]['t'] if total_expense_agg else 0
    revenue_agg = list(orders_col.aggregate([{"$match": {"status": "completed"}}, {"$group": {"_id": None, "t": {"$sum": "$grand_total"}}}]))
    total_income = revenue_agg[0]['t'] if revenue_agg else 0
    rent_agg = list(shops_col.aggregate([{"$group": {"_id": None, "t": {"$sum": "$rent"}}}]))
    total_income += rent_agg[0]['t'] if rent_agg else 0
    profit = total_income - total_expense
    cat_agg = list(expenses_col.aggregate([{"$group": {"_id": "$category", "total": {"$sum": "$amount"}}}]))
    monthly_exp = list(expenses_col.aggregate([
        {"$group": {"_id": {"$substr": ["$date", 0, 7]}, "total": {"$sum": "$amount"}}},
        {"$sort": {"_id": 1}}, {"$limit": 6}
    ]))
    return render_template('finance.html',
        expenses=expenses, total_expense=total_expense,
        total_income=total_income, profit=profit,
        cat_agg=cat_agg, monthly_exp=monthly_exp
    )

@app.route('/finance/delete/<id>')
@role_required('admin')
def delete_expense(id):
    expenses_col.delete_one({"_id": ObjectId(id)})
    flash('Expense deleted.', 'info')
    return redirect(url_for('finance'))

@app.route('/maintenance', methods=['GET', 'POST'])
@role_required('admin', 'manager')
def maintenance():
    if request.method == 'POST':
        maintenance_col.insert_one({
            "title":       request.form['title'].strip(),
            "location":    request.form['location'].strip(),
            "priority":    request.form['priority'],
            "category":    request.form['category'],
            "description": request.form.get('description', '').strip(),
            "technician":  request.form.get('technician', '').strip(),
            "status":      "open",
            "created_at":  datetime.utcnow()
        })
        flash('Maintenance request submitted!', 'success')
        return redirect(url_for('maintenance'))

    status_f   = request.args.get('status', 'all')
    priority_f = request.args.get('priority', 'all')
    query = {}
    if status_f   != 'all': query['status']   = status_f
    if priority_f != 'all': query['priority'] = priority_f
    requests_list  = list(maintenance_col.find(query).sort("created_at", -1))
    open_count     = maintenance_col.count_documents({"status": "open"})
    inprog_count   = maintenance_col.count_documents({"status": "in_progress"})
    done_count     = maintenance_col.count_documents({"status": "resolved"})
    critical_count = maintenance_col.count_documents({"priority": "critical"})
    technicians    = list(employees_col.find({"department": "Technical"}, {"name": 1}))
    return render_template('maintenance.html',
        requests=requests_list, status_filter=status_f, priority_filter=priority_f,
        open_count=open_count, inprog_count=inprog_count,
        done_count=done_count, critical_count=critical_count,
        technicians=technicians
    )

@app.route('/maintenance/update/<id>', methods=['POST'])
@role_required('admin', 'manager')
def update_maintenance(id):
    maintenance_col.update_one({"_id": ObjectId(id)}, {"$set": {
        "status":     request.form['status'],
        "technician": request.form.get('technician', '').strip(),
        "updated_at": datetime.utcnow()
    }})
    flash('Request updated!', 'success')
    return redirect(url_for('maintenance'))

@app.route('/maintenance/delete/<id>')
@role_required('admin', 'manager')
def delete_maintenance(id):
    maintenance_col.delete_one({"_id": ObjectId(id)})
    flash('Request deleted.', 'info')
    return redirect(url_for('maintenance'))

@app.route('/security', methods=['GET', 'POST'])
@role_required('admin', 'manager')
def security():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_incident':
            incidents_col.insert_one({
                "title":       request.form['title'].strip(),
                "location":    request.form['location'].strip(),
                "severity":    request.form['severity'],
                "category":    request.form['category'],
                "description": request.form.get('description', '').strip(),
                "reported_by": request.form.get('reported_by', '').strip(),
                "status":      "open",
                "created_at":  datetime.utcnow()
            })
            flash('Incident reported!', 'success')
        elif action == 'add_cctv':
            cctv_col.insert_one({
                "camera_id":  request.form['camera_id'].strip().upper(),
                "location":   request.form['location_cctv'].strip(),
                "floor":      request.form['floor'],
                "status":     request.form['cam_status'],
                "created_at": datetime.utcnow()
            })
            flash('CCTV camera added!', 'success')
        return redirect(url_for('security'))

    incidents      = list(incidents_col.find().sort("created_at", -1))
    cameras        = list(cctv_col.find().sort("floor", 1))
    open_count     = incidents_col.count_documents({"status": "open"})
    critical_count = incidents_col.count_documents({"severity": "critical"})
    active_cameras = cctv_col.count_documents({"status": "active"})
    faulty_cameras = cctv_col.count_documents({"status": "faulty"})
    return render_template('security.html',
        incidents=incidents, cameras=cameras,
        open_count=open_count, critical_count=critical_count,
        active_cameras=active_cameras, faulty_cameras=faulty_cameras
    )

@app.route('/security/incident/update/<id>', methods=['POST'])
@role_required('admin', 'manager')
def update_incident(id):
    incidents_col.update_one({"_id": ObjectId(id)}, {"$set": {
        "status": request.form['status'], "updated_at": datetime.utcnow()
    }})
    flash('Incident updated!', 'success')
    return redirect(url_for('security'))

@app.route('/security/cctv/update/<id>', methods=['POST'])
@role_required('admin', 'manager')
def update_cctv(id):
    cctv_col.update_one({"_id": ObjectId(id)}, {"$set": {
        "status": request.form['status'], "updated_at": datetime.utcnow()
    }})
    flash('Camera status updated!', 'success')
    return redirect(url_for('security'))

@app.route('/security/incident/delete/<id>')
@role_required('admin', 'manager')
def delete_incident(id):
    incidents_col.delete_one({"_id": ObjectId(id)})
    flash('Incident deleted.', 'info')
    return redirect(url_for('security'))

@app.route('/security/cctv/delete/<id>')
@role_required('admin', 'manager')
def delete_cctv(id):
    cctv_col.delete_one({"_id": ObjectId(id)})
    flash('Camera removed.', 'info')
    return redirect(url_for('security'))

@app.route('/mallservices', methods=['GET', 'POST'])
@role_required('admin', 'manager')
def mallservices():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_parking':
            parking_col.insert_one({
                "slot_id": request.form['slot_id'].strip().upper(),
                "type":    request.form['type'],
                "floor":   request.form['floor'],
                "status":  "available",
                "created_at": datetime.utcnow()
            })
            flash('Parking slot added!', 'success')
        elif action == 'toggle_parking':
            slot = parking_col.find_one({"_id": ObjectId(request.form['slot_id'])})
            if slot:
                new_s = "available" if slot['status'] == "occupied" else "occupied"
                parking_col.update_one({"_id": ObjectId(request.form['slot_id'])},
                    {"$set": {"status": new_s, "updated_at": datetime.utcnow()}})
            flash('Slot status updated!', 'success')
        elif action == 'add_event':
            events_col.insert_one({
                "name":        request.form['event_name'].strip(),
                "venue":       request.form['venue'].strip(),
                "date":        request.form['event_date'],
                "time":        request.form.get('event_time', ''),
                "description": request.form.get('description', '').strip(),
                "status":      "upcoming",
                "created_at":  datetime.utcnow()
            })
            flash('Event added!', 'success')
        elif action == 'add_stall':
            foodcourt_col.insert_one({
                "name":    request.form['stall_name'].strip(),
                "cuisine": request.form['cuisine'].strip(),
                "owner":   request.form.get('owner', '').strip(),
                "status":  request.form.get('stall_status', 'open'),
                "created_at": datetime.utcnow()
            })
            flash('Food stall added!', 'success')
        elif action == 'add_screen':
            cinema_col.insert_one({
                "screen":     request.form['screen'].strip(),
                "movie":      request.form['movie'].strip(),
                "show_times": request.form.get('show_times', '').strip(),
                "seats":      int(request.form.get('seats') or 0),
                "status":     request.form.get('screen_status', 'active'),
                "created_at": datetime.utcnow()
            })
            flash('Cinema screen added!', 'success')
        return redirect(url_for('mallservices'))

    parking_slots   = list(parking_col.find().sort("slot_id", 1))
    events          = list(events_col.find().sort("date", 1))
    stalls          = list(foodcourt_col.find().sort("name", 1))
    screens         = list(cinema_col.find().sort("screen", 1))
    available_slots = parking_col.count_documents({"status": "available"})
    occupied_slots  = parking_col.count_documents({"status": "occupied"})
    total_slots     = parking_col.count_documents({})
    upcoming_events = events_col.count_documents({"status": "upcoming"})
    open_stalls     = foodcourt_col.count_documents({"status": "open"})
    active_screens  = cinema_col.count_documents({"status": "active"})
    return render_template('mallservices.html',
        parking_slots=parking_slots, events=events, stalls=stalls, screens=screens,
        available_slots=available_slots, occupied_slots=occupied_slots,
        total_slots=total_slots, upcoming_events=upcoming_events,
        open_stalls=open_stalls, active_screens=active_screens
    )

@app.route('/mallservices/event/delete/<id>')
@role_required('admin', 'manager')
def delete_event(id):
    events_col.delete_one({"_id": ObjectId(id)})
    flash('Event deleted.', 'info')
    return redirect(url_for('mallservices'))

@app.route('/mallservices/event/update/<id>', methods=['POST'])
@role_required('admin', 'manager')
def update_event(id):
    events_col.update_one({"_id": ObjectId(id)}, {"$set": {
        "status": request.form['status'], "updated_at": datetime.utcnow()
    }})
    flash('Event updated!', 'success')
    return redirect(url_for('mallservices'))

@app.route('/mallservices/stall/delete/<id>')
@role_required('admin', 'manager')
def delete_stall(id):
    foodcourt_col.delete_one({"_id": ObjectId(id)})
    flash('Stall removed.', 'info')
    return redirect(url_for('mallservices'))

@app.route('/mallservices/screen/delete/<id>')
@role_required('admin', 'manager')
def delete_screen(id):
    cinema_col.delete_one({"_id": ObjectId(id)})
    flash('Screen removed.', 'info')
    return redirect(url_for('mallservices'))

@app.route('/mallservices/parking/delete/<id>')
@role_required('admin', 'manager')
def delete_parking(id):
    parking_col.delete_one({"_id": ObjectId(id)})
    flash('Slot removed.', 'info')
    return redirect(url_for('mallservices'))

@app.route('/marketing', methods=['GET', 'POST'])
@role_required('admin', 'manager')
def marketing():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add_campaign':
            campaigns_col.insert_one({
                "name":        request.form['name'].strip(),
                "type":        request.form['type'],
                "channel":     request.form['channel'],
                "budget":      float(request.form.get('budget') or 0),
                "start_date":  request.form.get('start_date', ''),
                "end_date":    request.form.get('end_date', ''),
                "target":      request.form.get('target', '').strip(),
                "description": request.form.get('description', '').strip(),
                "status":      "active",
                "created_at":  datetime.utcnow()
            })
            flash('Campaign created!', 'success')

        elif action == 'add_coupon':
            code = request.form['code'].strip().upper()
            if coupons_col.find_one({"code": code}):
                flash(f"Code {code} already exists!", 'error')
            else:
                coupons_col.insert_one({
                    "code":          code,
                    "type":          request.form['coupon_type'],
                    "value":         float(request.form.get('coupon_value') or 0),
                    "min_purchase":  float(request.form.get('min_purchase') or 0),
                    "max_uses":      int(request.form.get('max_uses') or 0),
                    "used_count":    0,
                    "valid_until":   request.form.get('valid_until', ''),
                    "description":   request.form.get('coupon_desc', '').strip(),
                    "active":        True,
                    "created_at":    datetime.utcnow()
                })
                flash('Coupon created!', 'success')

        return redirect(url_for('marketing'))

    campaigns   = list(campaigns_col.find().sort("created_at", -1))
    coupons     = list(coupons_col.find().sort("created_at", -1))
    active_camp = campaigns_col.count_documents({"status": "active"})
    active_coup = coupons_col.count_documents({"active": True})
    total_budget = list(campaigns_col.aggregate([{"$group": {"_id": None, "t": {"$sum": "$budget"}}}]))
    budget_total = total_budget[0]['t'] if total_budget else 0

    return render_template('marketing.html',
        campaigns=campaigns, coupons=coupons,
        active_camp=active_camp, active_coup=active_coup, budget_total=budget_total
    )

@app.route('/marketing/campaign/delete/<id>')
@role_required('admin', 'manager')
def delete_campaign(id):
    campaigns_col.delete_one({"_id": ObjectId(id)})
    flash('Campaign deleted.', 'info')
    return redirect(url_for('marketing'))

@app.route('/marketing/campaign/status/<id>', methods=['POST'])
@role_required('admin', 'manager')
def update_campaign_status(id):
    campaigns_col.update_one({"_id": ObjectId(id)}, {"$set": {"status": request.form['status']}})
    flash('Campaign updated!', 'success')
    return redirect(url_for('marketing'))

@app.route('/marketing/coupon/toggle/<id>')
@role_required('admin', 'manager')
def toggle_coupon(id):
    c = coupons_col.find_one({"_id": ObjectId(id)})
    if c:
        coupons_col.update_one({"_id": ObjectId(id)}, {"$set": {"active": not c.get('active', True)}})
    flash('Coupon toggled.', 'info')
    return redirect(url_for('marketing'))

@app.route('/marketing/coupon/delete/<id>')
@role_required('admin', 'manager')
def delete_coupon(id):
    coupons_col.delete_one({"_id": ObjectId(id)})
    flash('Coupon deleted.', 'info')
    return redirect(url_for('marketing'))

@app.route('/marketing/coupon/validate', methods=['POST'])
@login_required
def validate_coupon():
    payload = request.get_json() or {}
    code    = payload.get('code', '').upper()
    amount  = float(payload.get('amount', 0))
    coupon  = coupons_col.find_one({"code": code, "active": True})
    if not coupon:
        return jsonify({"valid": False, "message": "Invalid or inactive coupon"})
    if coupon.get('valid_until') and coupon['valid_until'] < datetime.utcnow().strftime('%Y-%m-%d'):
        return jsonify({"valid": False, "message": "Coupon expired"})
    if coupon.get('max_uses') and coupon.get('used_count', 0) >= coupon['max_uses']:
        return jsonify({"valid": False, "message": "Coupon usage limit reached"})
    if amount < coupon.get('min_purchase', 0):
        return jsonify({"valid": False, "message": f"Minimum purchase ₹{coupon['min_purchase']} required"})
    disc = 0
    if coupon['type'] == 'percent':
        disc = round(amount * coupon['value'] / 100, 2)
    elif coupon['type'] == 'flat':
        disc = min(coupon['value'], amount)
    elif coupon['type'] == 'bogo':
        disc = 0
    return jsonify({"valid": True, "discount": disc, "type": coupon['type'],
                    "value": coupon['value'], "message": f"Coupon applied! Save ₹{disc}"})

@app.route('/feedback', methods=['GET', 'POST'])
@role_required('admin', 'manager')
def feedback():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add_feedback':
            feedback_col.insert_one({
                "customer_name": request.form['customer_name'].strip(),
                "contact":       request.form.get('contact', '').strip(),
                "type":          request.form['feedback_type'],
                "category":      request.form['category'],
                "rating":        int(request.form.get('rating') or 3),
                "message":       request.form['message'].strip(),
                "shop":          request.form.get('shop', '').strip(),
                "status":        "new",
                "response":      "",
                "created_at":    datetime.utcnow()
            })
            flash('Feedback submitted!', 'success')

        elif action == 'respond':
            feedback_col.update_one({"_id": ObjectId(request.form['feedback_id'])}, {"$set": {
                "response":      request.form['response'].strip(),
                "status":        "responded",
                "responded_at": datetime.utcnow(),
                "responded_by": request.form.get('staff_name', 'Management').strip()
            }})
            flash('Response sent!', 'success')

        return redirect(url_for('feedback'))

    ftype  = request.args.get('type', 'all')
    status = request.args.get('status', 'all')
    query  = {}
    if ftype  != 'all': query['type']   = ftype
    if status != 'all': query['status'] = status

    feedback_list = list(feedback_col.find(query).sort("created_at", -1))
    total_fb      = feedback_col.count_documents({})
    avg_rating_agg = list(feedback_col.aggregate([{"$group": {"_id": None, "avg": {"$avg": "$rating"}}}]))
    avg_rating    = round(avg_rating_agg[0]['avg'], 1) if avg_rating_agg else 0
    new_count     = feedback_col.count_documents({"status": "new"})
    complaints    = feedback_col.count_documents({"type": "complaint"})
    shops_list    = list(shops_col.find({}, {"shop_name": 1}))

    return render_template('feedback.html',
        feedback_list=feedback_list, ftype=ftype, status=status,
        total_fb=total_fb, avg_rating=avg_rating,
        new_count=new_count, complaints=complaints,
        shops_list=shops_list
    )

@app.route('/feedback/delete/<id>')
@role_required('admin', 'manager')
def delete_feedback(id):
    feedback_col.delete_one({"_id": ObjectId(id)})
    flash('Feedback deleted.', 'info')
    return redirect(url_for('feedback'))

@app.route('/reports')
@role_required('admin', 'manager')
def reports():
    period          = request.args.get('period', 'all')
    date_from      = request.args.get('date_from', '')
    date_to        = request.args.get('date_to', '')
    
    now          = datetime.utcnow()
    date_match = {"status": "completed"}

    if period == 'daily':
        start_dt = datetime(now.year, now.month, now.day)
        date_match["created_at"] = {"$gte": start_dt}
    elif period == 'weekly':
        start_dt = datetime(now.year, now.month, now.day) - timedelta(days=now.weekday())
        date_match["created_at"] = {"$gte": start_dt}
    elif period == 'monthly':
        start_dt = datetime(now.year, now.month, 1)
        date_match["created_at"] = {"$gte": start_dt}
    elif period == 'custom' and date_from and date_to:
        try:
            start_dt = datetime.strptime(date_from, '%Y-%m-%d')
            end_dt   = datetime.strptime(date_to,   '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            date_match["created_at"] = {"$gte": start_dt, "$lte": end_dt}
        except Exception:
            pass

    filtered_orders = list(orders_col.find(date_match).sort("created_at", -1).limit(200))
    
    monthly_sales = list(orders_col.aggregate([
        {"$match": {"status": "completed"}},
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m", "date": "$created_at"}},
                    "revenue": {"$sum": "$grand_total"}, "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}, {"$limit": 6}
    ]))

    monthly_expenses = list(expenses_col.aggregate([
        {"$group": {"_id": {"$substr": ["$date", 0, 7]}, "total": {"$sum": "$amount"}}},
        {"$sort": {"_id": 1}}, {"$limit": 6}
    ]))

    payment_breakdown = list(orders_col.aggregate([
        {"$match": {"status": "completed"}},
        {"$group": {"_id": "$payment_method", "count": {"$sum": 1}, "total": {"$sum": "$grand_total"}}}
    ]))

    top_products = list(orders_col.aggregate([
        {"$match": {"status": "completed"}},
        {"$unwind": "$items"},
        {"$group": {"_id": "$items.product_name", "qty": {"$sum": "$items.qty"}, "revenue": {"$sum": "$items.line_total"}}},
        {"$sort": {"qty": -1}}, {"$limit": 5}
    ]))

    tier_dist = list(customers_col.aggregate([
        {"$group": {"_id": "$tier", "count": {"$sum": 1}}}
    ]))

    expense_by_cat = list(expenses_col.aggregate([
        {"$group": {"_id": "$category", "total": {"$sum": "$amount"}}},
        {"$sort": {"total": -1}}
    ]))

    total_products  = products_col.count_documents({})
    low_stock       = products_col.count_documents({"$expr": {"$lte": ["$stock", "$low_stock_alert"]}})
    out_of_stock    = products_col.count_documents({"stock": 0})
    healthy_stock   = total_products - low_stock - out_of_stock

    maint_open   = maintenance_col.count_documents({"status": "open"})
    maint_prog   = maintenance_col.count_documents({"status": "in_progress"})
    maint_done   = maintenance_col.count_documents({"status": "resolved"})

    total_revenue = list(orders_col.aggregate([{"$match": {"status": "completed"}}, {"$group": {"_id": None, "t": {"$sum": "$grand_total"}}}]))
    total_expense = list(expenses_col.aggregate([{"$group": {"_id": None, "t": {"$sum": "$amount"}}}]))
    rev = total_revenue[0]['t'] if total_revenue else 0
    exp = total_expense[0]['t'] if total_expense else 0

    return render_template('reports.html',
        monthly_sales=monthly_sales, monthly_expenses=monthly_expenses,
        payment_breakdown=payment_breakdown, top_products=top_products,
        tier_dist=tier_dist, expense_by_cat=expense_by_cat,
        total_products=total_products, low_stock=low_stock,
        out_of_stock=out_of_stock, healthy_stock=healthy_stock,
        maint_open=maint_open, maint_prog=maint_prog, maint_done=maint_done,
        total_revenue=rev, total_expense=exp, net_profit=rev - exp
    )

@app.route('/aiinsights')
@role_required('admin', 'manager')
def aiinsights():
    monthly_sales = list(orders_col.aggregate([
        {"$match": {"status": "completed"}},
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m", "date": "$created_at"}}, "revenue": {"$sum": "$grand_total"}}},
        {"$sort": {"_id": 1}}, {"$limit": 6}
    ]))
    revenues = [m['revenue'] for m in monthly_sales]
    if len(revenues) >= 2:
        avg_growth = sum(revenues[i] - revenues[i-1] for i in range(1, len(revenues))) / (len(revenues) - 1)
        predicted_next = round(revenues[-1] + avg_growth, 2) if revenues else 0
        trend = "up" if avg_growth > 0 else "down" if avg_growth < 0 else "stable"
    else:
        predicted_next = revenues[-1] if revenues else 0
        trend = "stable"
        avg_growth = 0

    critical_stock  = list(products_col.find({"stock": {"$lte": 2, "$gt": 0}}).sort("stock", 1))
    out_of_stock    = list(products_col.find({"stock": 0}))
    low_stock_items = list(products_col.find({"$expr": {"$lte": ["$stock", "$low_stock_alert"]}, "stock": {"$gt": 2}}).limit(10))

    fast_movers = list(orders_col.aggregate([
        {"$match": {"status": "completed"}},
        {"$unwind": "$items"},
        {"$group": {"_id": "$items.product_name", "qty": {"$sum": "$items.qty"}}},
        {"$sort": {"qty": -1}}, {"$limit": 5}
    ]))

    top_customers = list(customers_col.find({"total_spent": {"$gt": 0}}).sort("total_spent", -1).limit(5))
    dormant_customers = list(customers_col.find({"visit_count": {"$lte": 1}}).limit(8))

    tier_counts = {
        t: customers_col.count_documents({"tier": t})
        for t in ["Bronze", "Silver", "Gold", "Platinum"]
    }

    avg_order_agg = list(orders_col.aggregate([
        {"$match": {"status": "completed"}},
        {"$group": {"_id": None, "avg": {"$avg": "$grand_total"}}}
    ]))
    avg_order_val = round(avg_order_agg[0]['avg'], 2) if avg_order_agg else 0

    repeat_customers = customers_col.count_documents({"visit_count": {"$gte": 2}})
    total_customers  = customers_col.count_documents({})
    retention_rate   = round(repeat_customers / total_customers * 100, 1) if total_customers else 0

    revenue_agg = list(orders_col.aggregate([{"$match": {"status": "completed"}}, {"$group": {"_id": None, "t": {"$sum": "$grand_total"}}}]))
    expense_agg = list(expenses_col.aggregate([{"$group": {"_id": None, "t": {"$sum": "$amount"}}}]))
    total_rev = revenue_agg[0]['t'] if revenue_agg else 0
    total_exp = expense_agg[0]['t'] if expense_agg else 0
    margin    = round((total_rev - total_exp) / total_rev * 100, 1) if total_rev else 0

    open_incidents  = incidents_col.count_documents({"status": "open"})
    open_maint      = maintenance_col.count_documents({"status": "open"})
    supplier_debt   = list(suppliers_col.aggregate([{"$group": {"_id": None, "t": {"$sum": "$outstanding"}}}]))
    total_debt      = supplier_debt[0]['t'] if supplier_debt else 0

    return render_template('aiinsights.html',
        monthly_sales=monthly_sales, predicted_next=predicted_next,
        trend=trend, avg_growth=avg_growth, revenues=revenues,
        critical_stock=critical_stock, out_of_stock=out_of_stock,
        low_stock_items=low_stock_items, fast_movers=fast_movers,
        top_customers=top_customers, dormant_customers=dormant_customers,
        tier_counts=tier_counts, avg_order_val=avg_order_val,
        retention_rate=retention_rate, repeat_customers=repeat_customers,
        total_customers=total_customers,
        total_rev=total_rev, total_exp=total_exp, margin=margin,
        open_incidents=open_incidents, open_maint=open_maint, total_debt=total_debt
    )

@app.route('/razorpay/ping')
@login_required
def razorpay_ping():
    key_id     = os.getenv("RAZORPAY_KEY_ID", "")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
    try:
        import razorpay
        client = razorpay.Client(auth=(key_id, key_secret))
        order  = client.order.create({
            "amount": 100, "currency": "INR",
            "receipt": "ping_test", "payment_capture": 1
        })
        return jsonify({"ok": True, "order_id": order["id"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route('/receipt/<order_id>')
@login_required
def receipt(order_id):
    order = orders_col.find_one({"order_id": order_id})
    if not order:
        flash("Receipt not found.", "error")
        return redirect(url_for("orders"))
    return render_template("receipt.html", order=order)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if is_logged_in():
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Please enter both username and password.', 'error')
            return render_template('login.html')

        user = verify_user(username, password)
        if user:
            session.permanent = True
            login_user(user)
            flash(f"Welcome back, {user['username']}!", 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'error')
            return render_template('login.html')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if is_logged_in():
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username   = request.form.get('username', '').strip()
        password   = request.form.get('password', '').strip()
        confirm_pw = request.form.get('confirm_password', '').strip()
        role       = request.form.get('role', 'cashier').strip()
        errors = []
        if not username:
            errors.append('Username is required.')
        if len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if password != confirm_pw:
            errors.append('Passwords do not match.')
        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('register.html', form=request.form)
        ok, err = create_user(username, password, role)
        if not ok:
            flash(err, 'error')
            return render_template('register.html', form=request.form)
        flash(f'Account created for {username}. Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form={})

@app.route('/logout')
def logout():
    username = session.get('username', '')
    logout_user()
    flash(f'Goodbye, {username}! You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/users', methods=['GET', 'POST'])
@role_required('admin')
def manage_users():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'create':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            role     = request.form.get('role', 'cashier')
            if not username or not password:
                flash('Username and password are required.', 'error')
            else:
                ok, err = create_user(username, password, role)
                if ok:
                    flash(f"User '{username}' created successfully.", 'success')
                else:
                    flash(err, 'error')

        elif action == 'delete':
            user_id = request.form.get('user_id', '')
            if user_id == str(session.get('user_id')):
                flash("You cannot delete your own account.", 'error')
            else:
                delete_user(user_id)
                flash('User deleted.', 'info')

        elif action == 'change_password':
            user_id      = request.form.get('user_id', '')
            new_password = request.form.get('new_password', '').strip()
            if not new_password:
                flash('New password cannot be empty.', 'error')
            else:
                update_password(user_id, new_password)
                flash('Password updated.', 'success')

        return redirect(url_for('manage_users'))

    users = get_all_users()
    return render_template('users.html', users=users)

if __name__ == '__main__':
    app.run(debug=True)