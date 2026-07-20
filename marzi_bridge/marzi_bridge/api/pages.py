"""Pages proxy — mirrors publishingApi.ts PAGES endpoints (Backend-for-org API_DOC §14)."""

import frappe

from marzi_bridge.client import MarziClient, request_params
from marzi_bridge.permissions import require_marzi


@frappe.whitelist()
@require_marzi()
def list_pages():
	return MarziClient().get("/v1/publishing/admin/pages", service="publishing", params=request_params())


@frappe.whitelist()
@require_marzi()
def get_page(page_id: str):
	return MarziClient().get(f"/v1/publishing/admin/pages/{page_id}", service="publishing")


@frappe.whitelist()
@require_marzi()
def create_page():
	return MarziClient().post(
		"/v1/publishing/admin/pages", service="publishing", json_body=request_params()
	)


@frappe.whitelist()
@require_marzi()
def update_page(page_id: str):
	return MarziClient().patch(
		f"/v1/publishing/admin/pages/{page_id}",
		service="publishing",
		json_body=request_params(exclude=["page_id"]),
	)


@frappe.whitelist()
@require_marzi()
def publish_page(page_id: str):
	return MarziClient().post(f"/v1/publishing/admin/pages/{page_id}/publish", service="publishing")


@frappe.whitelist()
@require_marzi()
def archive_page(page_id: str):
	return MarziClient().post(f"/v1/publishing/admin/pages/{page_id}/archive", service="publishing")
