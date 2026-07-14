import frappe
from frappe.model.document import Document


class MarziUserLink(Document):
	def validate(self):
		# A link always belongs to its user; the user cannot be another person's.
		if self.user != self.owner and frappe.session.user not in ("Administrator",):
			if not _is_system_manager():
				if self.user != frappe.session.user:
					frappe.throw("You can only manage your own Marzi User Link.")


def _is_system_manager() -> bool:
	return "System Manager" in frappe.get_roles(frappe.session.user)


def get_link(user: str | None = None) -> "MarziUserLink | None":
	"""Return the Marzi User Link for `user` (default: current session user), or None."""
	user = user or frappe.session.user
	name = frappe.db.exists("Marzi User Link", {"user": user})
	return frappe.get_doc("Marzi User Link", name) if name else None
