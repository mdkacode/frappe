#!/usr/bin/env python3
"""Generate API-backed Virtual DocTypes for Marzi Bridge from declarative specs.

Each spec describes one dashboard entity: its backend list/detail endpoint, the
response envelope, the id field, field renames (backend key -> Frappe fieldname),
the fields to surface (scalars, images, read-only JSON blocks, child-table grids),
and the relational child collections. The generator writes, per entity:

    marzi_bridge/marzi_bridge/doctype/<scrubbed>/<scrubbed>.json   (is_virtual)
    marzi_bridge/marzi_bridge/doctype/<scrubbed>/<scrubbed>.py     (controller)
    marzi_bridge/marzi_bridge/doctype/<scrubbed>/__init__.py

Child (istable) DocTypes for the relational grids are emitted the same way from
CHILD_SPECS; they are populated by the parent's load_from_db and never listed alone.

Run from anywhere (pure file generation, no bench needed):

    python3 marzi_bridge/scripts/gen_doctypes.py

Then, inside the bench/container: `bench --site <site> migrate`.

Displaying the FULL detail (every field + images + nested collections):
  * `Image` fieldtype renders an external URL held by a sibling `Data` field
    (its `options`); `Attach Image` only takes /files/ paths, so it is NOT used.
  * The DocType `image_field` (set to the URL Data field) drives the list thumbnail.
  * Nested objects/arrays go in read-only `Code`(JSON) fields (ApiDocument serializes
    dict/list values into them); big relational collections become child `Table`s.
  * 6 entities call a richer GET-by-id detail endpoint (single_from_list=False); the
    rest have no detail route and load a single record from the collection.

These are READ-ONLY (list + view). Write flows differ per entity and are enabled
case by case. Speaker (hand-built, verified CRUD) is intentionally not regenerated.
"""

import json
import os

# scripts/ lives at the app root; the module's doctype folder is <root>/marzi_bridge/marzi_bridge/doctype
APP_DOCTYPE_DIR = os.path.join(
	os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
	"marzi_bridge",
	"marzi_bridge",
	"doctype",
)


# -- field tuple: (fieldname, label, fieldtype, options, in_list_view, read_only, reqd, write) --
# `write=1` makes a field editable (emitted WITHOUT read_only) and `reqd=1` marks it required.
# Layout/display helpers stay read-only; writability is opted in per field on writable entities.
def f(name, label, ftype="Data", options=None, in_list=0, read_only=1, reqd=0, write=0):
	return (name, label, ftype, options, in_list, read_only, reqd, write)


def tab(fid, label):
	return (fid, label, "Tab Break", None, 0, 0, 0, 0)


def sec(fid, label=None):
	return (fid, label, "Section Break", None, 0, 0, 0, 0)


def col(fid):
	return (fid, None, "Column Break", None, 0, 0, 0, 0)


def img(name, label, url_field):
	# `options` names the sibling Data field holding the external URL.
	return (name, label, "Image", url_field, 0, 0, 0, 0)


def jsonf(name, label, write=0):
	return (name, label, "Code", "JSON", 0, 0 if write else 1, 0, write)


def table(name, label, child_doctype, write=0):
	return (name, label, "Table", child_doctype, 0, 0 if write else 1, 0, write)


# =====================================================================================
# CHILD (istable) DocTypes — relational grids, populated by their parent.
# =====================================================================================
CHILD_SPECS = [
	{
		"doctype": "Marzi Event Attendee",
		"fields": [
			f("attendee_name", "Name", "Data", None, 1),
			f("user_phone", "Phone", "Data", None, 1),
			f("seats_booked", "Seats", "Int", None, 1),
			f("status", "Status", "Data", None, 1),
			f("check_in_status", "Check-in", "Data", None, 1),
			f("total_amount", "Amount", "Float", None, 1),
			f("confirmation_number", "Confirmation #", "Data"),
			f("user_first_name", "First Name", "Data"),
			f("user_last_name", "Last Name", "Data"),
			f("user_profile_pic_url", "Profile Pic", "Data"),
			f("created_at", "Booked At", "Data"),
		],
	},
	{
		"doctype": "Marzi Event Tier",
		"fields": [
			f("tier_name", "Tier", "Data", None, 1),
			f("final_price_rupees", "Final Price (₹)", "Float", None, 1),
			f("max_tickets", "Max Tickets", "Int", None, 1),
			f("admissible_pax", "Pax / Ticket", "Int", None, 1),
			f("is_best_value", "Best Value", "Check", None, 1),
			f("list_price_rupees", "List Price (₹)", "Float"),
			f("discounted_price_rupees", "Discounted (₹)", "Float"),
			f("gst_percentage", "GST %", "Float"),
			f("availability", "Availability", "Data"),
			f("description", "Description", "Small Text"),
			f("sort_order", "Order", "Int"),
		],
	},
	{
		"doctype": "Marzi Group Member",
		"fields": [
			f("first_name", "First Name", "Data", None, 1),
			f("last_name", "Last Name", "Data", None, 1),
			f("role", "Role", "Data", None, 1),
			f("joined_at", "Joined", "Data", None, 1),
			f("profile_pic_url", "Profile Pic", "Data"),
			f("user_id", "User ID", "Data"),
		],
	},
	{
		"doctype": "Marzi Group Post",
		"fields": [
			f("content", "Content", "Small Text", None, 1),
			f("like_count", "Likes", "Int", None, 1),
			f("comment_count", "Comments", "Int", None, 1),
			f("status", "Status", "Data", None, 1),
			f("created_at", "Posted", "Data", None, 1),
			f("author", "Author", "Long Text"),
			f("media_urls", "Media", "Long Text"),
			f("post_id", "Post ID", "Data"),
		],
	},
	{
		"doctype": "Marzi User Booking",
		"fields": [
			f("event_title", "Event", "Data", None, 1),
			f("event_start_time", "Starts", "Data", None, 1),
			f("status", "Status", "Data", None, 1),
			f("seats_booked", "Seats", "Int", None, 1),
			f("total_amount", "Amount", "Float", None, 1),
			f("confirmation_number", "Confirmation #", "Data"),
			f("paid_at", "Paid At", "Data"),
			f("created_at", "Booked At", "Data"),
			f("event_id", "Event ID", "Data"),
		],
	},
	{
		"doctype": "Marzi User Transaction",
		"fields": [
			f("source", "Source", "Data", None, 1),
			f("event_title", "Event", "Data", None, 1),
			f("status", "Status", "Data", None, 1),
			f("total_amount", "Amount", "Float", None, 1),
			f("discount_amount", "Discount", "Float"),
			f("promo_code", "Promo", "Data"),
			f("currency", "Currency", "Data"),
			f("confirmation_number", "Confirmation #", "Data"),
			f("transaction_id", "Txn ID", "Data"),
			f("razorpay_order_id", "Razorpay Order", "Data"),
			f("razorpay_payment_id", "Razorpay Payment", "Data"),
			f("paid_at", "Paid At", "Data"),
			f("created_at", "Created At", "Data"),
		],
	},
	{
		"doctype": "Marzi Blog Tag",
		"fields": [
			f("tag_name", "Tag", "Data", None, 1),
			f("slug", "Slug", "Data", None, 1),
			f("created_at", "Created At", "Data"),
		],
	},
	{
		"doctype": "Marzi FAQ Item",
		"fields": [
			f("question", "Question", "Small Text", None, 1),
			f("answer", "Answer", "Text", None, 1),
		],
	},
	# -- writable child grids (edited on the parent Form, assembled into arrays) --
	{
		"doctype": "Marzi Page Breadcrumb",
		"fields": [
			f("label", "Label", "Data", None, 1, write=1),
			f("href", "Link", "Data", None, 1, write=1),
		],
	},
	{
		"doctype": "Marzi Template Section",
		"fields": [
			f("key", "Section", "Select",
			  "\nhero\nintro\nupcomingEvents\npastEvents\nabout\nfaq\nrelatedBlogs\ncta", 1, write=1),
			f("enabled", "Enabled", "Check", None, 1, write=1),
		],
	},
]


