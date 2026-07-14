"""Payments proxy — Backend-for-org API_DOC §6.

The backend has no standalone `/payments` resource; customer payment records are
surfaced through admin bookings (which carry `user_phone` + monetary/GST fields),
and checkout confirmation is idempotent. Search-by-phone is a booking filter.
"""

import frappe

from marzi_bridge.client import MarziClient, request_params
from marzi_bridge.permissions import require_marzi


@frappe.whitelist()
@require_marzi()
def search_payments():
	# Search by phone (and any other admin-booking filters).
	return MarziClient().get("/admin/bookings", params=request_params())


@frappe.whitelist()
@require_marzi()
def confirm_payment(order_id: str):
	# Idempotent: replaying the same order_id may return ALREADY_CONFIRMED.
	return MarziClient().post(f"/checkout/{order_id}/confirm", json_body=request_params(exclude=["order_id"]))
