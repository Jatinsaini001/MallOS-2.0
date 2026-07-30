from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/"))
db = client[os.getenv("DB_NAME", "mall_management")]

# ── Phase 1 Collections ────────────────────────────────────
shops_col     = db["shops"]
employees_col = db["employees"]

# ── Phase 2 Collections ────────────────────────────────────
products_col   = db["products"]   # Inventory
orders_col     = db["orders"]     # Orders (created from POS)

# ── Phase 3 Collections ────────────────────────────────────
customers_col  = db["customers"]  # Customer profiles + loyalty
suppliers_col  = db["suppliers"]  # Supplier details + balances

# ── Phase 4 Collections ────────────────────────────────────
expenses_col     = db["expenses"]
maintenance_col  = db["maintenance"]
incidents_col    = db["incidents"]
cctv_col         = db["cctv"]
parking_col      = db["parking"]
events_col       = db["events"]
foodcourt_col    = db["foodcourt"]
cinema_col       = db["cinema"]

# ── Phase 5 Collections ────────────────────────────────────
campaigns_col    = db["campaigns"]    # Marketing campaigns
coupons_col      = db["coupons"]      # Discount codes & BOGO
feedback_col     = db["feedback"]     # Reviews & complaints