# =====================================================================================
# PARENT DocTypes.
# =====================================================================================
SPECS = [
	{
		"doctype": "Marzi Event",
		"endpoint": "/admin/events",
		"detail_endpoint": "/events",  # GET /events/{id} -> full detail (v1 getEventDetail)
		"service": "v1",
		"id_field": "id",
		"list_key": "events",
		"item_key": None,
		"single_from_list": False,
		"title_field": "title",
		"image_field": "hero_image_cdn_url",
		"aliases": {},
		"writable": True,
		"write_endpoint": "/events",   # writes go to /events/{id}; read list is /admin/events
		"update_method": "PUT",         # backend updates events via PUT (DRAFT only)
		"write_fields": [
			"title", "short_description", "about_event", "about_event_html", "event_mode",
			"venue_name", "address_line1", "address_line2", "city_id", "state", "postal_code",
			"latitude", "longitude", "booking_start_time", "booking_end_time",
			"event_start_time", "event_end_time", "max_capacity", "booking_limit_per_user",
			"ticket_price_rupees", "gst_percentage", "hero_image_cdn_url", "hero_video_url",
			"online_event_url", "online_access_code", "tags", "categories",
			"gallery_image_urls", "video_urls",
		],
		"write_aliases": {"hero_image_cdn_url": "hero_image_url"},
		"child_tables": {
			"attendees": {
				"doctype": "Marzi Event Attendee",
				"source": "/events/{id}/attendees",
				"list_key": "attendees",
				"aliases": {"name": "attendee_name"},
			},
			"tiers": {
				"doctype": "Marzi Event Tier",
				"source": "item",
				"item_key": "tiers",
				"aliases": {},
			},
		},
		"fields": [
			tab("tab_overview", "Overview"),
			f("title", "Title", "Data", None, 1, write=1, reqd=1),
			f("status", "Status", "Select", "\nDRAFT\nPUBLISHED\nCANCELLED\nCOMPLETED", 1),
			f("event_mode", "Mode", "Select", "\nOFFLINE\nONLINE", 0, write=1, reqd=1),
			f("slug", "Slug", "Data"),
			f("short_description", "Short Description", "Small Text", None, 0, write=1, reqd=1),
			sec("sec_schedule", "Schedule"),
			f("event_start_time", "Start (ISO 8601)", "Data", None, 1, write=1),
			f("event_end_time", "End (ISO 8601)", "Data", None, 0, write=1),
			col("col_sched2"),
			f("booking_start_time", "Booking Opens (ISO 8601)", "Data", None, 0, write=1),
			f("booking_end_time", "Booking Closes (ISO 8601)", "Data", None, 0, write=1),
			f("timezone_id", "Timezone", "Data"),
			sec("sec_venue", "Venue"),
			f("venue_name", "Venue", "Data", None, 0, write=1),
			f("city_name", "City", "Data", None, 1),
			f("city_id", "City ID", "Data", None, 0, write=1),
			f("address_line1", "Address 1", "Data", None, 0, write=1),
			f("address_line2", "Address 2", "Data", None, 0, write=1),
			f("state", "State", "Data", None, 0, write=1),
			f("postal_code", "Postal Code", "Data", None, 0, write=1),
			col("col_venue2"),
			f("latitude", "Latitude", "Data", None, 0, write=1),
			f("longitude", "Longitude", "Data", None, 0, write=1),
			f("online_event_url", "Online URL", "Data", "URL", 0, write=1),
			f("online_access_code", "Access Code", "Data", None, 0, write=1),
			sec("sec_pricing", "Pricing & Capacity"),
			f("ticket_price_rupees", "Ticket Price (₹)", "Int", None, 0, write=1),
			f("gst_percentage", "GST %", "Float", None, 0, write=1),
			f("final_amount", "Final Amount", "Float", None, 1),
			col("col_price2"),
			f("max_capacity", "Max Capacity", "Int", None, 0, write=1),
			f("booking_limit_per_user", "Limit / User", "Int", None, 0, write=1),
			f("is_multitier", "Multi-tier", "Check"),
			sec("sec_meta", "Meta"),
			f("share_url", "Share URL", "Data"),
			f("meta_title", "Meta Title", "Data"),
			f("meta_description", "Meta Description", "Small Text"),
			jsonf("tags", "Tags", write=1),
			jsonf("categories", "Categories", write=1),
			col("col_meta2"),
			f("created_at", "Created At", "Data"),
			f("updated_at", "Updated At", "Data"),
			f("published_at", "Published At", "Data"),
			tab("tab_media", "Media"),
			img("hero_image", "Hero Image", "hero_image_cdn_url"),
			f("hero_image_cdn_url", "Hero Image URL", "Data", "URL", 0, write=1),
			f("hero_video_url", "Hero Video URL", "Data", "URL", 0, write=1),
			jsonf("gallery_image_urls", "Gallery Image URLs", write=1),
			jsonf("video_urls", "Video URLs", write=1),
			tab("tab_content", "Content"),
			f("about_event", "About", "Text", None, 0, write=1),
			f("about_event_html", "About (HTML)", "Text Editor", None, 0, write=1),
			jsonf("good_to_know", "Good to Know"),
			jsonf("whats_included", "What's Included"),
			jsonf("faqs", "FAQs"),
			jsonf("testimonials", "Testimonials"),
			jsonf("galleries", "Galleries"),
			tab("tab_attendees", "Attendees"),
			table("attendees", "Attendees", "Marzi Event Attendee"),
			tab("tab_ticketing", "Ticketing"),
			table("tiers", "Ticket Tiers", "Marzi Event Tier"),
		],
	},
	{
		"doctype": "Marzi Booking",
		"endpoint": "/admin/bookings",
		"service": "v1",
		"id_field": "booking_id",
		"list_key": "bookings",
		"item_key": None,
		"single_from_list": True,  # no admin GET-by-id; list rows are already denormalized
		"title_field": "confirmation_number",
		"image_field": "user_profile_pic_url",
		"aliases": {},
		"fields": [
			tab("tab_overview", "Overview"),
			img("attendee_photo", "Attendee", "user_profile_pic_url"),
			f("confirmation_number", "Confirmation #", "Data", None, 1),
			f("event_title", "Event", "Data", None, 1),
			f("event_city", "City", "Data"),
			f("status", "Status", "Data", None, 1),
			f("check_in_status", "Check-in", "Data"),
			f("check_in_time", "Check-in Time", "Data"),
			col("col_ov2"),
			f("user_first_name", "First Name", "Data"),
			f("user_last_name", "Last Name", "Data"),
			f("phone", "Phone", "Data", None, 1),
			f("email", "Email", "Data"),
			f("user_profile_pic_url", "Profile Pic URL", "Data"),
			f("seats_booked", "Seats", "Int"),
			sec("sec_payment", "Payment"),
			f("total_amount", "Total Amount", "Float", None, 1),
			f("original_amount", "Original Amount", "Float"),
			f("discount_amount", "Discount", "Float"),
			f("final_paid_amount", "Final Paid", "Float"),
			f("promo_code_applied", "Promo Code", "Data"),
			f("coupon_applied", "Coupon Applied", "Check"),
			col("col_pay2"),
			f("gst_percentage", "GST %", "Float"),
			f("gst_amount", "GST Amount", "Float"),
			f("cgst_amount", "CGST", "Float"),
			f("sgst_amount", "SGST", "Float"),
			f("igst_amount", "IGST", "Float"),
			f("gst_jurisdiction", "GST Jurisdiction", "Data"),
			f("paid", "Paid", "Check"),
			f("paid_at", "Paid At", "Data"),
			f("created_at", "Created At", "Data"),
			sec("sec_tiers", "Tiers"),
			f("is_multitier", "Multi-tier", "Check"),
			jsonf("tiers", "Tiers"),
		],
	},
	{
		"doctype": "Marzi Group",
		"endpoint": "/groups",
		"service": "v1",
		"id_field": "group_id",
		"list_key": "groups",
		"item_key": None,
		"single_from_list": False,
		"title_field": "group_name",
		"image_field": "cover_image_url",
		"aliases": {"name": "group_name"},
		"writable": True,
		"write_fields": ["group_name", "description", "category", "type", "city", "interests", "rules", "tags"],
		"write_aliases": {"group_name": "name"},
		"defaults": {"type": "OPEN"},
		"child_tables": {
			"members": {
				"doctype": "Marzi Group Member",
				"source": "/groups/{id}/members",
				"list_key": "members",
				"aliases": {},
			},
			"posts": {
				"doctype": "Marzi Group Post",
				"source": "/groups/{id}/posts",
				"list_key": "posts",
				"aliases": {},
			},
		},
		"fields": [
			tab("tab_overview", "Overview"),
			f("group_name", "Name", "Data", None, 1, write=1, reqd=1),
			f("category", "Category", "Select",
			  "\nHEALTH\nFITNESS\nHOBBIES\nTRAVEL\nFOOD\nTECH\nARTS\nSOCIAL\nSUPPORT\nLEARNING\nOTHER", 1, write=1, reqd=1),
			f("type", "Type", "Select", "\nOPEN\nCLOSED", 0, write=1, reqd=1),
			f("status", "Status", "Select", "\nACTIVE\nINACTIVE\nARCHIVED", 1),
			f("city", "City", "Data", None, 1, write=1),
			f("is_default", "Default", "Check"),
			col("col_ov2"),
			f("member_count", "Members", "Int", None, 1),
			f("post_count", "Posts", "Int"),
			f("created_at", "Created At", "Data"),
			f("updated_at", "Updated At", "Data"),
			sec("sec_about", "About"),
			f("description", "Description", "Small Text", None, 0, write=1),
			f("rules", "Rules", "Small Text", None, 0, write=1),
			jsonf("interests", "Interests", write=1),
			jsonf("tags", "Tags", write=1),
			tab("tab_media", "Media"),
			img("cover_image", "Cover", "cover_image_url"),
			f("cover_image_url", "Cover Image URL", "Data"),
			col("col_media2"),
			img("icon_image", "Icon", "icon_image_url"),
			f("icon_image_url", "Icon Image URL", "Data"),
			tab("tab_members", "Members"),
			table("members", "Members", "Marzi Group Member"),
			tab("tab_posts", "Posts"),
			table("posts", "Posts", "Marzi Group Post"),
		],
	},
	{
		"doctype": "Marzi Testimony",
		"endpoint": "/admin/testimonials",
		"service": "v1",
		"id_field": "testimony_id",
		"list_key": "testimonies",
		"item_key": None,
		"single_from_list": True,  # no dedicated detail route
		"title_field": "person_name",
		"image_field": "image_url",
		"aliases": {"name": "person_name", "author_name": "person_name", "content": "quote", "author_pic_url": "image_url"},
		"writable": True,
		# Write keys differ from the read shape: create/update send name/quote/image/videoUrl.
		"write_fields": ["person_name", "quote", "image_url", "video_url", "age", "location", "rating", "is_published", "display_order"],
		"write_aliases": {"person_name": "name", "quote": "quote", "image_url": "image", "video_url": "videoUrl"},
		"defaults": {"is_published": 0},
		"fields": [
			tab("tab_overview", "Overview"),
			img("photo", "Photo", "image_url"),
			f("person_name", "Name", "Data", None, 1, write=1, reqd=1),
			f("quote", "Quote", "Small Text", None, 1, write=1, reqd=1),
			f("age", "Age", "Int", None, 0, write=1),
			f("location", "Location", "Data", None, 1, write=1),
			f("rating", "Rating", "Int", None, 0, write=1),
			col("col_ov2"),
			f("is_published", "Published", "Check", None, 1, write=1),
			f("display_order", "Order", "Int", None, 0, write=1),
			f("image_url", "Image URL", "Data", "URL", 0, write=1, reqd=1),
			f("video_url", "Video URL", "Data", "URL", 0, write=1),
			f("created_at", "Created At", "Data"),
		],
	},
	{
		"doctype": "Marzi User",
		"endpoint": "/users",
		"detail_endpoint": "/users",  # GET /users/{id} -> profile + events + transactions
		"service": "v1",
		"id_field": "userId",
		"list_key": "items",
		"item_key": None,
		"single_from_list": False,
		# /users is cursor-paginated (max 50/page): walk pages for list/count/find.
		"list_params": {"limit": 50},
		"cursor_key": "nextCursor",
		# GET /users/{id} is a profile subset (no phone/email/role/status/created);
		# merge the list row underneath so the Form shows the complete record.
		"detail_merge_list": True,
		"title_field": "first_name",
		"image_field": "profile_pic_url",
		"aliases": {
			"firstName": "first_name",
			"lastName": "last_name",
			"accountStatus": "account_status",
			"createdAt": "created_at",
			"profilePicUrl": "profile_pic_url",
			"totalBadges": "total_badges",
			"totalEvents": "total_events",
			"totalTransactions": "total_transactions",
			"totalPosts": "total_posts",
			"eventsBooked": "events_booked",
			"isOnboardingCompleted": "is_onboarding_completed",
			"isFirstDiscountApplied": "is_first_discount_applied",
		},
		"child_tables": {
			"bookings": {
				"doctype": "Marzi User Booking",
				"source": "item",
				"item_key": "events",
				"aliases": {
					"bookingId": "booking_id",
					"eventId": "event_id",
					"eventTitle": "event_title",
					"eventStartTime": "event_start_time",
					"seatsBooked": "seats_booked",
					"confirmationNumber": "confirmation_number",
					"totalAmount": "total_amount",
					"paidAt": "paid_at",
					"createdAt": "created_at",
				},
			},
			"transactions": {
				"doctype": "Marzi User Transaction",
				"source": "item",
				"item_key": "transactions",
				"aliases": {
					"transactionId": "transaction_id",
					"eventId": "event_id",
					"eventTitle": "event_title",
					"totalAmount": "total_amount",
					"discountAmount": "discount_amount",
					"promoCode": "promo_code",
					"confirmationNumber": "confirmation_number",
					"razorpayOrderId": "razorpay_order_id",
					"razorpayPaymentId": "razorpay_payment_id",
					"paidAt": "paid_at",
					"createdAt": "created_at",
				},
			},
		},
		"fields": [
			tab("tab_overview", "Overview"),
			img("avatar", "Avatar", "profile_pic_url"),
			f("first_name", "First Name", "Data", None, 1),
			f("last_name", "Last Name", "Data", None, 1),
			f("phone", "Phone", "Data", None, 1),
			f("email", "Email", "Data"),
			col("col_ov2"),
			f("role", "Role", "Select", "\nSUPER_ADMIN\nADMIN\nMEMBER", 1),
			f("account_status", "Account Status", "Select", "\nACTIVE\nPENDING_VERIFICATION\nSUSPENDED\nDELETED", 1),
			f("city", "City", "Data"),
			f("profile_pic_url", "Profile Pic URL", "Data"),
			f("created_at", "Created At", "Data"),
			sec("sec_stats", "Stats"),
			f("total_events", "Events", "Int"),
			f("total_transactions", "Transactions", "Int"),
			col("col_stats2"),
			f("total_posts", "Posts", "Int"),
			f("total_badges", "Badges", "Int"),
			sec("sec_flags", "Journey"),
			f("events_booked", "Events Booked", "Int", None, 1),
			f("is_onboarding_completed", "Onboarding Completed", "Check"),
			col("col_flags2"),
			f("is_first_discount_applied", "First Discount Applied", "Check"),
			sec("sec_bio", "Bio"),
			f("bio", "Bio", "Small Text"),
			tab("tab_bookings", "Bookings"),
			table("bookings", "Bookings", "Marzi User Booking"),
			tab("tab_transactions", "Transactions"),
			table("transactions", "Transactions", "Marzi User Transaction"),
		],
	},
	{
		"doctype": "Marzi Blog Post",
		"endpoint": "/admin/posts",
		"detail_endpoint": "/admin/posts",  # GET /admin/posts/{id} -> {post, tags}
		"service": "blog",
		"id_field": "id",
		"list_key": "posts",
		"item_key": "post",
		"single_from_list": False,
		"title_field": "title",
		"image_field": "cover_image_url",
		"merge_keys": ("tags",),
		"aliases": {},
		"writable": True,
		"write_fields": [
			"title", "slug", "subtitle", "excerpt", "content_json", "cover_image_url",
			"category_id", "tag_ids", "seo_title", "seo_description", "og_image_url", "canonical_url",
		],
		"child_tables": {
			"tags": {
				"doctype": "Marzi Blog Tag",
				"source": "item",
				"item_key": "tags",
				"aliases": {"name": "tag_name"},
			},
		},
		"fields": [
			tab("tab_overview", "Overview"),
			f("title", "Title", "Data", None, 1, write=1, reqd=1),
			f("slug", "Slug", "Data", None, 1, write=1, reqd=1),
			f("subtitle", "Subtitle", "Data", None, 0, write=1),
			f("status", "Status", "Select", "\nDRAFT\nSCHEDULED\nPUBLISHED\nARCHIVED", 1),
			f("locale", "Locale", "Data", None, 1),
			f("translation_group", "Translation Group", "Data"),
			col("col_ov2"),
			f("excerpt", "Excerpt", "Small Text", None, 0, write=1),
			f("author_id", "Author ID", "Data"),
			f("category_id", "Category ID", "Data", None, 0, write=1),
			f("reading_minutes", "Reading Minutes", "Int"),
			f("publish_at", "Publish At", "Data"),
			f("published_at", "Published At", "Data"),
			f("created_at", "Created At", "Data"),
			f("updated_at", "Updated At", "Data"),
			sec("sec_seo", "SEO"),
			f("seo_title", "SEO Title", "Data", None, 0, write=1),
			f("seo_description", "SEO Description", "Small Text", None, 0, write=1),
			f("canonical_url", "Canonical URL", "Data", "URL", 0, write=1),
			tab("tab_media", "Media"),
			img("cover_image", "Cover", "cover_image_url"),
			f("cover_image_url", "Cover Image URL", "Data", "URL", 0, write=1),
			col("col_media2"),
			img("og_image", "OG Image", "og_image_url"),
			f("og_image_url", "OG Image URL", "Data", "URL", 0, write=1),
			tab("tab_content", "Content"),
			f("content_html", "Content (HTML)", "Text Editor"),
			jsonf("content_json", "Content (JSON)", write=1),
			jsonf("tag_ids", "Tag IDs (write)", write=1),
			tab("tab_tags", "Tags"),
			table("tags", "Tags", "Marzi Blog Tag"),
		],
	},
	{
		"doctype": "Marzi Page",
		"endpoint": "/v1/publishing/admin/pages",
		"detail_endpoint": "/v1/publishing/admin/pages",
		"service": "publishing",
		"id_field": "id",
		"list_key": None,
		"item_key": None,
		"single_from_list": False,
		"title_field": "title",
		"image_field": "hero_image_url",
		# Top-level camelCase keys only; SEO lives under meta{} (read_nested), images/about
		# are nested objects (nested_fields), breadcrumb is an array (child table).
		"aliases": {
			"templateId": "template_id",
			"pathPrefix": "path_prefix",
			"sitemapInclude": "sitemap_include",
			"faqIds": "faq_ids",
			"blogIds": "blog_ids",
			"upcomingEventIds": "upcoming_event_ids",
			"pastEventIds": "past_event_ids",
			"publishedAt": "published_at",
			"createdAt": "created_at",
			"updatedAt": "updated_at",
			"tenantId": "tenant_id",
		},
		"writable": True,
		# Flat body keys (write is flat camelCase even though read nests SEO under meta{}).
		"write_fields": [
			"slug", "title", "type", "meta_title", "meta_description", "meta_keywords",
			"og_title", "og_description", "og_image_url", "canonical_url", "primary_keyword",
			"secondary_keywords", "robots_index", "robots_follow", "twitter_card", "h1",
			"excerpt", "city", "category", "author", "sitemap_include", "ctas",
			"faq_ids", "blog_ids", "upcoming_event_ids", "past_event_ids",
		],
		"write_aliases": {
			"meta_title": "metaTitle", "meta_description": "metaDescription",
			"meta_keywords": "metaKeywords", "og_title": "ogTitle", "og_description": "ogDescription",
			"og_image_url": "ogImageUrl", "canonical_url": "canonicalUrl",
			"primary_keyword": "primaryKeyword", "secondary_keywords": "secondaryKeywords",
			"robots_index": "robotsIndex", "robots_follow": "robotsFollow",
			"twitter_card": "twitterCard", "sitemap_include": "sitemapInclude",
			"faq_ids": "faqIds", "blog_ids": "blogIds",
			"upcoming_event_ids": "upcomingEventIds", "past_event_ids": "pastEventIds",
		},
		# SEO nested under meta{} on read; written flat above.
		"read_nested": {
			"meta": {
				"title": "meta_title", "description": "meta_description", "keywords": "meta_keywords",
				"ogTitle": "og_title", "ogDescription": "og_description", "ogImage": "og_image_url",
				"canonical": "canonical_url", "primaryKeyword": "primary_keyword",
				"secondaryKeywords": "secondary_keywords", "twitterCard": "twitter_card",
				"robots": {"index": "robots_index", "follow": "robots_follow"},
			},
		},
		# Images + about are nested objects both ways (symmetric read/write).
		"nested_fields": {
			"heroImage": {"url": "hero_image_url", "alt": "hero_image_alt"},
			"mobileHeroImage": {"url": "mobile_hero_image_url", "alt": "mobile_hero_image_alt"},
			"featuredImage": {"url": "featured_image_url", "alt": "featured_image_alt"},
			"about": {"body": "about_body", "readMoreLabel": "about_read_more_label"},
		},
		"child_tables": {
			"breadcrumb": {
				"doctype": "Marzi Page Breadcrumb",
				"source": "item",
				"item_key": "breadcrumb",
				"aliases": {},
			},
		},
		"write_child_tables": {
			"breadcrumb": {"field": "breadcrumb", "map": {"label": "label", "href": "href"}},
		},
		"fields": [
			tab("tab_overview", "Overview"),
			f("title", "Title", "Data", None, 1, write=1, reqd=1),
			f("slug", "Slug", "Data", None, 1, write=1, reqd=1),
			f("type", "Type", "Select", "\nEVENT\nBLOG", 1, write=1, reqd=1),
			f("status", "Status", "Select", "\nDRAFT\nPUBLISHED\nARCHIVED", 1),
			f("path_prefix", "Path Prefix", "Data", None, 1),
			f("template_id", "Template ID", "Data"),
			col("col_ov2"),
			f("h1", "H1", "Data", None, 0, write=1),
			f("excerpt", "Excerpt", "Small Text", None, 0, write=1),
			f("city", "City", "Data", None, 0, write=1),
			f("category", "Category", "Data", None, 0, write=1),
			f("author", "Author", "Data", None, 0, write=1),
			f("published_at", "Published At", "Data"),
			f("created_at", "Created At", "Data"),
			sec("sec_seo", "SEO & Meta"),
			f("meta_title", "Meta Title", "Data", None, 0, write=1),
			f("meta_description", "Meta Description", "Small Text", None, 0, write=1),
			f("primary_keyword", "Primary Keyword", "Data", None, 0, write=1),
			f("canonical_url", "Canonical URL", "Data", "URL", 0, write=1),
			f("robots_index", "Robots Index", "Check", None, 0, write=1),
			f("robots_follow", "Robots Follow", "Check", None, 0, write=1),
			f("sitemap_include", "Sitemap Include", "Check", None, 0, write=1),
			col("col_seo2"),
			f("og_title", "OG Title", "Data", None, 0, write=1),
			f("og_description", "OG Description", "Small Text", None, 0, write=1),
			f("og_image_url", "OG Image URL", "Data", "URL", 0, write=1),
			jsonf("meta_keywords", "Meta Keywords", write=1),
			jsonf("secondary_keywords", "Secondary Keywords", write=1),
			jsonf("twitter_card", "Twitter Card", write=1),
			tab("tab_media", "Media"),
			img("hero_image", "Hero", "hero_image_url"),
			f("hero_image_url", "Hero Image URL", "Data", "URL", 0, write=1),
			f("hero_image_alt", "Hero Alt", "Data", None, 0, write=1),
			col("col_media2"),
			img("mobile_hero_image", "Mobile Hero", "mobile_hero_image_url"),
			f("mobile_hero_image_url", "Mobile Hero URL", "Data", "URL", 0, write=1),
			f("mobile_hero_image_alt", "Mobile Hero Alt", "Data", None, 0, write=1),
			img("featured_image", "Featured", "featured_image_url"),
			f("featured_image_url", "Featured URL", "Data", "URL", 0, write=1),
			f("featured_image_alt", "Featured Alt", "Data", None, 0, write=1),
			tab("tab_content", "Content"),
			f("about_body", "About Body (HTML)", "Text Editor", None, 0, write=1),
			f("about_read_more_label", "About Read-More Label", "Data", None, 0, write=1),
			jsonf("ctas", "CTAs", write=1),
			jsonf("faq_ids", "FAQ IDs", write=1),
			jsonf("blog_ids", "Blog IDs", write=1),
			jsonf("upcoming_event_ids", "Upcoming Event IDs", write=1),
			jsonf("past_event_ids", "Past Event IDs", write=1),
			tab("tab_breadcrumb", "Breadcrumb"),
			table("breadcrumb", "Breadcrumb", "Marzi Page Breadcrumb", write=1),
		],
	},
	{
		"doctype": "Marzi Media",
		"endpoint": "/media",
		"service": "v1",
		"id_field": "asset_id",
		"list_key": "data.items",
		"item_key": "data",
		"single_from_list": False,
		"title_field": "filename",
		"image_field": "public_url",
		"aliases": {"url": "public_url", "mime_type": "content_type"},
		"fields": [
			tab("tab_overview", "Overview"),
			img("preview", "Preview", "public_url"),
			f("filename", "Filename", "Data", None, 1),
			f("kind", "Kind", "Select", "\nimage\ndocument", 1),
			f("content_type", "Content Type", "Data"),
			f("visibility", "Visibility", "Select", "\npublic\nprivate", 1),
			f("status", "Status", "Data", None, 1),
			col("col_ov2"),
			f("size_bytes", "Size (bytes)", "Int"),
			f("width", "Width", "Int"),
			f("height", "Height", "Int"),
			f("alt_text", "Alt Text", "Data"),
			f("uploaded_by", "Uploaded By", "Data"),
			f("s3_key", "S3 Key", "Data"),
			f("public_url", "Public URL", "Data"),
			f("created_at", "Created At", "Data"),
		],
	},
	{
		"doctype": "Marzi Status",
		"endpoint": "/admin/statuses",
		"service": "v1",
		"id_field": "status_id",
		"list_key": "statuses",
		"item_key": None,
		"single_from_list": True,
		"title_field": "description",
		"image_field": "image_url",
		"aliases": {},
		"writable": True,
		"write_fields": ["description", "status", "visible_to_users"],
		"defaults": {"status": "draft"},
		"fields": [
			tab("tab_overview", "Overview"),
			img("image", "Image", "image_url"),
			f("description", "Description", "Small Text", None, 1, write=1, reqd=1),
			f("status", "Status", "Select", "\ndraft\npublished", 1, write=1),
			f("visible_to_users", "Visible To Users", "Check", None, 1, write=1),
			col("col_ov2"),
			f("image_url", "Image URL", "Data"),
			f("image_key", "Image Key", "Data"),
			f("created_by", "Created By", "Data"),
			f("created_at", "Created At", "Data"),
			f("updated_at", "Updated At", "Data"),
		],
	},
	{
		"doctype": "Marzi Escalation",
		"endpoint": "/dashboard/escalations/pending",
		"service": "v1",
		"id_field": "escalationId",
		"list_key": "data",
		"item_key": None,
		"single_from_list": True,
		"title_field": "mobile",
		"aliases": {
			"agentHandling": "agent_handling",
			"updatedAt": "updated_at",
			"resolvedAt": "resolved_at",
			"resolvedBy": "resolved_by",
			"userMessage": "user_message",
		},
		"writable": True,
		"can_create": False,
		"can_delete": False,
		"write_endpoint": "/dashboard/escalations",
		"write_fields": ["status", "notes", "resolved_by"],
		"write_aliases": {"resolved_by": "resolvedBy"},
		"fields": [
			tab("tab_overview", "Overview"),
			f("mobile", "Mobile", "Data", None, 1),
			f("status", "Status", "Select", "\npending\nresolved", 1, write=1, reqd=1),
			f("reason", "Reason", "Small Text", None, 1),
			f("user_message", "User Message", "Small Text"),
			col("col_ov2"),
			f("agent_handling", "Agent Handling", "Check"),
			f("notes", "Notes", "Small Text", None, 0, write=1),
			f("resolved_by", "Resolved By", "Data", None, 0, write=1),
			f("resolved_at", "Resolved At", "Data"),
			f("updated_at", "Updated At", "Data"),
		],
	},
	{
		"doctype": "Marzi Blocked Message",
		"endpoint": "/moderation/blocked-messages",
		"service": "v1",
		"id_field": "id",
		"list_key": "data",
		"item_key": None,
		"single_from_list": True,
		"title_field": "phone",
		"aliases": {"userId": "user_id", "messageType": "message_type", "createdAt": "created_at"},
		"fields": [
			tab("tab_overview", "Overview"),
			f("phone", "Phone", "Data", None, 1),
			f("message_type", "Type", "Select", "\npost\ncomment", 1),
			f("content", "Content", "Small Text", None, 1),
			f("message", "Moderation Reason", "Small Text", None, 1),
			col("col_ov2"),
			f("user_id", "User ID", "Data"),
			f("created_at", "Created At", "Data"),
		],
	},
	{
		"doctype": "Marzi Campaign",
		"endpoint": "/v1/publishing/admin/campaigns",
		"service": "publishing",
		"id_field": "id",
		"list_key": "campaigns",
		"item_key": None,
		"single_from_list": True,
		"title_field": "name",
		"aliases": {
			"startsAt": "starts_at",
			"endsAt": "ends_at",
			"discountCampaignName": "discount_campaign_name",
			"pageCount": "page_count",
			"tenantId": "tenant_id",
			"createdAt": "created_at",
			"updatedAt": "updated_at",
		},
		"writable": True,
		"write_fields": ["slug", "name", "description", "starts_at", "ends_at", "discount_campaign_name"],
		"write_aliases": {
			"starts_at": "startsAt",
			"ends_at": "endsAt",
			"discount_campaign_name": "discountCampaignName",
		},
		"nested_fields": {
			"defaultUtm": {
				"source": "utm_source", "medium": "utm_medium", "campaign": "utm_campaign",
				"term": "utm_term", "content": "utm_content",
			},
		},
		"fields": [
			tab("tab_overview", "Overview"),
			f("name", "Name", "Data", None, 1, write=1, reqd=1),
			f("slug", "Slug", "Data", None, 1, write=1, reqd=1),
			f("status", "Status", "Select", "\nDRAFT\nACTIVE\nARCHIVED", 1),
			col("col_ov2"),
			f("discount_campaign_name", "Discount Campaign", "Data", None, 0, write=1),
			f("page_count", "Pages", "Int", None, 1),
			f("created_at", "Created At", "Data"),
			f("updated_at", "Updated At", "Data"),
			sec("sec_schedule", "Schedule"),
			f("starts_at", "Starts At (ISO 8601)", "Data", None, 0, write=1),
			f("ends_at", "Ends At (ISO 8601)", "Data", None, 0, write=1),
			sec("sec_about", "Description"),
			f("description", "Description", "Small Text", None, 0, write=1),
			sec("sec_utm", "Default UTM"),
			f("utm_source", "UTM Source", "Data", None, 0, write=1),
			f("utm_medium", "UTM Medium", "Data", None, 0, write=1),
			f("utm_campaign", "UTM Campaign", "Data", None, 0, write=1),
			col("col_utm2"),
			f("utm_term", "UTM Term", "Data", None, 0, write=1),
			f("utm_content", "UTM Content", "Data", None, 0, write=1),
		],
	},
	{
		"doctype": "Marzi Template",
		"endpoint": "/v1/publishing/admin/templates",
		"service": "publishing",
		"id_field": "id",
		"list_key": "templates",
		"item_key": None,
		"single_from_list": True,
		"title_field": "template_name",
		"aliases": {"name": "template_name"},
		"writable": True,
		"write_fields": ["template_name", "slug"],
		"write_aliases": {"template_name": "name"},
		"write_child_tables": {
			"config": {"field": "config_sections", "map": {"key": "key", "enabled": "enabled"}, "wrap": "sections"},
		},
		"child_tables": {
			"config_sections": {
				"doctype": "Marzi Template Section",
				"source": "item",
				"item_key": "config.sections",
				"aliases": {},
			},
		},
		"fields": [
			tab("tab_overview", "Overview"),
			f("template_name", "Name", "Data", None, 1, write=1, reqd=1),
			f("slug", "Slug", "Data", None, 1, write=1, reqd=1),
			col("col_ov2"),
			f("created_at", "Created At", "Data"),
			f("updated_at", "Updated At", "Data"),
			tab("tab_config", "Sections"),
			table("config_sections", "Sections", "Marzi Template Section", write=1),
		],
	},
	{
		"doctype": "Marzi FAQ Group",
		"endpoint": "/admin/event-library/faq-groups",
		"service": "v1",
		"id_field": "id",
		"list_key": "faq_groups",
		"item_key": None,
		"single_from_list": True,
		"title_field": "group_name",
		"aliases": {"name": "group_name"},
		"child_tables": {
			"faqs": {
				"doctype": "Marzi FAQ Item",
				"source": "item",
				"item_key": "faqs",
				"aliases": {},
			},
		},
		"fields": [
			tab("tab_overview", "Overview"),
			f("group_name", "Name", "Data", None, 1),
			f("description", "Description", "Small Text", None, 1),
			f("is_active", "Active", "Check", None, 1),
			col("col_ov2"),
			f("created_at", "Created At", "Data"),
			f("updated_at", "Updated At", "Data"),
			tab("tab_faqs", "FAQs"),
			table("faqs", "FAQs", "Marzi FAQ Item"),
		],
	},
	{
		"doctype": "Marzi Info Item",
		"endpoint": "/admin/event-library/info-items",
		"service": "v1",
		"id_field": "id",
		"list_key": "info_items",
		"item_key": None,
		"single_from_list": True,
		"title_field": "title",
		"image_field": "icon_url",
		"aliases": {},
		"writable": True,
		"update_method": "PUT",
		"write_fields": ["kind", "title", "icon_url", "description", "category", "is_active"],
		"defaults": {"is_active": 1},
		"fields": [
			tab("tab_overview", "Overview"),
			img("icon", "Icon", "icon_url"),
			f("title", "Title", "Data", None, 1, write=1, reqd=1),
			f("kind", "Kind", "Select", "\nGOOD_TO_KNOW\nWHATS_INCLUDED", 1, write=1, reqd=1),
			f("description", "Description", "Small Text", None, 1, write=1, reqd=1),
			f("category", "Category", "Data", None, 1, write=1),
			col("col_ov2"),
			f("icon_url", "Icon URL", "Data", "URL", 0, write=1, reqd=1),
			f("is_active", "Active", "Check", None, 0, write=1),
			f("created_at", "Created At", "Data"),
		],
	},
	{
		"doctype": "Marzi WhatsApp Conversation",
		"endpoint": "/dashboard/conversations",
		"service": "whatsapp",
		"auth": False,
		"id_field": "mobile",
		"list_key": "data.items",
		"item_key": None,
		"single_from_list": True,
		"title_field": "mobile",
		"aliases": {
			"name": "contact_name",
			"fullName": "full_name",
			"lastMessage": "last_message",
			"lastMessageDirection": "last_message_direction",
			"lastInteraction": "last_interaction",
			"flowState": "flow_state",
			"conversationId": "conversation_id",
		},
		"fields": [
			tab("tab_overview", "Overview"),
			f("mobile", "Mobile", "Data", None, 1),
			f("contact_name", "Name", "Data", None, 1),
			f("full_name", "Full Name", "Data"),
			f("city", "City", "Data", None, 1),
			f("area", "Area", "Data"),
			col("col_ov2"),
			f("last_message", "Last Message", "Small Text", None, 1),
			f("last_message_direction", "Direction", "Select", "\ninbound\noutbound"),
			f("flow_state", "Flow State", "Data"),
			f("last_interaction", "Last Interaction", "Data"),
			f("conversation_id", "Conversation ID", "Data"),
		],
	},
]


