"""Runtime parity smoke test for the Marzi Bridge proxy.

Calls every READ-ONLY proxy endpoint once and reports the outcome, so you can
confirm the Frappe proxy reaches the same backend the admin dashboard does.

Run it as a linked Marzi Admin (see the OTP-link step in SETUP.md):

    bench --site marzi.localhost execute marzi_bridge.verify.smoke_test

It never writes: only list/get endpoints that need no path argument are called.
Results are classified so "not configured" (e.g. blog/whatsapp/payments left
unset) and "not linked" are reported cleanly rather than looking like failures.
"""

import frappe

# (module, function) — read-only endpoints that take no required path argument.
# Grouped by the upstream service they exercise.
_READ_ENDPOINTS = [
	# v1 gateway
	("users", "list_users"),
	("events", "list_events"),
	("events", "list_cities"),
	("bookings", "list_admin_bookings"),
	("groups", "list_groups"),
	("speakers", "list_speakers"),
	("testimonies", "list_testimonies"),
	("media", "list_media"),
	("statuses", "list_statuses"),
	("moderation", "list_blocked_messages"),
	("moderation", "get_moderation_rules"),
	("escalations", "list_pending_escalations"),
	# v3 gateway
	("ticketing", "list_admin_events"),
	# publishing service
	("campaigns", "list_campaigns"),
	("pages", "list_pages"),
	("templates", "list_templates"),
	("event_library", "list_faqs"),
	# blog service
	("blog", "list_posts"),
	("blog", "list_categories"),
	("blog", "list_tags"),
	# tracking service
	("tracking", "get_presence"),
	# unauthenticated Lambdas
	("payments", "list_all_payments"),
	("whatsapp", "list_conversations"),
]


def _classify(exc: Exception) -> str:
	from marzi_bridge.auth.tokens import NotLinkedError

	msg = str(exc)
	if isinstance(exc, NotLinkedError):
		return "SKIP  not linked — run the OTP link first"
	if "base URL is not configured" in msg:
		return "SKIP  service base URL not set in Marzi Bridge Settings"
	if isinstance(exc, frappe.PermissionError):
		return "FAIL  permission denied (need Marzi Admin / System Manager)"
	# MarziAPIError carries the upstream status + message.
	return f"FAIL  {msg}"


def probe_lists():
	"""Call each entity's get_list and report count / error explicitly."""
	import importlib

	frappe.set_user("Administrator")
	frappe.local.form_dict = frappe._dict()
	entities = {
		"Marzi Speaker": "marzi_speaker",
		"Marzi Event": "marzi_event",
		"Marzi Booking": "marzi_booking",
		"Marzi Group": "marzi_group",
		"Marzi Testimony": "marzi_testimony",
		"Marzi User": "marzi_user",
		"Marzi Media": "marzi_media",
		"Marzi Blog Post": "marzi_blog_post",
		"Marzi Page": "marzi_page",
		"Marzi Status": "marzi_status",
		"Marzi Escalation": "marzi_escalation",
		"Marzi Blocked Message": "marzi_blocked_message",
		"Marzi Campaign": "marzi_campaign",
		"Marzi Template": "marzi_template",
		"Marzi FAQ Group": "marzi_faq_group",
		"Marzi Info Item": "marzi_info_item",
		"Marzi WhatsApp Conversation": "marzi_whatsapp_conversation",
	}
	print("\n=== get_list probe ===")
	for dt, folder in entities.items():
		try:
			mod = importlib.import_module(
				f"marzi_bridge.marzi_bridge.doctype.{folder}.{folder}"
			)
			cls = getattr(mod, dt.replace(" ", ""))
			rows = cls.get_list(start=0, page_length=20)
			n = len(rows) if rows is not None else "None"
			print(f"  {dt:<16} rows={n}")
		except Exception as exc:  # noqa: BLE001
			print(f"  {dt:<16} ERROR {type(exc).__name__}: {str(exc)[:160]}")
	print()


