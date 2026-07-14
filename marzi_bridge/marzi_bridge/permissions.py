"""Access-control seam for proxy endpoints.

This phase uses a single base role (`Marzi Admin`). Granular roles (Ops Admin /
Ops Support / Content Editor / Community Moderator) are a later RBAC track — they
plug in here by passing `roles=(...)` per endpoint, without touching call sites.
"""

import functools

import frappe
from frappe import _


def require_marzi(roles=("Marzi Admin",)):
	"""Gate a whitelisted method on Frappe roles.

	Usage — `@frappe.whitelist()` must remain the OUTERMOST decorator so the
	framework sees the wrapped function::

	    @frappe.whitelist()
	    @require_marzi()
	    def list_speakers():
	        ...

	`System Manager` always passes.
	"""

	allowed = set(roles) | {"System Manager"}

	def decorator(fn):
		@functools.wraps(fn)
		def wrapper(*args, **kwargs):
			if not (set(frappe.get_roles()) & allowed):
				frappe.throw(
					_("You do not have permission to use this action."),
					frappe.PermissionError,
				)
			return fn(*args, **kwargs)

		return wrapper

	return decorator