def scrub(name):
	return name.lower().replace(" ", "_")


def controller_class(name):
	return name.replace(" ", "")


def _build_fields(field_tuples):
	fields = []
	for fieldname, label, fieldtype, options, in_list, read_only, reqd, write in field_tuples:
		fld = {"fieldname": fieldname, "fieldtype": fieldtype}
		if label:
			fld["label"] = label
		if options:
			fld["options"] = options
		if in_list:
			fld["in_list_view"] = 1
		if write:  # writable fields must be editable
			read_only = 0
		if read_only:
			fld["read_only"] = 1
		if reqd:
			fld["reqd"] = 1
		fields.append(fld)
	return fields


def _crud_perms(spec):
	"""Full CRUD permission rows for a writable entity (gated by can_create/can_delete)."""
	def row(role):
		return {
			"read": 1, "write": 1, "email": 1, "print": 1, "share": 1, "role": role,
			"create": 1 if spec.get("can_create", True) else 0,
			"delete": 1 if spec.get("can_delete", True) else 0,
		}
	return [row("Marzi Admin"), row("System Manager")]


def _inject_overview_banner(fields):
	"""Insert a full-width HTML banner at the top of the Overview tab.

	The banner markup is rendered client-side (public/js/marzi_overview.js) from the
	doc's own metadata — hero image, title, status badges, key stats — so every parent
	Form opens with a rich visual summary of that row. Placed right after the first Tab
	Break (the Overview tab) so it leads the form; if there are no tabs, it goes first.
	"""
	banner = {"fieldname": "overview_banner", "fieldtype": "HTML"}
	insert_at = 0
	for i, fld in enumerate(fields):
		if fld["fieldtype"] == "Tab Break":
			insert_at = i + 1
			break
	fields.insert(insert_at, banner)
	return fields


