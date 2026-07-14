"""Templates proxy — page templates used to generate customer-facing pages.

In the backend, a publishing page carries a `template` field (T1|T2); there is no
standalone `/templates` CRUD resource documented in API_DOC §14. Until a dedicated
template endpoint is confirmed, this module exposes the template dimension via the
publishing pages surface (filtered by template) and leaves richer template
management as a TODO — we do not fabricate a route.
"""

import frappe

from marzi_bridge.client import MarziClient, request_params
from marzi_bridge.permissions import require_marzi


@frappe.whitelist()
@require_marzi()
def list_pages_by_template():
	# Forwards a `template` filter (e.g. T1|T2) to the publishing pages listing.
	return MarziClient().get("/publishing/admin/pages", params=request_params())


# TODO: confirm whether the backend exposes a dedicated template CRUD resource.
# If so, add list/get/create/update/delete proxies here following the standard
# pattern (see speakers.py). Do not invent routes before confirming.
