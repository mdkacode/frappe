"""Users proxy — mirrors admin-v2/src/store/api/usersApi.ts.

Thin pass-through to the backend `/users` routes (Backend-for-org API_DOC §2).
"""

import frappe

from marzi_bridge.client import MarziClient, request_params
from marzi_bridge.permissions import require_marzi


@frappe.whitelist()
@require_marzi()
def get_me():
	return MarziClient().get("/users/me")


@frappe.whitelist()
@require_marzi()
def update_me():
	return MarziClient().patch("/users/me", json_body=request_params())


@frappe.whitelist()
@require_marzi()
def list_users():
	return MarziClient().get("/users", params=request_params())


@frappe.whitelist()
@require_marzi()
def search_users():
	return MarziClient().get("/users/search", params=request_params())


@frappe.whitelist()
@require_marzi()
def get_user(user_id: str):
	return MarziClient().get(f"/users/{user_id}")
