"""Device Health proxy — device registration + admin install stats (v1 gateway).

Mirrors the device endpoints of Backend-for-org (userHandler): each user can
register/unregister their own push devices, and admins can read aggregate install
stats. `GET /admin/devices/stats` returns a summary object (counts by platform /
token type), NOT a list of individual devices — there is no admin per-device list
endpoint, so Device Health is surfaced as stats, not a browsable DocType.
"""

import frappe

from marzi_bridge.client import MarziClient, request_params
from marzi_bridge.permissions import require_marzi


@frappe.whitelist()
@require_marzi()
def get_device_stats():
	"""Aggregate install stats: installedUsers, totalUsers, installRate, byPlatform, byTokenType."""
	return MarziClient().get("/admin/devices/stats")


@frappe.whitelist()
@require_marzi()
def register_device():
	return MarziClient().post("/users/me/devices", json_body=request_params())


@frappe.whitelist()
@require_marzi()
def delete_device(device_id: str):
	return MarziClient().delete(f"/users/me/devices/{device_id}")
