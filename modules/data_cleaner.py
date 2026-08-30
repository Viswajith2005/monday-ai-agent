import re
import datetime
import numpy as np
import pandas as pd

class DataCleaner:
    @staticmethod
    def _clean_currency(val):
        if pd.isna(val) or val is None:
            return 0.0
        if isinstance(val, (int, float)):
            return float(val) if not np.isnan(val) else 0.0
        val_str = str(val).replace(",", "").replace("₹", "").replace("Rs.", "").replace("Rs", "").strip()
        try:
            return float(val_str)
        except Exception:
            return 0.0

    @staticmethod
    def _clean_probability(val):
        """Converts varied probability representations (0.2, '20%', '70', 80) into a 0.0 - 1.0 float."""
        if pd.isna(val) or val is None:
            return np.nan
        if isinstance(val, (int, float)):
            if np.isnan(val):
                return np.nan
            if val > 1.0:
                return float(val) / 100.0
            return float(val)
        val_str = str(val).replace("%", "").strip()
        try:
            num = float(val_str)
            if num > 1.0:
                return num / 100.0
            return num
        except Exception:
            return np.nan

    @staticmethod
    def _clean_date(val):
        if pd.isna(val) or val is None or str(val).strip().lower() in ["nan", "nat", "none", "", "null"]:
            return pd.NaT
        try:
            return pd.to_datetime(val)
        except Exception:
            return pd.NaT

    @staticmethod
    def _clean_text(val, fallback="Unspecified"):
        if pd.isna(val) or val is None or str(val).strip().lower() in ["nan", "none", "null", ""]:
            return fallback
        return str(val).strip()

    @classmethod
    def clean_deals(cls, raw_records: list) -> tuple[pd.DataFrame, dict]:
        if not raw_records:
            return pd.DataFrame(), {"status": "empty"}

        df = pd.DataFrame(raw_records)
        
        def find_col(possible_names):
            for p in possible_names:
                for c in df.columns:
                    if p.lower() in c.lower():
                        return c
            return None

        col_name = find_col(["item_name", "deal name", "name"])
        col_owner = find_col(["owner code", "owner"])
        col_client = find_col(["client code", "client", "customer"])
        col_status = find_col(["deal status", "status"])
        col_close_actual = find_col(["close date actual", "close date (a)", "actual close"])
        col_prob = find_col(["closure probability", "probability", "prob"])
        col_val = find_col(["masked deal value", "deal value", "value", "amount"])
        col_close_tent = find_col(["tentative close date", "tentative", "expected close"])
        col_stage = find_col(["deal stage", "stage"])
        col_product = find_col(["product deal", "product", "service"])
        col_sector = find_col(["sector/service", "sector"])
        col_created = find_col(["created date", "created_at", "created"])

        cleaned = pd.DataFrame()
        cleaned["item_id"] = df.get("item_id", [f"D-{i}" for i in range(len(df))])
        cleaned["deal_name"] = df[col_name].apply(lambda x: cls._clean_text(x, "Unnamed Deal")) if col_name else "Unnamed Deal"
        cleaned["owner_code"] = df[col_owner].apply(lambda x: cls._clean_text(x, "Unassigned")) if col_owner else "Unassigned"
        cleaned["client_code"] = df[col_client].apply(lambda x: cls._clean_text(x, "Unknown Client")) if col_client else "Unknown Client"
        cleaned["deal_status"] = df[col_status].apply(lambda x: cls._clean_text(x, "Open")) if col_status else "Open"
        
        cleaned["close_date_actual"] = df[col_close_actual].apply(cls._clean_date) if col_close_actual else pd.NaT
        cleaned["closure_probability"] = df[col_prob].apply(cls._clean_probability) if col_prob else np.nan
        cleaned["deal_value"] = df[col_val].apply(cls._clean_currency) if col_val else 0.0
        
        cleaned["weighted_value"] = cleaned.apply(
            lambda r: r["deal_value"] * r["closure_probability"] if pd.notna(r["closure_probability"]) and r["deal_value"] > 0 else 0.0,
            axis=1
        )
        
        cleaned["tentative_close_date"] = df[col_close_tent].apply(cls._clean_date) if col_close_tent else pd.NaT
        cleaned["deal_stage"] = df[col_stage].apply(lambda x: cls._clean_text(x, "Unknown Stage")) if col_stage else "Unknown Stage"
        cleaned["product_deal"] = df[col_product].apply(lambda x: cls._clean_text(x, "General")) if col_product else "General"
        
        raw_sector = df[col_sector].apply(lambda x: cls._clean_text(x, "Uncategorized")) if col_sector else pd.Series(["Uncategorized"] * len(df))
        sector_map = {
            "powerline": "Powerline",
            "mining": "Mining",
            "renewables": "Renewables",
            "renewable": "Renewables",
            "infra": "Infrastructure",
            "infrastructure": "Infrastructure",
            "enterprise": "Enterprise",
            "dls": "DLS",
            "geospatial": "Geospatial"
        }
        cleaned["sector"] = raw_sector.map(lambda x: sector_map.get(str(x).lower(), str(x)))
        cleaned["created_date"] = df[col_created].apply(cls._clean_date) if col_created else pd.NaT

        total_records = len(cleaned)
        missing_val_count = int((cleaned["deal_value"] == 0.0).sum())
        missing_prob_count = int(cleaned["closure_probability"].isna().sum())
        missing_close_date = int(cleaned["tentative_close_date"].isna().sum())
        open_deals = cleaned[~cleaned["deal_status"].str.lower().isin(["won", "lost", "closed", "dropped"])]
        
        quality_report = {
            "total_records": total_records,
            "open_deals_count": len(open_deals),
            "missing_value_count": missing_val_count,
            "missing_value_pct": round((missing_val_count / total_records) * 100, 1) if total_records else 0,
            "missing_probability_count": missing_prob_count,
            "missing_probability_pct": round((missing_prob_count / total_records) * 100, 1) if total_records else 0,
            "missing_tentative_close_count": missing_close_date,
            "caveats": [
                f"{missing_prob_count} deals ({round((missing_prob_count/total_records)*100, 1)}%) lack closure probabilities; weighted pipeline conservatively treats these as zero probability.",
                f"{missing_val_count} deals ({round((missing_val_count/total_records)*100, 1)}%) have null or zero masked deal value.",
                f"{missing_close_date} deals have no tentative close dates."
            ]
        }

        return cleaned, quality_report

    @classmethod
    def clean_work_orders(cls, raw_records: list) -> tuple[pd.DataFrame, dict]:
        if not raw_records:
            return pd.DataFrame(), {"status": "empty"}

        df = pd.DataFrame(raw_records)

        def find_col(possible_names):
            for p in possible_names:
                for c in df.columns:
                    if p.lower() in c.lower():
                        return c
            return None

        col_title = find_col(["item_name", "deal name", "name"])
        col_customer = find_col(["customer code", "customer name code", "client"])
        col_serial = find_col(["serial number", "serial #", "serial"])
        col_nature = find_col(["nature of work", "nature"])
        col_exec_status = find_col(["execution status", "execution"])
        col_delivery_date = find_col(["data delivery date", "delivery date"])
        col_po_date = find_col(["date of po", "po date", "date of po/loi"])
        col_sector = find_col(["sector"])
        col_type_work = find_col(["type of work", "work type"])
        col_last_inv_date = find_col(["last invoice date", "invoice date"])
        col_last_inv_no = find_col(["latest invoice no", "invoice no"])
        
        col_amt_excl = find_col(["amount in rupees (excl", "amount excl gst"])
        col_amt_incl = find_col(["amount in rupees (incl", "amount incl gst"])
        col_billed_excl = find_col(["billed value in rupees (excl", "billed value excl gst"])
        col_billed_incl = find_col(["billed value in rupees (incl", "billed value incl gst"])
        col_collected_incl = find_col(["collected amount in rupees", "collected amount incl gst", "collected"])
        col_to_bill_excl = find_col(["amount to be billed in rs. (exl", "amount to be billed excl gst", "unbilled"])
        col_receivable = find_col(["amount receivable", "receivable", "ar"])
        col_ar_priority = find_col(["ar priority", "priority"])
        col_billing_status = find_col(["billing status"])
        col_wo_status = find_col(["wo status", "status (billed)"])

        cleaned = pd.DataFrame()
        cleaned["item_id"] = df.get("item_id", [f"WO-{i}" for i in range(len(df))])
        cleaned["item_name"] = df[col_title].apply(lambda x: cls._clean_text(x, "Unnamed WO")) if col_title else "Unnamed WO"
        cleaned["customer_code"] = df[col_customer].apply(lambda x: cls._clean_text(x, "Unknown Customer")) if col_customer else "Unknown Customer"
        cleaned["serial_number"] = df[col_serial].apply(lambda x: cls._clean_text(x, "N/A")) if col_serial else "N/A"
        cleaned["nature_of_work"] = df[col_nature].apply(lambda x: cls._clean_text(x, "Standard")) if col_nature else "Standard"
        cleaned["execution_status"] = df[col_exec_status].apply(lambda x: cls._clean_text(x, "In Progress")) if col_exec_status else "In Progress"
        
        cleaned["delivery_date"] = df[col_delivery_date].apply(cls._clean_date) if col_delivery_date else pd.NaT
        cleaned["po_date"] = df[col_po_date].apply(cls._clean_date) if col_po_date else pd.NaT
        
        raw_wo_sector = df[col_sector].apply(lambda x: cls._clean_text(x, "Uncategorized")) if col_sector else pd.Series(["Uncategorized"] * len(df))
        sector_map = {
            "powerline": "Powerline",
            "mining": "Mining",
            "renewables": "Renewables",
            "renewable": "Renewables",
            "infra": "Infrastructure",
            "infrastructure": "Infrastructure",
            "enterprise": "Enterprise",
            "dls": "DLS",
            "geospatial": "Geospatial"
        }
        cleaned["sector"] = raw_wo_sector.map(lambda x: sector_map.get(str(x).lower(), str(x)))
        cleaned["type_of_work"] = df[col_type_work].apply(lambda x: cls._clean_text(x, "Standard")) if col_type_work else "Standard"
        cleaned["last_invoice_date"] = df[col_last_inv_date].apply(cls._clean_date) if col_last_inv_date else pd.NaT
        cleaned["latest_invoice_no"] = df[col_last_inv_no].apply(lambda x: cls._clean_text(x, "None")) if col_last_inv_no else "None"
        
        cleaned["amount_excl_gst"] = df[col_amt_excl].apply(cls._clean_currency) if col_amt_excl else 0.0
        cleaned["amount_incl_gst"] = df[col_amt_incl].apply(cls._clean_currency) if col_amt_incl else 0.0
        cleaned["billed_value_excl_gst"] = df[col_billed_excl].apply(cls._clean_currency) if col_billed_excl else 0.0
        cleaned["billed_value_incl_gst"] = df[col_billed_incl].apply(cls._clean_currency) if col_billed_incl else 0.0
        cleaned["collected_amount_incl_gst"] = df[col_collected_incl].apply(cls._clean_currency) if col_collected_incl else 0.0
        cleaned["amount_to_be_billed_excl_gst"] = df[col_to_bill_excl].apply(cls._clean_currency) if col_to_bill_excl else 0.0
        
        rec_direct = df[col_receivable].apply(cls._clean_currency) if col_receivable else 0.0
        cleaned["amount_receivable"] = cleaned.apply(
            lambda r: max(0.0, r["billed_value_incl_gst"] - r["collected_amount_incl_gst"]) if r["billed_value_incl_gst"] > 0 else rec_direct[r.name] if isinstance(rec_direct, pd.Series) else 0.0,
            axis=1
        )
        
        cleaned["ar_priority"] = df[col_ar_priority].apply(lambda x: cls._clean_text(x, "Normal")) if col_ar_priority else "Normal"
        cleaned["billing_status"] = df[col_billing_status].apply(lambda x: cls._clean_text(x, "Pending")) if col_billing_status else "Pending"
        cleaned["wo_status"] = df[col_wo_status].apply(lambda x: cls._clean_text(x, "Active")) if col_wo_status else "Active"

        total_wo = len(cleaned)
        completed_unbilled = len(cleaned[(cleaned["execution_status"].str.lower() == "completed") & (cleaned["billed_value_excl_gst"] == 0.0)])
        missing_invoice_date = int(cleaned["last_invoice_date"].isna().sum())
        total_receivables = float(cleaned["amount_receivable"].sum())
        
        quality_report = {
            "total_records": total_wo,
            "completed_unbilled_count": completed_unbilled,
            "missing_invoice_date_count": missing_invoice_date,
            "total_receivables": total_receivables,
            "caveats": [
                f"{completed_unbilled} work orders are marked 'Completed' in operations but have ₹0 billed value (potential revenue recognition backlog).",
                f"{missing_invoice_date} work orders ({round((missing_invoice_date/total_wo)*100, 1)}%) have no recorded last invoice date."
            ]
        }

        return cleaned, quality_report
