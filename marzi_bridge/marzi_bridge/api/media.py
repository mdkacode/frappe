"""Media proxy — mirrors admin-v2/src/store/api/mediaApi.ts (Backend-for-org API_DOC §11).

mediaApi uses the v1 gateway (NEXT_PUBLIC_AUTH_API_URL) — the default service, so
the `service` kwarg is omitted. Paths are taken verbatim from each slice's `query`
block. The blog-image upload flow (src/lib/blog-image.ts + use-blog-image-upload.ts)
presigns via the BLOG service, kept here as `blog_media_presign`.
"""

import frappe

from marzi_bridge.client import MarziClient, request_params
from marzi_bridge.permissions import require_marzi


@frappe.whitelist()
@require_marzi()
def list_media():
	return MarziClient().get("/media", params=request_params())


@frappe.whitelist()
@require_marzi()
def get_media(assetId: str):
	return MarziClient().get(f"/media/{assetId}")


@frappe.whitelist()
@require_marzi()
def create_media():
	return MarziClient().post("/media", json_body=request_params())


@frappe.whitelist()
@require_marzi()
def confirm_media(assetId: str):
	return MarziClient().post(
		f"/media/{assetId}/confirm", json_body=request_params(exclude=["assetId"])
	)


@frappe.whitelist()
@require_marzi()
def delete_media(assetId: str):
	return MarziClient().delete(f"/media/{assetId}", params=request_params(exclude=["assetId"]))


@frappe.whitelist()
@require_marzi()
def blog_media_presign():
	# Blog cover-image / in-editor uploads presign against the BLOG service.
	# Mirrors presignMedia in blogApi.ts (POST /admin/media/presign).
	return MarziClient().post("/admin/media/presign", service="blog", json_body=request_params())
