"""Tracking proxy — mirrors admin-v2/src/store/api/trackingApi.ts (GANGADHAR tracking service)."""

import frappe

from marzi_bridge.client import MarziClient, request_params
from marzi_bridge.permissions import require_marzi


@frappe.whitelist()
@require_marzi()
def get_events():
	return MarziClient().get("/v1/events", service="tracking", params=request_params())


@frappe.whitelist()
@require_marzi()
def get_presence():
	return MarziClient().get("/v1/presence", service="tracking", params=request_params())


@frappe.whitelist()
@require_marzi()
def get_user_events(user_id: str):
	return MarziClient().get(
		f"/v1/users/{user_id}/events",
		service="tracking",
		params=request_params(exclude=["user_id"]),
	)
