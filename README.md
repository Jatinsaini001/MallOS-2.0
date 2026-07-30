# 🏬 MallOS — Mall Management System

> A full-stack Flask + MongoDB web application for managing a shopping mall.
> Built in 2 phases with a clean dark-theme dashboard and sidebar navigation.

---

## 📁 Complete Project Structure

```
mall_phase2/
│
├── app.py                        ← Main Flask app — all routes (Phase 1 + 2)
├── database.py                   ← MongoDB connection + all collections
├── requirements.txt              ← Python dependencies
├── .env                          ← Environment variables (MongoDB URI, secret key)
│
├── templates/                    ← Jinja2 HTML templates
│   ├── base.html                 ← Master layout: sidebar, topbar, flash messages
│   ├── dashboard.html            ← Home stats, recent activity, low-stock alerts
│   ├── shops.html                ← Add, view, search, delete shops
│   ├── employees.html            ← Add, view, search, delete employees
│   ├── inventory.html            ← Add, view, filter, delete products + stock badges
│   ├── edit_product.html         ← Edit existing product form
│   ├── pos.html                  ← POS terminal: cart, discounts, payment, checkout
│   ├── orders.html               ← All orders with status pipeline + filters
│   └── order_detail.html         ← Full receipt view for a single order
│
└── static/
    ├── css/
    │   └── style.css             ← Full dark theme stylesheet (Phase 1 + Phase 2 styles)
    └── js/
        └── main.js               ← Flash auto-dismiss, stat count-up animations
```

---

## 🧩 Modules Overview

### Phase 1

| Module       | URL           | Description                                          |
|--------------|---------------|------------------------------------------------------|
| Dashboard    | `/dashboard`  | Stats overview: shops, employees, revenue, payroll   |
| Shops        | `/shops`      | Manage shop tenants, floors, rent info               |
| Employees    | `/employees`  | Manage staff: role, department, salary, join date    |

### Phase 2

| Module       | URL                       | Description                                              |
|--------------|---------------------------|----------------------------------------------------------|
| Inventory    | `/inventory`              | Product catalog with stock levels, cost/price, SKU       |
| Edit Product | `/inventory/edit/<id>`    | Edit any existing product                                |
| POS          | `/pos`                    | Point-of-sale terminal: cart, discounts, payments        |
| Orders       | `/orders`                 | Track all orders — pending / completed / returned        |
| Order Detail | `/orders/detail/<id>`     | Full receipt: items, discount breakdown, payment info    |

---

## 🗄️ Database Schema (MongoDB)

### Collection: `shops`
```json
{
  "shop_name":   "Zara",
  "tenant_name": "Fashion Pvt Ltd",
  "floor":       "1st Floor",
  "rent":        80000,
  "contact":     "9876543210",
  "category":    "Fashion",
  "created_at":  "2024-01-01T00:00:00Z"
}
```

### Collection: `employees`
```json
{
  "name":       "Rahul Sharma",
  "role":       "Security Guard",
  "department": "Security",
  "salary":     25000,
  "contact":    "9876543210",
  "join_date":  "2024-01-15",
  "created_at": "2024-01-15T00:00:00Z"
}
```

### Collection: `products`
```json
{
  "name":            "Levis Jeans",
  "sku":             "LEV-001",
  "category":        "Clothing",
  "price":           2499,
  "cost":            1200,
  "stock":           50,
  "unit":            "pcs",
  "low_stock_alert": 5,
  "created_at":      "2024-01-01T00:00:00Z"
}
```

### Collection: `orders`
```json
{
  "order_id":       "ORD-1001",
  "customer_name":  "Walk-in Customer",
  "items": [
    {
      "product_id":   "abc123",
      "product_name": "Levis Jeans",
      "sku":          "LEV-001",
      "qty":          2,
      "unit_price":   2499,
      "line_total":   4998
    }
  ],
  "subtotal":       4998,
  "discount_type":  "percent",
  "discount_value": 10,
  "discount_amt":   499.8,
  "grand_total":    4498.2,
  "payment_method": "upi",
  "status":         "completed",
  "created_at":     "2024-01-20T14:30:00Z"
}
```

---

## 🔗 Module Integration Map

```
POS ──────────────────────► Orders (creates order on checkout)
 │                               │
 └──► Inventory (deducts stock)  └──► Inventory (restores stock on return)

Dashboard ◄── reads all 4 collections (shops, employees, products, orders)
```

- **POS → Inventory:** Each sale automatically decrements `stock` using MongoDB `$inc`
- **POS → Orders:** Every completed sale creates a new document in `orders` collection
- **Orders → Inventory:** Changing order status to `returned` restores the stock back
- **Dashboard:** Aggregates live stats from all collections — revenue, payroll, low-stock alerts

---

## ⚙️ Local Setup & Run

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure `.env`
```env
# Local MongoDB
MONGO_URI=mongodb://localhost:27017/

# OR MongoDB Atlas (for cloud/Render deployment)
# MONGO_URI=mongodb+srv://<user>:<password>@cluster.mongodb.net/

DB_NAME=mall_management
SECRET_KEY=your_random_secret_key_here
```

### 3. Make sure MongoDB is running locally
```bash
# On Linux/Mac
mongod

# On Windows (if installed as service, it runs automatically)
```

### 4. Run the app
```bash
python app.py
```

### 5. Open in browser
```
http://localhost:5000
```

---

## ☁️ Deploy to Render (Free)

### Step 1 — Push to GitHub
```bash
git init
git add .
git commit -m "MallOS Phase 2"
git remote add origin https://github.com/yourusername/mallos.git
git push -u origin main
```

### Step 2 — Set up MongoDB Atlas (required for cloud)
1. Go to [https://www.mongodb.com/atlas](https://www.mongodb.com/atlas)
2. Create a free cluster
3. Click **Connect** → **Drivers** → copy the connection string
4. It looks like: `mongodb+srv://user:password@cluster0.xxxxx.mongodb.net/`

### Step 3 — Deploy on Render
1. Go to [https://render.com](https://render.com) → **New** → **Web Service**
2. Connect your GitHub repo
3. Fill in settings:

| Setting           | Value                              |
|-------------------|------------------------------------|
| Runtime           | Python 3                           |
| Build Command     | `pip install -r requirements.txt`  |
| Start Command     | `gunicorn app:app`                 |

4. Add **Environment Variables** in Render dashboard:

| Key          | Value                                  |
|--------------|----------------------------------------|
| `MONGO_URI`  | Your MongoDB Atlas connection string   |
| `DB_NAME`    | `mall_management`                      |
| `SECRET_KEY` | Any random string (e.g. `xyz_abc_123`) |

5. Click **Deploy** — your app will be live in ~2 minutes!

> ⚠️ **Never use `localhost` MongoDB URI on Render.** Render servers can't reach your local machine. Always use Atlas.

---

## 🛠️ Tech Stack

| Layer      | Technology              |
|------------|-------------------------|
| Backend    | Python 3, Flask         |
| Database   | MongoDB (via PyMongo)   |
| Frontend   | Jinja2, HTML5, CSS3, JS |
| Fonts      | Syne, DM Sans (Google)  |
| Deployment | Render + MongoDB Atlas  |

---

## 📦 requirements.txt

```
flask
pymongo
python-dotenv
gunicorn
```

---

## 🚀 Future Phases (Planned)

- **Phase 3:** Visitor & Parking Management
- **Phase 4:** Maintenance & Complaints Tracker  
- **Phase 5:** Reports & Analytics with charts
- **Phase 6:** Multi-user login with roles (Admin, Manager, Cashier)
