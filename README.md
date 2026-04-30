# ShopSmart Support Agent

An AI-powered customer support chatbot for an e-commerce store, built with the **Model Context Protocol (MCP)** and **OpenRouter**.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Browser                                                    │
│  static/index.html  ──SSE streaming──►  FastAPI (app.py)   │
└──────────────────────────────────────────────────────────┬──┘
                                                           │
                                                 src/agent/runner.py
                                                  (OpenRouter LLM)
                                                           │ tool calls
                                                           ▼
                                              src/mcp_server/server.py
                                              (FastMCP over stdio)
                                                           │
                                              src/mcp_server/data/
                                              mock_data.py (DB stand-in)
```

**Flow:**
1. User sends a message via the chat UI
2. FastAPI starts the MCP server as a subprocess (stdio transport)
3. The agent fetches the tool list from the MCP server
4. An OpenRouter LLM decides which tools to call
5. Tool results are fed back to the LLM until a final answer is reached
6. The response is streamed back to the browser as Server-Sent Events

## MCP Tools

| Tool | Description |
|------|-------------|
| `search_products` | Search the product catalog |
| `get_order_status` | Look up order tracking and status |
| `get_customer_account` | Retrieve account and order history |
| `create_support_ticket` | Open a support ticket |
| `search_knowledge_base` | Search FAQs and help articles |
| `process_return_request` | Initiate a return or refund |

## Quick Start

**1. Install dependencies**
```bash
uv sync
```

**2. Configure environment**
```bash
cp .env.example .env
# Edit .env and set your OPENROUTER_API_KEY
```

**3. Run locally**
```bash
uv run python main.py
# Open http://localhost:8000
```

## Deployment (Render)

1. Push this repo to GitHub
2. Go to render.com > New > Blueprint
3. Connect your repo — Render reads render.yaml automatically
4. Set OPENROUTER_API_KEY in the Render environment variables dashboard
5. Deploy

## Try these prompts

- "Where is my order ORD-12345?"
- "I want to return order ORD-11200, it arrived damaged"
- "Do you have any mechanical keyboards?"
- "What is your return policy?"
- "I am customer CUST-001, show me my recent orders"
- "Create a support ticket — my headphones stopped working after 2 days"

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| OPENROUTER_API_KEY | Yes | — | OpenRouter API key |
| OPENROUTER_MODEL | No | anthropic/claude-sonnet-4.6 | Model to use |
| APP_URL | No | http://localhost:8000 | Sent in OpenRouter request headers |
| ENV | No | production | Set to development for hot-reload |
| PORT | No | 8000 | Server port |
