"""Escalations proxy — mirrors admin-v2/src/store/api/escalationsApi.ts (v1 gateway)."""

import frappe

from marzi_bridge.client import MarziClient, request_params
from marzi_bridge.permissions import require_marzi


@frappe.whitelist()
@require_marzi()
def list_pending_escalations():
	return MarziClient().get("/dashboard/escalations/pending", params=request_params())


@frappe.whitelist()
@require_marzi()
def list_resolved_escalations():
	return MarziClient().get("/dashboard/escalations/resolved", params=request_params())


@frappe.whitelist()
@require_marzi()
def list_escalations_by_phone():
	return MarziClient().get("/dashboard/escalations/by-mobile", params=request_params())


@frappe.whitelist()
@require_marzi()
def update_escalation(escalation_id: str):
	return MarziClient().patch(
		f"/dashboard/escalations/{escalation_id}",
		json_body=request_params(exclude=["escalation_id"]),
	)
