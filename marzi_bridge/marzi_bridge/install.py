import frappe


def after_install():
	"""Create the base `Marzi Admin` role used to gate every proxy endpoint.

	Granular roles (Ops Admin / Ops Support / Content Editor / Community
	Moderator) are a later RBAC track; this phase only needs a single gate.
	"""
	_ensure_role("Marzi Admin")


def _ensure_role(role_name: str):
	if frappe.db.exists("Role", role_name):
		return
	frappe.get_doc(
		{
			"doctype": "Role",
			"role_name": role_name,
			"desk_access": 1,
		}
	).insert(ignore_permissions=True)
