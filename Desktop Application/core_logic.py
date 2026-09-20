import os
import re
from datetime import datetime
from difflib import SequenceMatcher
from itertools import groupby
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from mappings import (
    DEFAULT_VALUES,
    DEPARTMENT_MAPPING,
    EXTRACTION_PATTERNS,
)

# Precompiled regexes
REF_PATTERN = re.compile(EXTRACTION_PATTERNS["Communication No."], re.IGNORECASE)
DATE_PATTERN = re.compile(EXTRACTION_PATTERNS["Communication Date"], re.IGNORECASE)
SNO_PATTERN = re.compile(EXTRACTION_PATTERNS["Representation No."], re.IGNORECASE)


def clean_cell_value(val) -> str:
    """Sanitizes cell inputs and converts timestamps/floats to clean string representation."""
    if val is None or pd.isna(val):
        return ""
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.strftime("%d %B %Y")
    if isinstance(val, float):
        if val.is_integer():
            return str(int(val))
        return str(val).strip()
    return str(val).strip()


def normalize_string(val: str) -> str:
    """Normalizes string for fuzzy/case-insensitive matching."""
    if not val:
        return ""
    s = re.sub(r"[^a-zA-Z0-9\s]", " ", str(val).lower())
    return re.sub(r"\s+", " ", s).strip()


def format_to_full_date(val) -> str:
    """Normalizes incoming dates to standard 'DD MMMM YYYY' format."""
    if not val:
        return ""
    date_str = str(val).strip()
    if not date_str:
        return ""

    if isinstance(val, (datetime, pd.Timestamp)):
        return val.strftime("%d %B %Y")

    normalized = re.sub(r"[\./]", "-", date_str)
    formats = (
        "%d-%m-%Y",
        "%d-%m-%y",
        "%Y-%m-%d",
        "%m-%d-%Y",
    )
    for fmt in formats:
        try:
            dt = datetime.strptime(normalized, fmt)
            return dt.strftime("%d %B %Y")
        except ValueError:
            pass

    match = re.search(r"([0-3]?[0-9]-[0-1]?[0-9]-(?:19|20)\d{2})", normalized)
    if match:
        try:
            dt = datetime.strptime(match.group(1), "%d-%m-%Y")
            return dt.strftime("%d %B %Y")
        except ValueError:
            pass

    return date_str


