"""
tenant.py — Multi-tenant collection wrapper for MallOS
-------------------------------------------------------
Every MongoDB operation automatically injects the current
user's business_id so no business can ever touch another's data.

Usage (in app.py):
    shops_col = TenantCollection(_db_raw.shops_col)

Then every call:
    shops_col.find({"floor": "1"})
    → _col.find({"floor": "1", "business_id": "<bid>"})

    shops_col.insert_one({"name": "Nike"})
    → _col.insert_one({"name": "Nike", "business_id": "<bid>"})

    shops_col.aggregate([{"$group": ...}])
    → _col.aggregate([{"$match": {"business_id": "<bid>"}}, {"$group": ...}])
"""

from flask import g


def _current_bid() -> str:
    """Pull business_id from the JWT payload stored in g by jwt_middleware."""
    if not hasattr(g, "jwt_user") or not g.jwt_user:
        raise RuntimeError(
            "TenantCollection: no authenticated user in request context."
        )
    bid = g.jwt_user.get("business_id")
    if not bid:
        raise RuntimeError(
            "TenantCollection: logged-in user has no business_id assigned."
        )
    return bid


def _inject(query, bid: str) -> dict:
    """Return a new dict with business_id merged into query."""
    q = dict(query) if query else {}
    q["business_id"] = bid
    return q


class TenantCollection:
    """
    Wraps a raw pymongo Collection.
    Every read, write, and aggregate call is automatically scoped
    to the current user's business_id.
    """

    def __init__(self, collection):
        self._col = collection

    # ── Read ──────────────────────────────────────────────────────────────────

    def find(self, query=None, *args, **kwargs):
        return self._col.find(_inject(query, _current_bid()), *args, **kwargs)

    def find_one(self, query=None, *args, **kwargs):
        return self._col.find_one(_inject(query, _current_bid()), *args, **kwargs)

    def count_documents(self, query=None, *args, **kwargs):
        return self._col.count_documents(
            _inject(query or {}, _current_bid()), *args, **kwargs
        )

    def distinct(self, key, query=None, *args, **kwargs):
        return self._col.distinct(
            key, _inject(query or {}, _current_bid()), *args, **kwargs
        )

    def aggregate(self, pipeline, *args, **kwargs):
        """
        Prepend a $match stage so the pipeline only sees this business's
        documents. MongoDB optimizer merges adjacent $match stages.
        """
        bid_stage = {"$match": {"business_id": _current_bid()}}
        return self._col.aggregate([bid_stage, *pipeline], *args, **kwargs)

    # ── Write ─────────────────────────────────────────────────────────────────

    def insert_one(self, doc, *args, **kwargs):
        doc["business_id"] = _current_bid()
        return self._col.insert_one(doc, *args, **kwargs)

    def insert_many(self, docs, *args, **kwargs):
        bid = _current_bid()
        for doc in docs:
            doc["business_id"] = bid
        return self._col.insert_many(docs, *args, **kwargs)

    def update_one(self, query, update, *args, **kwargs):
        return self._col.update_one(
            _inject(query, _current_bid()), update, *args, **kwargs
        )

    def update_many(self, query, update, *args, **kwargs):
        return self._col.update_many(
            _inject(query, _current_bid()), update, *args, **kwargs
        )

    def delete_one(self, query, *args, **kwargs):
        return self._col.delete_one(
            _inject(query, _current_bid()), *args, **kwargs
        )

    def delete_many(self, query, *args, **kwargs):
        return self._col.delete_many(
            _inject(query, _current_bid()), *args, **kwargs
        )

    # ── Pass-through for anything not overridden (e.g. create_index) ─────────

    def __getattr__(self, name):
        return getattr(self._col, name)


def create_indexes():
    """
    Create a business_id index on every tenant collection.
    Called once at app startup. Safe to call multiple times (idempotent).
    """
    import database as _db
    tenant_cols = [
        _db.shops_col, _db.employees_col, _db.products_col,
        _db.orders_col, _db.customers_col, _db.suppliers_col,
        _db.expenses_col, _db.maintenance_col, _db.incidents_col,
        _db.cctv_col, _db.parking_col, _db.events_col,
        _db.foodcourt_col, _db.cinema_col, _db.campaigns_col,
        _db.coupons_col, _db.feedback_col,
    ]
    for col in tenant_cols:
        col.create_index("business_id")
    print(f"[MallOS] business_id index ensured on {len(tenant_cols)} collections")