def probe_details():
	"""Load ONE record per detail-capable entity; report scalars, images, child rows.

	Confirms the full-detail Form data actually resolves: image-field URL present,
	child-table grids populated. Run after migrate as Administrator (auto-links to the
	linked Marzi User's tokens via the client).
	"""
	import importlib

	frappe.set_user("Administrator")
	frappe.local.form_dict = frappe._dict()
	# entity -> folder; child_fields to count.
	targets = {
		"Marzi Event": ("marzi_event", ["attendees", "tiers"]),
		"Marzi Group": ("marzi_group", ["members", "posts"]),
		"Marzi User": ("marzi_user", ["bookings", "transactions"]),
		"Marzi Blog Post": ("marzi_blog_post", ["tags"]),
		"Marzi Page": ("marzi_page", []),
		"Marzi Booking": ("marzi_booking", []),
		"Marzi Media": ("marzi_media", []),
		"Marzi Speaker": ("marzi_speaker", []),
	}
	print("\n=== detail (load_from_db) probe ===")
	for dt, (folder, child_fields) in targets.items():
		try:
			mod = importlib.import_module(
				f"marzi_bridge.marzi_bridge.doctype.{folder}.{folder}"
			)
			cls = getattr(mod, dt.replace(" ", ""))
			rows = cls.get_list(start=0, page_length=1)
			if not rows:
				print(f"  {dt:<22} (no rows to open)")
				continue
			name = rows[0].get("name")
			doc = frappe.get_doc(dt, name)
			meta = frappe.get_meta(dt)
			img = meta.image_field
			img_val = (doc.get(img) if img else None) or ""
			scalars = sum(1 for df in meta.fields if df.fieldtype not in (
				"Section Break", "Column Break", "Tab Break", "Table", "Image") and doc.get(df.fieldname))
			child = " ".join(f"{cf}={len(doc.get(cf) or [])}" for cf in child_fields)
			print(f"  {dt:<22} scalars={scalars:<3} image={'Y' if img_val else '-'} {child}")
		except Exception as exc:  # noqa: BLE001
			print(f"  {dt:<22} ERROR {type(exc).__name__}: {str(exc)[:160]}")
	print()


def boot_can_read():
	"""List which Marzi DocTypes are in Administrator's readable set (router uses this)."""
	frappe.set_user("Administrator")
	user = frappe.get_user()
	user.build_permissions()
	can_read = set(user.can_read)
	names = [
		"Marzi Speaker",
		"Marzi Event",
		"Marzi Booking",
		"Marzi Group",
		"Marzi Testimony",
		"Marzi User",
		"Marzi Media",
	]
	print("\n=== readable (can_read) check ===")
	for dt in names:
		print(f"  {dt:<16} in can_read: {dt in can_read}")
	print()


def check_doctypes():
	"""Confirm each virtual DocType synced and its controller satisfies the contract."""
	import inspect

	from frappe.model.base_document import get_controller

	names = [
		"Marzi Speaker",
		"Marzi Event",
		"Marzi Booking",
		"Marzi Group",
		"Marzi Testimony",
		"Marzi User",
		"Marzi Media",
	]
	print("\n=== Marzi Bridge virtual DocTypes ===")
	for dt in names:
		synced = bool(frappe.db.exists("DocType", dt))
		if not synced:
			print(f"  {dt:<16} MISSING")
			continue
		controller = get_controller(dt)
		statics = all(
			isinstance(inspect.getattr_static(controller, m), staticmethod)
			for m in ("get_list", "get_count", "get_stats")
		)
		virtual = frappe.get_meta(dt).is_virtual
		print(f"  {dt:<16} synced=1 virtual={virtual} statics={int(statics)} ctrl={controller.__name__}")
	print()


def smoke_test():
	"""Call each read endpoint once; print a compact PASS/FAIL/SKIP report."""
	import importlib

	# Endpoints read query args from form_dict; ensure it's empty for arg-free calls.
	frappe.local.form_dict = frappe._dict()

	results = []
	for module, fn_name in _READ_ENDPOINTS:
		label = f"{module}.{fn_name}"
		try:
			mod = importlib.import_module(f"marzi_bridge.api.{module}")
			out = getattr(mod, fn_name)()
			n = len(out) if isinstance(out, (list, dict)) else "?"
			results.append((label, f"PASS  ({n} items/keys)"))
		except Exception as exc:  # noqa: BLE001 — smoke test: classify, never abort
			results.append((label, _classify(exc)))

	width = max(len(l) for l, _ in results)
	print("\n=== Marzi Bridge parity smoke test ===")
	print(f"(user: {frappe.session.user})\n")
	counts = {"PASS": 0, "FAIL": 0, "SKIP": 0}
	for label, status in results:
		counts[status[:4].strip()] = counts.get(status[:4].strip(), 0) + 1
		print(f"  {label:<{width}}  {status}")
	print(f"\n  PASS={counts.get('PASS',0)}  FAIL={counts.get('FAIL',0)}  SKIP={counts.get('SKIP',0)}\n")
	return counts
