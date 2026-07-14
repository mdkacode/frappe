"""OTP linking flow — links a Frappe user to their backend (marzi) admin account.

Called once per admin from a small Desk form. `verify_otp` only links accounts
whose backend role is ADMIN/SUPER_ADMIN and never returns the raw tokens to the
client — they are stored encrypted in the caller's `Marzi User Link`.
"""

import re

import frappe
from frappe import _
from frappe.utils import now_datetime

from marzi_bridge.auth.tokens import jwt_claims, store_tokens
from marzi_bridge.client import parse_response, raw_request
from marzi_bridge.marzi_bridge.doctype.marzi_bridge_settings.marzi_bridge_settings import get_settings
from marzi_bridge.permissions import require_marzi

_ADMIN_ROLES = {"ADMIN", "SUPER_ADMIN", "SUPER-ADMIN"}
_E164 = re.compile(r"^\+[1-9]\d{6,14}$")


@frappe.whitelist()
@require_marzi()
def send_otp(phone: str):
	phone = _validate_phone(phone)
	settings = get_settings()
	response = raw_request(
		"POST",
		"/auth/send-otp",
		version="v1",
		json_body={"phone": phone, "tenant_name": settings.default_tenant_name or "Marzi"},
	)
	if response.status_code >= 300:
		_fail(response, _("Failed to send OTP"))
	return {"status": "ok"}


@frappe.whitelist()
@require_marzi()
def verify_otp(phone: str, otp: str):
	phone = _validate_phone(phone)
	settings = get_settings()
	response = raw_request(
		"POST",
		"/auth/verify-otp",
		version="v1",
		json_body={
			"phone": phone,
			"otp": otp,
			"tenant_name": settings.default_tenant_name or "Marzi",
		},
	)
	if response.status_code >= 300:
		_fail(response, _("OTP verification failed"))

	data = (parse_response(response) or {}).get("data") or {}
	access, refresh = data.get("access"), data.get("refresh")
	if not access or not refresh:
		frappe.throw(_("Backend did not return tokens."))

	claims = jwt_claims(access)
	role = (claims.get("role") or "").strip().upper()
	if role not in _ADMIN_ROLES:
		frappe.throw(
			_("This phone is not an admin account and cannot be linked."),
			frappe.PermissionError,
		)

	_upsert_link(phone, data, claims, refresh, access)
	return {"status": "linked", "role": role}


@frappe.whitelist()
@require_marzi()
def link_status():
	"""Lightweight status for the linking UI — never exposes tokens."""
	from marzi_bridge.marzi_bridge.doctype.marzi_user_link.marzi_user_link import get_link

	link = get_link()
	if not link:
		return {"linked": False}
	return {
		"linked": True,
		"phone": link.phone,
		"marzi_role": link.marzi_role,
		"tenant_name": link.tenant_name,
		"access_expires_at": link.access_expires_at,
	}


# -- internals -----------------------------------------------------------------


def _upsert_link(phone, data, claims, refresh, access):
	from marzi_bridge.marzi_bridge.doctype.marzi_user_link.marzi_user_link import get_link

	link = get_link()
	if not link:
		link = frappe.new_doc("Marzi User Link")
		link.user = frappe.session.user

	link.phone = phone
	link.marzi_user_id = data.get("userId") or claims.get("sub")
	link.marzi_role = (claims.get("role") or "").strip().upper()
	link.tenant_name = claims.get("tenant_name") or (get_settings().default_tenant_name or "Marzi")
	link.linked_on = now_datetime()
	if not link.name:
		link.insert(ignore_permissions=True)
	store_tokens(link, access, refresh)


def _validate_phone(phone: str) -> str:
	phone = (phone or "").strip()
	if not _E164.match(phone):
		frappe.throw(_("Phone must be in E.164 format, e.g. +919876543210."))
	return phone


def _fail(response, prefix):
	body = parse_response(response)
	message = body.get("message") if isinstance(body, dict) else None
	frappe.throw(f"{prefix}: {message or response.status_code}")
