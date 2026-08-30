# 📋 Skylark Drones — AI Business Intelligence Agent
## Architectural Decision Log & Strategic Rationale

**Author:** T Viswajith Gupta  
**Project:** Monday.com AI Business Intelligence Agent  
**Assignment:** Skylark Drones Technical Evaluation  
**Target Audience:** Skylark Executive Leadership & Technical Review Panel  
**Date:** August 2026  

---

## 1. Executive Problem Framing
Skylark Drones operates in a fast-paced aerial surveying and drone analytics market across verticals including Mining, Powerlines, Renewables, and Infrastructure. Founders and executives require immediate, mathematically sound answers across distinct Monday.com boards without waiting for manual spreadsheet collation.

This system was engineered as a **conversational AI Business Intelligence Agent** integrated directly with live **monday.com** boards via GraphQL API, paired with a deterministic data resilience layer, cross-board telemetry correlation, and an executive leadership briefing generator.

---

## 2. Key Assumptions Made & Methodological Rationale

1. **Masked Financial Valuations & Currency Normalization:**
   * *Assumption:* The masked numerical values in the Deals and Work Orders datasets represent Indian Rupee (INR ₹) base denominations.
   * *Implementation:* Values are deterministically parsed, validated, and formatted using Indian numbering conventions (Crores ₹ Cr, Lakhs ₹ L, Thousands ₹ K) to maintain native executive readability.

2. **Conservative Weighted Pipeline (Handling 100% Missing Probabilities):**
   * *Assumption:* In the real-world Deals dataset, 100% of open deals lack closure probability estimates. Arbitrarily assuming an ungrounded 50% or 100% win rate would artificially inflate forecasts and mislead leadership capital allocation.
   * *Implementation:* The BI engine adopts a conservative risk policy: unestimated deals are treated as 0% weighted contribution in pipeline projections, while an explicit **Data Quality Caveat** is attached to every relevant response explaining the data gap and quantifying the total unweighted opportunity pool (₹221.05 Cr across 181 open deals).

3. **Canonical Cross-Board Sector Mapping:**
   * *Assumption:* Variations in sector naming across boards (e.g. `mining`, `Mining`, `renewables`, `Renewables`, `infra`, `Infrastructure`) represent identical operational business units.
   * *Implementation:* Standardized through a canonical dictionary mapper to enable accurate cross-board slicing.

4. **Accounts Receivable & Cashflow Realization:**
   * *Assumption:* Accounts Receivable (AR) represents billed revenue inclusive of GST minus recorded collections. Where recorded collections match or exceed billing, AR is bounded at ₹0 to prevent negative asset reporting.

---

## 3. Architectural Trade-Offs Chosen & Justification

| Architectural Decision | Chosen Approach | Alternative Evaluated | Strategic Justification |
| :--- | :--- | :--- | :--- |
| **Integration Architecture** | **Official Monday GraphQL API (v2024-01)** | Monday Model Context Protocol (MCP) | Direct GraphQL API provides fine-grained control over cursor pagination, error backoffs on HTTP 429, and eliminates external binary/socket dependencies, ensuring 1-click cloud deployment. |
| **Calculation Engine** | **Deterministic Python / Pandas BI Engine** | End-to-End LLM Prompt Arithmetic | LLMs suffer from floating-point errors and hallucinations when calculating multi-column aggregations. Mathematical logic was decoupled entirely to Pandas, guaranteeing 100% arithmetic fidelity. |
| **User Interface** | **Streamlit with Custom Obsidian Theme & Floating Chat** | Custom React SPA + FastAPI | Streamlit allowed complete full-stack delivery with responsive streaming chat, Plotly graphs, and markdown export within the 6-hour evaluation timebox without infrastructure bloat. |
| **LLM Resilience** | **Zero-Dependency Pure HTTP Client with Multi-Tier Fallback** | Hardcoded Single Model SDK | Built directly on standard HTTPS requests (`api.groq.com`), removing local SDK version conflicts and providing instant fallback from Groq (Llama-3/Qwen) to Gemini to deterministic templates. |

---

## 4. Interpretation & Implementation of "Leadership Updates" (Optional Requirement)

Rather than treating a leadership update as a simple dump of high-level totals, we designed an **Action-Oriented Executive Synthesis Hub** adhering to C-suite reporting standards:

1. **Executive Headline Pulse Check:** 2-sentence executive summary stating active pipeline (₹221.05 Cr), billed revenue (₹10.74 Cr), and uncollected debt (₹3.63 Cr).
2. **Commercial & Pipeline Momentum:** Highlights lead sectors (*Powerline* at ₹80.59 Cr, *Mining* at ₹43.84 Cr) and lists top strategic opportunities.
3. **Operational Delivery & Backlog:** Tracks fulfillment efficiency (50.7% billing rate) and alerts leadership to **23 completed work orders with ₹0 billed** (revenue recognition leakage).
4. **Financial Realization & Receivables Risk:** Evaluates collection efficiency (71.4%) and names top credit exposure accounts (*Faye Valentine* at ₹1.03 Cr, *Pumbaa* at ₹56.67 L).
5. **Data Quality & Governance Disclosures:** Discloses uncalibrated deals and missing invoice dates to maintain governance transparency.
6. **Prioritized Strategic Directives:** 4 tactical next steps for commercial, operational, and financial leads with downloadable Markdown export.

---

## 5. What We Would Implement with Additional Time

1. **Bidirectional Monday.com Mutation Actions (Write-Back):**
   * Allow executives to issue directives directly from chat (e.g. *"Flag Work Order SDPLDEAL-075 as High Priority AR in Monday"*).
2. **Real-Time Webhook Synchronization:**
   * Replace TTL polling with inbound Monday.com webhooks to invalidate in-memory caches instantly when cell edits occur.
3. **Predictive Project Delay Modeling:**
   * Train a lightweight scikit-learn model on historical PO dates, delivery dates, and drone telemetry to proactively forecast operational slippage.
4. **Automated WhatsApp / Slack Executive Digest:**
   * Schedule automated weekly briefings delivered directly to founders' messaging channels.
