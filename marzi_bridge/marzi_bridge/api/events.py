"""Events proxy — Backend-for-org API_DOC §5 (+ v3 admin events §13)."""

import frappe

from marzi_bridge.client import MarziClient, request_params
from marzi_bridge.permissions import require_marzi


@frappe.whitelist()
@require_marzi()
def list_events():
	return MarziClient().get("/admin/events", params=request_params())


@frappe.whitelist()
@require_marzi()
def get_event(event_id: str):
	return MarziClient().get(f"/events/{event_id}")


@frappe.whitelist()
@require_marzi()
def create_event():
	return MarziClient().post("/events", json_body=request_params())


@frappe.whitelist()
@require_marzi()
def update_event(event_id: str):
	return MarziClient().put(f"/events/{event_id}", json_body=request_params(exclude=["event_id"]))


@frappe.whitelist()
@require_marzi()
def publish_event(event_id: str):
	return MarziClient().post(f"/events/{event_id}/publish", json_body=request_params(exclude=["event_id"]))


@frappe.whitelist()
@require_marzi()
def cancel_event(event_id: str):
	# Backend expects cancellation_reason + optional notify_attendees.
	return MarziClient().post(f"/events/{event_id}/cancel", json_body=request_params(exclude=["event_id"]))


@frappe.whitelist()
@require_marzi()
def list_cities():
	return MarziClient().get("/cities")


# --- v3 tiered admin events (API_DOC §13) ------------------------------------


@frappe.whitelist()
@require_marzi()
def list_tiered_events():
	return MarziClient().get("/admin/events", version="v3", params=request_params())


@frappe.whitelist()
@require_marzi()
def get_tiered_event(event_id: str):
	return MarziClient().get(f"/admin/events/{event_id}", version="v3")
