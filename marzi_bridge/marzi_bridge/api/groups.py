"""Groups / Communities proxy — mirrors admin-v2/src/store/api/groupsApi.ts.

Thin pass-through to the backend `/groups` routes (Backend-for-org API_DOC §3).
"""

import frappe

from marzi_bridge.client import MarziClient, request_params
from marzi_bridge.permissions import require_marzi


@frappe.whitelist()
@require_marzi()
def list_groups():
	return MarziClient().get("/groups", params=request_params())


@frappe.whitelist()
@require_marzi()
def get_group(group_id: str):
	return MarziClient().get(f"/groups/{group_id}")


@frappe.whitelist()
@require_marzi()
def create_group():
	return MarziClient().post("/groups", json_body=request_params())


@frappe.whitelist()
@require_marzi()
def update_group(group_id: str):
	return MarziClient().patch(f"/groups/{group_id}", json_body=request_params(exclude=["group_id"]))


@frappe.whitelist()
@require_marzi()
def delete_group(group_id: str):
	return MarziClient().delete(f"/groups/{group_id}")


@frappe.whitelist()
@require_marzi()
def get_image_upload_urls(group_id: str):
	return MarziClient().post(
		f"/groups/{group_id}/images/upload-urls", json_body=request_params(exclude=["group_id"])
	)


@frappe.whitelist()
@require_marzi()
def confirm_image_upload(group_id: str):
	return MarziClient().post(
		f"/groups/{group_id}/images/confirm", json_body=request_params(exclude=["group_id"])
	)


@frappe.whitelist()
@require_marzi()
def list_members(group_id: str):
	return MarziClient().get(f"/groups/{group_id}/members", params=request_params(exclude=["group_id"]))


@frappe.whitelist()
@require_marzi()
def update_member_role(group_id: str, user_id: str):
	return MarziClient().patch(
		f"/groups/{group_id}/members/{user_id}",
		json_body=request_params(exclude=["group_id", "user_id"]),
	)


@frappe.whitelist()
@require_marzi()
def remove_member(group_id: str, user_id: str):
	return MarziClient().delete(f"/groups/{group_id}/members/{user_id}")


@frappe.whitelist()
@require_marzi()
def list_pending_members(group_id: str):
	return MarziClient().get(
		f"/groups/{group_id}/pending-members", params=request_params(exclude=["group_id"])
	)


@frappe.whitelist()
@require_marzi()
def approve_pending_member(group_id: str, user_id: str):
	return MarziClient().post(f"/groups/{group_id}/pending-members/{user_id}/approve")


@frappe.whitelist()
@require_marzi()
def reject_pending_member(group_id: str, user_id: str):
	return MarziClient().post(f"/groups/{group_id}/pending-members/{user_id}/reject")


@frappe.whitelist()
@require_marzi()
def list_posts(group_id: str):
	return MarziClient().get(f"/groups/{group_id}/posts", params=request_params(exclude=["group_id"]))


@frappe.whitelist()
@require_marzi()
def delete_post(group_id: str, post_id: str):
	return MarziClient().delete(f"/groups/{group_id}/posts/{post_id}")


@frappe.whitelist()
@require_marzi()
def list_comments(group_id: str, post_id: str):
	return MarziClient().get(
		f"/groups/{group_id}/posts/{post_id}/comments",
		params=request_params(exclude=["group_id", "post_id"]),
	)


@frappe.whitelist()
@require_marzi()
def delete_comment(group_id: str, post_id: str, comment_id: str):
	return MarziClient().delete(f"/groups/{group_id}/posts/{post_id}/comments/{comment_id}")
