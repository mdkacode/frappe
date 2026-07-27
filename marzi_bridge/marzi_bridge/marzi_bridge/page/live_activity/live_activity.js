// Marzi Bridge — Live Activity desk page.
//
// Mirrors admin-v2's LiveActivity (GANGADHAR tracking service). The admin-v2 app uses a
// Socket.IO /ops channel with a REST polling fallback; in the Frappe desk the backend JWT
// lives server-side, so we use the documented fallback: poll the whitelisted proxy
// (marzi_bridge.api.tracking.get_events / get_presence) every 5s through MarziClient.

frappe.provide("marzi");

frappe.pages["live-activity"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Live Activity"),
		single_column: true,
	});
	wrapper.__marzi_live = new marzi.LiveActivity(page, wrapper);
};

frappe.pages["live-activity"].on_page_show = function (wrapper) {
	wrapper.__marzi_live && wrapper.__marzi_live.start();
};

frappe.pages["live-activity"].on_page_hide = function (wrapper) {
	wrapper.__marzi_live && wrapper.__marzi_live.stop();
};

marzi.LiveActivity = class LiveActivity {
	constructor(page, wrapper) {
		this.page = page;
		this.$wrapper = $(wrapper);
		this.cursor = null;
		this.seen = new Set();
		this.events = [];
		this.active = [];
		this.timer = null;
		this.FEED_CAP = 400;
		this.render_shell();
	}

	start() {
		if (this.timer) return;
		this.tick(); // immediate paint
		this.timer = setInterval(() => this.tick(), 5000);
	}

	stop() {
		if (this.timer) clearInterval(this.timer);
		this.timer = null;
	}

	async tick() {
		if (document.hidden) return; // pause when tab/desk not visible
		await Promise.all([this.fetch_events(), this.fetch_presence()]);
		this.render();
	}

	async fetch_events() {
		const args = this.cursor ? { since: this.cursor, limit: 200 } : { limit: 100 };
		try {
			const r = await frappe.call({
				method: "marzi_bridge.api.tracking.get_events",
				args,
				silent: true,
			});
			const data = r && r.message;
			if (!data) return;
			if (data.cursor) this.cursor = data.cursor;
			const fresh = (data.events || []).filter((e) => e.eventId && !this.seen.has(e.eventId));
			fresh.forEach((e) => this.seen.add(e.eventId));
			if (this.seen.size > this.FEED_CAP * 4) {
				this.seen = new Set([...this.seen].slice(-this.FEED_CAP * 2));
			}
			// events come oldest→newest within a page; show newest first
			this.events = [...fresh.reverse(), ...this.events].slice(0, this.FEED_CAP);
		} catch (e) {
			this.connected = false;
		}
	}

	async fetch_presence() {
		try {
			const r = await frappe.call({
				method: "marzi_bridge.api.tracking.get_presence",
				silent: true,
			});
			const data = r && r.message;
			if (!data) return;
			this.active = data.active || [];
			this.connected = true;
		} catch (e) {
			this.connected = false;
		}
	}

	events_per_min() {
		const cutoff = Date.now() - 60_000;
		return this.events.filter((e) => new Date(e.createdAt).getTime() > cutoff).length;
	}

	render_shell() {
		this.page.main.html(`
			<div class="marzi-la">
				<div class="la-stats">
					<div class="la-stat"><div class="la-stat-k">Active now</div>
						<div class="la-stat-v" data-k="active">0</div><div class="la-stat-sub">last 5 min</div></div>
					<div class="la-stat"><div class="la-stat-k">Events / min</div>
						<div class="la-stat-v" data-k="epm">0</div><div class="la-stat-sub">last 60s</div></div>
					<div class="la-stat">
						<div class="la-stat-k">Feed</div>
						<div class="la-stat-v"><span class="la-dot"></span><span data-k="mode">connecting…</span></div>
						<div class="la-stat-sub">polling · 5s</div>
					</div>
				</div>
				<div class="la-body">
					<div class="la-col la-feed-col">
						<div class="la-col-head">Live feed</div>
						<div class="la-feed" data-k="feed"></div>
					</div>
					<div class="la-col la-active-col">
						<div class="la-col-head">Active now</div>
						<div class="la-active" data-k="activelist"></div>
					</div>
				</div>
			</div>
		`);
	}

	render() {
		const $m = this.page.main;
		$m.find('[data-k="active"]').text(this.active.length);
		$m.find('[data-k="epm"]').text(this.events_per_min());
		$m.find('[data-k="mode"]').text(this.connected === false ? "reconnecting…" : "live");
		$m.find(".la-dot").toggleClass("is-down", this.connected === false);

		// Active-now panel
		const active_html = this.active.length
			? this.active
					.slice()
					.sort((a, b) => String(b.lastSeenAt).localeCompare(String(a.lastSeenAt)))
					.map((u) => {
						const name = frappe.utils.escape_html(u.fullName || (u.phone ? "Lead" : "Visitor"));
						const phone = u.phone ? frappe.utils.escape_html(u.phone) : "";
						const page = frappe.utils.escape_html(u.page || "—");
						return `<div class="la-person">
							<div class="la-avatar">${name.slice(0, 1).toUpperCase()}</div>
							<div class="la-person-body">
								<div class="la-person-name">${name}${phone ? ` <span class="la-person-phone">${phone}</span>` : ""}</div>
								<div class="la-person-page">${page} · ${marzi.la_ago(u.lastSeenAt)}</div>
							</div>
						</div>`;
					})
					.join("")
			: `<div class="la-empty">No one active right now.</div>`;
		$m.find('[data-k="activelist"]').html(active_html);

		// Feed
		const feed_html = this.events.length
			? this.events
					.map((e) => {
						const meta = marzi.la_event_meta(e.name);
						const who =
							frappe.utils.escape_html(e.userFullName || e.userPhone || "Anonymous");
						const page = e.page ? frappe.utils.escape_html(e.page) : "";
						return `<div class="la-row">
							<span class="la-row-dot la-${meta.cls}"></span>
							<div class="la-row-body">
								<div class="la-row-top"><span class="la-row-label">${meta.label}</span>
									<span class="la-row-who">${who}</span></div>
								<div class="la-row-sub">${page ? page + " · " : ""}${marzi.la_ago(e.createdAt)}</div>
							</div>
						</div>`;
					})
					.join("")
			: `<div class="la-empty">Waiting for events…</div>`;
		$m.find('[data-k="feed"]').html(feed_html);
	}
};

// event name -> {label, colour class}, mirroring admin-v2 eventMeta().
marzi.la_event_meta = function (name) {
	name = String(name || "");
	if (name === "$pageview") return { label: "Page view", cls: "s1" };
	if (name === "$identify") return { label: "Profile", cls: "s2" };
	if (/payment|purchase|booking/i.test(name))
		return /fail|error/i.test(name)
			? { label: "Payment failed", cls: "s5" }
			: { label: "Payment", cls: "s4" };
	if (/fail|error/i.test(name)) return { label: "Issue", cls: "s5" };
	if (name.startsWith("campaign_")) return { label: "Campaign", cls: "s3" };
	return { label: name || "Event", cls: "s1" };
};

marzi.la_ago = function (ts) {
	const d = new Date(ts).getTime();
	if (isNaN(d)) return "";
	const s = Math.max(0, Math.round((Date.now() - d) / 1000));
	if (s < 60) return s + "s ago";
	const m = Math.round(s / 60);
	if (m < 60) return m + "m ago";
	const h = Math.round(m / 60);
	if (h < 24) return h + "h ago";
	return Math.round(h / 24) + "d ago";
};
