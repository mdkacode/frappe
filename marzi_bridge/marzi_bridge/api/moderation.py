"""Moderation proxy — mirrors admin-v2/src/store/api/moderationApi.ts (v1 gateway)."""

import frappe

from marzi_bridge.client import MarziClient, request_params
from marzi_bridge.permissions import require_marzi


@frappe.whitelist()
@require_marzi()
def list_blocked_messages():
	return MarziClient().get("/moderation/blocked-messages", params=request_params())


@frappe.whitelist()
@require_marzi()
def list_blocked_messages_by_phone():
	return MarziClient().get("/moderation/blocked-messages/by-phone", params=request_params())


@frappe.whitelist()
@require_marzi()
def get_moderation_rules():
	return MarziClient().get("/moderation/rules")


@frappe.whitelist()
@require_marzi()
def update_moderation_rules():
	return MarziClient().post("/moderation/rules", json_body=request_params())


@frappe.whitelist()
@require_marzi()
def check_content():
	return MarziClient().post("/content/moderation", json_body=request_params())
