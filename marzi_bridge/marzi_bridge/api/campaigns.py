"""Campaigns proxy — Backend-for-org API_DOC §6b (admin campaign config)."""

import frappe

from marzi_bridge.client import MarziClient, request_params
from marzi_bridge.permissions import require_marzi


@frappe.whitelist()
@require_marzi()
def list_campaigns():
	return MarziClient().get("/admin/campaigns", params=request_params())


@frappe.whitelist()
@require_marzi()
def create_campaign():
	# Create or replace a campaign config.
	return MarziClient().post("/admin/campaigns", json_body=request_params())


@frappe.whitelist()
@require_marzi()
def update_campaign(campaign_name: str):
	return MarziClient().put(
		f"/admin/campaigns/{campaign_name}", json_body=request_params(exclude=["campaign_name"])
	)
