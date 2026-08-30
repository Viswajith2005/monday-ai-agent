import datetime
from modules.bi_engine import BIEngine

class LeadershipSummaryGenerator:
    @classmethod
    def generate_brief(cls, deals_df, wo_df, deals_quality: dict = None, wo_quality: dict = None) -> dict:
        """
        Generates a comprehensive executive-ready leadership brief
        synthesizing Sales Pipeline, Operational Execution, Financial Realization, and Data Quality Caveats.
        """
        pipeline_data = BIEngine.analyze_pipeline(deals_df)
        ops_data = BIEngine.analyze_operations(wo_df)
        cross_data = BIEngine.cross_board_analysis(deals_df, wo_df)

        today_str = datetime.date.today().strftime("%B %d, %Y")

        # Top sectors by pipeline
        sectors_by_val = pipeline_data.get("sector_breakdown", [])
        top_sector_name = sectors_by_val[0]["sector"] if sectors_by_val else "N/A"
        top_sector_val = sectors_by_val[0]["total_value_formatted"] if sectors_by_val else "₹0"

        # Executive summary narrative
        headline = (
            f"As of {today_str}, Skylark Drones holds an active sales pipeline of "
            f"**{pipeline_data.get('total_pipeline_formatted')}** across **{pipeline_data.get('open_deals_count')} open deals**, "
            f"yielding a risk-adjusted weighted pipeline of **{pipeline_data.get('weighted_pipeline_formatted')}**. "
            f"Operationally, **{ops_data.get('total_work_orders')} work orders** have generated **{ops_data.get('total_billed_formatted')}** in billed revenue, "
            f"with **{ops_data.get('total_receivables_formatted')}** in outstanding receivables requiring collection focus."
        )

        # Strategic Action Items
        action_items = [
            f"**Sales Probability Calibration**: Direct the commercial team to supply closure probabilities for {deals_quality.get('missing_probability_count', 0) if deals_quality else 'unestimated'} open deals to avoid understating weighted forecasts.",
            f"**Unbilled Revenue Capture**: Audit {wo_quality.get('completed_unbilled_count', 0) if wo_quality else 'completed'} work orders that are physically completed but unbilled to accelerate revenue recognition.",
            f"**Accounts Receivable Priority**: Focus collections on top exposure accounts representing {ops_data.get('total_receivables_formatted', '₹0')} in outstanding balances.",
            f"**Sector Expansion**: Capitalize on momentum in the **{top_sector_name}** sector ({top_sector_val} pipeline) while aligning drone deployment capacity."
        ]

        markdown_report = f"""# 🚁 Skylark Drones — Executive Leadership Update
**Generated Date:** {today_str} | **Scope:** Cross-Board Business Intelligence (Deals & Operations)

---

### 📌 Executive Headline
{headline}

---

### 📊 1. Commercial & Pipeline Momentum
* **Total Pipeline Value:** {pipeline_data.get('total_pipeline_formatted')} ({pipeline_data.get('open_deals_count')} active opportunities)
* **Risk-Adjusted Weighted Pipeline:** {pipeline_data.get('weighted_pipeline_formatted')}
* **Average Deal Size:** {pipeline_data.get('avg_deal_size_formatted')}
* **Lead Sector:** **{top_sector_name}** at {top_sector_val} total value
* **High Confidence Deals (≥70% Prob):** {pipeline_data.get('probability_distribution', {}).get('high_confidence_count (>=70%)', 0)} deals

#### 🏆 Top Strategic Opportunities
"""
        for d in pipeline_data.get("top_deals", [])[:4]:
            markdown_report += f"- **{d['deal_name']}** ({d['client_code']}) | Sector: `{d['sector']}` | Stage: `{d['stage']}` | Value: **{d['value_formatted']}** (Prob: {d['probability']})\n"

        markdown_report += f"""
---

### ⚙️ 2. Operational Delivery & Fulfillment
* **Active Work Orders:** {ops_data.get('total_work_orders')} orders ({ops_data.get('completed_orders_count')} Completed, {ops_data.get('in_progress_orders_count')} In-Progress)
* **Total Contract Value (Excl GST):** {ops_data.get('total_contract_value_formatted')}
* **Billed Revenue:** {ops_data.get('total_billed_formatted')} (Billing Efficiency: **{ops_data.get('billing_efficiency_pct')}%**)
* **Unbilled Operational Backlog:** {ops_data.get('total_unbilled_backlog_formatted')}

---

### 💰 3. Financial Realization & Collections Risk
* **Total Collected Amount (Incl GST):** {ops_data.get('total_collected_formatted')} (Collection Efficiency: **{ops_data.get('collection_efficiency_pct')}%**)
* **Outstanding Receivables (AR):** {ops_data.get('total_receivables_formatted')}

#### ⚠️ High Priority Receivables Exposure
"""
        for ar in ops_data.get("top_receivables_risk", [])[:3]:
            markdown_report += f"- **{ar['item_name']}** ({ar['customer_code']}) | Sector: `{ar['sector']}` | Outstanding AR: **{ar['amount_receivable_formatted']}** | Priority: `{ar['ar_priority']}`\n"

        markdown_report += f"""
---

### ⚠️ 4. Data Quality Disclosures & Caveats
"""
        if deals_quality and deals_quality.get("caveats"):
            for c in deals_quality["caveats"]:
                markdown_report += f"- **Deals Pipeline:** {c}\n"
        if wo_quality and wo_quality.get("caveats"):
            for c in wo_quality["caveats"]:
                markdown_report += f"- **Work Orders:** {c}\n"

        markdown_report += f"""
---

### 🎯 5. Executive Action Items & Directives
"""
        for item in action_items:
            markdown_report += f"- {item}\n"

        return {
            "headline": headline,
            "pipeline_summary": pipeline_data,
            "ops_summary": ops_data,
            "action_items": action_items,
            "markdown_report": markdown_report
        }
