"""Campaigns proxy — mirrors campaignApi.ts (campaigns + campaign-pages + leads; Backend-for-org API_DOC §14)."""

import frappe

from marzi_bridge.client import MarziClient, request_params
from marzi_bridge.permissions import require_marzi


# ─── Campaigns ────────────────────────────────────────────────────────────────


@frappe.whitelist()
@require_marzi()
def list_campaigns():
	return MarziClient().get("/v1/publishing/admin/campaigns", service="publishing", params=request_params())


@frappe.whitelist()
@require_marzi()
def get_campaign(campaign_id: str):
	return MarziClient().get(f"/v1/publishing/admin/campaigns/{campaign_id}", service="publishing")


@frappe.whitelist()
@require_marzi()
def create_campaign():
	return MarziClient().post(
		"/v1/publishing/admin/campaigns", service="publishing", json_body=request_params()
	)


@frappe.whitelist()
@require_marzi()
def update_campaign(campaign_id: str):
	# Dashboard uses PATCH here (campaignApi.ts updateCampaign) — not PUT.
	return MarziClient().patch(
		f"/v1/publishing/admin/campaigns/{campaign_id}",
		service="publishing",
		json_body=request_params(exclude=["campaign_id"]),
	)


@frappe.whitelist()
@require_marzi()
def activate_campaign(campaign_id: str):
	return MarziClient().post(
		f"/v1/publishing/admin/campaigns/{campaign_id}/publish", service="publishing"
	)


@frappe.whitelist()
@require_marzi()
def archive_campaign(campaign_id: str):
	return MarziClient().post(
		f"/v1/publishing/admin/campaigns/{campaign_id}/archive", service="publishing"
	)


# ─── Leads ────────────────────────────────────────────────────────────────────


@frappe.whitelist()
@require_marzi()
def list_campaign_leads(campaign_id: str):
	return MarziClient().get(
		f"/v1/publishing/admin/campaigns/{campaign_id}/leads", service="publishing"
	)


# ─── Campaign pages ─────────────────────────────────────────────────────────────


@frappe.whitelist()
@require_marzi()
def list_campaign_pages(campaign_id: str):
	return MarziClient().get(
		f"/v1/publishing/admin/campaigns/{campaign_id}/pages", service="publishing"
	)


@frappe.whitelist()
@require_marzi()
def get_campaign_page(page_id: str):
	return MarziClient().get(f"/v1/publishing/admin/campaign-pages/{page_id}", service="publishing")


@frappe.whitelist()
@require_marzi()
def create_campaign_page(campaign_id: str):
	return MarziClient().post(
		f"/v1/publishing/admin/campaigns/{campaign_id}/pages",
		service="publishing",
		json_body=request_params(exclude=["campaign_id"]),
	)


@frappe.whitelist()
@require_marzi()
def update_campaign_page(page_id: str):
	return MarziClient().patch(
		f"/v1/publishing/admin/campaign-pages/{page_id}",
		service="publishing",
		json_body=request_params(exclude=["page_id"]),
	)


@frappe.whitelist()
@require_marzi()
def publish_campaign_page(page_id: str):
	return MarziClient().post(
		f"/v1/publishing/admin/campaign-pages/{page_id}/publish", service="publishing"
	)


@frappe.whitelist()
@require_marzi()
def archive_campaign_page(page_id: str):
	return MarziClient().post(
		f"/v1/publishing/admin/campaign-pages/{page_id}/archive", service="publishing"
	)
