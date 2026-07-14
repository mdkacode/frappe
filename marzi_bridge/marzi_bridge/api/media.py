"""Media proxy — presigned upload URLs for images/assets.

Media in the backend is not a single resource; each domain issues its own
presigned-upload endpoints (API_DOC §3, §4, §8, §11). This module fans those out
so the Frappe UI has one place to request upload URLs.
"""

import frappe

from marzi_bridge.client import MarziClient, request_params
from marzi_bridge.permissions import require_marzi


@frappe.whitelist()
@require_marzi()
def group_image_upload_urls(group_id: str):
	return MarziClient().post(
		f"/groups/{group_id}/images/upload-urls", json_body=request_params(exclude=["group_id"])
	)


@frappe.whitelist()
@require_marzi()
def group_image_confirm(group_id: str):
	return MarziClient().post(
		f"/groups/{group_id}/images/confirm", json_body=request_params(exclude=["group_id"])
	)


@frappe.whitelist()
@require_marzi()
def post_media_upload_urls(group_id: str):
	return MarziClient().post(
		f"/groups/{group_id}/posts/media/upload-urls", json_body=request_params(exclude=["group_id"])
	)


@frappe.whitelist()
@require_marzi()
def blog_media_presign():
	return MarziClient().post("/admin/blog/media/presign", json_body=request_params())


@frappe.whitelist()
@require_marzi()
def home_hero_presign():
	# PUT /admin/home-hero returns a presigned URL for the home hero image.
	return MarziClient().put("/admin/home-hero", json_body=request_params())
