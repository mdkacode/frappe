"""Event Library proxy — reusable content referenced by events.

Mirrors the event-library endpoints of admin-v2/src/store/api/eventsApi.ts
(info items/sections, FAQ groups, testimonials/sections, galleries — v1 service,
Backend-for-org "Event Library API") plus the FAQ-item endpoints of
admin-v2/src/store/api/publishingApi.ts (publishing service, API_DOC §14).
"""

import frappe

from marzi_bridge.client import MarziClient, request_params
from marzi_bridge.permissions import require_marzi


# --- Info items (v1) ---------------------------------------------------------


@frappe.whitelist()
@require_marzi()
def list_info_items():
	return MarziClient().get("/admin/event-library/info-items", params=request_params())


@frappe.whitelist()
@require_marzi()
def create_info_item():
	return MarziClient().post("/admin/event-library/info-items", json_body=request_params())


@frappe.whitelist()
@require_marzi()
def update_info_item(item_id: str):
	return MarziClient().put(
		f"/admin/event-library/info-items/{item_id}", json_body=request_params(exclude=["item_id"])
	)


@frappe.whitelist()
@require_marzi()
def delete_info_item(item_id: str):
	return MarziClient().delete(f"/admin/event-library/info-items/{item_id}")


# --- Info sections (v1) ------------------------------------------------------


@frappe.whitelist()
@require_marzi()
def list_info_sections():
	return MarziClient().get("/admin/event-library/info-sections", params=request_params())


@frappe.whitelist()
@require_marzi()
def create_info_section():
	return MarziClient().post("/admin/event-library/info-sections", json_body=request_params())


@frappe.whitelist()
@require_marzi()
def update_info_section(section_id: str):
	return MarziClient().put(
		f"/admin/event-library/info-sections/{section_id}", json_body=request_params(exclude=["section_id"])
	)


@frappe.whitelist()
@require_marzi()
def delete_info_section(section_id: str):
	return MarziClient().delete(f"/admin/event-library/info-sections/{section_id}")


# --- FAQ groups (v1) ---------------------------------------------------------


@frappe.whitelist()
@require_marzi()
def list_faq_groups():
	return MarziClient().get("/admin/event-library/faq-groups", params=request_params())


@frappe.whitelist()
@require_marzi()
def create_faq_group():
	return MarziClient().post("/admin/event-library/faq-groups", json_body=request_params())


@frappe.whitelist()
@require_marzi()
def update_faq_group(group_id: str):
	return MarziClient().put(
		f"/admin/event-library/faq-groups/{group_id}", json_body=request_params(exclude=["group_id"])
	)


@frappe.whitelist()
@require_marzi()
def delete_faq_group(group_id: str):
	return MarziClient().delete(f"/admin/event-library/faq-groups/{group_id}")


# --- Testimonials (v1) -------------------------------------------------------


@frappe.whitelist()
@require_marzi()
def list_testimonials():
	return MarziClient().get("/admin/event-library/testimonials", params=request_params())


@frappe.whitelist()
@require_marzi()
def create_testimonial():
	return MarziClient().post("/admin/event-library/testimonials", json_body=request_params())


@frappe.whitelist()
@require_marzi()
def update_testimonial(testimonial_id: str):
	return MarziClient().put(
		f"/admin/event-library/testimonials/{testimonial_id}",
		json_body=request_params(exclude=["testimonial_id"]),
	)


@frappe.whitelist()
@require_marzi()
def delete_testimonial(testimonial_id: str):
	return MarziClient().delete(f"/admin/event-library/testimonials/{testimonial_id}")


# --- Testimonial sections (v1) -----------------------------------------------


@frappe.whitelist()
@require_marzi()
def list_testimonial_sections():
	return MarziClient().get("/admin/event-library/testimonial-sections", params=request_params())


@frappe.whitelist()
@require_marzi()
def create_testimonial_section():
	return MarziClient().post("/admin/event-library/testimonial-sections", json_body=request_params())


@frappe.whitelist()
@require_marzi()
def update_testimonial_section(section_id: str):
	return MarziClient().put(
		f"/admin/event-library/testimonial-sections/{section_id}",
		json_body=request_params(exclude=["section_id"]),
	)


@frappe.whitelist()
@require_marzi()
def delete_testimonial_section(section_id: str):
	return MarziClient().delete(f"/admin/event-library/testimonial-sections/{section_id}")


# --- Galleries (v1) ----------------------------------------------------------


@frappe.whitelist()
@require_marzi()
def list_galleries():
	return MarziClient().get("/admin/event-library/galleries", params=request_params())


@frappe.whitelist()
@require_marzi()
def create_gallery():
	return MarziClient().post("/admin/event-library/galleries", json_body=request_params())


@frappe.whitelist()
@require_marzi()
def update_gallery(gallery_id: str):
	return MarziClient().put(
		f"/admin/event-library/galleries/{gallery_id}", json_body=request_params(exclude=["gallery_id"])
	)


@frappe.whitelist()
@require_marzi()
def delete_gallery(gallery_id: str):
	return MarziClient().delete(f"/admin/event-library/galleries/{gallery_id}")


# --- FAQ items (publishing service; FAQ groups above reference these ids) ----


@frappe.whitelist()
@require_marzi()
def list_faqs():
	return MarziClient().get("/v1/publishing/admin/faqs", service="publishing", params=request_params())


@frappe.whitelist()
@require_marzi()
def create_faq():
	return MarziClient().post("/v1/publishing/admin/faqs", service="publishing", json_body=request_params())
