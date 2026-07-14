"""Event Library proxy — info chips / FAQ groups / testimonials shown in-app.

Concrete, confirmed surface: the reusable global FAQ library under publishing
(Backend-for-org API_DOC §14). Info-chips and event-info sections were referenced
in the admin-v2 UI but do not have a crisply documented route in API_DOC — those
are left as TODOs to confirm against the live backend before wiring, rather than
guessing an endpoint.
"""

import frappe

from marzi_bridge.client import MarziClient, request_params
from marzi_bridge.permissions import require_marzi


@frappe.whitelist()
@require_marzi()
def list_faqs():
	return MarziClient().get("/publishing/admin/faqs", params=request_params())


@frappe.whitelist()
@require_marzi()
def get_faq(faq_id: str):
	return MarziClient().get(f"/publishing/admin/faqs/{faq_id}")


@frappe.whitelist()
@require_marzi()
def create_faq():
	return MarziClient().post("/publishing/admin/faqs", json_body=request_params())


@frappe.whitelist()
@require_marzi()
def update_faq(faq_id: str):
	return MarziClient().patch(f"/publishing/admin/faqs/{faq_id}", json_body=request_params(exclude=["faq_id"]))


@frappe.whitelist()
@require_marzi()
def delete_faq(faq_id: str):
	return MarziClient().delete(f"/publishing/admin/faqs/{faq_id}")


# TODO: confirm backend routes for info-chips and event-info sections, then add
# list/create/update/delete proxies here following the same pattern.
