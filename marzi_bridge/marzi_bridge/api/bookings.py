"""Bookings proxy — Backend-for-org API_DOC §6."""

import frappe

from marzi_bridge.client import MarziClient, request_params
from marzi_bridge.permissions import require_marzi


@frappe.whitelist()
@require_marzi()
def list_bookings():
	# Supports filters + ?format=csv (see API_DOC §6 notes).
	return MarziClient().get("/admin/bookings", params=request_params())


@frappe.whitelist()
@require_marzi()
def list_attendees(event_id: str):
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
def check_in(booking_id: str):
	return MarziClient().post(f"/bookings/{booking_id}/check-in", json_body=request_params(exclude=["booking_id"]))
