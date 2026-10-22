"""
SmartShop AI Customer Service Chatbot Engine
---------------------------------------------
This module implements the core conversational logic:
1. Intent Classification (rule-based and keyword scoring)
2. FAQ Matching (token overlap, keyword weighting, and similarity)
3. Prototype Order Verification (using sample_orders.json)
4. Context & Session State Tracking
5. Groq LLM API Integration (with automatic Fallback Engine)
6. Human-Agent Escalation with Simulated Demonstration Tickets
7. Data Privacy Protection & Boundary Enforcement
"""

import os
import re
import json
import random
import logging
from typing import Dict, Any, List, Optional, Tuple
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SmartShopChatbot")

# Load environment variables
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FAQ_FILE = os.path.join(BASE_DIR, "faq.json")
ORDERS_FILE = os.path.join(BASE_DIR, "sample_orders.json")

# Groq API configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()

# Lazy-loaded Groq client
_groq_client = None

def get_groq_client():
    """Initializes and returns the Groq client if API key is present."""
    global _groq_client
    if _groq_client is not None:
        return _groq_client
    
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return None
    
    try:
        from groq import Groq
        _groq_client = Groq(api_key=api_key)
        logger.info(f"Groq API client successfully initialized with model {GROQ_MODEL}.")
        return _groq_client
    except Exception as e:
        logger.error(f"Failed to initialize Groq client: {e}")
        return None


