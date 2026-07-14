"""Pages proxy — Backend-for-org API_DOC §14 (publishing / CMS landing pages)."""

import frappe

from marzi_bridge.client import MarziClient, request_params
from marzi_bridge.permissions import require_marzi


@frappe.whitelist()
@require_marzi()
def list_pages():
	return MarziClient().get("/publishing/admin/pages", params=request_params())


@frappe.whitelist()
@require_marzi()
def get_page(page_id: str):
	return MarziClient().get(f"/publishing/admin/pages/{page_id}")


@frappe.whitelist()
@require_marzi()
def create_page():
	return MarziClient().post("/publishing/admin/pages", json_body=request_params())


@frappe.whitelist()
@require_marzi()
def update_page(page_id: str):
	return MarziClient().patch(
		f"/publishing/admin/pages/{page_id}", json_body=request_params(exclude=["page_id"])
	)


@frappe.whitelist()
@require_marzi()
def publish_page(page_id: str):
	return MarziClient().post(f"/publishing/admin/pages/{page_id}/publish")


@frappe.whitelist()
@require_marzi()
def archive_page(page_id: str):
	return MarziClient().post(f"/publishing/admin/pages/{page_id}/archive")
