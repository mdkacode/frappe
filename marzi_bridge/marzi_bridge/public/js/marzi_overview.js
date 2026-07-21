// Marzi Bridge — record "overview" header, styled after admin-v2's detail pages.
//
// admin-v2 design language (event-detail.tsx / user-detail.tsx): a FLAT header —
// `text-2xl font-semibold` title with small rounded-full pill badges inline and a
// muted monospace id below; user-ish records get a round avatar beside the title,
// event-ish records get a full-width hero image (max-h-72, rounded-lg, border,
// object-cover) under the header; key fields render as a responsive grid of plain
// bordered cards (muted xs label over a medium value). No gradients, no shadows.
//
// Rendered into the `overview_banner` HTML field (injected by scripts/gen_doctypes.py)
// and driven entirely by each doctype's own metadata (`image_field`, `title_field`,
// `in_list_view` fields) — zero per-doctype code. Loaded via hooks `app_include_js`;
// we wrap Form.refresh once and gate on the "Marzi " doctype prefix.

frappe.provide("marzi");

(function () {
	const proto = frappe.ui.form && frappe.ui.form.Form && frappe.ui.form.Form.prototype;
	if (!proto || proto.__marzi_overview_patched) return;
	proto.__marzi_overview_patched = true;

	const _refresh = proto.refresh;
	proto.refresh = function (...args) {
		const out = _refresh.apply(this, args);
		try {
			if (this.doctype && this.doctype.indexOf("Marzi ") === 0 && this.doc && !this.is_new()) {
				marzi.render_overview(this);
				marzi.render_actions(this);
			}
		} catch (e) {
			console.error("marzi overview render failed", e); // never break the form
		}
		return out;
	};
})();

// State-transition actions per doctype -> whitelisted proxy methods (which already
// exist in marzi_bridge/api/*). Each: {label, method, arg (id kwarg name), when(doc),
// prompt (extra fields), primary}.
marzi.ACTIONS = {
	"Marzi Event": [
		{ label: "Publish", method: "marzi_bridge.api.events.publish_event", arg: "event_id",
		  when: (d) => d.status === "DRAFT", primary: true },
		{ label: "Cancel Event", method: "marzi_bridge.api.events.cancel_event", arg: "event_id",
		  when: (d) => d.status === "PUBLISHED",
		  prompt: [{ fieldname: "cancellation_reason", fieldtype: "Small Text", label: "Reason", reqd: 1 }] },
	],
	"Marzi Blog Post": [
		{ label: "Publish", method: "marzi_bridge.api.blog.publish_post", arg: "id",
		  when: (d) => d.status !== "PUBLISHED", primary: true },
		{ label: "Schedule", method: "marzi_bridge.api.blog.schedule_post", arg: "id",
		  when: (d) => d.status !== "PUBLISHED",
		  prompt: [{ fieldname: "publish_at", fieldtype: "Datetime", label: "Publish At", reqd: 1 }] },
		{ label: "Archive", method: "marzi_bridge.api.blog.archive_post", arg: "id",
		  when: (d) => d.status === "PUBLISHED" },
	],
	"Marzi Page": [
		{ label: "Publish", method: "marzi_bridge.api.pages.publish_page", arg: "page_id",
		  when: (d) => d.status === "DRAFT", primary: true },
		{ label: "Archive", method: "marzi_bridge.api.pages.archive_page", arg: "page_id",
		  when: (d) => d.status === "PUBLISHED" },
	],
	"Marzi Campaign": [
		{ label: "Activate", method: "marzi_bridge.api.campaigns.activate_campaign", arg: "campaign_id",
		  when: (d) => d.status !== "ACTIVE", primary: true },
		{ label: "Archive", method: "marzi_bridge.api.campaigns.archive_campaign", arg: "campaign_id",
		  when: (d) => d.status === "ACTIVE" },
	],
};

marzi.render_actions = function (frm) {
	const actions = marzi.ACTIONS[frm.doctype];
	if (!actions) return;
	actions.forEach((a) => {
		if (a.when && !a.when(frm.doc)) return;
		frm.add_custom_button(__(a.label), () => marzi._run_action(frm, a));
		if (a.primary) frm.change_custom_button_type(__(a.label), null, "primary");
	});
};

marzi._run_action = function (frm, a) {
	const call = (extra) =>
		frappe
			.call({ method: a.method, args: Object.assign({ [a.arg]: frm.doc.name }, extra || {}) })
			.then((r) => {
				if (!r.exc) {
					frappe.show_alert({ message: __("{0} done", [a.label]), indicator: "green" });
					frm.reload_doc();
				}
			});
	if (a.prompt) {
		frappe.prompt(a.prompt, (values) => call(values), __(a.label), __("Confirm"));
	} else {
		frappe.confirm(__("{0} — {1}?", [a.label, frm.doc.name]), () => call());
	}
};

