import os
import sys
from dotenv import load_dotenv

load_dotenv()

KEY_ID     = os.getenv("RAZORPAY_KEY_ID", "")
KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")

print("=" * 50)
print("  MallOS — Razorpay Connection Test")
print("=" * 50)

if not KEY_ID or KEY_ID.startswith("REPLACE"):
    print("\n❌  RAZORPAY_KEY_ID not set in .env")
    sys.exit(1)

if not KEY_SECRET or KEY_SECRET.startswith("REPLACE"):
    print("\n❌  RAZORPAY_KEY_SECRET not set in .env")
    sys.exit(1)

print(f"\n  Key ID     : {KEY_ID[:12]}...")
print(f"  Key Secret : {'*' * 20}")

try:
    import razorpay
except ImportError:
    print("\n❌  razorpay package not installed.")
    print("    Run: pip install razorpay")
    sys.exit(1)

try:
    client = razorpay.Client(auth=(KEY_ID, KEY_SECRET))
    order = client.order.create({
        "amount":          100,
        "currency":        "INR",
        "receipt":         "test_receipt_001",
        "payment_capture": 1
    })
    print(f"\n  ✅  Razorpay connected successfully!")
    print(f"  ✅  Test order created : {order['id']}")
    print(f"  ✅  Amount             : ₹{order['amount'] / 100}")
    print(f"  ✅  Status             : {order['status']}")
    print(f"\n  Gateway is LIVE and ready.\n")

except razorpay.errors.BadRequestError as e:
    print(f"\n❌  Bad request — check your API keys: {e}")
    sys.exit(1)
except razorpay.errors.ServerError as e:
    print(f"\n❌  Razorpay server error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"\n❌  Connection failed: {e}")
    sys.exit(1)
