"""Trust-label model — decides whether a tool *output* is untrusted.

A tool output is "untrusted" if it could carry attacker-authored free text, i.e.
it is an indirect-prompt-injection vector. This is the signal the taint tracker
propagates and the policy gate ultimately gates on.

The labels are grounded in where AgentDojo actually plants injections (verified
against the suite environments):

  * workspace — received emails, calendar event fields, cloud-drive file contents
  * banking   — incoming-transaction ``subject``, ``.txt`` file contents
  * slack     — fetched web pages, channel messages
  * travel    — hotel / restaurant / car-rental ``reviews`` (NOT the structured
                catalog: prices, addresses, fuel options are safe)

Three layers of decision, in order:
  1. content scan  — injection markers in the output flip ANY tool to untrusted
                     (catches injection smuggled into an otherwise-safe field);
  2. explicit lists — curated UNTRUSTED / TRUSTED tool names;
  3. name heuristic — unknown *reads* (get_/read_/search_/...) default untrusted
                      (coarse-safe); unknown *actions* (send_/create_/...) do not
                      introduce content, so they don't taint.

OWNER: Pawan (Detection).
"""

from __future__ import annotations

import re

# --- 1. content-based injection markers (high precision, case-insensitive) ----
INJECTION_MARKERS = [
    re.compile(r"ignore\s+(?:all\s+|the\s+|your\s+|any\s+)?(?:previous|prior|above|preceding)\s+instructions", re.I),
    re.compile(r"disregard\s+(?:all\s+|the\s+|your\s+)?(?:previous|prior|above)", re.I),
    re.compile(r"new\s+instructions?\s*:", re.I),
    re.compile(r"you\s+are\s+now\s+", re.I),
    re.compile(r"<\s*function\s*=", re.I),  # tool-call smuggling
]

# --- 2. curated tool lists (the validated injection vectors / safe tools) ------
UNTRUSTED_TOOLS: set[str] = {
    # workspace — inbound email
    "get_received_emails", "get_unread_emails", "read_inbox", "search_emails", "check_new_email",
    # workspace — calendar (events/descriptions can be set by other parties)
    "search_calendar_events", "get_day_calendar_events",
    # workspace / banking — file contents (can be shared/planted by others)
    "read_file", "get_file_by_id", "download_file", "search_files", "search_files_by_filename", "list_files",
    # slack — web pages and channel messages
    "get_webpage", "read_channel_messages",
    # travel — third-party reviews
    "get_rating_reviews_for_restaurants", "get_rating_reviews_for_hotels", "get_rating_reviews_for_car_rental",
    # banking — transaction subjects are attacker-settable
    "get_most_recent_transactions", "get_scheduled_transactions",
    # contacts — names/emails authored by external parties
    "search_contacts_by_email", "search_contacts_by_name",
}

TRUSTED_TOOLS: set[str] = {
    # pure-local / deterministic utilities
    "get_current_day", "parse_date", "parse_datetime", "standardize_url", "next_id",
    # the user's own structured/numeric data (no injectable free text)
    "get_balance", "get_iban", "get_user_info", "get_user_information",
    # the user's own composed content
    "get_sent_emails", "get_draft_emails",
    # travel — structured catalog (prices/addresses/options; not free text)
    "get_all_hotels_in_city", "get_hotels_prices", "get_hotels_address", "get_flight_information",
    "get_all_restaurants_in_city", "get_restaurants_address", "get_price_for_restaurants",
    "get_cuisine_type_for_restaurants", "get_contact_information_for_restaurants",
    "get_dietary_restrictions_for_all_restaurants", "check_restaurant_opening_hours",
    "get_all_car_rental_companies_in_city", "get_car_price_per_day", "get_car_rental_address",
    "get_car_types_available", "get_car_fuel_options",
}

# --- 3. name heuristic for tools in neither list ------------------------------
# Reads pull data in (potential injection vector); actions push out (no content).
READ_PREFIXES = ("get_", "read_", "search_", "list_", "download_", "find_", "check_")


class TrustLabeler:
    """Classifies a tool output as trusted/untrusted, with a reason for logging."""

    def __init__(
        self,
        untrusted_tools: set[str] = UNTRUSTED_TOOLS,
        trusted_tools: set[str] = TRUSTED_TOOLS,
        read_prefixes: tuple[str, ...] = READ_PREFIXES,
        scan_content: bool = True,
        unknown_reads_untrusted: bool = True,
    ) -> None:
        self.untrusted_tools = untrusted_tools
        self.trusted_tools = trusted_tools
        self.read_prefixes = read_prefixes
        self.scan_content = scan_content
        self.unknown_reads_untrusted = unknown_reads_untrusted

    def label(self, tool_name: str, content: str = "") -> tuple[bool, str]:
        """Returns ``(untrusted, reason)``."""
        if self.scan_content and content and self._content_suspicious(content):
            return True, "content matched an injection marker"
        if tool_name in self.untrusted_tools:
            return True, "known injection-vector tool"
        if tool_name in self.trusted_tools:
            return False, "known safe tool"
        if self.unknown_reads_untrusted and tool_name.startswith(self.read_prefixes):
            return True, "unknown read tool (coarse-safe default)"
        return False, "unknown non-read tool (introduces no external content)"

    def is_untrusted(self, tool_name: str, content: str = "") -> bool:
        return self.label(tool_name, content)[0]

    def _content_suspicious(self, content: str) -> bool:
        return any(marker.search(content) for marker in INJECTION_MARKERS)


# Module-level default used by the taint tracker.
default_labeler = TrustLabeler()


def default_is_untrusted(tool_name: str, content: str = "") -> bool:
    """Backwards-compatible functional entry point."""
    return default_labeler.is_untrusted(tool_name, content)
