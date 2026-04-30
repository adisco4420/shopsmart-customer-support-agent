"""
Mock e-commerce database. In production this would be replaced with real DB calls.
"""

PRODUCTS: list[dict] = [
    {
        "id": "PRD-001",
        "name": "Wireless Noise-Cancelling Headphones",
        "category": "electronics",
        "price": 299.99,
        "stock": 45,
        "sku": "WH-NC-001",
        "description": "Premium over-ear headphones with 30-hour battery life, active noise cancellation, and multi-device Bluetooth pairing.",
        "rating": 4.7,
    },
    {
        "id": "PRD-002",
        "name": "Ergonomic Office Chair",
        "category": "furniture",
        "price": 549.00,
        "stock": 12,
        "sku": "CH-ERG-002",
        "description": "Fully adjustable lumbar support, breathable mesh back, 4D armrests. Supports up to 300 lbs.",
        "rating": 4.5,
    },
    {
        "id": "PRD-003",
        "name": "4K Ultra HD Smart TV - 55 inch",
        "category": "electronics",
        "price": 699.99,
        "stock": 8,
        "sku": "TV-4K-55-003",
        "description": "55-inch 4K OLED display, built-in streaming apps, voice control, and HDR10+ support.",
        "rating": 4.6,
    },
    {
        "id": "PRD-004",
        "name": "Stainless Steel Water Bottle",
        "category": "accessories",
        "price": 34.99,
        "stock": 200,
        "sku": "WB-SS-004",
        "description": "32oz double-wall vacuum insulated bottle. Keeps drinks cold 24hrs, hot 12hrs. BPA-free.",
        "rating": 4.8,
    },
    {
        "id": "PRD-005",
        "name": "Running Shoes - Men's",
        "category": "footwear",
        "price": 129.99,
        "stock": 67,
        "sku": "SH-RUN-M-005",
        "description": "Lightweight breathable mesh upper with responsive foam midsole. Available in sizes 7-14.",
        "rating": 4.4,
    },
    {
        "id": "PRD-006",
        "name": "Mechanical Keyboard",
        "category": "electronics",
        "price": 159.99,
        "stock": 30,
        "sku": "KB-MECH-006",
        "description": "Tenkeyless layout, Cherry MX Red switches, RGB per-key backlighting, USB-C detachable cable.",
        "rating": 4.9,
    },
    {
        "id": "PRD-007",
        "name": "Yoga Mat - Non-Slip",
        "category": "fitness",
        "price": 49.99,
        "stock": 150,
        "sku": "YM-NS-007",
        "description": "6mm thick premium TPE mat with alignment lines. 72 x 24 inches. Includes carry strap.",
        "rating": 4.6,
    },
    {
        "id": "PRD-008",
        "name": "Coffee Maker - 12 Cup",
        "category": "kitchen",
        "price": 89.99,
        "stock": 55,
        "sku": "CM-12C-008",
        "description": "Programmable 12-cup drip coffee maker with built-in grinder, thermal carafe, and brew-strength selector.",
        "rating": 4.3,
    },
]

ORDERS: dict[str, dict] = {
    "ORD-12345": {
        "order_id": "ORD-12345",
        "customer_id": "CUST-001",
        "status": "shipped",
        "items": [
            {"product_id": "PRD-001", "name": "Wireless Noise-Cancelling Headphones", "qty": 1, "price": 299.99},
            {"product_id": "PRD-004", "name": "Stainless Steel Water Bottle", "qty": 1, "price": 34.99},
        ],
        "subtotal": 334.98,
        "shipping": 0.00,
        "total": 334.98,
        "tracking_number": "1Z999AA10123456784",
        "carrier": "UPS",
        "estimated_delivery": "2026-05-02",
        "shipping_address": "123 Main St, Austin, TX 78701",
        "created_at": "2026-04-27T10:30:00Z",
    },
    "ORD-11200": {
        "order_id": "ORD-11200",
        "customer_id": "CUST-001",
        "status": "delivered",
        "items": [
            {"product_id": "PRD-006", "name": "Mechanical Keyboard", "qty": 1, "price": 159.99},
        ],
        "subtotal": 159.99,
        "shipping": 5.99,
        "total": 165.98,
        "tracking_number": "9400111899223397623768",
        "carrier": "USPS",
        "estimated_delivery": "2026-04-20",
        "delivered_at": "2026-04-19T14:22:00Z",
        "shipping_address": "123 Main St, Austin, TX 78701",
        "created_at": "2026-04-15T08:00:00Z",
    },
    "ORD-99871": {
        "order_id": "ORD-99871",
        "customer_id": "CUST-002",
        "status": "processing",
        "items": [
            {"product_id": "PRD-003", "name": "4K Ultra HD Smart TV - 55 inch", "qty": 1, "price": 699.99},
        ],
        "subtotal": 699.99,
        "shipping": 0.00,
        "total": 699.99,
        "tracking_number": None,
        "carrier": None,
        "estimated_delivery": "2026-05-05",
        "shipping_address": "456 Oak Ave, Portland, OR 97201",
        "created_at": "2026-04-29T16:45:00Z",
    },
    "ORD-55032": {
        "order_id": "ORD-55032",
        "customer_id": "CUST-003",
        "status": "delivered",
        "items": [
            {"product_id": "PRD-002", "name": "Ergonomic Office Chair", "qty": 1, "price": 549.00},
            {"product_id": "PRD-007", "name": "Yoga Mat - Non-Slip", "qty": 2, "price": 49.99},
        ],
        "subtotal": 648.98,
        "shipping": 0.00,
        "total": 648.98,
        "tracking_number": "1ZX236920348109274",
        "carrier": "FedEx",
        "estimated_delivery": "2026-04-25",
        "delivered_at": "2026-04-24T11:05:00Z",
        "shipping_address": "789 Elm Blvd, Chicago, IL 60601",
        "created_at": "2026-04-20T09:15:00Z",
    },
    "ORD-78410": {
        "order_id": "ORD-78410",
        "customer_id": "CUST-002",
        "status": "cancelled",
        "items": [
            {"product_id": "PRD-005", "name": "Running Shoes - Men's", "qty": 1, "price": 129.99},
        ],
        "subtotal": 129.99,
        "shipping": 5.99,
        "total": 135.98,
        "tracking_number": None,
        "carrier": None,
        "cancellation_reason": "Customer requested cancellation",
        "cancelled_at": "2026-04-28T10:00:00Z",
        "shipping_address": "456 Oak Ave, Portland, OR 97201",
        "created_at": "2026-04-27T22:30:00Z",
    },
}

