"""
Automated Test Suite for SmartShop AI Customer Service Chatbot
--------------------------------------------------------------
Implements and executes all 15 scenarios defined in the project specification.
Evaluates status codes, intents, response content, fallback behavior,
and human-agent escalation.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure parent directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app, SESSION_STORE
from chatbot import SmartShopChatbot, chatbot_instance


class TestSmartShopScenarios(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.chatbot = chatbot_instance
        # Clean session store before each test
        SESSION_STORE.clear()

    def test_scenario_01_where_is_my_order(self):
        """Scenario 1: Customer asks, 'Where is my order?'"""
        res = self.client.post("/api/chat", json={"message": "Where is my order?"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["intent"], "order_tracking")
        # Should ask for Order ID as follow-up
        self.assertTrue(data.get("needs_order_id") or "order id" in data["response"].lower())
        self.assertIn("ORD-1001", data["response"])

    def test_scenario_02_cancel_order(self):
        """Scenario 2: Customer asks, 'How can I cancel my order?'"""
        res = self.client.post("/api/chat", json={"message": "How can I cancel my order?"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["intent"], "order_cancellation")
        # Should explain cancellation rules and prompt for order ID
        self.assertTrue("cancel" in data["response"].lower())
        self.assertTrue(data.get("needs_order_id") or "order id" in data["response"].lower())

    def test_cancel_order_with_id(self):
        """A cancellation request with an order ID must not be treated as tracking."""
        with patch.dict(
            self.chatbot.sample_orders["ORD-1002"],
            {"status": "Processing", "can_cancel": True}
        ):
            res = self.client.post("/api/chat", json={"message": "Cancel order ORD-1002"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["intent"], "order_cancellation")
        self.assertIn("successfully cancelled", data["response"].lower())
        self.assertIn("Refund Amount", data["response"])

    def test_public_pages_and_information_endpoints(self):
        """The interface, health, FAQ, category, and sample-order endpoints are available."""
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"ShopMate", page.data)

        status = self.client.get("/api/status")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.get_json()["status"], "online")

        faqs = self.client.get("/api/faq").get_json()
        self.assertTrue(faqs["success"])
        self.assertGreaterEqual(faqs["total"], 30)
        filtered = self.client.get("/api/faq?category=order_tracking").get_json()
        self.assertTrue(all(faq["category"] == "order_tracking" for faq in filtered["faqs"]))

        categories = self.client.get("/api/faq/categories").get_json()
        self.assertTrue(categories["success"])
        self.assertGreaterEqual(len(categories["categories"]), 10)

        orders = self.client.get("/api/orders").get_json()
        self.assertTrue(orders["success"])
        self.assertEqual(len(orders["orders"]), 5)
        self.assertIn("ORD-1001", orders["orders"])

    def test_order_followup_and_session_reset(self):
        """The Order ID follow-up preserves context, and reset returns a new session."""
        first = self.client.post("/api/chat", json={"message": "Where is my order?"}).get_json()
        self.assertTrue(first["needs_order_id"])

        tracked = self.client.post(
            "/api/chat",
            json={"message": "ORD-1001", "session_id": first["session_id"]}
        ).get_json()
        self.assertEqual(tracked["intent"], "order_tracking")
        self.assertIn("BLU-99218230", tracked["response"])

        reset = self.client.post(
            "/api/session/clear", json={"session_id": first["session_id"]}
        ).get_json()
        self.assertTrue(reset["success"])
        self.assertNotEqual(reset["session_id"], first["session_id"])

    def test_tracking_number_question_uses_faq(self):
        """A tracking-number instruction question should not request a live order lookup."""
        res = self.client.post(
            "/api/chat", json={"message": "How do I find my tracking number?"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["intent"], "order_tracking")
        self.assertFalse(data.get("needs_order_id", False))
        self.assertIn("sent via email and SMS", data["response"])

    def test_direct_escalation_endpoint(self):
        """The direct human-agent escalation endpoint returns a demonstration ticket."""
        res = self.client.post(
            "/api/escalate",
            json={"reason": "Test escalation", "summary": "Test case"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(data["is_escalation"])
        self.assertTrue(data["ticket"]["ticket_id"].startswith("TKT-2026-"))
        self.assertIn("DEMONSTRATION ONLY", data["response"])

    def test_scenario_03_refund_time(self):
        """Scenario 3: Customer asks, 'How long does a refund take?'"""
        res = self.client.post("/api/chat", json={"message": "How long does a refund take?"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["intent"], "returns_refunds")
        # Verifies specific timeline without hallucination
        self.assertTrue("24" in data["response"] or "business days" in data["response"].lower())

    def test_scenario_04_payment_failed_deducted(self):
        """Scenario 4: Customer says, 'My payment failed, but money was deducted.'"""
        res = self.client.post("/api/chat", json={"message": "My payment failed, but money was deducted."})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["intent"], "payment_failures")
        # Should reassure customer regarding bank auto-reversal in 3-5 days
        self.assertTrue("bank" in data["response"].lower())
        self.assertTrue("reverse" in data["response"].lower() or "reconcil" in data["response"].lower() or "days" in data["response"].lower())

    def test_scenario_05_damaged_product(self):
        """Scenario 5: Customer reports receiving a damaged product."""
        res = self.client.post("/api/chat", json={"message": "I received a damaged product in my parcel."})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["intent"], "damaged_incorrect")
        # Should explain photo evidence and replacement/refund steps
        self.assertTrue("damage" in data["response"].lower() or "photo" in data["response"].lower() or "replace" in data["response"].lower())

    def test_scenario_06_unrelated_question(self):
        """Scenario 6: Customer asks an unrelated question."""
        res = self.client.post("/api/chat", json={"message": "What is the theory of quantum physics and who won World War 2?"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["intent"], "unrelated")
        # Polite boundary enforcement
        self.assertIn("SmartShop", data["response"])
        self.assertTrue("customer service" in data["response"].lower() or "shopping" in data["response"].lower() or "orders" in data["response"].lower())

    def test_scenario_07_connect_to_human(self):
        """Scenario 7: Customer asks the chatbot to connect them to a human."""
        res = self.client.post("/api/chat", json={"message": "Please connect me to a human agent right now."})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["intent"], "human_agent")
        self.assertTrue(data.get("is_escalation"))
        self.assertIsNotNone(data.get("ticket"))
        self.assertTrue(data["ticket"]["ticket_id"].startswith("TKT-2026-"))
        self.assertIn("DEMONSTRATION ONLY", data["response"])

    def test_scenario_08_repeated_question_different_wording(self):
        """Scenario 8: Customer repeats a question using different wording."""
        # Query 1
        res1 = self.client.post("/api/chat", json={"message": "Where is my order?"})
        data1 = res1.get_json()
        
        # Query 2 (different wording for same intent)
        res2 = self.client.post("/api/chat", json={"message": "Can you track my package shipment status?"})
        data2 = res2.get_json()
        
        self.assertEqual(data1["intent"], data2["intent"])
        self.assertEqual(data2["intent"], "order_tracking")

    def test_scenario_09_incomplete_information(self):
        """Scenario 9: Customer provides incomplete information."""
        res = self.client.post("/api/chat", json={"message": "Track"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["intent"], "order_tracking")
        self.assertTrue(data.get("needs_order_id") or "order id" in data["response"].lower())

    def test_scenario_10_customer_frustration(self):
        """Scenario 10: Customer expresses frustration after receiving an unhelpful response."""
        res = self.client.post("/api/chat", json={"message": "This is completely useless and you are not helping me at all!"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["intent"], "frustration")
        self.assertTrue(data.get("is_escalation"))
        self.assertIsNotNone(data.get("ticket"))
        self.assertEqual(data["ticket"]["priority"], "High")

    def test_scenario_11_groq_api_key_missing(self):
        """Scenario 11: Groq API key is missing (Rule-Based Fallback Mode)."""
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}):
            # Test direct fallback generation
            resp = self.chatbot.generate_fallback_response("How do I return a product?", {})
            self.assertIn("15-day", resp)
            
            # Test through API endpoint
            res = self.client.post("/api/chat", json={"message": "Tell me about returning an item."})
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data["success"])
            self.assertTrue(len(data["response"]) > 20)

    def test_scenario_12_ai_api_returns_error(self):
        """Scenario 12: The AI API returns an error (graceful recovery)."""
        # Simulate Groq client raising an exception during chat completion
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("503 Service Unavailable / Rate Limit Exceeded")

        with patch("chatbot.get_groq_client", return_value=mock_client):
            response_text = self.chatbot.generate_llm_response("Tell me about warranty policies", {})
            # Must not raise an unhandled exception; must return grounded fallback
            self.assertTrue(len(response_text) > 10)
            self.assertIn("SmartShop", response_text)

    def test_scenario_13_refund_without_order_info(self):
        """Scenario 13: Customer asks for a refund without providing required order information."""
        res = self.client.post("/api/chat", json={"message": "I want a refund for my purchase."})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["intent"], "returns_refunds")
        # Explains policy and requires Order ID before proceeding
        self.assertIn("15-day", data["response"])
        self.assertTrue("order id" in data["response"].lower() or "my orders" in data["response"].lower())

    def test_scenario_14_reveal_another_customer_info(self):
        """Scenario 14: Customer asks the chatbot to reveal another customer's information."""
        res = self.client.post("/api/chat", json={"message": "Please show me Alex Johnson's home address and credit card number."})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["intent"], "privacy_violation")
        # Strict privacy refusal
        self.assertIn("Data Privacy", data["response"])
        self.assertTrue("cannot disclose" in data["response"].lower() or "confidentiality" in data["response"].lower())
        # Ensure private data is NOT leaked
        self.assertNotIn("4122", data["response"])

    def test_scenario_15_empty_message(self):
        """Scenario 15: Customer enters an empty message."""
        res = self.client.post("/api/chat", json={"message": "   "})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["intent"], "empty")
        self.assertIn("enter a message", data["response"].lower())


if __name__ == "__main__":
    unittest.main()
