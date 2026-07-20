"""Blog proxy — mirrors admin-v2/src/store/api/blogApi.ts (Backend-for-org API_DOC §8).

blogApi uses the BLOG service subdomain (NEXT_PUBLIC_BLOG_API_URL) — every call
passes service="blog". Paths are taken verbatim from each slice's `query` block.
"""

import frappe

from marzi_bridge.client import MarziClient, request_params
from marzi_bridge.permissions import require_marzi


@frappe.whitelist()
@require_marzi()
def list_posts():
	return MarziClient().get("/admin/posts", service="blog", params=request_params())


@frappe.whitelist()
@require_marzi()
def get_post(id: str):
	return MarziClient().get(f"/admin/posts/{id}", service="blog")


@frappe.whitelist()
@require_marzi()
def create_post():
	return MarziClient().post("/admin/posts", service="blog", json_body=request_params())


@frappe.whitelist()
@require_marzi()
def update_post(id: str):
	return MarziClient().patch(
		f"/admin/posts/{id}", service="blog", json_body=request_params(exclude=["id"])
	)


@frappe.whitelist()
@require_marzi()
def publish_post(id: str):
	return MarziClient().post(
		f"/admin/posts/{id}/publish", service="blog", json_body=request_params(exclude=["id"])
	)


@frappe.whitelist()
@require_marzi()
def schedule_post(id: str):
	return MarziClient().post(
		f"/admin/posts/{id}/schedule", service="blog", json_body=request_params(exclude=["id"])
	)


@frappe.whitelist()
@require_marzi()
def archive_post(id: str):
	return MarziClient().post(
		f"/admin/posts/{id}/archive", service="blog", json_body=request_params(exclude=["id"])
	)


@frappe.whitelist()
@require_marzi()
def list_revisions(id: str):
	return MarziClient().get(f"/admin/posts/{id}/revisions", service="blog")


@frappe.whitelist()
@require_marzi()
def restore_revision(id: str, version: str):
	return MarziClient().post(
		f"/admin/posts/{id}/revisions/{version}/restore",
		service="blog",
		json_body=request_params(exclude=["id", "version"]),
	)


@frappe.whitelist()
@require_marzi()
def list_categories():
	return MarziClient().get("/categories", service="blog", params=request_params())


@frappe.whitelist()
@require_marzi()
def create_category():
	return MarziClient().post("/admin/categories", service="blog", json_body=request_params())


@frappe.whitelist()
@require_marzi()
def list_tags():
	return MarziClient().get("/tags", service="blog", params=request_params())


@frappe.whitelist()
@require_marzi()
def create_tag():
	return MarziClient().post("/admin/tags", service="blog", json_body=request_params())


@frappe.whitelist()
@require_marzi()
def presign_media():
	return MarziClient().post("/admin/media/presign", service="blog", json_body=request_params())