class SmartShopChatbot:
    """Intelligent e-commerce customer support chatbot with FAQ matching,
    sample order verification, LLM generation, and human escalation."""

    def __init__(self):
        self.faqs = self._load_faqs()
        self.sample_orders = self._load_sample_orders()
        self.categories = list({f["category"] for f in self.faqs})
        logger.info(f"Chatbot initialized with {len(self.faqs)} FAQs and {len(self.sample_orders)} sample orders.")

    def _load_faqs(self) -> List[Dict[str, Any]]:
        """Load categorized FAQ database from faq.json."""
        try:
            with open(FAQ_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading {FAQ_FILE}: {e}")
            return []

    def _load_sample_orders(self) -> Dict[str, Any]:
        """Load mock orders from sample_orders.json."""
        try:
            with open(ORDERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading {ORDERS_FILE}: {e}")
            return {}

    def extract_order_id(self, text: str) -> Optional[str]:
        """Extract order ID like ORD-1001 or 1001 from user text."""
        match = re.search(r"\bORD[-_]?(\d{4})\b", text, re.IGNORECASE)
        if match:
            return f"ORD-{match.group(1)}"
        # Check standalone 4 digits if within order range
        num_match = re.search(r"\b(100[1-9])\b", text)
        if num_match:
            return f"ORD-{num_match.group(1)}"
        return None

    def classify_intent(self, user_msg: str, session: Dict[str, Any]) -> str:
        """Classify customer message into predefined customer service intents."""
        msg = user_msg.strip().lower()
        if not msg:
            return "empty"

        # Check for privacy violations (asking for another customer's data)
        privacy_keywords = [
            "other customer", "another customer", "someone else's", "someone elses",
            "alex johnson's", "priya sharma's", "marcus lee's", "sara davis's", "david kim's",
            "reveal customer", "show me customer data", "another user's account", "leak customer",
            "other user's address", "other user's phone", "other user's credit card"
        ]
        if any(pk in msg for pk in privacy_keywords):
            return "privacy_violation"

        # Check for human agent request
        human_keywords = [
            "human", "real person", "agent", "representative", "talk to someone",
            "speak with someone", "live person", "support executive", "escalate",
            "manager", "operator", "customer care number", "call support"
        ]
        if any(hk in msg for hk in human_keywords):
            return "human_agent"

        # Check for customer frustration or unhelpful response complaints
        frustration_keywords = [
            "useless", "unhelpful", "stupid bot", "terrible", "waste of time",
            "worst service", "not helping", "frustrated", "angry", "you don't know",
            "stop repeating", "doesn't answer", "does not help", "ridiculous", "horrible"
        ]
        if any(fk in msg for fk in frustration_keywords):
            return "frustration"

        # Check for cancellation intent
        if any(w in msg for w in ["cancel", "cancellation", "stop my order", "annul order", "dont want order"]):
            return "order_cancellation"

        # Tracking instructions and stale-link questions are FAQs, not live lookups.
        if any(w in msg for w in [
            "tracking number", "tracking code", "tracking link", "awb",
            "tracking status is stuck", "tracking has not updated", "tracking not updated"
        ]):
            return "general_faq"

        # Check for order tracking
        if any(w in msg for w in ["where is my order", "track", "tracking", "status of order", "locate package", "shipment status"]):
            return "order_tracking"

        # Check for delivery delay
        if any(w in msg for w in ["delayed", "delay", "late delivery", "not arrived", "overdue", "past delivery date"]):
            return "delivery_delays"

        # Check for payment failures & deducted money
        if any(w in msg for w in ["payment failed", "money deducted", "debited", "charged but", "payment deducted", "transaction failed", "double charge"]):
            return "payment_failures"

        # Check for damaged / incorrect product
        if any(w in msg for w in ["damaged", "broken", "crushed", "defective", "wrong item", "wrong product", "incorrect item", "missing item"]):
            return "damaged_incorrect"

        # Check for returns / refunds
        if any(w in msg for w in ["refund", "money back", "return item", "return policy", "how to return", "reimbursement"]):
            return "returns_refunds"

        # Check for exchange requests
        if any(w in msg for w in ["exchange", "swap size", "wrong size", "replace with different size", "color exchange"]):
            return "exchange_requests"

        # Check for account & security
        if any(w in msg for w in ["hacked", "compromised", "unauthorized", "reset password", "forgot password", "change email", "cant log in", "login error"]):
            return "account_login"

        # Check for product availability
        if any(w in msg for w in ["out of stock", "restock", "available again", "inventory", "when in stock", "pre-order"]):
            return "product_availability"

        # Treat a bare order ID as a follow-up, after checking for specific order actions.
        extracted_id = self.extract_order_id(msg)
        if extracted_id and (len(msg.split()) <= 4 or session.get("pending_order_action")):
            return "order_id_lookup"

        # Check for resolution feedback
        if msg in ["yes", "yes, resolved", "resolved", "yes thank you", "solved", "it helped"]:
            return "resolution_yes"
        if msg in ["no", "no, not resolved", "not resolved", "still need help", "unresolved"]:
            return "resolution_no"

        # Check for completely unrelated queries
        unrelated_signals = [
            "weather in", "recipe for", "write a poem", "quantum physics", "who won",
            "capital of", "code in c++", "solve equation", "movie recommendation",
            "tell me a joke", "homework help", "world war"
        ]
        if any(us in msg for us in unrelated_signals):
            return "unrelated"

        return "general_faq"

    def match_faq(self, user_msg: str) -> Tuple[Optional[Dict[str, Any]], float]:
        """Search FAQ list using token overlap and keyword weighted scoring."""
        msg_clean = re.sub(r"[^\w\s]", " ", user_msg.lower()).strip()
        user_tokens = set(msg_clean.split())
        
        # Stop words to filter out common grammatical tokens
        stop_words = {"is", "my", "the", "a", "an", "i", "can", "to", "for", "in", "of", "and", "do", "how", "what", "where", "why"}
        significant_tokens = user_tokens - stop_words
        if not significant_tokens:
            significant_tokens = user_tokens

        best_faq = None
        best_score = 0.0

        for faq in self.faqs:
            # Score against standard question
            q_clean = re.sub(r"[^\w\s]", " ", faq["question"].lower())
            q_tokens = set(q_clean.split())
            q_sig = q_tokens - stop_words or q_tokens
            
            # Token overlap score
            overlap_q = len(significant_tokens & q_sig) / max(len(significant_tokens | q_sig), 1)

            # Score against alternative questions
            alt_scores = []
            for alt in faq.get("alternative_questions", []):
                alt_clean = re.sub(r"[^\w\s]", " ", alt.lower())
                alt_tokens = set(alt_clean.split())
                alt_sig = alt_tokens - stop_words or alt_tokens
                score = len(significant_tokens & alt_sig) / max(len(significant_tokens | alt_sig), 1)
                alt_scores.append(score)
            max_alt_score = max(alt_scores) if alt_scores else 0.0

            # Score against keywords
            kw_matches = sum(1 for kw in faq.get("keywords", []) if kw.lower() in msg_clean)
            kw_score = min(kw_matches / max(len(faq.get("keywords", [])), 1), 1.0) * 0.45

            # Phrase containment bonus
            phrase_bonus = 0.0
            if q_clean in msg_clean or msg_clean in q_clean:
                phrase_bonus = 0.35

            total_score = max(overlap_q, max_alt_score) * 0.5 + kw_score + phrase_bonus
            
            if total_score > best_score:
                best_score = total_score
                best_faq = faq

        # Match threshold
        if best_score >= 0.32:
            return best_faq, best_score
        return None, best_score

    def handle_order_action(self, order_id: str, action: str) -> Dict[str, Any]:
        """Perform verified lookup and prototype operations on sample orders."""
        order = self.sample_orders.get(order_id)
        if not order:
            available_ids = ", ".join(self.sample_orders.keys())
            return {
                "message": (
                    f"⚠️ Order ID **{order_id}** was not found in our records.\n\n"
                    f"*Note: For this college prototype demonstration, available mock orders are:* `{available_ids}`.\n"
                    f"Please check your order confirmation email or enter one of the sample IDs above."
                ),
                "order_found": False,
                "needs_followup": True
            }

        # Format clearly labeled prototype response
        badge = "📦 **[PROTOTYPE MOCK DATA - SMART-SHOP DATABASE]**"
        
        if action in ["order_tracking", "track"]:
            msg = (
                f"{badge}\n\n"
                f"**Order ID:** {order['order_id']}\n"
                f"**Customer:** {order['customer_name']}\n"
                f"**Item:** {order['item']} (Qty: {order['quantity']})\n"
                f"**Current Status:** `{order['status']}`\n"
                f"**Courier:** {order['courier']}\n"
                f"**Tracking Number:** `{order['tracking_number']}`\n"
                f"**Current Location:** {order['current_location']}\n"
                f"**Expected Delivery:** {order.get('expected_delivery', order.get('delivered_date', 'N/A'))}\n\n"
                f"*(Real-time logistics updates are synchronized directly from courier tracking).* "
            )
            return {"message": msg, "order_found": True, "order": order}

        elif action in ["order_cancellation", "cancel"]:
            if order["can_cancel"]:
                # Execute simulated cancellation
                order["status"] = "Cancelled & Refund Processing"
                order["can_cancel"] = False
                msg = (
                    f"{badge}\n\n"
                    f"✅ **Order {order['order_id']} has been successfully cancelled!**\n\n"
                    f"• **Item:** {order['item']}\n"
                    f"• **Refund Amount:** {order['amount']}\n"
                    f"• **Refund Status:** Initiated to original payment method ({order['payment_method']}). Expected credit within 24-48 hours.\n"
                    f"• **Confirmation:** An email confirmation has been sent to the registered address."
                )
                return {"message": msg, "order_found": True, "cancelled": True, "order": order}
            else:
                msg = (
                    f"{badge}\n\n"
                    f"⚠️ **Order {order['order_id']} cannot be cancelled online.**\n\n"
                    f"• **Current Status:** `{order['status']}`\n"
                    f"• **Reason:** {order.get('cancellation_note', 'Order has already been processed or dispatched.')}\n\n"
                    f"💡 *Doorstep Refusal Option:* When the delivery courier arrives with your package, simply refuse the delivery. Once returned to our warehouse, your 100% full refund is automatically triggered."
                )
                return {"message": msg, "order_found": True, "cancelled": False, "order": order}

        elif action in ["returns_refunds", "refund", "return"]:
            if order.get("return_eligible"):
                msg = (
                    f"{badge}\n\n"
                    f"**Order ID:** {order['order_id']}\n"
                    f"**Item:** {order['item']}\n"
                    f"**Status:** `{order['status']}`\n"
                    f"**Return Eligibility:** ✅ Eligible ({order.get('return_window', 'Within 15 days of delivery')})\n\n"
                    f"**To schedule your return pickup:**\n"
                    f"1. Choose your preferred pickup time slot (next 48 hours).\n"
                    f"2. Ensure original tags and box packaging are preserved.\n"
                    f"3. Full refund of **{order['amount']}** will be credited to {order['payment_method']} within 2-3 business days after pickup verification."
                )
            else:
                msg = (
                    f"{badge}\n\n"
                    f"**Order ID:** {order['order_id']}\n"
                    f"**Item:** {order['item']}\n"
                    f"**Current Status:** `{order['status']}`\n"
                    f"**Return Eligibility:** ⚠️ {order.get('return_window', 'Item is not eligible for return at this stage')}.\n\n"
                    f"If you believe this is in error or your product arrived damaged, I can immediately connect you with a human support agent."
                )
            return {"message": msg, "order_found": True, "order": order}

        elif action in ["delivery_delays", "delay"]:
            delay_reason = order.get("delay_reason", "Logistics route transit check in progress")
            revised = order.get("revised_delivery", order.get("expected_delivery", "In 1-2 business days"))
            msg = (
                f"{badge}\n\n"
                f"**Order ID:** {order['order_id']}\n"
                f"**Item:** {order['item']}\n"
                f"**Status:** `{order['status']}`\n"
                f"**Courier:** {order['courier']} (`{order['tracking_number']}`)\n"
                f"**Current Location:** {order['current_location']}\n"
                f"**Reason for Delay:** {delay_reason}\n"
                f"**Revised Delivery Date:** 📅 **{revised}**\n\n"
                f"We sincerely apologize for the inconvenience! We have flagged this tracking number for priority transit handling."
            )
            return {"message": msg, "order_found": True, "order": order}

        # Default fallback for order lookup
        return self.handle_order_action(order_id, "order_tracking")

    def generate_escalation_ticket(self, reason: str, user_summary: str, priority: str = "Normal") -> Dict[str, Any]:
        """Generate a simulated human support escalation ticket."""
        ticket_id = f"TKT-2026-{random.randint(1000, 9999)}"
        queue_pos = random.randint(1, 4)
        wait_mins = queue_pos * 2

        ticket_details = {
            "ticket_id": ticket_id,
            "priority": priority,
            "status": "Escalated to Human Agent",
            "escalation_reason": reason,
            "customer_summary": user_summary,
            "queue_position": queue_pos,
            "estimated_wait_time": f"{wait_mins} minutes",
            "disclaimer": "DEMONSTRATION ONLY - SIMULATED SUPPORT TICKET (In production, this routes to live Zendesk / Freshdesk queues)."
        }

        ticket_markdown = (
            f"### 🎫 Support Escalation Ticket: `{ticket_id}`\n"
            f"> ⚠️ **[DEMONSTRATION ONLY — SIMULATED TICKET]**\n\n"
            f"| Detail | Value |\n"
            f"|---|---|\n"
            f"| **Ticket ID** | `{ticket_id}` |\n"
            f"| **Status** | Escalated to Tier-2 Support |\n"
            f"| **Priority** | `{priority}` |\n"
            f"| **Reason** | {reason} |\n"
            f"| **Queue Position** | #{queue_pos} in queue |\n"
            f"| **Estimated Response** | ~{wait_mins} mins |\n\n"
            f"**Customer Issue Summary:** *\"{user_summary}\"*\n\n"
            f"A live human specialist has been alerted to review your case history. You may also contact phone support directly at **1-800-SMART-SHOP**."
        )

        return {
            "ticket_data": ticket_details,
            "ticket_markdown": ticket_markdown
        }

    def generate_llm_response(self, user_msg: str, session: Dict[str, Any]) -> str:
        """Call Groq API with grounded prompt; if API key is missing or fails,
        cleanly falls back to the rule-based engine."""
        client = get_groq_client()
        if not client:
            return self.generate_fallback_response(user_msg, session, reason="Groq API key not configured")

        system_prompt = (
            "You are ShopMate, the AI customer service assistant for SmartShop, an e-commerce online shopping platform. "
            "Your tone is friendly, professional, empathetic, concise, and helpful.\n\n"
            "STRICT GROUNDING & SECURITY RULES:\n"
            "1. Ground all your answers strictly in standard e-commerce policies: 15-day return window, free exchanges for size/color, "
            "refunds in 24-48 hrs for UPI or 3-5 days for cards, standard delivery in 3-5 business days, 100% cancellation before shipping.\n"
            "2. NEVER invent fake order IDs, non-existent customer names, fake tracking numbers, or personal accounts.\n"
            "3. If a user asks to track, cancel, or refund an order without giving an Order ID, politely ask them to provide their Order ID "
            "(sample demo IDs: ORD-1001, ORD-1002, ORD-1003, ORD-1004, ORD-1005).\n"
            "4. NEVER disclose another customer's private information, addresses, phone numbers, or credit card details under any circumstances.\n"
            "5. If a question is completely unrelated to shopping, orders, or SmartShop (e.g., science, politics, general coding), "
            "politely state your role as ShopMate, SmartShop's customer support assistant, and decline the off-topic query.\n"
            "6. If the customer is reporting fraud, disputed credit card charges, or expresses intense frustration, recommend escalating to a human support agent."
        )

        # Build message history for Groq
        messages = [{"role": "system", "content": system_prompt}]
        for item in session.get("history", [])[-6:]:
            messages.append({"role": item["role"], "content": item["text"]})
        messages.append({"role": "user", "content": user_msg})

        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                temperature=0.3,
                max_tokens=350,
            )
            content = response.choices[0].message.content.strip()
            return content
        except Exception as e:
            logger.warning(f"Groq API call encountered error ({e}). Seamlessly switching to Rule-Based Fallback Engine.")
            return self.generate_fallback_response(user_msg, session, reason=f"Groq API error ({type(e).__name__})")

    def generate_fallback_response(self, user_msg: str, session: Dict[str, Any], reason: str = "") -> str:
        """Intelligent, grounded rule-based fallback response engine."""
        msg = user_msg.lower()

        # Check damaged / defective product keywords first
        if any(w in msg for w in ["damaged", "broken", "defective", "crushed", "wrong item", "faulty"]):
            return (
                "We sincerely apologize for the damaged item! If your package arrived damaged or defective:\n\n"
                "1. Please photograph the damaged item and outer packaging box.\n"
                "2. Navigate to 'My Orders' -> 'Report Issue' -> 'Damaged Product' within 48 hours of delivery.\n"
                "3. We will immediately arrange a free replacement or 100% full refund.\n\n"
                "Please provide your **Order ID** so we can initiate replacement processing."
            )

        # Check order-related keywords
        if any(w in msg for w in ["order", "package", "item", "delivery", "shipping"]):
            return (
                "I'm ShopMate, SmartShop's customer support assistant. To look into your order details, tracking status, or cancellation eligibility, "
                "could you please share your **Order ID**?\n\n"
                "*For this prototype demonstration, you can test with sample IDs like:* `ORD-1001` (Shipped), `ORD-1002` (Processing), "
                "`ORD-1003` (Delivered), or `ORD-1005` (Delayed)."
            )

        # Check return / refund keywords
        if any(w in msg for w in ["refund", "return", "money"]):
            return (
                "SmartShop provides a **15-day hassle-free return policy** for all eligible items starting from the delivery date.\n\n"
                "• **Refund Processing:** Once approved, refunds reflect within 24-48 hours (UPI/Wallets) or 3-5 business days (Cards/Net Banking).\n"
                "• **How to return:** Go to 'My Orders' -> 'Return Item' -> Select reason and pickup slot.\n\n"
                "If you need assistance with an existing order, please share your **Order ID**."
            )

        # Check payment keywords
        if any(w in msg for w in ["pay", "payment", "card", "upi", "deducted", "transaction"]):
            return (
                "Regarding payments on SmartShop:\n\n"
                "• If your transaction failed but funds were debited, banking settlement rules automatically initiate a full reversal within 3 to 5 business days.\n"
                "• We accept all major Credit/Debit cards, UPI (GPay, PhonePe, Paytm), Net Banking, and Cash on Delivery.\n"
                "• If you require manual bank reconciliation, you can click 'Connect to Human Agent' for immediate assistance."
            )

        # Default polite fallback
        return (
            "Thank you for contacting ShopMate, SmartShop's customer support assistant. I'm here to assist you with order tracking, cancellations, returns, refunds, "
            "payment concerns, exchanges, and product information.\n\n"
            "Could you please specify your question, or choose from one of the quick options below?"
        )

    def process_message(self, user_msg: str, session: Dict[str, Any]) -> Dict[str, Any]:
        """Main conversation flow controller adhering to Steps 1-9."""
        # Initialize session state if missing
        session.setdefault("history", [])
        session.setdefault("unsuccessful_attempts", 0)
        session.setdefault("pending_order_action", None)
        session.setdefault("escalated", False)
        session.setdefault("last_order_id", None)

        msg_clean = user_msg.strip()

        # Step 0: Handle empty input
        if not msg_clean:
            return {
                "response": "Please enter a message or question so I can assist you.",
                "intent": "empty",
                "resolved_check": False,
                "can_escalate": False
            }

        # Step 2: Classify intent
        intent = self.classify_intent(msg_clean, session)
        logger.info(f"Classified intent: '{intent}' for message: '{msg_clean[:40]}...'")

        # Step 6.1: Handle Privacy Violation attempts immediately
        if intent == "privacy_violation":
            response_text = (
                "🛡️ **Data Privacy & Security Policy:**\n\n"
                "Under customer privacy and data protection compliance rules, I cannot disclose personal information, delivery addresses, "
                "phone numbers, or order histories belonging to other customers.\n\n"
                "You can securely review and manage information related strictly to your own verified SmartShop account."
            )
            return {
                "response": response_text,
                "intent": "privacy_violation",
                "resolved_check": False,
                "can_escalate": False
            }

        # Step 6.2: Handle Unrelated Queries
        if intent == "unrelated":
            response_text = (
                "I'm ShopMate, and I specialize exclusively in **SmartShop E-Commerce Support** (orders, tracking, returns, cancellations, "
                "payments, and products).\n\n"
                "I'm unable to answer off-topic questions outside our customer service domain. How may I assist you with your shopping or orders today?"
            )
            return {
                "response": response_text,
                "intent": "unrelated",
                "resolved_check": False,
                "quick_replies": ["Track my order", "Return an item", "Payment issues", "Cancel order"]
            }

        # Step 7.1: Explicit Human Agent Escalation
        if intent == "human_agent":
            escalation = self.generate_escalation_ticket(
                reason="Customer requested direct connection with human representative.",
                user_summary=msg_clean,
                priority="Normal"
            )
            session["escalated"] = True
            return {
                "response": escalation["ticket_markdown"],
                "intent": "human_agent",
                "is_escalation": True,
                "ticket": escalation["ticket_data"],
                "resolved_check": False
            }

        # Step 7.2: Customer Frustration / Dissatisfaction
        if intent == "frustration":
            session["unsuccessful_attempts"] += 1
            escalation = self.generate_escalation_ticket(
                reason="Customer expressed dissatisfaction / automated resolution unsuccessful.",
                user_summary=msg_clean,
                priority="High"
            )
            session["escalated"] = True
            response_text = (
                "I truly apologize for the frustration! I understand this issue requires personalized attention, "
                "so I have automatically transferred this conversation to our senior human support queue.\n\n"
                + escalation["ticket_markdown"]
            )
            return {
                "response": response_text,
                "intent": "frustration",
                "is_escalation": True,
                "ticket": escalation["ticket_data"],
                "resolved_check": False
            }

        # Resolution feedback response
        if intent == "resolution_yes":
            session["unsuccessful_attempts"] = 0
            session["pending_order_action"] = None
            return {
                "response": "Wonderful! We're delighted to have helped you today. Thank you for shopping with SmartShop! Have a fantastic day! 🛍️✨",
                "intent": "resolution_yes",
                "resolved_check": False,
                "quick_replies": ["Track another order", "Return policy", "Browse FAQs"]
            }
        elif intent == "resolution_no":
            session["unsuccessful_attempts"] += 1
            if session["unsuccessful_attempts"] >= 2 or session.get("escalated"):
                escalation = self.generate_escalation_ticket(
                    reason="Customer indicated issue remains unresolved after multiple attempts.",
                    user_summary="Customer issue unresolved via automated steps.",
                    priority="High"
                )
                session["escalated"] = True
                return {
                    "response": (
                        "I'm sorry that the provided solution didn't completely resolve your issue. "
                        "Let me connect you directly to our human support team right away.\n\n"
                        + escalation["ticket_markdown"]
                    ),
                    "intent": "escalated_after_unresolved",
                    "is_escalation": True,
                    "ticket": escalation["ticket_data"],
                    "resolved_check": False
                }
            else:
                return {
                    "response": (
                        "I'm sorry to hear that! Could you please give me more details about what you need assistance with, "
                        "or would you prefer me to connect you to a live human agent?"
                    ),
                    "intent": "resolution_no",
                    "resolved_check": False,
                    "can_escalate": True,
                    "quick_replies": ["Connect to Human Agent", "Talk to support", "Try different question"]
                }

        # Check for direct order ID lookup (e.g. user answered follow-up with "ORD-1001")
        extracted_id = self.extract_order_id(msg_clean)
        if intent == "order_id_lookup" or (extracted_id and session.get("pending_order_action")):
            action = session.get("pending_order_action") or "order_tracking"
            session["last_order_id"] = extracted_id
            session["pending_order_action"] = None
            result = self.handle_order_action(extracted_id, action)
            return {
                "response": result["message"],
                "intent": action,
                "order_found": result.get("order_found", False),
                "resolved_check": result.get("order_found", False),
                "quick_replies": ["Track another order", "Return policy", "Help with payment"]
            }

        # Check if message mentions an Order ID directly with an order-related intent
        if extracted_id:
            session["last_order_id"] = extracted_id
            order_action = "order_tracking"
            if intent in ["order_cancellation", "returns_refunds", "delivery_delays"]:
                order_action = intent
            result = self.handle_order_action(extracted_id, order_action)
            return {
                "response": result["message"],
                "intent": order_action,
                "order_found": result.get("order_found", False),
                "resolved_check": result.get("order_found", False),
                "quick_replies": ["View sample orders", "Track another order", "Return policy"]
            }

        # If user asks order-specific action without Order ID, ask context-aware follow-up
        if intent in ["order_tracking", "order_cancellation", "delivery_delays"]:
            session["pending_order_action"] = intent
            if intent == "order_tracking":
                resp = (
                    "I can certainly track your order! Could you please provide your **Order ID** (for example, `ORD-1001` or `ORD-1002`)?\n\n"
                    "*(You can find this in your confirmation SMS or under 'My Orders' in your account).* "
                )
            elif intent == "order_cancellation":
                resp = (
                    "I can help cancel your order if it hasn't dispatched yet. Could you please provide your **Order ID** (e.g., `ORD-1002`) "
                    "so I can check its current processing status?"
                )
            else: # delivery delays
                resp = (
                    "I'm sorry to hear your package is delayed! Please share your **Order ID** (e.g., `ORD-1005`) so I can check courier transit logs "
                    "and expedite the shipment."
                )
            return {
                "response": resp,
                "intent": intent,
                "needs_order_id": True,
                "resolved_check": False,
                "quick_replies": ["ORD-1001", "ORD-1002", "ORD-1003", "ORD-1005"]
            }

        # Step 3 & 4: Search FAQ Database
        faq_match, score = self.match_faq(msg_clean)
        if faq_match:
            logger.info(f"FAQ Match found: '{faq_match['id']}' with score {score:.2f}")
            response_text = faq_match["answer"]

            # If the FAQ requires an order ID for personalized execution, append follow-up prompt
            if faq_match.get("requires_order_id"):
                session["pending_order_action"] = faq_match["category"]
                response_text += f"\n\n👉 **Follow-Up:** {faq_match.get('action_hint', 'Please provide your Order ID (e.g. ORD-1001) to verify this for your purchase.')}"

            # If payment failure query, offer immediate human escalation option for bank disputes
            is_payment_issue = faq_match["category"] == "payment_failures"

            return {
                "response": response_text,
                "intent": faq_match["category"],
                "faq_id": faq_match["id"],
                "confidence": round(score, 2),
                "resolved_check": True,
                "can_escalate": is_payment_issue,
                "quick_replies": ["Yes, that helped!", "No, need more help", "Connect to Human Agent"]
            }

        # Step 6: FAQ does not cover the question -> Generate response via LLM (or Fallback Engine)
        logger.info(f"No direct FAQ match (best score was {score:.2f}). Forwarding to AI / Fallback generation.")
        llm_answer = self.generate_llm_response(msg_clean, session)

        final_intent = intent if intent != "general_faq" else "ai_generated"
        return {
            "response": llm_answer,
            "intent": final_intent,
            "confidence": round(score, 2),
            "resolved_check": True,
            "can_escalate": True,
            "quick_replies": ["Yes, that helped!", "No, need more help", "Connect to Human Agent"]
        }


# Global singleton instance
chatbot_instance = SmartShopChatbot()
