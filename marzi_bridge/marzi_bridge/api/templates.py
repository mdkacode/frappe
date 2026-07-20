"""Templates proxy — mirrors publishingApi.ts page-TEMPLATE endpoints (Backend-for-org API_DOC §14)."""

import frappe

from marzi_bridge.client import MarziClient, request_params
from marzi_bridge.permissions import require_marzi


@frappe.whitelist()
@require_marzi()
def list_templates():
	return MarziClient().get("/v1/publishing/admin/templates", service="publishing", params=request_params())


@frappe.whitelist()
@require_marzi()
def get_template(template_id: str):
	return MarziClient().get(f"/v1/publishing/admin/templates/{template_id}", service="publishing")


@frappe.whitelist()
@require_marzi()
def create_template():
	return MarziClient().post(
		"/v1/publishing/admin/templates", service="publishing", json_body=request_params()
	)


@frappe.whitelist()
@require_marzi()
def update_template(template_id: str):
	return MarziClient().patch(
		f"/v1/publishing/admin/templates/{template_id}",
		service="publishing",
		json_body=request_params(exclude=["template_id"]),
	)


@frappe.whitelist()
@require_marzi()
def delete_template(template_id: str):
	return MarziClient().delete(f"/v1/publishing/admin/templates/{template_id}", service="publishing")
