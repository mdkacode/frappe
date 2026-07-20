"""Events proxy — core v1 event endpoints.

Mirrors the v1 (service default) endpoints of admin-v2/src/store/api/eventsApi.ts
(Backend-for-org API_DOC §5). v3 tiered-ticketing endpoints live in ticketing.py.
"""

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
def get_attendees(event_id: str):
	return MarziClient().get(f"/events/{event_id}/attendees", params=request_params(exclude=["event_id"]))


@frappe.whitelist()
@require_marzi()
def get_booking(booking_id: str):
	return MarziClient().get(f"/bookings/{booking_id}")


@frappe.whitelist()
@require_marzi()
def cancel_booking(booking_id: str):
	return MarziClient().delete(f"/bookings/{booking_id}")


@frappe.whitelist()
@require_marzi()
def check_in_attendee(booking_id: str):
	return MarziClient().post(f"/bookings/{booking_id}/check-in", json_body=request_params(exclude=["booking_id"]))


@frappe.whitelist()
@require_marzi()
def list_cities():
	return MarziClient().get("/cities")


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