marzi.render_overview = function (frm) {
	const field = frm.get_field("overview_banner");
	if (!field || !field.$wrapper) return;

	const meta = frm.meta;
	const doc = frm.doc;
	const esc = frappe.utils.escape_html;

	// -- image: avatar (people-ish fields) vs full-width hero (everything else) --
	let image_url = meta.image_field ? doc[meta.image_field] : null;
	if (image_url && !/^https?:\/\//.test(image_url)) image_url = null;
	const is_avatar = !!(meta.image_field && /profile|avatar|photo|author|pic|icon/i.test(meta.image_field));

	// -- title / subtitle --------------------------------------------------------
	const title = String((meta.title_field && doc[meta.title_field]) || doc.name || "—");
	const subtitle = doc.name && String(doc.name) !== title ? String(doc.name) : "";
	const initials = title
		.split(/\s+/)
		.slice(0, 2)
		.map((w) => w[0] || "")
		.join("")
		.toUpperCase();

	// -- key fields (the ones flagged for the list view) -> badges + info cards --
	// A field the hero already presents is hidden below to avoid duplication — but ONLY
	// when it's read-only. Editable fields stay visible so writable records can be edited.
	const title_df = meta.title_field && meta.fields.find((d) => d.fieldname === meta.title_field);
	const skip = new Set([meta.title_field, meta.image_field, "overview_banner"]);
	const layout = ["Section Break", "Column Break", "Tab Break", "HTML", "Table", "Image"];
	const badges = [];
	const cards = [];
	const used = title_df && title_df.read_only ? [meta.title_field] : [];
	(meta.fields || []).forEach((df) => {
		if (
			!df.in_list_view ||
			skip.has(df.fieldname) ||
			layout.indexOf(df.fieldtype) !== -1 ||
			doc[df.fieldname] == null ||
			doc[df.fieldname] === ""
		) {
			return;
		}
		if (df.fieldtype === "Select" || /status|state|mode|role|type/i.test(df.fieldname)) {
			badges.push({ value: doc[df.fieldname], klass: marzi._badge_class(doc[df.fieldname]) });
		} else {
			cards.push({ label: df.label || df.fieldname, value: marzi._fmt(df, doc[df.fieldname]) });
		}
		if (df.read_only) used.push(df.fieldname);
	});

	const badge_html = badges
		.map((b) => `<span class="marzi-badge ${b.klass}">${esc(String(b.value))}</span>`)
		.join("");

	const avatar_html = is_avatar
		? `<span class="marzi-avatar">${
				image_url ? `<img src="${esc(image_url)}" alt="" onerror="this.remove()">` : ""
		  }<span class="marzi-avatar-fb">${esc(initials || "M")}</span></span>`
		: "";

	const hero_html =
		!is_avatar && image_url
			? `<img class="marzi-hero-img" src="${esc(image_url)}" alt="" onerror="this.parentElement.removeChild(this)">`
			: "";

	const cards_html = cards.length
		? `<div class="marzi-cards">${cards
				.slice(0, 8)
				.map(
					(c) =>
						`<div class="marzi-card"><p class="marzi-card-k">${esc(
							String(c.label)
						)}</p><p class="marzi-card-v">${esc(String(c.value))}</p></div>`
				)
				.join("")}</div>`
		: "";

	const html = `
		<div class="marzi-ov">
			<div class="marzi-ov-head">
				${avatar_html}
				<div class="marzi-ov-idn">
					<div class="marzi-ov-titlerow">
						<h1 class="marzi-ov-title">${esc(title)}</h1>
						${badge_html}
					</div>
					${subtitle ? `<p class="marzi-ov-sub">${esc(subtitle)}</p>` : ""}
				</div>
			</div>
			${hero_html}
			${cards_html}
		</div>`;

	field.html ? field.html(html) : field.$wrapper.html(html);

	// The header already presents these (title, status pills, key stats) — hide their
	// plain read-only inputs below so the Overview doesn't repeat itself.
	used.forEach((fn) => frm.toggle_display(fn, false));
};

marzi._fmt = function (df, val) {
	if (df.fieldtype === "Check") return val ? "Yes" : "No";
	// Rupee amounts, admin-v2 style: ₹707 / ₹4,724 (en-IN grouping).
	if (df.fieldtype === "Float" || df.fieldtype === "Currency" || df.fieldtype === "Int") {
		const n = Number(val);
		if (!isNaN(n) && /amount|price|paid|total|gst|fee|revenue/i.test(df.fieldname)) {
			return "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
		}
		return isNaN(n) ? String(val) : n.toLocaleString("en-IN");
	}
	// ISO timestamps -> "9 Aug 2026, 10:30 pm" (raw 2026-08-09T17:00:00.000Z reads awful).
	if (typeof val === "string" && /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/.test(val)) {
		const d = new Date(val);
		if (!isNaN(d.getTime())) {
			return d.toLocaleString("en-IN", {
				day: "numeric",
				month: "short",
				year: "numeric",
				hour: "numeric",
				minute: "2-digit",
			});
		}
	}
	const s = String(val);
	return s.length > 64 ? s.slice(0, 61) + "…" : s;
};

// Mirrors admin-v2 statusColor(): green / blue / red / amber / gray, tailwind palette.
marzi._badge_class = function (val) {
	const v = String(val || "").toUpperCase();
	if (/ACTIVE|PUBLISHED|COMPLETED|CONFIRMED|APPROVED|SUCCESS|PAID|LIVE|RESOLVED/.test(v)) return "is-green";
	if (/CHECKED_IN|ONLINE|SENT/.test(v)) return "is-blue";
	if (/CANCELLED|SUSPENDED|DELETED|FAILED|REJECTED|BLOCKED|EXPIRED|CLOSED/.test(v)) return "is-red";
	if (/PENDING|DRAFT|PROCESSING|SCHEDULED|WAITING|OPEN/.test(v)) return "is-amber";
	return "is-gray";
};
