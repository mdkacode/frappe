"""Marzi Bridge desk branding: the left-sidebar navigation + logos.

`setup_sidebar()` builds a standard **Workspace Sidebar** for the Marzi Bridge
workspace so every API-backed entity is reachable directly from the left side nav
(grouped into the same sections as the admin-v2 dashboard), instead of only as
cards in the workspace body. Run it once (or after adding entities):

    bench --site <site> execute marzi_bridge.branding.setup_sidebar

The Marzi logo/favicon themselves are wired via hooks (app_logo_url,
website_context) + Website/Navbar Settings; the sidebar workspace icon is branded
with a small app-level CSS include (see public/css/marzi_branding.css).
"""

import frappe

SIDEBAR_TITLE = "Marzi Bridge"
WORKSPACE = "Marzi Bridge"

# (Section label, [(label, DocType, icon), ...]) — mirrors the dashboard sidebar.
SECTIONS = [
	("Configuration", [
		("Settings", "Marzi Bridge Settings", "setting-gear"),
		("User Link", "Marzi User Link", "link-url"),
	]),
	("Event Management", [
		("Events", "Marzi Event", "calendar"),
		("Bookings", "Marzi Booking", "check"),
		("FAQ Groups", "Marzi FAQ Group", "message"),
		("Info Items", "Marzi Info Item", "list"),
	]),
	("Communities", [
		("Groups", "Marzi Group", "users"),
		("WhatsApp", "Marzi WhatsApp Conversation", "message"),
		("Escalations", "Marzi Escalation", "alert"),
		("Blocked Messages", "Marzi Blocked Message", "unlink"),
	]),
	("App Configuration", [
		("Statuses", "Marzi Status", "activity"),
		("Testimonies", "Marzi Testimony", "star"),
		("Speakers", "Marzi Speaker", "user"),
	]),
	("Content", [
		("Blog Posts", "Marzi Blog Post", "text"),
		("Pages", "Marzi Page", "file"),
		("Campaigns", "Marzi Campaign", "tag"),
		("Templates", "Marzi Template", "layout"),
	]),
	("Users & Assets", [
		("Users", "Marzi User", "users"),
		("Media", "Marzi Media", "image-view"),
	]),
]


def _rows():
	"""Ordered list of item dicts: Home, then each Section Break + its child links."""
	rows = [
		# Home = the (API-backed) Marzi User list, per the dashboard's landing tab.
		{"label": "Home", "link_to": "Marzi User", "link_type": "DocType", "type": "Link", "icon": "home"},
	]
	for section_label, entries in SECTIONS:
		rows.append({"label": section_label, "type": "Section Break"})
		for label, doctype, icon in entries:
			if not frappe.db.exists("DocType", doctype):
				continue
			rows.append({
				"label": label,
				"link_to": doctype,
				"link_type": "DocType",
				"type": "Link",
				"icon": icon,
				"child": 1,
			})
	return rows


def setup_sidebar():
	"""(Re)create the standard Marzi Bridge Workspace Sidebar with all entities nested."""
	if frappe.db.exists("Workspace Sidebar", SIDEBAR_TITLE):
		frappe.delete_doc("Workspace Sidebar", SIDEBAR_TITLE, force=True, ignore_permissions=True)

	doc = frappe.new_doc("Workspace Sidebar")
	doc.title = SIDEBAR_TITLE
	doc.app = "marzi_bridge"
	doc.module = "Marzi Bridge"
	doc.standard = 1
	doc.header_icon = "integration"
	# append() assigns idx sequentially so the section/link order is preserved.
	for row in _rows():
		doc.append("items", row)
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	frappe.clear_cache()
	print(f"Workspace Sidebar '{SIDEBAR_TITLE}' created with {len(doc.items)} items.")
	return doc.name


LOGO_MARK = "/assets/marzi_bridge/images/marzi-favicon.png"


def apply_desk_branding():
	"""Native (non-CSS) branding: Marzi logo on the sidebar header, no Notification item.

	- The sidebar header (SidebarHeader.set_header_icon) renders `Desktop Icon.logo_url`
	  as an <img> when a Desktop Icon matching the workspace label exists; otherwise it
	  falls back to a generated initials avatar (the gray "M"). So we create/update a
	  Desktop Icon for the Marzi Bridge sidebar with the Marzi mark.
	- The sidebar "Notification" item stays hidden unless the user's `notifications`
	  desk property is on (notifications.js only unhides it when
	  boot.desk_settings.notifications is truthy). Turn it off for all system users.
	- The Form's right rail (Assigned To / Shared / Tags / Attachments) and the bottom
	  Activity/Comments footer are gated by the `form_sidebar` and `timeline` desk
	  properties (form.js checks boot.desk_settings.{form_sidebar,timeline}). These are
	  meaningless for read-only API-backed docs, so turn them off too. This is the
	  native gate Frappe itself checks — no CSS/JS override needed.

	    bench --site <site> execute marzi_bridge.branding.apply_desk_branding
	"""
	# 1) Desktop Icon with the Marzi logo (same shape as the standard sidebar icons).
	if frappe.db.exists("Desktop Icon", {"label": SIDEBAR_TITLE, "standard": 1}):
		icon = frappe.get_doc("Desktop Icon", {"label": SIDEBAR_TITLE, "standard": 1})
	else:
		icon = frappe.new_doc("Desktop Icon")
		icon.label = SIDEBAR_TITLE
	icon.update(
		{
			"standard": 1,
			"icon_type": "Link",
			"link_type": "Workspace Sidebar",
			"link_to": SIDEBAR_TITLE,
			"logo_url": LOGO_MARK,
			"app": "marzi_bridge",
			"hidden": 0,
		}
	)
	icon.flags.ignore_permissions = True
	icon.save(ignore_permissions=True) if not icon.is_new() else icon.insert(ignore_permissions=True)

	# 2) Strip desk chrome that's meaningless for read-only API docs, for every real
	# user: the Notification sidebar item, the Form right rail (assign/share/tags),
	# and the bottom Activity/Comments footer.
	users = frappe.get_all(
		"User", filters={"user_type": "System User", "enabled": 1}, pluck="name"
	)
	for user in users:
		frappe.db.set_value(
			"User",
			user,
			{"notifications": 0, "form_sidebar": 0, "timeline": 0},
			update_modified=False,
		)

	# 3) "Users" must always mean the API-backed Marzi users: hide Frappe's standard
	# "Users" rail icon so the only Users entry is Marzi User.
	if frappe.db.exists("Desktop Icon", {"label": "Users", "app": "frappe", "standard": 1}):
		frappe.db.set_value(
			"Desktop Icon", {"label": "Users", "app": "frappe", "standard": 1}, "hidden", 1
		)

	# 4) Land on this app (-> its route, the Marzi User list) after login.
	frappe.db.set_single_value("System Settings", "default_app", "marzi_bridge")

	frappe.db.commit()
	frappe.clear_cache()
	print(
		f"Desktop Icon '{SIDEBAR_TITLE}' -> {LOGO_MARK}; notifications/form_sidebar/timeline "
		f"off for {len(users)} users; Frappe 'Users' icon hidden; default_app=marzi_bridge."
	)
