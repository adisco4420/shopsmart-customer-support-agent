"""
ShopSmart MCP Server — exposes e-commerce tools over the Model Context Protocol.
Run via: python -m src.mcp_server
"""

import json
import logging
import uuid
from datetime import UTC, datetime

from mcp.server.fastmcp import FastMCP

from src.mcp_server.data.mock_data import CUSTOMERS, KB_ARTICLES, ORDERS, PRODUCTS

# MCP stdio transport must not pollute stdout — log to stderr only
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

mcp = FastMCP("ShopSmart Support Server")

# In-memory ticket store (would be a DB in production)
_tickets: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------


@mcp.tool()
def search_products(query: str, limit: int = 5) -> str:
    """
    Search the ShopSmart product catalog.

    Args:
        query: Search term — matches product name, category, or description.
        limit: Maximum number of results to return (1–10).
    """
    limit = max(1, min(limit, 10))
    q = query.lower()
    results = [
        p
        for p in PRODUCTS
        if q in p["name"].lower()
        or q in p["category"].lower()
        or q in p["description"].lower()
    ][:limit]

    if not results:
        return json.dumps({"message": f"No products found matching '{query}'"})
    return json.dumps(results)


@mcp.tool()
def get_order_status(order_id: str) -> str:
    """
    Retrieve the current status and tracking details for an order.

    Args:
        order_id: The order identifier (e.g. ORD-12345).
    """
    order = ORDERS.get(order_id.upper())
    if not order:
        return json.dumps({"error": f"Order '{order_id}' not found. Check the order ID and try again."})
    return json.dumps(order)


@mcp.tool()
def get_customer_account(customer_id: str) -> str:
    """
    Retrieve customer account details including order history and membership tier.

    Args:
        customer_id: The customer identifier (e.g. CUST-001).
    """
    customer = CUSTOMERS.get(customer_id.upper())
    if not customer:
        return json.dumps({"error": f"Customer '{customer_id}' not found."})
    return json.dumps(customer)


@mcp.tool()
def create_support_ticket(
    customer_id: str,
    subject: str,
    description: str,
    priority: str = "medium",
) -> str:
    """
    Open a new customer support ticket.

    Args:
        customer_id: The customer's ID.
        subject: Short title for the issue (max 100 characters).
        description: Full description of the problem or request.
        priority: Urgency level — must be 'low', 'medium', or 'high'.
    """
    if priority not in ("low", "medium", "high"):
        priority = "medium"
    if len(subject) > 100:
        subject = subject[:100]

    ticket_id = f"TKT-{uuid.uuid4().hex[:6].upper()}"
    ticket = {
        "ticket_id": ticket_id,
        "customer_id": customer_id.upper(),
        "subject": subject,
        "description": description,
        "priority": priority,
        "status": "open",
        "created_at": datetime.now(UTC).isoformat(),
        "estimated_response": "within 24 hours" if priority == "low" else "within 4 hours" if priority == "medium" else "within 1 hour",
    }
    _tickets[ticket_id] = ticket
    logger.info("Created ticket %s for customer %s", ticket_id, customer_id)
    return json.dumps(ticket)


@mcp.tool()
def search_knowledge_base(query: str) -> str:
    """
    Search ShopSmart's FAQ and help article knowledge base.

    Args:
        query: A question or keyword to search for (e.g. 'how do I return an item').
    """
    q = query.lower()
    results = [
        article
        for article in KB_ARTICLES
        if q in article["title"].lower()
        or q in article["content"].lower()
        or any(q in tag for tag in article["tags"])
    ][:3]

    if not results:
        return json.dumps({"message": "No relevant help articles found for that query."})
    return json.dumps(results)


@mcp.tool()
def process_return_request(order_id: str, reason: str) -> str:
    """
    Initiate a return or refund for a delivered order.

    Args:
        order_id: The order to return (e.g. ORD-12345).
        reason: The customer's reason for returning (e.g. 'wrong size', 'defective').
    """
    order = ORDERS.get(order_id.upper())
    if not order:
        return json.dumps({"error": f"Order '{order_id}' not found."})

    eligible_statuses = ("delivered", "shipped")
    if order["status"] not in eligible_statuses:
        return json.dumps({
            "error": (
                f"Cannot process a return for order '{order_id}'. "
                f"Current status is '{order['status']}'. "
                "Returns are only available for shipped or delivered orders."
            )
        })

    return_id = f"RET-{uuid.uuid4().hex[:6].upper()}"
    result = {
        "return_id": return_id,
        "order_id": order_id.upper(),
        "reason": reason,
        "status": "approved",
        "refund_amount": order["total"],
        "currency": "USD",
        "refund_method": "original payment method",
        "estimated_processing_days": "3–5 business days",
        "prepaid_label_sent_to": CUSTOMERS.get(order["customer_id"], {}).get("email", "customer email on file"),
        "instructions": "A prepaid return label has been emailed. Drop off at any carrier location within 14 days.",
    }
    logger.info("Return %s approved for order %s", return_id, order_id)
    return json.dumps(result)
