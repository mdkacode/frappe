"""Testimonies proxy — Backend-for-org API_DOC §2 (admin testimonials)."""

import frappe

from marzi_bridge.client import MarziClient, request_params
from marzi_bridge.permissions import require_marzi


@frappe.whitelist()
@require_marzi()
def list_testimonies():
	return MarziClient().get("/admin/testimonials", params=request_params())


@frappe.whitelist()
@require_marzi()
def get_testimony(testimony_id: str):
	return MarziClient().get(f"/admin/testimonials/{testimony_id}")


@frappe.whitelist()
@require_marzi()
def create_testimony():
	return MarziClient().post("/admin/testimonials", json_body=request_params())


@frappe.whitelist()
@require_marzi()
def update_testimony(testimony_id: str):
	return MarziClient().patch(
		f"/admin/testimonials/{testimony_id}", json_body=request_params(exclude=["testimony_id"])
	)


@frappe.whitelist()
@require_marzi()
def delete_testimony(testimony_id: str):
	return MarziClient().delete(f"/admin/testimonials/{testimony_id}")
