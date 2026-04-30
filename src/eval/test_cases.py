"""
Evaluation test cases for the ShopSmart Support Agent.

Each case defines an input, the tools expected to be called, keywords that
MUST appear in the response, and a minimum overall quality score (1–5).
Run them with: uv run python src/eval/run_eval.py
"""

EVAL_CASES: list[dict] = [
    # ------------------------------------------------------------------
    # Order tracking
    # ------------------------------------------------------------------
    {
        "id": "TC-001",
        "category": "order_tracking",
        "name": "Track a shipped order by ID",
        "user_input": "Where is my order ORD-12345?",
        "expected_tools": ["get_order_status"],
        "must_contain": ["shipped", "UPS"],
        "must_not_contain": ["I don't know", "cannot help", "I'm not sure"],
        "min_score": 4,
    },
    {
        "id": "TC-002",
        "category": "order_tracking",
        "name": "Track a processing order (no tracking number yet)",
        "user_input": "Can you check on order ORD-99871 for me?",
        "expected_tools": ["get_order_status"],
        "must_contain": ["processing"],
        "must_not_contain": ["tracking number"],
        "min_score": 4,
    },
    {
        "id": "TC-003",
        "category": "order_tracking",
        "name": "Query a delivered order",
        "user_input": "What happened to order ORD-11200?",
        "expected_tools": ["get_order_status"],
        "must_contain": ["delivered"],
        "must_not_contain": [],
        "min_score": 4,
    },
    # ------------------------------------------------------------------
    # Returns & refunds
    # ------------------------------------------------------------------
    {
        "id": "TC-004",
        "category": "returns",
        "name": "Return a delivered order",
        "user_input": "I want to return my order ORD-11200. The keyboard arrived damaged.",
        "expected_tools": ["process_return_request"],
        "must_contain": ["return", "refund"],
        "must_not_contain": ["cannot", "not possible"],
        "min_score": 4,
    },
    {
        "id": "TC-005",
        "category": "returns",
        "name": "Attempt return on a processing order — should be blocked",
        "user_input": "I'd like to return order ORD-99871 please.",
        "expected_tools": ["process_return_request"],
        "must_contain": ["processing"],
        "must_not_contain": ["approved"],
        "min_score": 3,
    },
    # ------------------------------------------------------------------
    # Product search
    # ------------------------------------------------------------------
    {
        "id": "TC-006",
        "category": "product_search",
        "name": "Search for electronics",
        "user_input": "Do you sell any mechanical keyboards?",
        "expected_tools": ["search_products"],
        "must_contain": ["keyboard"],
        "must_not_contain": ["no products", "nothing found"],
        "min_score": 4,
    },
    {
        "id": "TC-007",
        "category": "product_search",
        "name": "Search for a non-existent product",
        "user_input": "Do you sell motorcycles?",
        "expected_tools": ["search_products"],
        "must_contain": [],
        "must_not_contain": ["motorcycle"],  # should not fabricate products
        "min_score": 3,
    },
    # ------------------------------------------------------------------
    # Knowledge base
    # ------------------------------------------------------------------
    {
        "id": "TC-008",
        "category": "knowledge_base",
        "name": "Ask about the return policy",
        "user_input": "What is your return policy?",
        "expected_tools": ["search_knowledge_base"],
        "must_contain": ["30 days", "refund"],
        "must_not_contain": ["I don't know"],
        "min_score": 4,
    },
    {
        "id": "TC-009",
        "category": "knowledge_base",
        "name": "Ask about shipping costs",
        "user_input": "How much does shipping cost?",
        "expected_tools": ["search_knowledge_base"],
        "must_contain": ["shipping"],
        "must_not_contain": [],
        "min_score": 4,
    },
    # ------------------------------------------------------------------
    # Support tickets
    # ------------------------------------------------------------------
    {
        "id": "TC-010",
        "category": "support_ticket",
        "name": "Create a high-priority ticket",
        "user_input": (
            "I'm customer CUST-001 and my headphones completely stopped working "
            "after 2 days. I need urgent help."
        ),
        "expected_tools": ["create_support_ticket"],
        "must_contain": ["ticket"],
        "must_not_contain": ["cannot create"],
        "min_score": 4,
    },
    # ------------------------------------------------------------------
    # Customer account
    # ------------------------------------------------------------------
    {
        "id": "TC-011",
        "category": "account",
        "name": "Look up customer account and order history",
        "user_input": "I'm customer CUST-003. Can you show me my account and recent orders?",
        "expected_tools": ["get_customer_account"],
        "must_contain": ["Priya", "platinum"],
        "must_not_contain": ["not found"],
        "min_score": 4,
    },
    # ------------------------------------------------------------------
    # Multi-tool / complex scenarios
    # ------------------------------------------------------------------
    {
        "id": "TC-012",
        "category": "multi_tool",
        "name": "Order lookup then return initiation",
        "user_input": (
            "I'm customer CUST-001. Can you check my order ORD-11200 "
            "and then start a return because the item is wrong?"
        ),
        "expected_tools": ["get_order_status", "process_return_request"],
        "must_contain": ["return"],
        "must_not_contain": ["cannot"],
        "min_score": 4,
    },
    {
        "id": "TC-013",
        "category": "multi_tool",
        "name": "Product search then support ticket",
        "user_input": (
            "I bought a keyboard last week (order ORD-11200) and one key stopped "
            "working. Can you also check if you have replacement keyboards in stock?"
        ),
        "expected_tools": ["get_order_status", "search_products"],
        "must_contain": ["keyboard"],
        "must_not_contain": [],
        "min_score": 4,
    },
    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------
    {
        "id": "TC-014",
        "category": "edge_case",
        "name": "Vague greeting — agent should ask clarifying question",
        "user_input": "Hi",
        "expected_tools": [],
        "must_contain": [],
        "must_not_contain": ["error", "exception"],
        "min_score": 3,
    },
    {
        "id": "TC-015",
        "category": "edge_case",
        "name": "Unknown order ID — agent should communicate gracefully",
        "user_input": "Where is my order ORD-00000?",
        "expected_tools": ["get_order_status"],
        "must_contain": ["not found"],
        "must_not_contain": ["I made up", "approximately"],
        "min_score": 3,
    },
]
