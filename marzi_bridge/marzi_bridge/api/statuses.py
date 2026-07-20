"""Statuses proxy — mirrors admin-v2/src/store/api/statusesApi.ts (v1 gateway)."""

import frappe

from marzi_bridge.client import MarziClient, request_params
from marzi_bridge.permissions import require_marzi


@frappe.whitelist()
@require_marzi()
def list_statuses():
	return MarziClient().get("/admin/statuses", params=request_params())


@frappe.whitelist()
@require_marzi()
def create_status():
	return MarziClient().post("/admin/statuses", json_body=request_params())


@frappe.whitelist()
@require_marzi()
def update_status(status_id: str):
	return MarziClient().patch(
		f"/admin/statuses/{status_id}",
		json_body=request_params(exclude=["status_id"]),
	)


@frappe.whitelist()
@require_marzi()
def delete_status(status_id: str):
	return MarziClient().delete(f"/admin/statuses/{status_id}")