def build_json(spec):
	fields = _inject_overview_banner(_build_fields(spec["fields"]))
	doc = {
		"actions": [],
		"allow_copy": 1,
		"allow_rename": 0,
		"autoname": "hash",
		"creation": "2026-07-19 00:00:00.000000",
		"doctype": "DocType",
		"editable_grid": 1,
		"engine": "InnoDB",
		"field_order": [fld["fieldname"] for fld in fields],
		"fields": fields,
		"index_web_pages_for_search": 0,
		"is_virtual": 1,
		"links": [],
		"modified": "2026-07-20 09:00:00.000000",
		"modified_by": "Administrator",
		"module": "Marzi Bridge",
		"name": spec["doctype"],
		"naming_rule": "Random",
		"owner": "Administrator",
		"permissions": [
			{"read": 1, "role": "Marzi Admin"},
			{"read": 1, "role": "System Manager"},
		],
		"sort_field": "creation",
		"sort_order": "DESC",
		"states": [],
		"title_field": spec["title_field"],
		"track_changes": 0,
	}
	if spec.get("image_field"):
		doc["image_field"] = spec["image_field"]
	if spec.get("writable"):
		doc["permissions"] = _crud_perms(spec)
		doc["quick_entry"] = 1
	defaults = spec.get("defaults", {})
	if defaults:
		for fld in fields:
			if fld["fieldname"] in defaults:
				fld["default"] = defaults[fld["fieldname"]]
	return doc


