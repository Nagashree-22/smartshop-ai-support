
"""
SmartShop AI Customer Service Chatbot - Flask Web Application
--------------------------------------------------------------
Endpoints:
- GET  /                     : Render main web interface
- POST /api/chat             : Send message and receive chatbot response
- GET  /api/faq              : Retrieve categorized FAQs
- GET  /api/faq/categories   : Retrieve available FAQ categories
- GET  /api/orders           : Retrieve sample prototype orders for testing
- POST /api/escalate         : Request human agent escalation & support ticket
- POST /api/session/clear    : Reset conversation session state
- GET  /api/status           : Health and AI mode diagnostic status
"""

import os
import uuid
import logging
from typing import Dict, Any
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv

from chatbot import chatbot_instance, get_groq_client, GROQ_MODEL

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "smartshop-default-secret-key-2026")

logger = logging.getLogger("SmartShopApp")

# In-memory storage for client conversation sessions
# In production, use Redis or a database session store
SESSION_STORE: Dict[str, Dict[str, Any]] = {}


def get_or_create_session(session_id: str = None) -> Tuple_Session:
    """Retrieve or initialize user session state."""
    if not session_id or session_id not in SESSION_STORE:
        new_id = str(uuid.uuid4())
        SESSION_STORE[new_id] = {
            "session_id": new_id,
            "history": [],
            "unsuccessful_attempts": 0,
            "pending_order_action": None,
            "escalated": False,
            "last_order_id": None
        }
        return new_id, SESSION_STORE[new_id]
    return session_id, SESSION_STORE[session_id]

# Type helper alias for clean code
Tuple_Session = tuple


