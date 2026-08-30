import json
import logging
import requests
import pandas as pd
from config import Config
from modules.bi_engine import BIEngine
from modules.leadership_summary import LeadershipSummaryGenerator

logger = logging.getLogger(__name__)

class SkylarkBIAgent:
    def __init__(self, gemini_api_key: str = None, groq_api_key: str = None):
        self.gemini_key = gemini_api_key or Config.GEMINI_API_KEY
        self.groq_key = groq_api_key or Config.GROQ_API_KEY

    def _call_groq(self, prompt: str, system_prompt: str = "") -> str:
        if not self.groq_key:
            return None
        
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.groq_key}",
            "Content-Type": "application/json"
        }

        models_to_try = ["openai/gpt-oss-20b", "qwen/qwen3.8-27b", "canopylabs/orpheus-v1-english"]
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        for model in models_to_try:
            try:
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": 0.2,
                    "max_tokens": 1500
                }
                resp = requests.post(url, json=payload, headers=headers, timeout=20)
                if resp.status_code == 200:
                    data = resp.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    logger.warning(f"Groq {model} returned HTTP {resp.status_code}: {resp.text}")
            except Exception as e:
                logger.warning(f"Groq request error for {model}: {e}")

        return None

    def _call_gemini(self, prompt: str, system_prompt: str = "") -> str:
        if not self.gemini_key:
            return None
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_key}"
        headers = {"Content-Type": "application/json"}
        full_text = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        try:
            payload = {
                "contents": [{
                    "parts": [{"text": full_text}]
                }]
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            logger.warning(f"Gemini REST error: {e}")

        return None

    def _call_llm(self, prompt: str, system_prompt: str = "") -> str:
        res = self._call_groq(prompt, system_prompt)
        if res:
            return res
        res = self._call_gemini(prompt, system_prompt)
        if res:
            return res
        return None

    def _search_entities(self, query: str, deals_df: pd.DataFrame, wo_df: pd.DataFrame) -> list:
        """Searches deals and work orders for any mentioned deal name, owner code, or client code."""
        results = []
        words = [w.strip("?,.!'\"") for w in query.split() if len(w) > 2]
        
        for w in words:
            # Check owner codes (e.g. OWNER_001 or 001)
            matched_deals_owner = deals_df[deals_df["owner_code"].astype(str).str.contains(w, case=False, na=False)]
            if not matched_deals_owner.empty:
                val_sum = matched_deals_owner["deal_value"].sum()
                results.append(f"- Owner '{w.upper()}': Manages {len(matched_deals_owner)} deals totaling {BIEngine.format_currency_inr(val_sum)} across {', '.join(matched_deals_owner['sector'].unique())}.")

            # Check deal names (e.g. Naruto, Faye, Pumbaa, Sakura)
            matched_deal_name = deals_df[deals_df["deal_name"].astype(str).str.contains(w, case=False, na=False)]
            if not matched_deal_name.empty:
                for _, r in matched_deal_name.head(3).iterrows():
                    results.append(f"- Deal '{r['deal_name']}': Client={r['client_code']}, Sector={r['sector']}, Stage={r['deal_stage']}, Value={BIEngine.format_currency_inr(r['deal_value'])}, Owner={r['owner_code']}.")

            # Check work orders customer code or item name
            matched_wo = wo_df[wo_df["customer_code"].astype(str).str.contains(w, case=False, na=False) | wo_df["item_name"].astype(str).str.contains(w, case=False, na=False)]
            if not matched_wo.empty:
                for _, r in matched_wo.head(3).iterrows():
                    results.append(f"- Work Order '{r['item_name']}': Customer={r['customer_code']}, Status={r['execution_status']}, Billed={BIEngine.format_currency_inr(r['billed_value_excl_gst'])}, AR={BIEngine.format_currency_inr(r['amount_receivable'])}.")

        return results[:8]

    def answer_query(self, query: str, deals_df, wo_df, deals_quality: dict, wo_quality: dict) -> dict:
        q_lower = query.lower()

        # Check if leadership update
        is_leadership = any(w in q_lower for w in ["leadership update", "leadership brief", "board update", "executive update", "board report"])
        if is_leadership:
            brief = LeadershipSummaryGenerator.generate_brief(deals_df, wo_df, deals_quality, wo_quality)
            return {
                "type": "leadership_update",
                "answer": brief["markdown_report"],
                "data": brief
            }

        # Identify mentioned sectors
        known_sectors = ["mining", "powerline", "renewables", "renewable", "infrastructure", "infra", "enterprise", "dls", "geospatial", "tender", "aviation"]
        mentioned_sectors = []
        for s in known_sectors:
            if s in q_lower:
                canonical = "Renewables" if "renewable" in s else ("Infrastructure" if "infra" in s else s.capitalize())
                if canonical not in mentioned_sectors:
                    mentioned_sectors.append(canonical)

        # High-level aggregate metrics
        overall_pipe = BIEngine.analyze_pipeline(deals_df)
        overall_ops = BIEngine.analyze_operations(wo_df)
        cross_data = BIEngine.cross_board_analysis(deals_df, wo_df).get("cross_board_matrix", [])

        # Owner rankings
        owner_counts = deals_df["owner_code"].value_counts().head(5).to_dict()
        owner_summary_str = ", ".join([f"{k} ({v} deals)" for k, v in owner_counts.items()])

        # Entity search hits
        entity_matches = self._search_entities(query, deals_df, wo_df)

        deals_count = len(deals_df)
        wo_count = len(wo_df)
        deals_id = Config.MONDAY_DEALS_BOARD_ID or "5030967681"
        wo_id = Config.MONDAY_WORK_ORDERS_BOARD_ID or "5030967761"

        telemetry_lines = [
            f"CONNECTED MONDAY.COM BOARDS:",
            f"- Total Monday.com Boards: 2 active boards connected via GraphQL API.",
            f"  1. Deals Board: 'Deal funnel Data' (ID: {deals_id}) containing {deals_count} total deal records.",
            f"  2. Work Orders Board: 'Work_Order_Tracker Data' (ID: {wo_id}) containing {wo_count} total operational work orders.",
            f"- Active Deal Owners in Data: {owner_summary_str} (All owners and clients are privacy-masked by Skylark using codes like OWNER_001-007 and COMPANY001-200).",
            "",
            f"OVERALL BUSINESS TOTALS:",
            f"- Sales Pipeline: {overall_pipe.get('total_pipeline_formatted')} across {overall_pipe.get('open_deals_count')} open deals (Weighted: {overall_pipe.get('weighted_pipeline_formatted')}, Avg deal: {overall_pipe.get('avg_deal_size_formatted')}).",
            f"- Operational Delivery: {overall_ops.get('total_work_orders')} work orders ({overall_ops.get('completed_orders_count')} Completed, {overall_ops.get('in_progress_orders_count')} In-Progress).",
            f"- Revenue & Realization: Billed: {overall_ops.get('total_billed_formatted')} (Eff: {overall_ops.get('billing_efficiency_pct')}%), Collected: {overall_ops.get('total_collected_formatted')} (Eff: {overall_ops.get('collection_efficiency_pct')}%), Outstanding AR: {overall_ops.get('total_receivables_formatted')}.",
            "",
            "SECTOR BREAKDOWN:"
        ]

        for s in cross_data[:8]:
            telemetry_lines.append(f"- {s['sector']}: Open Pipeline={s['open_pipeline']} ({s['open_deals']} deals), Active Work Orders={s['active_work_orders']}, Status={s['strategic_observation']}")

        if entity_matches:
            telemetry_lines.append("\nMATCHED SPECIFIC ENTITIES IN QUERY:")
            for em in entity_matches:
                telemetry_lines.append(em)

        if mentioned_sectors:
            telemetry_lines.append("\nSPECIFIC SECTOR DRILLDOWNS:")
            for sec in mentioned_sectors:
                p_s = BIEngine.analyze_pipeline(deals_df, sector=sec)
                o_s = BIEngine.analyze_operations(wo_df, sector=sec)
                telemetry_lines.append(f"[{sec} Sector]")
                telemetry_lines.append(f"  Pipeline: Total={p_s.get('total_pipeline_formatted')}, Weighted={p_s.get('weighted_pipeline_formatted')}, Deals={p_s.get('open_deals_count')}, Avg Deal={p_s.get('avg_deal_size_formatted')}")
                telemetry_lines.append(f"  Operations: Work Orders={o_s.get('total_work_orders')} ({o_s.get('completed_orders_count')} Completed, {o_s.get('in_progress_orders_count')} In-Progress)")
                telemetry_lines.append(f"  Financials: Billed={o_s.get('total_billed_formatted')}, Collected={o_s.get('total_collected_formatted')}, Receivables={o_s.get('total_receivables_formatted')}")

        telemetry_lines.append("\nTOP RECEIVABLES RISKS:")
        for r in overall_ops.get("top_receivables_risk", [])[:4]:
            telemetry_lines.append(f"- {r['item_name']} ({r['customer_code']}) | Sector: {r['sector']} | AR: {r['amount_receivable_formatted']} | Priority: {r['ar_priority']}")

        telemetry_lines.append("\nDATA QUALITY CAVEATS:")
        for c in deals_quality.get("caveats", [])[:2]:
            telemetry_lines.append(f"- Deals: {c}")
        for c in wo_quality.get("caveats", [])[:2]:
            telemetry_lines.append(f"- Work Orders: {c}")

        telemetry_text = "\n".join(telemetry_lines)

        system_prompt = """You are the Senior AI Business Intelligence Advisor to the Founder of Skylark Drones.
Answer the founder's EXACT question directly, strategically, and concisely using the provided real-time data from Monday.com.

CRITICAL INSTRUCTIONS:
1. If the user asks about people, owners, clients, or specific deal names (e.g. 'OWNER_001', 'Naruto', 'Sasuke', 'Faye', or an unmasked real-world name like 'R. Patel'):
   - Note that in this dataset, Skylark masked all real human names with privacy codes (e.g. OWNER_001 to OWNER_007, and COMPANY001 to COMPANY200).
   - If matched entities exist in telemetry, report their exact deals, sectors, and values.
2. If asked about Monday boards or system connection, explicitly state the 2 connected boards (Deals and Work Orders with their respective record counts and IDs).
3. Structure your response cleanly:
   - **Direct Executive Answer** (1-2 sharp sentences)
   - **Key Metrics & Specifics** (Exact figures with ₹ Cr / ₹ L)
   - **Strategic Cross-Board Insight** (Connect sales demand to operational delivery & cash realization)
   - **⚠️ Data Quality Caveats** (Relevant missing probabilities or unbilled orders)
   - **Founder Action Item** (1 clear tactical recommendation)
4. Keep it crisp, sharp, and tailored.
"""

        user_prompt = f"""Founder Question: "{query}"

Live Data Context:
{telemetry_text}

Provide the tailored executive answer."""

        ai_response = self._call_llm(user_prompt, system_prompt)

        if not ai_response:
            ai_response = self._smart_deterministic_response(query, mentioned_sectors, overall_pipe, overall_ops, deals_quality, wo_quality)

        return {
            "type": "conversational_bi",
            "answer": ai_response,
            "data": telemetry_text
        }

    def _smart_deterministic_response(self, query: str, sectors: list, pipe: dict, ops: dict, dq_deals: dict, dq_wo: dict) -> str:
        deals_id = Config.MONDAY_DEALS_BOARD_ID or "5030967681"
        wo_id = Config.MONDAY_WORK_ORDERS_BOARD_ID or "5030967761"

        if "board" in query.lower():
            out = "### 📊 Connected Monday.com Boards\n\n"
            out += "There are **2 active Monday.com boards** connected:\n"
            out += f"1. **Deal funnel Data** (Board ID: `{deals_id}`) — 346 deals (Sales Pipeline)\n"
            out += f"2. **Work_Order_Tracker Data** (Board ID: `{wo_id}`) — 176 work orders (Operations & Billing)\n"
            return out

        if sectors:
            s_name = " & ".join(sectors)
            out = f"### 📊 Business Intelligence Briefing — {s_name}\n\n"
            out += f"**Direct Answer for:** *\"{query}\"*\n\n"
        else:
            out = f"### 📊 Business Intelligence Summary\n\n"
            out += f"**Direct Answer for:** *\"{query}\"*\n\n"
            
        out += f"- **Total Sales Pipeline:** {pipe.get('total_pipeline_formatted')} across {pipe.get('open_deals_count')} active deals.\n"
        out += f"- **Billed Revenue:** {ops.get('total_billed_formatted')} (Billing Efficiency: {ops.get('billing_efficiency_pct')}%).\n"
        out += f"- **Collections & Receivables:** Collected {ops.get('total_collected_formatted')} with **{ops.get('total_receivables_formatted')}** outstanding.\n\n"

        out += "#### ⚠️ Data Quality Disclosures\n"
        for c in dq_deals.get("caveats", [])[:2]:
            out += f"- {c}\n"
        for c in dq_wo.get("caveats", [])[:2]:
            out += f"- {c}\n"

        return out
