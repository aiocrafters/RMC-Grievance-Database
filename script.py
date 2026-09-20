import os
import re
import csv
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from itertools import groupby
import pandas as pd

from mappings import (
    DEPARTMENT_MAPPING,
    DEFAULT_VALUES,
    EXTRACTION_PATTERNS,
    REPRESENTATIONS_COLUMNS,
    CONCERNED_DEPARTMENTS_COLUMNS,
)

REF_PATTERN = re.compile(EXTRACTION_PATTERNS["Communication No."], re.IGNORECASE)
DATE_PATTERN = re.compile(EXTRACTION_PATTERNS["Communication Date"], re.IGNORECASE)
SNO_PATTERN = re.compile(EXTRACTION_PATTERNS["Representation No."], re.IGNORECASE)


def format_to_full_date(val) -> str:
    """Converts dates, timestamps, or date strings to 'DD MMMM YYYY' format."""
    if val is None or pd.isna(val):
        return ""
    if isinstance(val, (pd.Timestamp, datetime)):
        return val.strftime("%d %B %Y")

    date_str = str(val).strip()
    normalized = re.sub(r"[./]", "-", date_str)

    formats = (
        "%d-%m-%Y %I:%M %p",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %I:%M %p",
        "%d-%m-%Y",
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
        d_name = (d.get("dept_name") or "").strip()
        r_no = (d.get("receipt_no") or "").strip()
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


def extract_subject_details(subject_text: str):
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
        raw_date = date_match.group(1).strip(" .:,;-_")
        comm_date = format_to_full_date(raw_date)
    else:
        warnings.append("Communication Date")

    s_no = ""
    sno_match = SNO_PATTERN.search(text)
    if sno_match:
        s_no = sno_match.group(1).strip(" .:,;-_")
    else:
        warnings.append("Representation Serial Number")

    return comm_no, comm_date, s_no, warnings


def normalize_string(val) -> str:
    """Normalizes strings by removing prefixes, punctuation, and extra whitespace."""
    if val is None or pd.isna(val):
        return ""
    text = str(val).lower().strip()
    text = re.sub(r"^o/o\s+", "", text)
    text = re.sub(r"\b(department|dept|office)\b", "", text)
    text = re.sub(r"[^a-z0-9]", "", text)
    return text


def natural_sort_key(val: str):
    """Splits alphanumeric text into strings and ints for accurate ascending sorting."""
    if not val:
        return []
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", str(val).strip())]


class DepartmentResolver:
    def __init__(self, ref_csv_path: Path):
        self.dept_records = []
        self.alias_map = {
            "jkhod": ("Head of Department", "HOD"),
            "jkdcof": ("Deputy Commissioner", "DC"),
            "pwd": ("Public Works (R&B) Department", "PWD"),
            "pwdrb": ("Public Works (R&B) Department", "PWD"),
            "youthservice": ("Youth Services and Sports Department", "YSS"),
            "youthservicesports": ("Youth Services and Sports Department", "YSS"),
            "healthmedicaleducation": ("Health & Medical Education Department", "HME"),
            "agricultureproduction": ("Agriculture Production Department", "APD"),
            "schooleducation": ("School Education Department", "SED"),
            "culture": ("Department of Culture", "CUL"),
            "estates": ("Estates Department", "ESD"),
            "forest": ("Forest, Ecology and Environment Department", "FED"),
            "tourism": ("Tourism Department", "TOUR"),
            "home": ("Home Department", "HOME"),
            "revenue": ("Revenue Department", "REV"),
        }

        for raw_k, meta in DEPARTMENT_MAPPING.items():
            norm_k = normalize_string(raw_k)
            if norm_k not in self.alias_map:
                self.alias_map[norm_k] = (meta["name"], meta["abbr"])

        if ref_csv_path.exists():
            try:
                df_ref = pd.read_csv(ref_csv_path, dtype=str)
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
            except Exception as e:
                print(f"Warning: Failed to load reference CSV ({e})")

    def resolve(self, raw_input):
        if raw_input is None or pd.isna(raw_input):
            return "", ""

        raw_clean = str(raw_input).strip()
        norm_in = normalize_string(raw_clean)

        if norm_in in self.alias_map:
            return self.alias_map[norm_in]

        exact_abbr = raw_clean.upper()
        for rec in self.dept_records:
            if exact_abbr == rec["abbr"].upper():
                return rec["name"], rec["abbr"]

        best_match = None
        highest_ratio = 0.0

        for rec in self.dept_records:
            if (
                norm_in == rec["norm_name"]
                or norm_in == rec["norm_abbr"]
                or (len(norm_in) >= 4 and (norm_in in rec["norm_name"] or rec["norm_name"] in norm_in))
            ):
                return rec["name"], rec["abbr"]

            ratio = SequenceMatcher(None, norm_in, rec["norm_name"]).ratio()
            if ratio > highest_ratio:
                highest_ratio = ratio
                best_match = rec

        if best_match and highest_ratio >= 0.60:
            return best_match["name"], best_match["abbr"]

        return raw_clean, ""


def normalize_column_name(col_name) -> str:
    return re.sub(r"[^a-z0-9]", "", str(col_name).lower())


def find_column(df_columns, target_aliases):
    norm_aliases = [normalize_column_name(a) for a in target_aliases]
    for col in df_columns:
        if normalize_column_name(col) in norm_aliases:
            return col
    return None


def clean_cell_value(val) -> str:
    if pd.isna(val) or val is None:
        return ""
    val_str = str(val).strip()
    if val_str.endswith(".0") and val_str[:-2].isdigit():
        return val_str[:-2]
    return val_str


def get_cell_value(row, col_name):
    """Safely extracts cell value even if columns are duplicated into a Series."""
    if col_name is None or col_name not in row:
        return ""
    val = row[col_name]
    if isinstance(val, pd.Series):
        val = val.iloc[0]
    return clean_cell_value(val)


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


def main():
    base_dir = Path(__file__).resolve().parent
    input_dir = base_dir / "Input"
    output_dir = base_dir / "Output"

    rep_csv_path = output_dir / "Representations.csv"
    dept_csv_path = output_dir / "Concerned Departments.csv"
    excel_out_path = output_dir / "Representations_and_Departments.xlsx"

    ref_dept_csv = base_dir / "Departments_Supabase_2026-09-15.csv"

    resolver = DepartmentResolver(ref_dept_csv)

    output_dir.mkdir(parents=True, exist_ok=True)
    input_dir.mkdir(parents=True, exist_ok=True)

    input_files = sorted([
        f for f in input_dir.iterdir()
        if f.is_file() and f.suffix.lower() in [".xlsx", ".xls", ".csv"] and not f.name.startswith("~$")
    ])

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

    raw_records = []
    print("\nStarting data extraction and normalization pipeline...")

    for file_path in input_files:
        try:
            df = load_input_file(file_path)
        except Exception as e:
            print(f"Skipped: {file_path.name} (Error reading file: {e})")
            continue

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

        if not all([col_comp, col_receipt, col_subject, col_dept]):
            print(f"Skipped: {file_path.name} (Missing required columns: Comp/Receipt/Subject/Dept)")
            continue

        for _, row in df.iterrows():
            grievance_id = get_cell_value(row, col_comp)
            eoffice_receipt_no = get_cell_value(row, col_receipt)
            raw_dept = get_cell_value(row, col_dept)
            raw_subject = get_cell_value(row, col_subject)
            sender_name = get_cell_value(row, col_sender) if col_sender else ""
            sent_on_val = format_to_full_date(get_cell_value(row, col_sent_on)) if col_sent_on else ""
            letter_ref = get_cell_value(row, col_letter_ref) if col_letter_ref else ""
            letter_date = format_to_full_date(get_cell_value(row, col_letter_date)) if col_letter_date else ""
            location_val = get_cell_value(row, col_location) if col_location else ""
            status_val = get_cell_value(row, col_status) if col_status else ""
            atr_no_val = get_cell_value(row, col_atr_no) if col_atr_no else ""
            atr_date_val = format_to_full_date(get_cell_value(row, col_atr_date)) if col_atr_date else ""
            atr_comp_val = get_cell_value(row, col_atr_comp) if col_atr_comp else ""

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

    grouped_items.sort(
        key=lambda g: (
            natural_sort_key(g["comm_no"]),
            natural_sort_key(g["s_no"]),
        )
    )

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

    final_grouped_items.sort(
        key=lambda x: (
            natural_sort_key(x[0]["comm_no"]),
            natural_sort_key(x[0]["s_no"]),
        )
    )

    representations_rows = []
    departments_rows = []

    for item, is_blank_gap in final_grouped_items:
        if is_blank_gap:
            rep_row = {col: "" for col in REPRESENTATIONS_COLUMNS}
            rep_row["Communication Number"] = item["comm_no"]
            rep_row["Communication Date"] = item["comm_date"]
            rep_row["Representation Serial Number"] = item["s_no"]
            rep_row["Remarks"] = item.get("remarks", "")
            representations_rows.append(rep_row)
            continue

        dept_list = item["departments"]
        issue_type = "Multiple" if len(dept_list) > 1 else "Single"
        concerned_depts_val = format_concerned_departments(dept_list)

        rep_row = {
            "Communication Number": item["comm_no"],
            "Communication Date": item["comm_date"],
            "Representation Serial Number": item["s_no"],
            "Applicant Name": "",
            "Subject": "",
            "Applicant Name On Portal": item["applicant"],
            "Representation Subject On Portal": item["subject"],
            "Issue Type (Single / Multiple)": issue_type,
            "Remarks": "",
            "Processing Channel": DEFAULT_VALUES.get("Processing Channel", "E-Office"),
            "Concerned Department(s)": concerned_depts_val,
            "Grievance ID / Computer Number": item["grievance_id"],
            "Sent On": item["sent_on"],
            "Letter Number": item["letter_no"],
            "Letter Date": item["letter_date"],
            "Overall ATR Status": "",  # Left blank per requirement
        }
        representations_rows.append(rep_row)

        for d in dept_list:
            departments_rows.append({
                "Communication Number": item["comm_no"],
                "Communication Date": item["comm_date"],
                "Representation Serial Number": item["s_no"],
                "Grievance ID / Computer Number": d["grievance_id"],
                "E-Office Receipt Number": d["receipt_no"],
                "Concerned Department Abbreviation": d["dept_abbr"],
                "Concerned Department": d["dept_name"],
                "Location": d["location"],
                "ATR Status": "",  # Left blank per requirement
                "ATR Number": d["atr_number"],
                "ATR Date": d["atr_date"],
                "ATR Computer Number": d["atr_comp_no"],
            })

    df_rep = pd.DataFrame(representations_rows, columns=REPRESENTATIONS_COLUMNS)
    df_dept = pd.DataFrame(departments_rows, columns=CONCERNED_DEPARTMENTS_COLUMNS)

    # 1. Output Representations.csv
    df_rep.to_csv(rep_csv_path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_NONNUMERIC)

    # 2. Output Concerned Departments.csv
    df_dept.to_csv(dept_csv_path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_NONNUMERIC)

    # 3. Output Excel file with two sheets
    try:
        with pd.ExcelWriter(excel_out_path, engine="openpyxl") as writer:
            df_rep.to_excel(writer, sheet_name="Representations", index=False)
            df_dept.to_excel(writer, sheet_name="Concerned Departments", index=False)

            try:
                from openpyxl.styles import Alignment
                ws_rep = writer.sheets["Representations"]
                col_idx = None
                for cell in ws_rep[1]:
                    if cell.value == "Concerned Department(s)":
                        col_idx = cell.column
                        break
                if col_idx:
                    for row in ws_rep.iter_rows(min_row=2, min_col=col_idx, max_col=col_idx):
                        for cell in row:
                            cell.alignment = Alignment(wrap_text=True, vertical="top")
            except Exception as e:
                print(f"Warning: Failed to apply Excel text wrapping ({e})")
    except PermissionError:
        print(f"\n[Warning] Could not update Excel file '{excel_out_path.name}' because it is currently open in another program (e.g. Microsoft Excel). Close the file to allow updating.")

    print("\n" + "=" * 50)
    print("Processing & Normalization Completed Successfully")
    print("=" * 50)
    print(f"Total Representations:           {len(df_rep):>6}")
    print(f"Total Concerned Department Rows: {len(df_dept):>6}\n")
    print("Output Files Generated:")
    print(f"  • CSV 1: {rep_csv_path}")
    print(f"  • CSV 2: {dept_csv_path}")
    print(f"  • Excel: {excel_out_path} (Sheets: 'Representations', 'Concerned Departments')\n")
    print("=" * 50)


if __name__ == "__main__":
    main()