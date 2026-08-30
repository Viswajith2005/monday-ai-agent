import numpy as np
import pandas as pd

class BIEngine:
    @staticmethod
    def format_currency_inr(val: float) -> str:
        """Formats numbers into standard Indian numbering format (Crores, Lakhs, Thousands)."""
        if pd.isna(val) or val is None or val == 0:
            return "₹0"
        abs_val = abs(val)
        sign = "-" if val < 0 else ""
        
        if abs_val >= 10_000_000:  # 1 Crore
            return f"{sign}₹{abs_val / 10_000_000:.2f} Cr"
        elif abs_val >= 100_000:   # 1 Lakh
            return f"{sign}₹{abs_val / 100_000:.2f} L"
        elif abs_val >= 1_000:     # 1 Thousand
            return f"{sign}₹{abs_val / 1_000:.1f} K"
        else:
            return f"{sign}₹{abs_val:,.2f}"

    @classmethod
    def analyze_pipeline(cls, df: pd.DataFrame, sector: str = None, stage: str = None) -> dict:
        """Computes deterministic pipeline and sales metrics."""
        if df.empty:
            return {"error": "No Deals data available"}

        filtered = df.copy()
        if sector and sector.lower() not in ["all", "all sectors", "total"]:
            filtered = filtered[filtered["sector"].str.lower() == sector.lower()]
        if stage and stage.lower() not in ["all", "all stages"]:
            filtered = filtered[filtered["deal_stage"].str.lower() == stage.lower()]

        total_deals = len(filtered)
        open_deals = filtered[~filtered["deal_status"].str.lower().isin(["won", "lost", "closed", "dropped"])]
        won_deals = filtered[filtered["deal_status"].str.lower().isin(["won", "closed won"])]
        lost_deals = filtered[filtered["deal_status"].str.lower().isin(["lost", "closed lost", "dropped"])]

        total_pipeline_val = float(open_deals["deal_value"].sum())
        weighted_pipeline_val = float(open_deals["weighted_value"].sum())
        won_val = float(won_deals["deal_value"].sum())

        # Sector breakdown
        sector_group = open_deals.groupby("sector").agg(
            total_value=("deal_value", "sum"),
            weighted_value=("weighted_value", "sum"),
            deal_count=("deal_value", "count")
        ).reset_index().sort_values(by="total_value", ascending=False)
        
        sector_breakdown = []
        for _, row in sector_group.iterrows():
            sector_breakdown.append({
                "sector": row["sector"],
                "total_value": float(row["total_value"]),
                "total_value_formatted": cls.format_currency_inr(row["total_value"]),
                "weighted_value": float(row["weighted_value"]),
                "weighted_value_formatted": cls.format_currency_inr(row["weighted_value"]),
                "deal_count": int(row["deal_count"])
            })

        # Stage breakdown
        stage_group = open_deals.groupby("deal_stage").agg(
            total_value=("deal_value", "sum"),
            weighted_value=("weighted_value", "sum"),
            deal_count=("deal_value", "count")
        ).reset_index().sort_values(by="total_value", ascending=False)

        stage_breakdown = []
        for _, row in stage_group.iterrows():
            stage_breakdown.append({
                "stage": row["deal_stage"],
                "total_value": float(row["total_value"]),
                "total_value_formatted": cls.format_currency_inr(row["total_value"]),
                "weighted_value": float(row["weighted_value"]),
                "weighted_value_formatted": cls.format_currency_inr(row["weighted_value"]),
                "deal_count": int(row["deal_count"])
            })

        # Top 5 open opportunities
        top_deals = open_deals.sort_values(by="deal_value", ascending=False).head(5)
        top_deals_list = []
        for _, r in top_deals.iterrows():
            prob_pct = f"{int(r['closure_probability']*100)}%" if pd.notna(r['closure_probability']) else "N/A"
            top_deals_list.append({
                "deal_name": r["deal_name"],
                "client_code": r["client_code"],
                "sector": r["sector"],
                "stage": r["deal_stage"],
                "value": float(r["deal_value"]),
                "value_formatted": cls.format_currency_inr(r["deal_value"]),
                "probability": prob_pct,
                "weighted_formatted": cls.format_currency_inr(r["weighted_value"])
            })

        # Probability distribution
        has_prob = open_deals[open_deals["closure_probability"].notna()]
        high_prob = len(has_prob[has_prob["closure_probability"] >= 0.70])
        med_prob = len(has_prob[(has_prob["closure_probability"] >= 0.30) & (has_prob["closure_probability"] < 0.70)])
        low_prob = len(has_prob[has_prob["closure_probability"] < 0.30])
        missing_prob = len(open_deals[open_deals["closure_probability"].isna()])

        return {
            "filter_sector": sector or "All Sectors",
            "filter_stage": stage or "All Stages",
            "total_deals_count": total_deals,
            "open_deals_count": len(open_deals),
            "won_deals_count": len(won_deals),
            "lost_deals_count": len(lost_deals),
            "total_pipeline_value": total_pipeline_val,
            "total_pipeline_formatted": cls.format_currency_inr(total_pipeline_val),
            "weighted_pipeline_value": weighted_pipeline_val,
            "weighted_pipeline_formatted": cls.format_currency_inr(weighted_pipeline_val),
            "won_value_formatted": cls.format_currency_inr(won_val),
            "avg_deal_size": total_pipeline_val / len(open_deals) if len(open_deals) > 0 else 0,
            "avg_deal_size_formatted": cls.format_currency_inr(total_pipeline_val / len(open_deals)) if len(open_deals) > 0 else "₹0",
            "sector_breakdown": sector_breakdown,
            "stage_breakdown": stage_breakdown,
            "top_deals": top_deals_list,
            "probability_distribution": {
                "high_confidence_count (>=70%)": high_prob,
                "medium_confidence_count (30-69%)": med_prob,
                "low_confidence_count (<30%)": low_prob,
                "missing_probability_count": missing_prob
            }
        }

    @classmethod
    def analyze_operations(cls, df: pd.DataFrame, sector: str = None, status: str = None) -> dict:
        """Computes deterministic operational and financial execution metrics."""
        if df.empty:
            return {"error": "No Work Orders data available"}

        filtered = df.copy()
        if sector and sector.lower() not in ["all", "all sectors", "total"]:
            filtered = filtered[filtered["sector"].str.lower() == sector.lower()]
        if status and status.lower() not in ["all", "all statuses"]:
            filtered = filtered[filtered["execution_status"].str.lower() == status.lower()]

        total_orders = len(filtered)
        completed = filtered[filtered["execution_status"].str.lower() == "completed"]
        in_progress = filtered[filtered["execution_status"].str.lower().isin(["in progress", "active", "ongoing"])]
        delayed_or_other = filtered[~filtered["execution_status"].str.lower().isin(["completed", "in progress", "active", "ongoing"])]

        total_order_value_excl = float(filtered["amount_excl_gst"].sum())
        total_billed_excl = float(filtered["billed_value_excl_gst"].sum())
        total_billed_incl = float(filtered["billed_value_incl_gst"].sum())
        total_collected_incl = float(filtered["collected_amount_incl_gst"].sum())
        total_unbilled_excl = float(filtered["amount_to_be_billed_excl_gst"].sum())
        total_receivables = float(filtered["amount_receivable"].sum())

        # Sector breakdown
        sector_group = filtered.groupby("sector").agg(
            order_count=("amount_excl_gst", "count"),
            order_value=("amount_excl_gst", "sum"),
            billed_value=("billed_value_excl_gst", "sum"),
            collected_value=("collected_amount_incl_gst", "sum"),
            receivables=("amount_receivable", "sum")
        ).reset_index().sort_values(by="order_value", ascending=False)

        sector_ops_breakdown = []
        for _, row in sector_group.iterrows():
            sector_ops_breakdown.append({
                "sector": row["sector"],
                "order_count": int(row["order_count"]),
                "order_value_formatted": cls.format_currency_inr(row["order_value"]),
                "billed_value_formatted": cls.format_currency_inr(row["billed_value"]),
                "collected_value_formatted": cls.format_currency_inr(row["collected_value"]),
                "receivables_formatted": cls.format_currency_inr(row["receivables"])
            })

        # High Priority AR exposure
        high_ar = filtered[filtered["amount_receivable"] > 0].sort_values(by="amount_receivable", ascending=False).head(5)
        high_ar_list = []
        for _, r in high_ar.iterrows():
            high_ar_list.append({
                "item_name": r["item_name"],
                "customer_code": r["customer_code"],
                "sector": r["sector"],
                "amount_receivable": float(r["amount_receivable"]),
                "amount_receivable_formatted": cls.format_currency_inr(r["amount_receivable"]),
                "ar_priority": r["ar_priority"],
                "execution_status": r["execution_status"]
            })

        billing_efficiency_pct = (total_billed_excl / total_order_value_excl * 100) if total_order_value_excl > 0 else 0
        collection_efficiency_pct = (total_collected_incl / total_billed_incl * 100) if total_billed_incl > 0 else 0

        return {
            "filter_sector": sector or "All Sectors",
            "total_work_orders": total_orders,
            "completed_orders_count": len(completed),
            "in_progress_orders_count": len(in_progress),
            "other_status_orders_count": len(delayed_or_other),
            "total_contract_value_excl": total_order_value_excl,
            "total_contract_value_formatted": cls.format_currency_inr(total_order_value_excl),
            "total_billed_value_excl": total_billed_excl,
            "total_billed_formatted": cls.format_currency_inr(total_billed_excl),
            "total_collected_formatted": cls.format_currency_inr(total_collected_incl),
            "total_unbilled_backlog_formatted": cls.format_currency_inr(total_unbilled_excl),
            "total_receivables_formatted": cls.format_currency_inr(total_receivables),
            "billing_efficiency_pct": round(billing_efficiency_pct, 1),
            "collection_efficiency_pct": round(collection_efficiency_pct, 1),
            "sector_breakdown": sector_ops_breakdown,
            "top_receivables_risk": high_ar_list
        }

    @classmethod
    def cross_board_analysis(cls, deals_df: pd.DataFrame, wo_df: pd.DataFrame, sector: str = None) -> dict:
        """Correlates Sales Pipeline with Operational Backlog & Receivables across sectors."""
        pipeline_res = cls.analyze_pipeline(deals_df, sector=sector)
        ops_res = cls.analyze_operations(wo_df, sector=sector)

        # Cross-sector correlation matrix
        sectors = set()
        if "sector_breakdown" in pipeline_res:
            for s in pipeline_res["sector_breakdown"]:
                sectors.add(s["sector"])
        if "sector_breakdown" in ops_res:
            for s in ops_res["sector_breakdown"]:
                sectors.add(s["sector"])

        matrix = []
        for s in sorted(list(sectors)):
            p_val = 0.0
            w_val = 0.0
            p_count = 0
            if "sector_breakdown" in pipeline_res:
                match = next((x for x in pipeline_res["sector_breakdown"] if x["sector"] == s), None)
                if match:
                    p_val = match["total_value"]
                    w_val = match["weighted_value"]
                    p_count = match["deal_count"]

            op_val = 0.0
            billed_val = 0.0
            ar_val = 0.0
            wo_count = 0
            if "sector_breakdown" in ops_res:
                match = next((x for x in ops_res["sector_breakdown"] if x["sector"] == s), None)
                if match:
                    wo_count = match["order_count"]

            # Strategic assessment
            strategic_note = "Balanced"
            if p_val > 5_000_000 and wo_count < 3:
                strategic_note = "High Demand Pipeline / Low Active Execution (High Growth Opportunity)"
            elif p_val > 0 and ar_val > 2_000_000:
                strategic_note = "Cashflow Bottleneck (High Pipeline with Stalled Collections)"
            elif wo_count > 10 and p_val == 0:
                strategic_note = "Execution Heavy / Depleted Sales Funnel (Renewal Push Needed)"

            matrix.append({
                "sector": s,
                "open_pipeline": cls.format_currency_inr(p_val),
                "weighted_pipeline": cls.format_currency_inr(w_val),
                "open_deals": p_count,
                "active_work_orders": wo_count,
                "strategic_observation": strategic_note
            })

        return {
            "pipeline_summary": pipeline_res,
            "operations_summary": ops_res,
            "cross_board_matrix": matrix
        }