def build_child_json(spec):
	"""Child (istable) virtual DocType — no perms/title, populated by its parent."""
	fields = _build_fields(spec["fields"])
	return {
		"actions": [],
		"allow_copy": 1,
		"creation": "2026-07-20 09:00:00.000000",
		"doctype": "DocType",
		"editable_grid": 1,
		"engine": "InnoDB",
		"field_order": [fld["fieldname"] for fld in fields],
		"fields": fields,
		"index_web_pages_for_search": 0,
		"is_virtual": 1,
		"istable": 1,
		"links": [],
		"modified": "2026-07-20 09:00:00.000000",
		"modified_by": "Administrator",
		"module": "Marzi Bridge",
		"name": spec["doctype"],
		"owner": "Administrator",
		"permissions": [],
		"sort_field": "creation",
		"sort_order": "DESC",
		"states": [],
		"track_changes": 0,
	}


CONTROLLER_TEMPLATE = '''"""{doctype} — read-only virtual DocType backed by `{endpoint}` ({service}).

Auto-generated by scripts/gen_doctypes.py. Data lives in Backend-for-org and is
read live via MarziClient (see marzi_bridge.api_document.ApiDocument).
"""

from marzi_bridge.api_document import ApiDocument


class {klass}(ApiDocument):
	DOCTYPE = "{doctype}"
	api_endpoint = "{endpoint}"
	api_detail_endpoint = {detail_endpoint!r}
	api_id_field = "{id_field}"
	api_service = "{service}"
	api_list_key = {list_key!r}
	api_item_key = {item_key!r}
	api_auth = {auth!r}
	api_single_from_list = {single_from_list!r}
	api_merge_keys = {merge_keys!r}
	api_field_aliases = {aliases!r}
	api_child_tables = {child_tables!r}
	api_list_params = {list_params!r}
	api_cursor_key = {cursor_key!r}
	api_detail_merge_list = {detail_merge_list!r}
	api_write_fields = {write_fields!r}
	api_write_endpoint = {write_endpoint!r}
	api_write_id_field = {write_id_field!r}
	api_update_method = {update_method!r}
	api_can_create = {can_create!r}
	api_can_delete = {can_delete!r}
	api_write_aliases = {write_aliases!r}
	api_nested_fields = {nested_fields!r}
	api_read_nested = {read_nested!r}
	api_write_child_tables = {write_child_tables!r}
	api_write_array_fields = {write_array_fields!r}

	@staticmethod
	def get_list(**kwargs):
		return {klass}._api_list(**kwargs)

	@staticmethod
	def get_count(**kwargs):
		return {klass}._api_count(**kwargs)

	@staticmethod
	def get_stats(**kwargs):
		return {{}}
'''