CUSTOMERS: dict[str, dict] = {
    "CUST-001": {
        "customer_id": "CUST-001",
        "name": "Alice Johnson",
        "email": "alice.johnson@email.com",
        "phone": "+1-512-555-0101",
        "membership": "gold",
        "joined": "2024-01-15",
        "order_ids": ["ORD-12345", "ORD-11200"],
        "total_spent": 500.96,
        "shipping_address": "123 Main St, Austin, TX 78701",
    },
    "CUST-002": {
        "customer_id": "CUST-002",
        "name": "Marcus Webb",
        "email": "marcus.webb@email.com",
        "phone": "+1-503-555-0182",
        "membership": "standard",
        "joined": "2025-03-10",
        "order_ids": ["ORD-99871", "ORD-78410"],
        "total_spent": 699.99,
        "shipping_address": "456 Oak Ave, Portland, OR 97201",
    },
    "CUST-003": {
        "customer_id": "CUST-003",
        "name": "Priya Sharma",
        "email": "priya.sharma@email.com",
        "phone": "+1-312-555-0247",
        "membership": "platinum",
        "joined": "2023-06-22",
        "order_ids": ["ORD-55032"],
        "total_spent": 648.98,
        "shipping_address": "789 Elm Blvd, Chicago, IL 60601",
    },
}

KB_ARTICLES: list[dict] = [
    {
        "id": "KB-001",
        "title": "How to track your order",
        "content": (
            "You can track your order in two ways: "
            "1) Log into your ShopSmart account and go to 'My Orders' — click any order to see real-time tracking. "
            "2) Use the tracking number from your shipping confirmation email on the carrier's website (UPS, FedEx, or USPS). "
            "Tracking updates may take up to 24 hours after your order ships."
        ),
        "tags": ["tracking", "order", "shipping", "where is my order"],
    },
    {
        "id": "KB-002",
        "title": "Return and refund policy",
        "content": (
            "ShopSmart accepts returns within 30 days of delivery. Items must be unused and in original packaging. "
            "To start a return: contact support or use our Returns Portal. Once approved, ship the item back using the prepaid label we email you. "
            "Refunds are processed within 3–5 business days after we receive the item and are issued to the original payment method. "
            "Electronics must be returned within 15 days. Final sale items are not returnable."
        ),
        "tags": ["return", "refund", "exchange", "policy", "send back"],
    },
    {
        "id": "KB-003",
        "title": "Shipping times and costs",
        "content": (
            "Standard shipping (5–7 business days): $5.99, free on orders over $50. "
            "Expedited shipping (2–3 business days): $12.99. "
            "Overnight shipping (next business day): $24.99. "
            "Gold members get free standard shipping on all orders. Platinum members get free expedited shipping. "
            "Orders placed before 2 PM ET on business days ship same day."
        ),
        "tags": ["shipping", "delivery", "cost", "free shipping", "expedited"],
    },
    {
        "id": "KB-004",
        "title": "Membership tiers and benefits",
        "content": (
            "ShopSmart has three membership tiers: "
            "Standard (free) — 1% cashback, standard shipping rates. "
            "Gold ($49/year) — 3% cashback, free standard shipping, early access to sales. "
            "Platinum ($99/year) — 5% cashback, free expedited shipping, priority support, exclusive deals. "
            "Upgrade in Account Settings > Membership."
        ),
        "tags": ["membership", "gold", "platinum", "benefits", "upgrade"],
    },
    {
        "id": "KB-005",
        "title": "How to cancel an order",
        "content": (
            "You can cancel an order within 1 hour of placing it, as long as it has not entered 'processing' status. "
            "To cancel: go to My Orders > select the order > click 'Cancel Order'. "
            "If the order is already processing or shipped, you cannot cancel it — but you can return it after delivery. "
            "Cancellation refunds are issued within 1–2 business days."
        ),
        "tags": ["cancel", "cancellation", "order", "stop order"],
    },
    {
        "id": "KB-006",
        "title": "Damaged or incorrect items",
        "content": (
            "If you received a damaged or wrong item, please contact us within 7 days of delivery. "
            "Take a photo of the item and packaging, then submit a support ticket with the photos attached. "
            "We will send a replacement at no cost or issue a full refund — your choice. "
            "You do not need to return damaged items unless specifically requested."
        ),
        "tags": ["damaged", "broken", "wrong item", "incorrect", "defective"],
    },
    {
        "id": "KB-007",
        "title": "Payment methods accepted",
        "content": (
            "ShopSmart accepts: Visa, Mastercard, American Express, Discover, PayPal, Apple Pay, Google Pay, and ShopSmart Gift Cards. "
            "We use 256-bit SSL encryption for all transactions. "
            "Buy Now Pay Later is available via Klarna for orders over $100. "
            "Cryptocurrency is not currently accepted."
        ),
        "tags": ["payment", "credit card", "paypal", "apple pay", "pay later"],
    },
]
