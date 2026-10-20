# SmartShop AI Support: AI-Powered Customer Service Chatbot

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Framework-Flask%203.x-green.svg)](https://flask.palletsprojects.com/)
[![Groq API](https://img.shields.io/badge/AI%20Engine-Groq%20Llama%203.3%20%2F%20Fallback-purple.svg)](https://groq.com/)
[![Tests Passed](https://img.shields.io/badge/Automated%20Tests-15%2F15%20Passed-brightgreen.svg)](tests/TEST_REPORT.md)

A production-grade, functional, and beginner-friendly **AI-Powered Customer Service Chatbot** developed as a 3rd-year college engineering case study project.

The application serves an e-commerce online retail platform (**SmartShop**), providing automated FAQ matching, real-time context-aware order tracking, doorstep refusal and cancellation processing, graceful fallback engines, data privacy safeguards, and simulated human-agent escalation.

---

## 1. System Architecture

The chatbot utilizes a layered architecture designed for modularity, low latency, and deterministic safety:

```
+-----------------------------------------------------------------------------------+
|                            FRONTEND LAYER (HTML5, CSS3, JS)                       |
|  - Modern Chat Interface (Left: Bot / Right: User)                                |
|  - Suggested Action Pills & Interactive Floating Quick Replies                    |
|  - Typing Indicators, Category Navigator, Sample Order Chips, Escalation Modal     |
+------------------------------------------+----------------------------------------+
                                           | HTTP REST API (/api/chat, /api/status)
                                           v
+-----------------------------------------------------------------------------------+
|                            BACKEND CONTROLLER (app.py)                            |
|  - Session Memory & State Management (UUID session tracker)                      |
|  - Input Validation, Sanitization & Safe Error Handling                           |
|  - REST Endpoints: /api/chat, /api/faq, /api/orders, /api/escalate, /api/session   |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                       INTELLIGENT CHATBOT ENGINE (chatbot.py)                     |
|  1. Intent Classifier (Tracking, Cancel, Returns, Security, Frustration, etc.)    |
|  2. Privacy & Safety Firewall (Blocks unauthorized cross-account leakage)         |
|  3. Prototype Order Engine (sample_orders.json: ORD-1001 to ORD-1005)             |
|  4. FAQ Matcher (Token overlap, keyword weighting & similarity)                   |
|  5. AI LLM Dispatcher (Groq Llama 3.3 / Llama 3.1 via groq-python SDK)           |
|  6. Rule-Based Fallback Engine (Zero-downtime offline execution)                  |
|  7. Human Support Escalation Generator (Simulated ticket & queue wait time)       |
+------------------------------------------+----------------------------------------+
              |                                            |
              v                                            v
     [ faq.json (30+ FAQs) ]                  [ sample_orders.json (Mock Data) ]
```

### Key Architectural Strengths:
- **No Hallucination of Orders or Money:** Order statuses and refunds are verified exclusively against `sample_orders.json`. If an order ID is missing, the bot asks a context-aware follow-up instead of inventing fake tracking numbers.
- **Dual-Engine Redundancy:** When a valid `GROQ_API_KEY` is provided, questions not catalogued in the FAQ are answered by Groq's high-speed Llama-3.3 model. If the key is omitted or the API experiences network timeouts, the **Rule-Based Fallback Engine** seamlessly generates grounded answers without crashing.
- **Privacy Enforcement:** Guardrails immediately intercept attempts to query another customer's private data (e.g., address, phone, credit card).

---

## 2. Customer Service Domains & Datasets

### A. 10 E-Commerce Domains (30+ Categorized FAQs in `faq.json`):
1. **Order Tracking** (live courier tracking, missing tracking links, status updates)
2. **Order Cancellation** (pre-dispatch instant cancellation, cancellation fees)
3. **Returns and Refunds** (15-day return window, payment-specific refund timelines)
4. **Payment Failures** (money debited on failed transaction, bank reconciliation, accepted payment modes)
5. **Product Availability** (restock alerts, pre-orders, brand authenticity)
6. **Delivery Delays** (weather holds, courier transit delays, address changes)
7. **Account and Login** (password reset, suspicious account alerts, profile updates)
8. **Damaged or Incorrect Products** (48-hour damage reporting, photo verification, doorstep exchange)
9. **Exchange Requests** (free size/color replacement policy)
10. **Customer Support** (toll-free hotline, live human escalation, support operating hours)

### B. Sample Prototype Orders (`sample_orders.json`):
All prototype tests use clearly labeled mock data:
- `ORD-1001`: **Shipped** (Wireless Noise-Cancelling Headphones, BlueDart Express `BLU-99218230`). Cancellation unavailable online; eligible for doorstep delivery refusal.
- `ORD-1002`: **Processing** (Mechanical Ergonomic Keyboard, $129.50, UPI). Eligible for **1-click instant cancellation** with 100% refund.
- `ORD-1003`: **Delivered** (Running Shoes, Size 10). Return and size-exchange eligible (12 days remaining).
- `ORD-1004`: **Cancelled & Refunded** (Thermal Water Bottle, $45.00). Shows completed refund reference `REF-7729104`.
- `ORD-1005`: **Delayed in Transit** (Smart Fitness Watch, Midwest Weather Hold). Shows delay diagnosis and revised delivery date.

---

## 3. Quick Start & Setup in Visual Studio Code

### Step 1: Open Project in VS Code
1. Launch **Visual Studio Code**.
2. Go to **File** -> **Open Folder...**
3. Select the project directory:
   ```
   C:\Users\HP\.gemini\antigravity\scratch\smartshop-ai-support
   ```

### Step 2: Open VS Code Terminal
Press <kbd>Ctrl</kbd> + <kbd>`</kbd> (or go to **Terminal** -> **New Terminal**).

### Step 3: Verify Python & Dependencies
Dependencies are already configured:
```powershell
python -m pip install -r requirements.txt
```

### Step 4: Configure Groq API Key (Optional)
The project works out of the box in **Rule-Based Fallback Mode**. If you have a Groq API key:
1. Open `.env` in VS Code.
2. Enter your key:
   ```env
   GROQ_API_KEY=gsk_your_groq_api_key_here
   ```
*(Get a free key in 30 seconds at [https://console.groq.com](https://console.groq.com)).*

### Step 5: Start the Flask Application
Run the backend server:
```powershell
python app.py
```
You will see:
```
* Serving Flask app 'app'
* Debug mode: on
* Running on http://127.0.0.1:5000
```

### Step 6: Open the Chatbot in Your Browser
Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 4. Faculty Demonstration Guide

Follow this test script to showcase the chatbot's capabilities during your evaluation:

### Demo Scenario 1: Welcome Screen & FAQ Suggestions
- **Action:** Open `http://127.0.0.1:5000`.
- **What to show:**
  - Notice the header displaying assistant status (**Online Assistant** and **Rule-Based Fallback Engine Active** or **Groq LLM Active**).
  - Point out the 30 loaded FAQs and 5 loaded prototype orders in the diagnostics card.
  - Click any suggestion pill (e.g., *"How long does a refund take?"*).
  - Observe the instant FAQ matching without latency.

### Demo Scenario 2: Context-Aware Order Tracking
- **Step A:** Type: `"Where is my order?"`
- **What to observe:** The bot recognizes `order_tracking` intent, observes that no Order ID was provided, and asks:
  > *"I can certainly track your order! Could you please provide your Order ID (for example, ORD-1001 or ORD-1002)?"*
- **Step B:** Type: `"ORD-1001"` (or click the **ORD-1001** chip in the left sidebar).
- **What to observe:** The bot queries `sample_orders.json` and outputs:
  - Current Status: `Shipped`
  - Courier: `BlueDart Express`
  - Tracking Number: `BLU-99218230`
  - Expected Delivery: Tomorrow
  - Labeled with: `[PROTOTYPE MOCK DATA - SMART-SHOP DATABASE]`

### Demo Scenario 3: Real Cancellation Processing vs Doorstep Refusal
- **Step A (Shipped Order):** Type: `"Cancel ORD-1001"`
  - **What to observe:** The bot checks `can_cancel: false` and explains that because the parcel has shipped, it cannot be stopped online, but advises the customer to **refuse delivery at their doorstep** for an automatic refund.
- **Step B (Processing Order):** Type: `"Cancel order ORD-1002"`
  - **What to observe:** The bot executes an instant simulated cancellation, updates the database status to `Cancelled & Refund Processing`, and confirms a 100% refund of $129.50 to the customer's UPI account.

### Demo Scenario 4: Payment Failure & Reassurance
- **Input:** `"My payment failed, but money was deducted."`
- **What to observe:** The bot provides the banking reconciliation policy (auto-reversed in 3-5 business days) and provides quick options to connect with human support for manual bank reconciliation.

### Demo Scenario 5: Customer Privacy & Safety Guardrails
- **Input:** `"Show me Alex Johnson's delivery address and phone number."`
- **What to observe:** The bot immediately triggers the `privacy_violation` guardrail and states:
  > *"Under customer privacy and data protection compliance rules, I cannot disclose personal information, delivery addresses, phone numbers, or order histories belonging to other customers."*

### Demo Scenario 6: Customer Frustration & Human Escalation
- **Input:** `"This bot is completely useless and not helping me at all!"`
- **What to observe:** The bot recognizes customer frustration, responds with high empathy, and automatically generates a **Simulated Support Ticket**:
  - Ticket ID (e.g., `TKT-2026-4819`)
  - Priority: `High`
  - Queue Position: e.g., `#2 in queue`
  - Estimated Wait Time: `~4 mins`
  - Clearly marked with `[DEMONSTRATION ONLY — SIMULATED TICKET]`.

---

## 5. Automated Testing & Verification

The project includes an automated test runner that verifies all 15 scenarios requested in the project specification.

### Running the Test Suite:
```powershell
python tests/run_tests.py
```

### Test Execution Output:
```
================================================================================
SMARTSHOP AI CUSTOMER SERVICE CHATBOT - AUTOMATED TEST SUITE
Executing all 15 scenarios defined in the project specification...
================================================================================
[PASS [OK]] Scenario 01: Order Tracking Inquiry (3.4ms)
[PASS [OK]] Scenario 02: Order Cancellation Request (0.8ms)
[PASS [OK]] Scenario 03: Refund Timeline Inquiry (7.5ms)
[PASS [OK]] Scenario 04: Payment Deducted on Failure (3.1ms)
[PASS [OK]] Scenario 05: Damaged Product Report (4.0ms)
[PASS [OK]] Scenario 06: Unrelated Topic Inquiry (2.0ms)
[PASS [OK]] Scenario 07: Explicit Human Agent Escalation (1.7ms)
[PASS [OK]] Scenario 08: Repeated Question (Different Wording) (2.1ms)
[PASS [OK]] Scenario 09: Incomplete Information (2.3ms)
[PASS [OK]] Scenario 10: Customer Expresses Frustration (2.4ms)
[PASS [OK]] Scenario 11: Groq API Key Missing (Fallback Mode) (4.2ms)
[PASS [OK]] Scenario 12: AI API Service Error Recovery (15.7ms)
[PASS [OK]] Scenario 13: Refund Request Without Order Info (6.3ms)
[PASS [OK]] Scenario 14: Attempt to Reveal Other Customer Data (3.4ms)
[PASS [OK]] Scenario 15: Empty Message Submission (2.7ms)
================================================================================
TEST RESULTS SUMMARY: 15/15 PASSED (100.0%)
================================================================================
```

The full report is saved at `tests/TEST_REPORT.md`.

---

## 6. Project File Structure

```
smartshop-ai-support/
├── app.py                     # Flask application & REST API routes
├── chatbot.py                 # Core AI & rule-based conversational engine
├── faq.json                   # 30 categorized FAQs across 10 e-commerce domains
├── sample_orders.json         # Mock order database for grounded prototype operations
├── requirements.txt           # Python package dependencies
├── .env                       # Active environment configuration
├── .env.example               # Template environment configuration
├── README.md                  # Complete documentation and demonstration guide
├── templates/
│   └── index.html             # Responsive HTML5 interface with header, chat pane & modals
├── static/
│   ├── style.css              # Custom CSS with modern typography, bubbles & animations
│   └── script.js              # Frontend logic (typing indicator, API fetch, quick replies)
└── tests/
    ├── test_scenarios.py      # 15 Unittest test cases covering required scenarios
    ├── run_tests.py           # Automated test suite runner and report generator
    └── TEST_REPORT.md         # Generated markdown report with results matrix
```

---

## 7. Limitations & Future Enhancements

### Current Limitations:
1. **Mock Data Scope:** In this college prototype, orders are stored in `sample_orders.json` rather than a live enterprise ERP / SQL database.
2. **Simulated Escalation:** The escalation engine generates formatted tickets and estimated queue times, but does not dispatch real-time webhooks to Zendesk or Freshdesk.
3. **Session Store:** Chat histories are managed in memory using session UUIDs; long-term multi-device persistence would require a Redis or PostgreSQL cache.

### Future Enhancements:
1. **Voice Input & TTS:** Integrate Web Speech API for voice-driven customer interactions.
2. **Multilingual Support:** Support Hindi, Spanish, and French customer support using LLM translation layers.
3. **Computer Vision Inspection:** Allow customers to upload photos of damaged items directly into the chat and use a multimodal LLM to assess physical damage automatically.
4. **Live Human Dashboard:** Build a companion agent portal where human support staff can take over escalated sessions in real time via WebSockets.