CHILD_CONTROLLER_TEMPLATE = '''"""{doctype} — istable virtual child DocType, populated by its parent's load_from_db.

Auto-generated by scripts/gen_doctypes.py. Never listed on its own.
"""

from marzi_bridge.api_document import ApiDocument


class {klass}(ApiDocument):
	DOCTYPE = "{doctype}"

	@staticmethod
	def get_list(**kwargs):
		return []

	@staticmethod
	def get_count(**kwargs):
		return 0

	@staticmethod
	def get_stats(**kwargs):
		return {{}}
'''


def build_controller(spec):
	return CONTROLLER_TEMPLATE.format(
		doctype=spec["doctype"],
		endpoint=spec["endpoint"],
		detail_endpoint=spec.get("detail_endpoint"),
		service=spec["service"],
		id_field=spec["id_field"],
		list_key=spec["list_key"],
		item_key=spec["item_key"],
		auth=spec.get("auth", True),
		single_from_list=spec["single_from_list"],
		merge_keys=spec.get("merge_keys", ()),
		aliases=spec["aliases"],
		child_tables=spec.get("child_tables", {}),
		list_params=spec.get("list_params", {}),
		cursor_key=spec.get("cursor_key"),
		detail_merge_list=spec.get("detail_merge_list", False),
		write_fields=tuple(spec.get("write_fields", ())),
		write_endpoint=spec.get("write_endpoint"),
		write_id_field=spec.get("write_id_field"),
		update_method=spec.get("update_method", "PATCH"),
		can_create=spec.get("can_create", True) if spec.get("writable") else True,
		can_delete=spec.get("can_delete", True) if spec.get("writable") else True,
		write_aliases=spec.get("write_aliases", {}),
		nested_fields=spec.get("nested_fields", {}),
		read_nested=spec.get("read_nested", {}),
		write_child_tables=spec.get("write_child_tables", {}),
		write_array_fields=tuple(spec.get("write_array_fields", ())),
		klass=controller_class(spec["doctype"]),
	)


def build_child_controller(spec):
	return CHILD_CONTROLLER_TEMPLATE.format(
		doctype=spec["doctype"],
		klass=controller_class(spec["doctype"]),
	)


def _write(folder, json_doc, controller_src):
	path = os.path.join(APP_DOCTYPE_DIR, folder)
	os.makedirs(path, exist_ok=True)
	open(os.path.join(path, "__init__.py"), "w").close()
	with open(os.path.join(path, f"{folder}.json"), "w") as fh:
		json.dump(json_doc, fh, indent=1)
		fh.write("\n")
	with open(os.path.join(path, f"{folder}.py"), "w") as fh:
		fh.write(controller_src)


def main():
	for spec in CHILD_SPECS:
		folder = scrub(spec["doctype"])
		_write(folder, build_child_json(spec), build_child_controller(spec))
		print(f"generated child  {spec['doctype']:<24} -> {folder}/")
	for spec in SPECS:
		folder = scrub(spec["doctype"])
		_write(folder, build_json(spec), build_controller(spec))
		print(f"generated parent {spec['doctype']:<24} -> {folder}/")


if __name__ == "__main__":
	main()
