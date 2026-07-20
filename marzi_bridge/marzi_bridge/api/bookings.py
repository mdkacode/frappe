"""Bookings proxy — mirrors admin-v2/src/store/api/bookingsApi.ts.

Thin pass-through to the backend admin booking routes (Backend-for-org API_DOC §6).
"""

import frappe

from marzi_bridge.client import MarziClient, request_params
from marzi_bridge.permissions import require_marzi


@frappe.whitelist()
@require_marzi()
def list_admin_bookings():
	return MarziClient().get("/admin/bookings", params=request_params())


@frappe.whitelist()
@require_marzi()
def list_coupon_audit():
	return MarziClient().get("/admin/offers/first-event-audit", params=request_params())
