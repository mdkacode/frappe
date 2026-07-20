"""Tiered ticketing proxy — v3 admin ticketing endpoints.

Mirrors admin-v2/src/store/api/ticketingApi.ts (Backend-for-org API_DOC §13):
tiered events CRUD, Pretix linking, tiers, orders, sales, attendees, check-in.
All paths are relative to the v3 service base URL.
"""

import frappe

from marzi_bridge.client import MarziClient, request_params
from marzi_bridge.permissions import require_marzi


@frappe.whitelist()
@require_marzi()
def list_admin_events():
	return MarziClient().get("/admin/events", service="v3", params=request_params())


@frappe.whitelist()
@require_marzi()
def get_admin_event(event_id: str):
	return MarziClient().get(f"/admin/events/{event_id}", service="v3")


@frappe.whitelist()
@require_marzi()
def create_admin_event():
	return MarziClient().post("/admin/events", service="v3", json_body=request_params())


@frappe.whitelist()
@require_marzi()
def list_admin_tiers(event_id: str):
	return MarziClient().get(f"/admin/events/{event_id}/tiers", service="v3")


@frappe.whitelist()
@require_marzi()
def create_admin_tier(event_id: str):
	return MarziClient().post(
		f"/admin/events/{event_id}/tiers", service="v3", json_body=request_params(exclude=["event_id"])
	)


@frappe.whitelist()
@require_marzi()
def update_admin_tier(event_id: str, tier_id: str):
	return MarziClient().put(
		f"/admin/events/{event_id}/tiers/{tier_id}",
		service="v3",
		json_body=request_params(exclude=["event_id", "tier_id"]),
	)


@frappe.whitelist()
@require_marzi()
def link_pretix_event(event_id: str):
	return MarziClient().post(
		f"/admin/events/{event_id}/pretix-link", service="v3", json_body=request_params(exclude=["event_id"])
	)


@frappe.whitelist()
@require_marzi()
def unlink_pretix_event(event_id: str):
	return MarziClient().delete(f"/admin/events/{event_id}/pretix-link", service="v3")


@frappe.whitelist()
@require_marzi()
def list_admin_orders(event_id: str):
	return MarziClient().get(
		f"/admin/events/{event_id}/orders", service="v3", params=request_params(exclude=["event_id"])
	)


@frappe.whitelist()
@require_marzi()
def get_admin_sales(event_id: str):
	return MarziClient().get(
		f"/admin/events/{event_id}/sales", service="v3", params=request_params(exclude=["event_id"])
	)


@frappe.whitelist()
@require_marzi()
def list_admin_attendees(event_id: str):
	return MarziClient().get(f"/admin/events/{event_id}/attendees", service="v3")


@frappe.whitelist()
@require_marzi()
def check_in_attendee(event_id: str, position_id: str):
	return MarziClient().post(f"/admin/events/{event_id}/attendees/{position_id}/check-in", service="v3")
