import csv
from dataclasses import dataclass, field
import io
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

import database
from core_logic import (
    DepartmentResolver,
    load_input_file,
    process_raw_dataframe,
)
from mappings import (
    CONCERNED_DEPARTMENTS_COLUMNS,
    REPRESENTATIONS_COLUMNS,
)


class ImportSummary:
    def __init__(self):
        self.total_input_rows: int = 0
        self.representations_inserted: int = 0
        self.representations_updated: int = 0
        self.departments_processed: int = 0
        self.skipped_count: int = 0
        self.errors: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_input_rows": self.total_input_rows,
            "representations_inserted": self.representations_inserted,
            "representations_updated": self.representations_updated,
            "departments_processed": self.departments_processed,
            "skipped_count": self.skipped_count,
            "errors": self.errors,
            "is_success": len(self.errors) == 0,
        }


def import_file_to_database(
    file_path: str,
    db_path: str,
    resolver: Optional[DepartmentResolver] = None,
) -> ImportSummary:
    """
    Imports a CSV or Excel file into the SQLite database, preserving existing business logic,
    updating existing representations or inserting new ones, and maintaining parent-child relations.
    """
    summary = ImportSummary()
    path_obj = Path(file_path)

    if not path_obj.exists():
        summary.errors.append(f"Selected file does not exist: {file_path}")
        return summary

    if resolver is None:
        ref_csv = Path(__file__).resolve().parent / "Departments_Supabase_2026-09-15.csv"
        resolver = DepartmentResolver(ref_csv if ref_csv.exists() else None, db_path=db_path)

    try:
        df = load_input_file(path_obj)
        summary.total_input_rows = len(df)
    except Exception as e:
        summary.errors.append(f"Failed to read file '{path_obj.name}': {str(e)}")
        return summary

    if summary.total_input_rows == 0:
        summary.errors.append("The imported file contains no rows.")
        return summary

    reps, depts, errors = process_raw_dataframe(df, resolver)
    if errors:
        summary.errors.extend(errors)
        return summary

    # Group depts by representation serial & communication number
    for rep in reps:
        comm_no = rep["communication_number"]
        serial_no = rep["representation_serial_number"]

        if not serial_no:
            summary.skipped_count += 1
            continue

        rep_depts = rep.get("departments", [])

        # Check if representation already exists in DB
        existing_reps = database.get_representations(
            db_path,
            filters={"communication_number": comm_no},
        )
        matched_existing = None
        for r in existing_reps:
            if str(r.get("representation_serial_number", "")).strip() == str(serial_no).strip():
                matched_existing = r
                break

        if matched_existing:
            rep_uuid = matched_existing["uuid"]
            database.update_representation(db_path, rep_uuid, rep, rep_depts)
            summary.representations_updated += 1
        else:
            rep_uuid = str(uuid.uuid4())
            rep["uuid"] = rep_uuid
            database.insert_representation_with_departments(db_path, rep, rep_depts)
            summary.representations_inserted += 1

        summary.departments_processed += len(rep_depts)

    return summary


def export_to_csv(
    reps: List[Dict[str, Any]],
    output_path: str,
    include_departments: bool = True,
    db_path: Optional[str] = None,
) -> None:
    """Exports representations list to CSV."""
    df_rep = pd.DataFrame(reps)

    # Map database keys to schema column names
    col_mapping = {
        "communication_number": "Communication Number",
        "communication_date": "Communication Date",
        "representation_serial_number": "Representation Serial Number",
        "applicant_name": "Applicant Name",
        "subject": "Subject",
        "applicant_name_on_portal": "Applicant Name On Portal",
        "representation_subject_on_portal": "Representation Subject On Portal",
        "issue_type": "Issue Type (Single / Multiple)",
        "remarks": "Remarks",
        "processing_channel": "Processing Channel",
        "concerned_departments": "Concerned Department(s)",
        "grievance_id_computer_number": "Grievance ID / Computer Number",
        "sent_on": "Sent On",
        "letter_number": "Letter Number",
        "letter_date": "Letter Date",
        "overall_atr_status": "Overall ATR Status",
    }
    df_rep = df_rep.rename(columns=col_mapping)

    for col in REPRESENTATIONS_COLUMNS:
        if col not in df_rep.columns:
            df_rep[col] = ""

    df_rep = df_rep[REPRESENTATIONS_COLUMNS]
    df_rep.to_csv(output_path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_NONNUMERIC)

    # Optionally export Concerned Departments companion CSV if db_path is provided
    if include_departments and db_path:
        out_p = Path(output_path)
        dept_csv_path = out_p.parent / f"{out_p.stem}_Concerned_Departments.csv"
        all_depts = []
        for r in reps:
            rep_uuid = r.get("uuid")
            if rep_uuid:
                depts = database.get_departments_for_representation(db_path, rep_uuid)
                all_depts.extend(depts)
        if all_depts:
            df_dept = pd.DataFrame(all_depts)
            dept_col_mapping = {
                "communication_number": "Communication Number",
                "communication_date": "Communication Date",
                "representation_serial_number": "Representation Serial Number",
                "grievance_id_computer_number": "Grievance ID / Computer Number",
                "eoffice_receipt_number": "E-Office Receipt Number",
                "concerned_department_abbreviation": "Concerned Department Abbreviation",
                "concerned_department": "Concerned Department",
                "location": "Location",
                "atr_status": "ATR Status",
                "atr_number": "ATR Number",
                "atr_date": "ATR Date",
                "atr_computer_number": "ATR Computer Number",
            }
            df_dept = df_dept.rename(columns=dept_col_mapping)
            for col in CONCERNED_DEPARTMENTS_COLUMNS:
                if col not in df_dept.columns:
                    df_dept[col] = ""
            df_dept = df_dept[CONCERNED_DEPARTMENTS_COLUMNS]
            df_dept.to_csv(dept_csv_path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_NONNUMERIC)