def to_roman(n: int) -> str:
    """Converts an integer to lowercase Roman numerals (1 -> i, 2 -> ii, 3 -> iii, etc.)."""
    val_map = [
        (1000, "m"), (900, "cm"), (500, "d"), (400, "cd"),
        (100, "c"), (90, "xc"), (50, "l"), (40, "xl"),
        (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")
    ]
    res = []
    for val, roman in val_map:
        while n >= val:
            res.append(roman)
            n -= val
    return "".join(res)


def format_concerned_departments(dept_list: list) -> str:
    """
    Formats the Concerned Department(s) column:
    - Single entry: "{Department} vide E-Office Receipt Number {ReceiptNo}"
    - Multiple entries: Roman numeral-numbered, each on a new line:
      (i) {Department1} vide E-Office Receipt Number {ReceiptNo1}
      (ii) {Department2} vide E-Office Receipt Number {ReceiptNo2}
    """
    seen = set()
    unique_depts = []
    for d in dept_list:
        d_name = (d.get("dept_name") or d.get("concerned_department") or "").strip()
        r_no = (d.get("receipt_no") or d.get("eoffice_receipt_number") or "").strip()
        if not d_name and not r_no:
            continue
        pair = (d_name, r_no)
        if pair not in seen:
            seen.add(pair)
            unique_depts.append((d_name, r_no))

    if not unique_depts:
        return ""

    if len(unique_depts) == 1:
        d_name, r_no = unique_depts[0]
        if d_name and r_no:
            return f"{d_name} vide E-Office Receipt Number {r_no}"
        elif d_name:
            return d_name
        else:
            return f"vide E-Office Receipt Number {r_no}"

    lines = []
    for idx, (d_name, r_no) in enumerate(unique_depts, 1):
        numeral = to_roman(idx)
        if d_name and r_no:
            lines.append(f"({numeral}) {d_name} vide E-Office Receipt Number {r_no}")
        elif d_name:
            lines.append(f"({numeral}) {d_name}")
        else:
            lines.append(f"({numeral}) vide E-Office Receipt Number {r_no}")
    return "\n".join(lines)


def extract_subject_details(subject_text: str) -> Tuple[str, str, str, List[str]]:
    """Extracts Communication Number, Date, and Representation No. from subject."""
    if not isinstance(subject_text, str) or not subject_text.strip():
        return "", "", "", ["Subject is blank or missing"]

    text = " ".join(subject_text.split())
    warnings = []

    comm_no = ""
    ref_match = REF_PATTERN.search(text)
    if ref_match:
        comm_no = ref_match.group(1).strip(" .:,;-_")
    else:
        warnings.append("Communication Number")

    comm_date = ""
    date_match = DATE_PATTERN.search(text)
    if date_match:
        raw_date = date_match.group(1)
        comm_date = format_to_full_date(raw_date)

    s_no = ""
    sno_match = SNO_PATTERN.search(text)
    if sno_match:
        s_no = sno_match.group(1).strip(" .:,;-_()")
    else:
        warnings.append("Representation Serial Number")

    return comm_no, comm_date, s_no, warnings


class DepartmentResolver:
    """Resolves department names using SQLite master departments table, dictionary mappings, aliases, and fuzzy similarity."""

    def __init__(self, ref_csv_path: Optional[Path] = None, db_path: Optional[str] = None):
        self.ref_csv_path = ref_csv_path
        self.db_path = db_path
        self.alias_map: Dict[str, Tuple[str, str]] = {}
        self.dept_records: List[Dict[str, str]] = []
        self.refresh(db_path=db_path)

    def refresh(self, db_path: Optional[str] = None):
        """Reloads department records and aliases, prioritizing SQLite master departments table."""
        if db_path:
            self.db_path = db_path

        self.alias_map = {}
        self.dept_records = []

        # 1. Built-in common fallback aliases
        built_in_aliases = {
            "jkhod": ("Head of Department", "HOD"),
            "jkdcof": ("Deputy Commissioner", "DC"),
            "deputy commissioner": ("Deputy Commissioner", "DC"),
            "pwd": ("Public Works (R&B) Department", "PWD"),
            "r&b": ("Public Works (R&B) Department", "PWD"),
            "revenue": ("Revenue Department", "REV"),
        }
        for k, v in built_in_aliases.items():
            self.alias_map[k] = v

        for raw_k, meta in DEPARTMENT_MAPPING.items():
            norm_k = normalize_string(raw_k)
            if norm_k not in self.alias_map:
                self.alias_map[norm_k] = (meta["name"], meta["abbr"])

        # 2. Load from reference CSV if provided
        if self.ref_csv_path and self.ref_csv_path.exists():
            try:
                df_ref = pd.read_csv(self.ref_csv_path, dtype=str)
                for _, r in df_ref.iterrows():
                    name = str(r.get("Department Name", "")).strip()
                    abbr = str(r.get("Department Abbreviation", "")).strip()
                    if name or abbr:
                        self.dept_records.append({
                            "name": name,
                            "abbr": abbr,
                            "norm_name": normalize_string(name),
                            "norm_abbr": normalize_string(abbr),
                        })
                        if name:
                            self.alias_map[normalize_string(name)] = (name, abbr)
                        if abbr:
                            self.alias_map[normalize_string(abbr)] = (name, abbr)
            except Exception as e:
                print(f"Warning: Failed to load reference CSV ({e})")

        # 3. Master Departments from SQLite database (highest priority)
        if self.db_path and Path(self.db_path).exists():
            try:
                import database
                master_depts = database.get_departments(self.db_path)
                for d in master_depts:
                    name = (d.get("department_name") or "").strip()
                    abbr = (d.get("department_abbreviation") or "").strip()
                    if name or abbr:
                        self.dept_records.append({
                            "name": name,
                            "abbr": abbr,
                            "norm_name": normalize_string(name),
                            "norm_abbr": normalize_string(abbr),
                        })
                        if name:
                            self.alias_map[normalize_string(name)] = (name, abbr)
                        if abbr:
                            self.alias_map[normalize_string(abbr)] = (name, abbr)
            except Exception as e:
                print(f"Warning: Failed to load master departments from database ({e})")

    def resolve(self, raw_input: Any) -> Tuple[str, str]:
        if raw_input is None or pd.isna(raw_input):
            return "", ""

        raw_clean = str(raw_input).strip()
        norm_in = normalize_string(raw_clean)

        if not norm_in:
            return "", ""

        if norm_in in self.alias_map:
            return self.alias_map[norm_in]

        # Check in records
        for item in self.dept_records:
            if norm_in == item["norm_name"] or norm_in == item["norm_abbr"]:
                return item["name"], item["abbr"]

        # Word-level overlap heuristics
        tokens_in = set(norm_in.split())
        best_match = None
        highest_score = 0.0

        for item in self.dept_records:
            norm_dept = item["norm_name"]
            dept_tokens = set(norm_dept.split())
            intersection = tokens_in & dept_tokens
            overlap_score = len(intersection) / max(len(tokens_in | dept_tokens), 1)

            seq_ratio = SequenceMatcher(None, norm_in, norm_dept).ratio()
            combined_score = (overlap_score * 0.4) + (seq_ratio * 0.6)

            if combined_score > highest_score:
                highest_score = combined_score
                best_match = item

        if best_match and highest_score >= 0.70:
            return best_match["name"], best_match["abbr"]

        # Fallback: keep original text
        return raw_clean, ""


def natural_sort_key(s: Any) -> List[Any]:
    """Splits string into integers and text segments for natural sorting (e.g. 2 before 10)."""
    if s is None:
        return []
    s = str(s).strip()
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", s)]


def find_column(columns: List[Any], aliases: List[str]) -> Optional[str]:
    """Finds matching column name from aliases."""
    clean_cols = {re.sub(r"[^a-zA-Z0-9]", "", str(c).lower()): c for c in columns}
    for alias in aliases:
        norm_alias = re.sub(r"[^a-zA-Z0-9]", "", alias.lower())
        if norm_alias in clean_cols:
            return clean_cols[norm_alias]
    return None


def load_input_file(file_path: Path) -> pd.DataFrame:
    """Reads input files supporting Excel (.xlsx, .xls) and CSV (.csv) with fallback encodings."""
    ext = file_path.suffix.lower()
    if ext == ".xlsx":
        return pd.read_excel(file_path, dtype=object, engine="openpyxl")
    elif ext == ".xls":
        return pd.read_excel(file_path, dtype=object, engine="xlrd")
    elif ext == ".csv":
        for encoding in ("utf-8", "utf-8-sig", "latin1", "cp1252"):
            try:
                return pd.read_csv(file_path, dtype=object, encoding=encoding)
            except UnicodeDecodeError:
                continue
        return pd.read_csv(file_path, dtype=object)
    else:
        raise ValueError(f"Unsupported file extension: {ext}")


def process_raw_dataframe(
    df: pd.DataFrame,
    resolver: DepartmentResolver,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    """
    Parses a raw DataFrame into normalized representations and department rows,
    applying sequence gap detection and duplicate consolidation.
    """
    alias_comp = ["comp. no.", "comp no", "compno", "computer no", "computer number", "grievance id", "grievance id / computer number"]
    alias_receipt = ["receipt no.", "receipt no", "receiptno", "receipt.no.", "receipt number", "e-office receipt number"]
    alias_subject = ["subject", "sub", "subject details", "representation subject"]
    alias_dept = ["department", "dept", "dept.", "department name", "addressed to", "addressed to (dept.)"]
    alias_sender = ["sender", "applicant name", "applicant"]
    alias_sent_on = ["sent on", "sent_on", "sent date", "dispatch date"]
    alias_letter_ref = ["letter ref. no.", "letter ref no", "letter no", "letter number"]
    alias_letter_date = ["letter date"]
    alias_location = ["location", "place", "district"]
    alias_status = ["status", "atr status", "overall atr status"]
    alias_atr_no = ["atr number", "atr no", "atr no."]
    alias_atr_date = ["atr date"]
    alias_atr_comp = ["atr computer number", "atr comp no", "atr comp. no."]

    col_comp = find_column(df.columns, alias_comp)
    col_receipt = find_column(df.columns, alias_receipt)
    col_subject = find_column(df.columns, alias_subject)
    col_dept = find_column(df.columns, alias_dept)
    col_sender = find_column(df.columns, alias_sender)
    col_sent_on = find_column(df.columns, alias_sent_on)
    col_letter_ref = find_column(df.columns, alias_letter_ref)
    col_letter_date = find_column(df.columns, alias_letter_date)
    col_location = find_column(df.columns, alias_location)
    col_status = find_column(df.columns, alias_status)
    col_atr_no = find_column(df.columns, alias_atr_no)
    col_atr_date = find_column(df.columns, alias_atr_date)
    col_atr_comp = find_column(df.columns, alias_atr_comp)

    errors = []
    if not (col_comp and col_receipt and col_subject and col_dept):
        missing = []
        if not col_comp: missing.append("Computer/Grievance ID")
        if not col_receipt: missing.append("Receipt No")
        if not col_subject: missing.append("Subject")
        if not col_dept: missing.append("Department")
        errors.append(f"Missing required columns in dataset: {', '.join(missing)}")
        return [], [], errors

    raw_records = []
    for _, row in df.iterrows():
        grievance_id = clean_cell_value(row[col_comp])
        eoffice_receipt_no = clean_cell_value(row[col_receipt])
        raw_dept = clean_cell_value(row[col_dept])
        raw_subject = clean_cell_value(row[col_subject])
        sender_name = clean_cell_value(row[col_sender]) if col_sender else ""
        sent_on_val = format_to_full_date(clean_cell_value(row[col_sent_on])) if col_sent_on else ""
        letter_ref = clean_cell_value(row[col_letter_ref]) if col_letter_ref else ""
        letter_date = format_to_full_date(clean_cell_value(row[col_letter_date])) if col_letter_date else ""
        location_val = clean_cell_value(row[col_location]) if col_location else ""
        status_val = clean_cell_value(row[col_status]) if col_status else ""
        atr_no_val = clean_cell_value(row[col_atr_no]) if col_atr_no else ""
        atr_date_val = format_to_full_date(clean_cell_value(row[col_atr_date])) if col_atr_date else ""
        atr_comp_val = clean_cell_value(row[col_atr_comp]) if col_atr_comp else ""

        dept_name, dept_abbr = resolver.resolve(raw_dept)
        comm_no, comm_date, s_no, _ = extract_subject_details(raw_subject)

        raw_records.append({
            "grievance_id": grievance_id,
            "eoffice_receipt_no": eoffice_receipt_no,
            "comm_no": comm_no,
            "comm_date": comm_date,
            "s_no": s_no,
            "applicant": sender_name,
            "sent_on": sent_on_val,
            "subject": raw_subject,
            "dept_name": dept_name or raw_dept,
            "dept_abbr": dept_abbr,
            "letter_no": letter_ref,
            "letter_date": letter_date,
            "location": location_val,
            "raw_status": status_val,
            "atr_number": atr_no_val,
            "atr_date": atr_date_val,
            "atr_comp_no": atr_comp_val,
        })

    consolidated_groups = {}
    for r in raw_records:
        group_key = (
            r["grievance_id"].strip().lower(),
            r["comm_no"].strip().lower(),
            r["s_no"].strip().lower(),
            r["subject"].strip().lower(),
        )

        if group_key not in consolidated_groups:
            consolidated_groups[group_key] = {
                "grievance_id": r["grievance_id"],
                "comm_no": r["comm_no"],
                "comm_date": r["comm_date"],
                "s_no": r["s_no"],
                "applicant": r["applicant"],
                "sent_on": r["sent_on"],
                "subject": r["subject"],
                "letter_no": r["letter_no"],
                "letter_date": r["letter_date"],
                "status_list": [],
                "departments": [],
            }

        group = consolidated_groups[group_key]
        if not group["applicant"] and r["applicant"]:
            group["applicant"] = r["applicant"]
        if not group["sent_on"] and r["sent_on"]:
            group["sent_on"] = r["sent_on"]
        if not group["letter_no"] and r["letter_no"]:
            group["letter_no"] = r["letter_no"]
        if not group["letter_date"] and r["letter_date"]:
            group["letter_date"] = r["letter_date"]

        if r["raw_status"] and r["raw_status"] not in group["status_list"]:
            group["status_list"].append(r["raw_status"])

        dept_item = {
            "grievance_id": r["grievance_id"],
            "receipt_no": r["eoffice_receipt_no"],
            "dept_name": r["dept_name"],
            "dept_abbr": r["dept_abbr"],
            "location": r["location"],
            "atr_number": r["atr_number"],
            "atr_date": r["atr_date"],
            "atr_comp_no": r["atr_comp_no"],
        }
        if dept_item not in group["departments"]:
            group["departments"].append(dept_item)

    grouped_items = list(consolidated_groups.values())
    grouped_items.sort(key=lambda g: (natural_sort_key(g["comm_no"]), natural_sort_key(g["s_no"])))

    final_grouped_items = []
    for comm_no_val, items_iter in groupby(grouped_items, key=lambda x: x["comm_no"]):
        items = list(items_iter)
        comm_date_val = next((it["comm_date"] for it in items if it["comm_date"]), "")

        existing_nums = set()
        for it in items:
            s_val = str(it["s_no"]).strip()
            if s_val.isdigit():
                existing_nums.add(int(s_val))

        for g in items:
            final_grouped_items.append((g, False))

        if existing_nums:
            min_num = 1
            max_num = max(existing_nums)
            missing_nums = set(range(min_num, max_num + 1)) - existing_nums

            for missing in missing_nums:
                blank_group = {
                    "grievance_id": "",
                    "comm_no": comm_no_val,
                    "comm_date": comm_date_val,
                    "s_no": str(missing),
                    "applicant": "",
                    "sent_on": "",
                    "subject": "",
                    "letter_no": "",
                    "letter_date": "",
                    "status_list": [],
                    "departments": [],
                    "remarks": DEFAULT_VALUES.get("Missing Row Remarks", "Missing representation number"),
                }
                final_grouped_items.append((blank_group, True))

    final_grouped_items.sort(key=lambda x: (natural_sort_key(x[0]["comm_no"]), natural_sort_key(x[0]["s_no"])))

    processed_reps = []
    processed_depts = []

    for item, is_blank_gap in final_grouped_items:
        if is_blank_gap:
            rep_row = {
                "communication_number": item["comm_no"],
                "communication_date": item["comm_date"],
                "representation_serial_number": item["s_no"],
                "applicant_name": "",
                "subject": "",
                "applicant_name_on_portal": "",
                "representation_subject_on_portal": "",
                "issue_type": "",
                "remarks": item.get("remarks", ""),
                "processing_channel": "",
                "concerned_departments": "",
                "grievance_id_computer_number": "",
                "sent_on": "",
                "letter_number": "",
                "letter_date": "",
                "overall_atr_status": "",
                "departments": [],
            }
            processed_reps.append(rep_row)
            continue

        dept_list = item["departments"]
        issue_type = "Multiple" if len(dept_list) > 1 else "Single"
        concerned_depts_val = format_concerned_departments(dept_list)

        rep_row = {
            "communication_number": item["comm_no"],
            "communication_date": item["comm_date"],
            "representation_serial_number": item["s_no"],
            "applicant_name": "",
            "subject": "",
            "applicant_name_on_portal": item["applicant"],
            "representation_subject_on_portal": item["subject"],
            "issue_type": issue_type,
            "remarks": "",
            "processing_channel": DEFAULT_VALUES.get("Processing Channel", "E-Office"),
            "concerned_departments": concerned_depts_val,
            "grievance_id_computer_number": item["grievance_id"],
            "sent_on": item["sent_on"],
            "letter_number": item["letter_no"],
            "letter_date": item["letter_date"],
            "overall_atr_status": "",  # Empty per requirement
            "departments": [],
        }

        for d in dept_list:
            dept_dict = {
                "communication_number": item["comm_no"],
                "communication_date": item["comm_date"],
                "representation_serial_number": item["s_no"],
                "grievance_id_computer_number": d["grievance_id"],
                "eoffice_receipt_number": d["receipt_no"],
                "concerned_department_abbreviation": d["dept_abbr"],
                "concerned_department": d["dept_name"],
                "location": d["location"],
                "atr_status": "",
                "atr_number": d["atr_number"],
                "atr_date": d["atr_date"],
                "atr_computer_number": d["atr_comp_no"],
            }
            rep_row["departments"].append(dept_dict)
            processed_depts.append(dept_dict)

        processed_reps.append(rep_row)

    return processed_reps, processed_depts, errors
