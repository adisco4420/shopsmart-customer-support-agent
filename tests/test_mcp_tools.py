"""
Unit tests for the MCP server tools.

These tests call the tool functions directly (bypassing the MCP protocol)
to validate business logic without any external dependencies.
"""

import json

import pytest

from src.mcp_server.server import (
    create_support_ticket,
    get_customer_account,
    get_order_status,
    process_return_request,
    search_knowledge_base,
    search_products,
)


# ===========================================================================
# search_products
# ===========================================================================


class TestSearchProducts:
    def test_returns_matching_results(self):
        result = json.loads(search_products("headphones"))
        assert isinstance(result, list)
        assert len(result) > 0
        assert any("headphones" in p["name"].lower() for p in result)

    def test_case_insensitive_match(self):
        lower = json.loads(search_products("headphones"))
        upper = json.loads(search_products("HEADPHONES"))
        assert lower == upper

    def test_matches_by_category(self):
        result = json.loads(search_products("electronics"))
        assert len(result) > 0
        assert all(p["category"] == "electronics" for p in result)

    def test_matches_by_description_keyword(self):
        result = json.loads(search_products("lumbar"))
        assert len(result) > 0
        assert result[0]["id"] == "PRD-002"

    def test_respects_limit(self):
        result = json.loads(search_products("a", limit=2))
        assert len(result) <= 2

    def test_clamps_limit_to_max_10(self):
        result = json.loads(search_products("a", limit=999))
        assert len(result) <= 10

    def test_clamps_limit_to_min_1(self):
        result = json.loads(search_products("keyboard", limit=0))
        assert len(result) >= 1

    def test_returns_message_for_no_match(self):
        result = json.loads(search_products("xyzabc_notaproduct_123"))
        assert "message" in result
        assert "No products found" in result["message"]

    def test_result_contains_expected_fields(self):
        result = json.loads(search_products("keyboard"))
        assert len(result) > 0
        product = result[0]
        for key in ("id", "name", "category", "price", "stock", "description"):
            assert key in product


# ===========================================================================
# get_order_status
# ===========================================================================


class TestGetOrderStatus:
    def test_returns_order_for_valid_id(self):
        result = json.loads(get_order_status("ORD-12345"))
        assert result["order_id"] == "ORD-12345"
        assert result["status"] == "shipped"

    def test_case_insensitive_order_id(self):
        lower = json.loads(get_order_status("ord-12345"))
        upper = json.loads(get_order_status("ORD-12345"))
        assert lower == upper

    def test_shipped_order_has_tracking_number(self):
        result = json.loads(get_order_status("ORD-12345"))
        assert result["tracking_number"] is not None
        assert result["carrier"] is not None

    def test_processing_order_has_no_tracking(self):
        result = json.loads(get_order_status("ORD-99871"))
        assert result["status"] == "processing"
        assert result["tracking_number"] is None

    def test_delivered_order_has_delivered_at(self):
        result = json.loads(get_order_status("ORD-11200"))
        assert result["status"] == "delivered"
        assert "delivered_at" in result

    def test_cancelled_order_has_cancellation_reason(self):
        result = json.loads(get_order_status("ORD-78410"))
        assert result["status"] == "cancelled"
        assert "cancellation_reason" in result

    def test_returns_error_for_unknown_order(self):
        result = json.loads(get_order_status("ORD-99999"))
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_result_contains_expected_fields(self):
        result = json.loads(get_order_status("ORD-12345"))
        for key in ("order_id", "customer_id", "status", "items", "total"):
            assert key in result


# ===========================================================================
# get_customer_account
# ===========================================================================


class TestGetCustomerAccount:
    def test_returns_customer_for_valid_id(self):
        result = json.loads(get_customer_account("CUST-001"))
        assert result["customer_id"] == "CUST-001"
        assert result["name"] == "Alice Johnson"

    def test_case_insensitive_customer_id(self):
        lower = json.loads(get_customer_account("cust-001"))
        upper = json.loads(get_customer_account("CUST-001"))
        assert lower == upper

    def test_gold_customer_has_correct_tier(self):
        result = json.loads(get_customer_account("CUST-001"))
        assert result["membership"] == "gold"

    def test_platinum_customer_has_correct_tier(self):
        result = json.loads(get_customer_account("CUST-003"))
        assert result["membership"] == "platinum"

    def test_customer_has_order_history(self):
        result = json.loads(get_customer_account("CUST-001"))
        assert isinstance(result["order_ids"], list)
        assert len(result["order_ids"]) > 0

    def test_returns_error_for_unknown_customer(self):
        result = json.loads(get_customer_account("CUST-999"))
        assert "error" in result

    def test_result_contains_expected_fields(self):
        result = json.loads(get_customer_account("CUST-001"))
        for key in ("customer_id", "name", "email", "membership", "order_ids"):
            assert key in result


# ===========================================================================
# create_support_ticket
# ===========================================================================