def export_to_excel(
    reps: List[Dict[str, Any]],
    output_path: str,
    db_path: Optional[str] = None,
) -> None:
    """Exports representations and concerned departments to an Excel workbook with formatting."""
    df_rep = pd.DataFrame(reps)
    col_mapping = {
        "communication_number": "Communication Number",
        "communication_date": "Communication Date",
        "representation_serial_number": "Representation Serial Number",
        "applicant_name": "Applicant Name",
        "subject": "Subject",
        "applicant_name_on_portal": "Applicant Name On Portal",
        "representation_subject_on_portal": "Representation Subject On Portal",
        "issue_type": "Issue Type (Single / Multiple)",
        "remarks": "Remarks",
        "processing_channel": "Processing Channel",
        "concerned_departments": "Concerned Department(s)",
        "grievance_id_computer_number": "Grievance ID / Computer Number",
        "sent_on": "Sent On",
        "letter_number": "Letter Number",
        "letter_date": "Letter Date",
        "overall_atr_status": "Overall ATR Status",
    }
    df_rep = df_rep.rename(columns=col_mapping)
    for col in REPRESENTATIONS_COLUMNS:
        if col not in df_rep.columns:
            df_rep[col] = ""
    df_rep = df_rep[REPRESENTATIONS_COLUMNS]

    all_depts = []
    if db_path:
        for r in reps:
            rep_uuid = r.get("uuid")
            if rep_uuid:
                depts = database.get_departments_for_representation(db_path, rep_uuid)
                all_depts.extend(depts)

    df_dept = pd.DataFrame(all_depts) if all_depts else pd.DataFrame(columns=CONCERNED_DEPARTMENTS_COLUMNS)
    if not df_dept.empty:
        dept_col_mapping = {
            "communication_number": "Communication Number",
            "communication_date": "Communication Date",
            "representation_serial_number": "Representation Serial Number",
            "grievance_id_computer_number": "Grievance ID / Computer Number",
            "eoffice_receipt_number": "E-Office Receipt Number",
            "concerned_department_abbreviation": "Concerned Department Abbreviation",
            "concerned_department": "Concerned Department",
            "location": "Location",
            "atr_status": "ATR Status",
            "atr_number": "ATR Number",
            "atr_date": "ATR Date",
            "atr_computer_number": "ATR Computer Number",
        }
        df_dept = df_dept.rename(columns=dept_col_mapping)
        for col in CONCERNED_DEPARTMENTS_COLUMNS:
            if col not in df_dept.columns:
                df_dept[col] = ""
        df_dept = df_dept[CONCERNED_DEPARTMENTS_COLUMNS]

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_rep.to_excel(writer, sheet_name="Representations", index=False)
        df_dept.to_excel(writer, sheet_name="Concerned Departments", index=False)

        ws_rep = writer.sheets["Representations"]
        header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True, size=10)

        for cell in ws_rep[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        col_dept_idx = None
        col_subj_idx = None
        for cell in ws_rep[1]:
            if cell.value == "Concerned Department(s)":
                col_dept_idx = cell.column
            elif cell.value == "Representation Subject On Portal":
                col_subj_idx = cell.column

        for row in ws_rep.iter_rows(min_row=2):
            for cell in row:
                if cell.column in (col_dept_idx, col_subj_idx):
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
                else:
                    cell.alignment = Alignment(vertical="top")

        ws_rep.column_dimensions["A"].width = 20
        ws_rep.column_dimensions["C"].width = 12
        ws_rep.column_dimensions["F"].width = 25
        ws_rep.column_dimensions["G"].width = 45
        ws_rep.column_dimensions["K"].width = 50

        # Style Concerned Departments sheet
        ws_dept = writer.sheets["Concerned Departments"]
        for cell in ws_dept[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")


class NumberedCanvas(canvas.Canvas):
    """Adds page numbers and footer rule to each page in ReportLab PDF generation."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)

        # Footer
        footer_y = 20
        self.line(30, footer_y + 12, self._pagesize[0] - 30, footer_y + 12)
        date_str = datetime.now().strftime("%d %B %Y, %I:%M %p")
        self.drawString(30, footer_y, f"RMC Grievance Monitoring System | Generated: {date_str}")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(self._pagesize[0] - 30, footer_y, page_str)
        self.restoreState()


def export_to_pdf(
    reps: List[Dict[str, Any]],
    output_path: str,
    title: str = "RMC Grievance Database - Representations Report",
) -> None:
    """Exports representations to a professional multi-page landscape PDF document using ReportLab."""
    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(A3),
        leftMargin=25,
        rightMargin=25,
        topMargin=25,
        bottomMargin=35,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#1E3A8A"),
    )

    meta_style = ParagraphStyle(
        "ReportMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#475569"),
    )

    header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=1,  # Center
    )

    cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#0F172A"),
    )

    cell_bold_style = ParagraphStyle(
        "TableCellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#0F172A"),
    )

    elements = []

    # Title & Subtitle block
    elements.append(Paragraph(title, title_style))
    elements.append(Spacer(1, 4))
    now_str = datetime.now().strftime("%d %B %Y, %I:%M %p")
    meta_text = f"Total Records: <b>{len(reps)}</b> | Generated on: <b>{now_str}</b> | Channel: <b>e-Office / Portal</b>"
    elements.append(Paragraph(meta_text, meta_style))
    elements.append(Spacer(1, 8))

    # Selected essential columns for clean landscape display
    pdf_headers = [
        "Comm No.",
        "Comm Date",
        "S.No",
        "Applicant On Portal",
        "Representation Subject",
        "Issue",
        "Concerned Department(s)",
        "Grievance ID",
        "Sent On",
        "Letter Ref",
        "Remarks",
        "Overall ATR",
    ]

    table_data = [[Paragraph(h, header_style) for h in pdf_headers]]

    for r in reps:
        comm_no = str(r.get("communication_number", "") or "")
        comm_date = str(r.get("communication_date", "") or "")
        s_no = str(r.get("representation_serial_number", "") or "")
        applicant = str(r.get("applicant_name_on_portal", "") or "")
        subject = str(r.get("representation_subject_on_portal", "") or r.get("subject", "") or "")
        issue = str(r.get("issue_type", "") or "")
        depts = str(r.get("concerned_departments", "") or "")
        gid = str(r.get("grievance_id_computer_number", "") or "")
        sent_on = str(r.get("sent_on", "") or "")
        letter_no = str(r.get("letter_number", "") or "")
        remarks = str(r.get("remarks", "") or "")
        overall_atr = str(r.get("overall_atr_status", "") or "")

        # Convert line breaks to HTML breaks for reportlab paragraph
        depts_html = depts.replace("\n", "<br/>")
        subject_html = subject.replace("\n", " ")

        row_cells = [
            Paragraph(comm_no, cell_style),
            Paragraph(comm_date, cell_style),
            Paragraph(f"<b>{s_no}</b>", cell_bold_style),
            Paragraph(applicant, cell_style),
            Paragraph(subject_html, cell_style),
            Paragraph(issue, cell_style),
            Paragraph(depts_html, cell_style),
            Paragraph(gid, cell_style),
            Paragraph(sent_on, cell_style),
            Paragraph(letter_no, cell_style),
            Paragraph(remarks, cell_style),
            Paragraph(overall_atr, cell_style),
        ]
        table_data.append(row_cells)

    # Column widths (Total ~1140 points for A3 landscape)
    col_widths = [
        75,   # Comm No
        55,   # Comm Date
        35,   # S.No
        100,  # Applicant
        260,  # Subject
        45,   # Issue
        270,  # Concerned Depts
        65,   # Grievance ID
        55,   # Sent On
        65,   # Letter Ref
        70,   # Remarks
        65,   # Overall ATR
    ]

    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FFFFFF"), colors.HexColor("#F8FAFC")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
    ]))

    elements.append(t)
    doc.build(elements, canvasmaker=NumberedCanvas)


# ==========================================
# MASTER DEPARTMENTS IMPORT / EXPORT
# ==========================================

@dataclass
class DepartmentImportSummary:
    """Summary of department CSV import results."""
    total_rows: int = 0
    inserted_count: int = 0
    updated_count: int = 0
    skipped_duplicate_count: int = 0
    error_count: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_rows": self.total_rows,
            "inserted_count": self.inserted_count,
            "updated_count": self.updated_count,
            "skipped_duplicate_count": self.skipped_duplicate_count,
            "error_count": self.error_count,
            "errors": self.errors,
        }


def validate_and_import_departments_csv(
    file_path: str,
    db_path: str,
    update_existing: bool = False,
) -> DepartmentImportSummary:
    """
    Validates and imports department records from a CSV file into SQLite.
    Prevents unintended duplicates by checking existing database records and
    in-file duplicates (case-insensitive name comparison).
    """
    summary = DepartmentImportSummary()
    path_obj = Path(file_path)

    if not path_obj.exists():
        summary.errors.append(f"File not found: {file_path}")
        summary.error_count += 1
        return summary

    try:
        df = pd.read_csv(path_obj, dtype=str, keep_default_na=False)
    except Exception as e:
        summary.errors.append(f"Could not read CSV file: {str(e)}")
        summary.error_count += 1
        return summary

    summary.total_rows = len(df)
    if summary.total_rows == 0:
        summary.errors.append("The CSV file contains no data rows.")
        summary.error_count += 1
        return summary

    # Identify column mappings flexibly
    col_map: Dict[str, str] = {}
    for col in df.columns:
        c_norm = col.strip().lower().replace("_", " ")
        if c_norm in ["department name", "dept name", "name", "department"]:
            col_map["name"] = col
        elif c_norm in ["department abbreviation", "dept abbreviation", "abbreviation", "abbr"]:
            col_map["abbr"] = col
        elif c_norm in ["department address", "dept address", "address"]:
            col_map["address"] = col
        elif c_norm in ["department additional address", "additional address", "address 2", "address2"]:
            col_map["additional_address"] = col
        elif c_norm in ["department addressee", "dept addressee", "addressee", "contact person", "officer"]:
            col_map["addressee"] = col

    if "name" not in col_map:
        summary.errors.append(
            f"Required column 'Department Name' not found in CSV. Found headers: {list(df.columns)}"
        )
        summary.error_count += 1
        return summary

    seen_in_file = set()

    for idx, row in df.iterrows():
        row_num = idx + 2  # 1-indexed accounting for CSV header
        raw_name = str(row[col_map["name"]]).strip() if col_map.get("name") else ""
        raw_abbr = str(row[col_map["abbr"]]).strip() if col_map.get("abbr") else ""
        raw_addr = str(row[col_map["address"]]).strip() if col_map.get("address") else ""
        raw_add_addr = str(row[col_map["additional_address"]]).strip() if col_map.get("additional_address") else ""
        raw_addressee = str(row[col_map["addressee"]]).strip() if col_map.get("addressee") else ""

        if not raw_name:
            summary.errors.append(f"Row {row_num}: Department Name is blank. Skipped.")
            summary.error_count += 1
            continue

        norm_name = raw_name.lower()

        # Check in-file duplicate
        if norm_name in seen_in_file:
            summary.skipped_duplicate_count += 1
            summary.errors.append(f"Row {row_num}: Duplicate department '{raw_name}' in CSV file. Skipped.")
            continue
        seen_in_file.add(norm_name)

        # Check existing database records
        existing_matches = database.get_departments(db_path, search_query=raw_name)
        matched = None
        for d in existing_matches:
            if d["department_name"].strip().lower() == norm_name:
                matched = d
                break

        if matched:
            if update_existing:
                update_data = {
                    "department_name": raw_name,
                    "department_abbreviation": raw_abbr or matched.get("department_abbreviation", ""),
                    "department_address": raw_addr or matched.get("department_address", ""),
                    "department_additional_address": raw_add_addr or matched.get("department_additional_address", ""),
                    "department_addressee": raw_addressee or matched.get("department_addressee", ""),
                }
                database.update_department(db_path, matched["uuid"], update_data)
                summary.updated_count += 1
            else:
                summary.skipped_duplicate_count += 1
        else:
            insert_data = {
                "department_name": raw_name,
                "department_abbreviation": raw_abbr,
                "department_address": raw_addr,
                "department_additional_address": raw_add_addr,
                "department_addressee": raw_addressee,
            }
            database.insert_department(db_path, insert_data)
            summary.inserted_count += 1

    return summary


def export_departments_to_csv(departments: List[Dict[str, Any]], target_path: str) -> None:
    """Exports master departments list to CSV format."""
    headers = [
        "Department Name",
        "Department Abbreviation",
        "Department Address",
        "Department Additional Address",
        "Department Addressee",
    ]
    with open(target_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for d in departments:
            writer.writerow([
                d.get("department_name", ""),
                d.get("department_abbreviation", ""),
                d.get("department_address", ""),
                d.get("department_additional_address", ""),
                d.get("department_addressee", ""),
            ])

