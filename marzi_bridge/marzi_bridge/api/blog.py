"""Blog proxy — Backend-for-org API_DOC §8 (admin blog CMS)."""

import frappe

from marzi_bridge.client import MarziClient, request_params
from marzi_bridge.permissions import require_marzi


@frappe.whitelist()
@require_marzi()
def list_posts():
	# Admin listing reuses the public list surface with admin auth.
	return MarziClient().get("/blog/posts", params=request_params())


@frappe.whitelist()
@require_marzi()
def create_post():
	return MarziClient().post("/admin/blog/posts", json_body=request_params())


@frappe.whitelist()
@require_marzi()
def update_post(post_id: str):
	return MarziClient().patch(f"/admin/blog/posts/{post_id}", json_body=request_params(exclude=["post_id"]))


@frappe.whitelist()
@require_marzi()
def publish_post(post_id: str):
	return MarziClient().patch(f"/admin/blog/posts/{post_id}/publish")


@frappe.whitelist()
@require_marzi()
def schedule_post(post_id: str):
	# Body carries publish_at.
	return MarziClient().patch(
		f"/admin/blog/posts/{post_id}/schedule", json_body=request_params(exclude=["post_id"])
	)


@frappe.whitelist()
@require_marzi()
def set_post_tags(post_id: str):
	# Body carries tag_ids array.
	return MarziClient().patch(
		f"/admin/blog/posts/{post_id}/tags", json_body=request_params(exclude=["post_id"])
	)


@frappe.whitelist()
@require_marzi()
def delete_post(post_id: str):
	return MarziClient().delete(f"/admin/blog/posts/{post_id}")


@frappe.whitelist()
@require_marzi()
def list_revisions(post_id: str):
	return MarziClient().get(f"/admin/blog/revisions/{post_id}")


@frappe.whitelist()
@require_marzi()
def create_category():
	return MarziClient().post("/admin/blog/categories", json_body=request_params())


@frappe.whitelist()
@require_marzi()
def create_tag():
	return MarziClient().post("/admin/blog/tags", json_body=request_params())