class TestCreateSupportTicket:
    def test_creates_ticket_with_valid_inputs(self):
        result = json.loads(
            create_support_ticket("CUST-001", "Headphones broken", "The left ear stopped working.")
        )
        assert result["status"] == "open"
        assert result["ticket_id"].startswith("TKT-")
        assert result["customer_id"] == "CUST-001"

    def test_defaults_priority_to_medium(self):
        result = json.loads(
            create_support_ticket("CUST-001", "Question", "General enquiry")
        )
        assert result["priority"] == "medium"

    def test_accepts_high_priority(self):
        result = json.loads(
            create_support_ticket("CUST-001", "Urgent", "My order is wrong", priority="high")
        )
        assert result["priority"] == "high"
        assert "1 hour" in result["estimated_response"]

    def test_accepts_low_priority(self):
        result = json.loads(
            create_support_ticket("CUST-001", "Feedback", "Great service!", priority="low")
        )
        assert result["priority"] == "low"
        assert "24 hours" in result["estimated_response"]

    def test_invalid_priority_falls_back_to_medium(self):
        result = json.loads(
            create_support_ticket("CUST-001", "Test", "Test desc", priority="critical")
        )
        assert result["priority"] == "medium"

    def test_truncates_long_subject(self):
        long_subject = "A" * 200
        result = json.loads(
            create_support_ticket("CUST-001", long_subject, "Description")
        )
        assert len(result["subject"]) <= 100

    def test_ticket_has_created_at_timestamp(self):
        result = json.loads(
            create_support_ticket("CUST-002", "Issue", "Details")
        )
        assert "created_at" in result
        # Accept both UTC representations: trailing "Z" or "+00:00" offset
        ts = result["created_at"]
        assert ts.endswith("Z") or "+00:00" in ts

    def test_each_ticket_has_unique_id(self):
        t1 = json.loads(create_support_ticket("CUST-001", "Issue 1", "Desc 1"))
        t2 = json.loads(create_support_ticket("CUST-001", "Issue 2", "Desc 2"))
        assert t1["ticket_id"] != t2["ticket_id"]


# ===========================================================================
# search_knowledge_base
# ===========================================================================


class TestSearchKnowledgeBase:
    def test_returns_results_for_return_query(self):
        result = json.loads(search_knowledge_base("return"))
        assert isinstance(result, list)
        assert len(result) > 0

    def test_matches_by_tag(self):
        result = json.loads(search_knowledge_base("tracking"))
        assert any("track" in a["title"].lower() for a in result)

    def test_matches_by_title_keyword(self):
        result = json.loads(search_knowledge_base("cancel"))
        assert any("cancel" in a["title"].lower() for a in result)

    def test_matches_by_content_keyword(self):
        result = json.loads(search_knowledge_base("prepaid label"))
        assert len(result) > 0

    def test_returns_at_most_3_results(self):
        result = json.loads(search_knowledge_base("order"))
        assert len(result) <= 3

    def test_returns_message_for_no_match(self):
        result = json.loads(search_knowledge_base("xyznotanything_qrst"))
        assert "message" in result

    def test_result_contains_expected_fields(self):
        result = json.loads(search_knowledge_base("shipping"))
        assert len(result) > 0
        for key in ("id", "title", "content", "tags"):
            assert key in result[0]


# ===========================================================================
# process_return_request
# ===========================================================================


class TestProcessReturnRequest:
    def test_approves_return_for_delivered_order(self):
        result = json.loads(process_return_request("ORD-11200", "defective product"))
        assert result["status"] == "approved"
        assert result["return_id"].startswith("RET-")

    def test_approves_return_for_shipped_order(self):
        result = json.loads(process_return_request("ORD-12345", "changed my mind"))
        assert result["status"] == "approved"

    def test_return_includes_refund_amount(self):
        result = json.loads(process_return_request("ORD-11200", "wrong item"))
        assert result["refund_amount"] == pytest.approx(165.98)
        assert result["currency"] == "USD"

    def test_return_includes_instructions(self):
        result = json.loads(process_return_request("ORD-11200", "damaged"))
        assert "instructions" in result
        assert "prepaid" in result["instructions"].lower()

    def test_rejects_return_for_processing_order(self):
        result = json.loads(process_return_request("ORD-99871", "too expensive"))
        assert "error" in result
        assert "processing" in result["error"]

    def test_rejects_return_for_cancelled_order(self):
        result = json.loads(process_return_request("ORD-78410", "changed mind"))
        assert "error" in result

    def test_returns_error_for_unknown_order(self):
        result = json.loads(process_return_request("ORD-00000", "reason"))
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_each_return_has_unique_id(self):
        r1 = json.loads(process_return_request("ORD-11200", "reason 1"))
        r2 = json.loads(process_return_request("ORD-11200", "reason 2"))
        assert r1["return_id"] != r2["return_id"]

    def test_return_stores_customer_email(self):
        result = json.loads(process_return_request("ORD-11200", "wrong size"))
        assert "alice.johnson@email.com" in result["prepaid_label_sent_to"]