@app.route("/")
def index():
    """Renders the main customer service chatbot interface."""
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """Primary chat endpoint. Accepts user message and returns chatbot response."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({
            "success": False,
            "error": "Invalid request. JSON body required."
        }), 400

    user_msg = data.get("message", "")
    session_id = data.get("session_id")
    
    # Validation
    if not isinstance(user_msg, str):
        return jsonify({
            "success": False,
            "error": "Message must be a string."
        }), 400

    sid, sess = get_or_create_session(session_id)

    # Empty message handling
    if not user_msg.strip():
        return jsonify({
            "success": True,
            "session_id": sid,
            "response": "Please enter a message or question so I can assist you.",
            "intent": "empty",
            "resolved_check": False,
            "can_escalate": False
        })

    # Record message to history
    sess["history"].append({"role": "user", "text": user_msg.strip()})

    try:
        # Process message through conversational engine
        result = chatbot_instance.process_message(user_msg, sess)

        # Record assistant reply to history
        sess["history"].append({"role": "assistant", "text": result.get("response", "")})

        # Cap history to prevent memory bloat
        if len(sess["history"]) > 30:
            sess["history"] = sess["history"][-30:]

        return jsonify({
            "success": True,
            "session_id": sid,
            "response": result.get("response", ""),
            "intent": result.get("intent", "general"),
            "confidence": result.get("confidence", 1.0),
            "order_found": result.get("order_found"),
            "needs_order_id": result.get("needs_order_id", False),
            "resolved_check": result.get("resolved_check", False),
            "can_escalate": result.get("can_escalate", False),
            "is_escalation": result.get("is_escalation", False),
            "ticket": result.get("ticket"),
            "quick_replies": result.get("quick_replies", [])
        })

    except Exception as e:
        logger.error(f"Error processing chat message: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "An internal error occurred while processing your request. Please try again or click 'Connect to Human Agent'."
        }), 500


@app.route("/api/faq", methods=["GET"])
def api_get_faqs():
    """Returns all categorized FAQs."""
    category = request.args.get("category")
    if category:
        filtered = [f for f in chatbot_instance.faqs if f.get("category") == category]
        return jsonify({"success": True, "faqs": filtered, "total": len(filtered)})
    return jsonify({
        "success": True,
        "faqs": chatbot_instance.faqs,
        "total": len(chatbot_instance.faqs)
    })


@app.route("/api/faq/categories", methods=["GET"])
def api_get_categories():
    """Returns FAQ categories with item counts and display labels."""
    category_labels = {
        "order_tracking": "📦 Order Tracking",
        "order_cancellation": "❌ Order Cancellation",
        "returns_refunds": "💰 Returns & Refunds",
        "payment_failures": "💳 Payment Issues",
        "product_availability": "🔍 Product Availability",
        "delivery_delays": "🚚 Delivery Delays",
        "account_login": "🔐 Account & Login",
        "damaged_incorrect": "⚠️ Damaged / Wrong Item",
        "exchange_requests": "🔄 Size & Color Exchange",
        "customer_support": "🎧 Human Support & Helpline"
    }

    counts = {}
    for f in chatbot_instance.faqs:
        cat = f.get("category", "other")
        counts[cat] = counts.get(cat, 0) + 1

    result = []
    for cat, count in counts.items():
        result.append({
            "id": cat,
            "label": category_labels.get(cat, cat.replace("_", " ").title()),
            "count": count
        })

    return jsonify({"success": True, "categories": result})


@app.route("/api/orders", methods=["GET"])
def api_get_sample_orders():
    """Returns sample prototype orders for test demonstrations."""
    # Redact full payment details for safety in prototype listing
    demo_orders = {}
    for oid, data in chatbot_instance.sample_orders.items():
        demo_orders[oid] = {
            "order_id": data["order_id"],
            "item": data["item"],
            "status": data["status"],
            "amount": data["amount"],
            "expected_delivery": data.get("expected_delivery", data.get("delivered_date", "N/A")),
            "courier": data.get("courier", "N/A"),
            "can_cancel": data.get("can_cancel", False)
        }
    return jsonify({"success": True, "orders": demo_orders})


@app.route("/api/escalate", methods=["POST"])
def api_escalate():
    """Directly triggers human agent escalation and returns a simulated support ticket."""
    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "Customer requested direct assistance from human support agent.")
    summary = data.get("summary", "Manual user escalation via support dashboard.")
    priority = data.get("priority", "Normal")
    session_id = data.get("session_id")

    sid, sess = get_or_create_session(session_id)
    sess["escalated"] = True

    escalation = chatbot_instance.generate_escalation_ticket(reason, summary, priority)
    sess["history"].append({
        "role": "assistant",
        "text": escalation["ticket_markdown"]
    })

    return jsonify({
        "success": True,
        "session_id": sid,
        "response": escalation["ticket_markdown"],
        "ticket": escalation["ticket_data"],
        "is_escalation": True
    })


@app.route("/api/session/clear", methods=["POST"])
def api_clear_session():
    """Clears and restarts the conversation session."""
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")

    if session_id and session_id in SESSION_STORE:
        del SESSION_STORE[session_id]

    new_id, _ = get_or_create_session()
    return jsonify({
        "success": True,
        "message": "Session reset successfully.",
        "session_id": new_id
    })


@app.route("/api/status", methods=["GET"])
def api_status():
    """Diagnostic status endpoint returning AI model status and loaded datasets."""
    groq_client = get_groq_client()
    has_api_key = bool(os.getenv("GROQ_API_KEY", "").strip())
    
    ai_status = "Groq LLM Active" if (groq_client and has_api_key) else "Rule-Based Fallback Engine Active"

    return jsonify({
        "status": "online",
        "service": "ShopMate AI Customer Support",
        "ai_engine": ai_status,
        "groq_model": GROQ_MODEL,
        "groq_key_configured": has_api_key,
        "faqs_loaded": len(chatbot_instance.faqs),
        "sample_orders_loaded": len(chatbot_instance.sample_orders),
        "categories_count": len(chatbot_instance.categories)
    })


@app.route("/favicon.ico")
def favicon():
    """Favicon endpoint returning an SVG shopping cart icon."""
    svg_icon = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#4f46e5" stroke-width="2"><circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/></svg>"""
    return svg_icon, 200, {"Content-Type": "image/svg+xml"}


@app.errorhandler(404)
def not_found(e):
    return jsonify({"success": False, "error": "Resource not found"}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"success": False, "error": "Internal server error occurred"}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("DEBUG", "True").lower() in ("true", "1")
    print(f"[*] Starting SmartShop AI Support on http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=debug, use_reloader=False)
