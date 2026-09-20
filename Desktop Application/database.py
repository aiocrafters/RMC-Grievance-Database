from datetime import datetime
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def get_connection(db_path: str) -> sqlite3.Connection:
    """Creates a connection to SQLite database with WAL mode and foreign keys enabled."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_db(db_path: str) -> None:
    """Initializes database schema and indexes."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # Table 1: representations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS representations (
                uuid TEXT PRIMARY KEY,
                communication_number TEXT,
                communication_date TEXT,
                representation_serial_number TEXT,
                applicant_name TEXT,
                subject TEXT,
                applicant_name_on_portal TEXT,
                representation_subject_on_portal TEXT,
                issue_type TEXT,
                remarks TEXT,
                processing_channel TEXT,
                concerned_departments TEXT,
                grievance_id_computer_number TEXT,
                sent_on TEXT,
                letter_number TEXT,
                letter_date TEXT,
                overall_atr_status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Table 2: concerned_departments
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS concerned_departments (
                uuid TEXT PRIMARY KEY,
                representation_uuid TEXT NOT NULL,
                communication_number TEXT,
                communication_date TEXT,
                representation_serial_number TEXT,
                grievance_id_computer_number TEXT,
                eoffice_receipt_number TEXT,
                concerned_department_abbreviation TEXT,
                concerned_department TEXT,
                location TEXT,
                atr_status TEXT,
                atr_number TEXT,
                atr_date TEXT,
                atr_computer_number TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (representation_uuid) REFERENCES representations (uuid) ON DELETE CASCADE
            );
        """)

        # Table 3: departments (Master Departments Table)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS departments (
                uuid TEXT PRIMARY KEY,
                department_name TEXT NOT NULL,
                department_abbreviation TEXT,
                department_address TEXT,
                department_additional_address TEXT,
                department_addressee TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Indexes for fast querying, filtering, and joins
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rep_comm_no ON representations(communication_number);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rep_serial ON representations(representation_serial_number);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rep_grievance ON representations(grievance_id_computer_number);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rep_status ON representations(overall_atr_status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dept_rep_uuid ON concerned_departments(representation_uuid);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dept_receipt ON concerned_departments(eoffice_receipt_number);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dept_name ON concerned_departments(concerned_department);")

        # Indexes for departments master table
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_dept_unique_name ON departments(LOWER(TRIM(department_name)));")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dept_abbr ON departments(LOWER(TRIM(department_abbreviation)));")

        conn.commit()


def get_representations(
    db_path: str,
    search_query: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
    sort_column: str = "representation_serial_number",
    sort_order: str = "ASC",
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Retrieves representations matching search and filters."""
    valid_sort_columns = {
        "communication_number": "communication_number",
        "communication_date": "communication_date",
        "representation_serial_number": "CAST(representation_serial_number AS INTEGER)",
        "applicant_name": "applicant_name",
        "subject": "subject",
        "applicant_name_on_portal": "applicant_name_on_portal",
        "representation_subject_on_portal": "representation_subject_on_portal",
        "issue_type": "issue_type",
        "remarks": "remarks",
        "processing_channel": "processing_channel",
        "concerned_departments": "concerned_departments",
        "grievance_id_computer_number": "grievance_id_computer_number",
        "sent_on": "sent_on",
        "letter_number": "letter_number",
        "letter_date": "letter_date",
        "overall_atr_status": "overall_atr_status",
    }
    col_order_clause = valid_sort_columns.get(sort_column, "CAST(representation_serial_number AS INTEGER)")
    order_dir = "DESC" if sort_order.upper() == "DESC" else "ASC"

    query = "SELECT * FROM representations WHERE 1=1"
    params: List[Any] = []

    if search_query:
        search_pattern = f"%{search_query.strip()}%"
        query += """ AND (
            communication_number LIKE ? OR
            representation_serial_number LIKE ? OR
            applicant_name LIKE ? OR
            subject LIKE ? OR
            applicant_name_on_portal LIKE ? OR
            representation_subject_on_portal LIKE ? OR
            concerned_departments LIKE ? OR
            grievance_id_computer_number LIKE ? OR
            letter_number LIKE ? OR
            remarks LIKE ? OR
            overall_atr_status LIKE ?
        )"""
        params.extend([search_pattern] * 11)

    if filters:
        if filters.get("communication_number"):
            query += " AND communication_number = ?"
            params.append(filters["communication_number"])
        if filters.get("issue_type"):
            query += " AND issue_type = ?"
            params.append(filters["issue_type"])
        if filters.get("processing_channel"):
            query += " AND processing_channel = ?"
            params.append(filters["processing_channel"])
        if filters.get("overall_atr_status"):
            query += " AND overall_atr_status LIKE ?"
            params.append(f"%{filters['overall_atr_status']}%")
        if filters.get("concerned_department"):
            query += " AND concerned_departments LIKE ?"
            params.append(f"%{filters['concerned_department']}%")
        if filters.get("atr_category"):
            cat = filters["atr_category"]
            if cat == "pending_atr":
                query += " AND (overall_atr_status IS NULL OR TRIM(overall_atr_status) = '' OR LOWER(overall_atr_status) LIKE '%pending%') AND LOWER(remarks) NOT LIKE '%missing%'"
            elif cat == "under_process":
                query += " AND (LOWER(overall_atr_status) LIKE '%under process%' OR LOWER(overall_atr_status) LIKE '%inside file%' OR LOWER(overall_atr_status) LIKE '%sent%')"
            elif cat == "reply_received":
                query += " AND (LOWER(overall_atr_status) LIKE '%reply received%' OR LOWER(overall_atr_status) LIKE '%reply%')"
            elif cat == "closed_resolved":
                query += " AND (LOWER(overall_atr_status) LIKE '%closed%' OR LOWER(overall_atr_status) LIKE '%resolved%' OR LOWER(overall_atr_status) LIKE '%disposed%')"

    query += f" ORDER BY {col_order_clause} {order_dir}, representation_serial_number {order_dir}"

    if limit is not None:
        query += f" LIMIT {int(limit)}"
        if offset is not None:
            query += f" OFFSET {int(offset)}"

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def count_representations(
    db_path: str,
    search_query: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> int:
    """Returns total count of representations matching search and filters."""
    query = "SELECT COUNT(*) as total FROM representations WHERE 1=1"
    params: List[Any] = []

    if search_query:
        search_pattern = f"%{search_query.strip()}%"
        query += """ AND (
            communication_number LIKE ? OR
            representation_serial_number LIKE ? OR
            applicant_name LIKE ? OR
            subject LIKE ? OR
            applicant_name_on_portal LIKE ? OR
            representation_subject_on_portal LIKE ? OR
            concerned_departments LIKE ? OR
            grievance_id_computer_number LIKE ? OR
            letter_number LIKE ? OR
            remarks LIKE ? OR
            overall_atr_status LIKE ?
        )"""
        params.extend([search_pattern] * 11)

    if filters:
        if filters.get("communication_number"):
            query += " AND communication_number = ?"
            params.append(filters["communication_number"])
        if filters.get("issue_type"):
            query += " AND issue_type = ?"
            params.append(filters["issue_type"])
        if filters.get("processing_channel"):
            query += " AND processing_channel = ?"
            params.append(filters["processing_channel"])
        if filters.get("overall_atr_status"):
            query += " AND overall_atr_status LIKE ?"
            params.append(f"%{filters['overall_atr_status']}%")
        if filters.get("concerned_department"):
            query += " AND concerned_departments LIKE ?"
            params.append(f"%{filters['concerned_department']}%")
        if filters.get("atr_category"):
            cat = filters["atr_category"]
            if cat == "pending_atr":
                query += " AND (overall_atr_status IS NULL OR TRIM(overall_atr_status) = '' OR LOWER(overall_atr_status) LIKE '%pending%') AND LOWER(remarks) NOT LIKE '%missing%'"
            elif cat == "under_process":
                query += " AND (LOWER(overall_atr_status) LIKE '%under process%' OR LOWER(overall_atr_status) LIKE '%inside file%' OR LOWER(overall_atr_status) LIKE '%sent%')"
            elif cat == "reply_received":
                query += " AND (LOWER(overall_atr_status) LIKE '%reply received%' OR LOWER(overall_atr_status) LIKE '%reply%')"
            elif cat == "closed_resolved":
                query += " AND (LOWER(overall_atr_status) LIKE '%closed%' OR LOWER(overall_atr_status) LIKE '%resolved%' OR LOWER(overall_atr_status) LIKE '%disposed%')"

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        return row["total"] if row else 0


def get_representation_by_uuid(db_path: str, rep_uuid: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single representation record by UUID."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM representations WHERE uuid = ?", (rep_uuid,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_departments_for_representation(db_path: str, rep_uuid: str) -> List[Dict[str, Any]]:
    """Retrieves all concerned departments belonging to a representation."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM concerned_departments WHERE representation_uuid = ? ORDER BY created_at ASC",
            (rep_uuid,),
        )
        return [dict(r) for r in cursor.fetchall()]


def insert_representation_with_departments(
    db_path: str,
    rep_data: Dict[str, Any],
    depts_data: List[Dict[str, Any]],
) -> str:
    """Inserts a new representation and its child concerned departments inside a transaction."""
    rep_uuid = rep_data.get("uuid") or str(uuid.uuid4())
    rep_data["uuid"] = rep_uuid

    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO representations (
                uuid, communication_number, communication_date, representation_serial_number,
                applicant_name, subject, applicant_name_on_portal, representation_subject_on_portal,
                issue_type, remarks, processing_channel, concerned_departments,
                grievance_id_computer_number, sent_on, letter_number, letter_date,
                overall_atr_status, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP
            )
        """, (
            rep_uuid,
            rep_data.get("communication_number", ""),
            rep_data.get("communication_date", ""),
            rep_data.get("representation_serial_number", ""),
            rep_data.get("applicant_name", ""),
            rep_data.get("subject", ""),
            rep_data.get("applicant_name_on_portal", ""),
            rep_data.get("representation_subject_on_portal", ""),
            rep_data.get("issue_type", "Single"),
            rep_data.get("remarks", ""),
            rep_data.get("processing_channel", "E-Office"),
            rep_data.get("concerned_departments", ""),
            rep_data.get("grievance_id_computer_number", ""),
            rep_data.get("sent_on", ""),
            rep_data.get("letter_number", ""),
            rep_data.get("letter_date", ""),
            rep_data.get("overall_atr_status", ""),
        ))

        for d in depts_data:
            dept_uuid = d.get("uuid") or str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO concerned_departments (
                    uuid, representation_uuid, communication_number, communication_date,
                    representation_serial_number, grievance_id_computer_number,
                    eoffice_receipt_number, concerned_department_abbreviation,
                    concerned_department, location, atr_status, atr_number,
                    atr_date, atr_computer_number, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP
                )
            """, (
                dept_uuid,
                rep_uuid,
                d.get("communication_number", rep_data.get("communication_number", "")),
                d.get("communication_date", rep_data.get("communication_date", "")),
                d.get("representation_serial_number", rep_data.get("representation_serial_number", "")),
                d.get("grievance_id_computer_number", rep_data.get("grievance_id_computer_number", "")),
                d.get("eoffice_receipt_number", ""),
                d.get("concerned_department_abbreviation", ""),
                d.get("concerned_department", ""),
                d.get("location", ""),
                d.get("atr_status", ""),
                d.get("atr_number", ""),
                d.get("atr_date", ""),
                d.get("atr_computer_number", ""),
            ))

        conn.commit()
    return rep_uuid


def update_representation(
    db_path: str,
    rep_uuid: str,
    rep_data: Dict[str, Any],
    depts_data: Optional[List[Dict[str, Any]]] = None,
) -> bool:
    """Updates a representation record and optionally refreshes its concerned departments."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE representations SET
                communication_number = ?,
                communication_date = ?,
                representation_serial_number = ?,
                applicant_name = ?,
                subject = ?,
                applicant_name_on_portal = ?,
                representation_subject_on_portal = ?,
                issue_type = ?,
                remarks = ?,
                processing_channel = ?,
                concerned_departments = ?,
                grievance_id_computer_number = ?,
                sent_on = ?,
                letter_number = ?,
                letter_date = ?,
                overall_atr_status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE uuid = ?
        """, (
            rep_data.get("communication_number", ""),
            rep_data.get("communication_date", ""),
            rep_data.get("representation_serial_number", ""),
            rep_data.get("applicant_name", ""),
            rep_data.get("subject", ""),
            rep_data.get("applicant_name_on_portal", ""),
            rep_data.get("representation_subject_on_portal", ""),
            rep_data.get("issue_type", "Single"),
            rep_data.get("remarks", ""),
            rep_data.get("processing_channel", "E-Office"),
            rep_data.get("concerned_departments", ""),
            rep_data.get("grievance_id_computer_number", ""),
            rep_data.get("sent_on", ""),
            rep_data.get("letter_number", ""),
            rep_data.get("letter_date", ""),
            rep_data.get("overall_atr_status", ""),
            rep_uuid,
        ))

        if depts_data is not None:
            # Delete existing departments and re-insert
            cursor.execute("DELETE FROM concerned_departments WHERE representation_uuid = ?", (rep_uuid,))
            for d in depts_data:
                dept_uuid = d.get("uuid") or str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO concerned_departments (
                        uuid, representation_uuid, communication_number, communication_date,
                        representation_serial_number, grievance_id_computer_number,
                        eoffice_receipt_number, concerned_department_abbreviation,
                        concerned_department, location, atr_status, atr_number,
                        atr_date, atr_computer_number, updated_at
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP
                    )
                """, (
                    dept_uuid,
                    rep_uuid,
                    d.get("communication_number", rep_data.get("communication_number", "")),
                    d.get("communication_date", rep_data.get("communication_date", "")),
                    d.get("representation_serial_number", rep_data.get("representation_serial_number", "")),
                    d.get("grievance_id_computer_number", rep_data.get("grievance_id_computer_number", "")),
                    d.get("eoffice_receipt_number", ""),
                    d.get("concerned_department_abbreviation", ""),
                    d.get("concerned_department", ""),
                    d.get("location", ""),
                    d.get("atr_status", ""),
                    d.get("atr_number", ""),
                    d.get("atr_date", ""),
                    d.get("atr_computer_number", ""),
                ))

        conn.commit()
    return True


def delete_representation(db_path: str, rep_uuid: str) -> bool:
    """Deletes a representation record; cascading deletes its concerned departments."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM representations WHERE uuid = ?", (rep_uuid,))
        conn.commit()
        return cursor.rowcount > 0


def update_department_atr(
    db_path: str,
    dept_uuid: str,
    atr_data: Dict[str, Any],
) -> Optional[str]:
    """Updates ATR fields for a concerned department and recalculates Overall ATR Status on parent representation."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE concerned_departments SET
                atr_status = ?,
                atr_number = ?,
                atr_date = ?,
                atr_computer_number = ?,
                location = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE uuid = ?
        """, (
            atr_data.get("atr_status", ""),
            atr_data.get("atr_number", ""),
            atr_data.get("atr_date", ""),
            atr_data.get("atr_computer_number", ""),
            atr_data.get("location", ""),
            dept_uuid,
        ))

        cursor.execute("SELECT representation_uuid FROM concerned_departments WHERE uuid = ?", (dept_uuid,))
        row = cursor.fetchone()
        if not row:
            conn.commit()
            return None

        rep_uuid = row["representation_uuid"]
        # Recalculate overall status
        cursor.execute("SELECT atr_status FROM concerned_departments WHERE representation_uuid = ?", (rep_uuid,))
        statuses = [r["atr_status"].strip() for r in cursor.fetchall() if r["atr_status"] and r["atr_status"].strip()]
        unique_statuses = list(dict.fromkeys(statuses))
        overall_status = "; ".join(unique_statuses) if unique_statuses else ""

        cursor.execute("""
            UPDATE representations SET
                overall_atr_status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE uuid = ?
        """, (overall_status, rep_uuid))

        conn.commit()
        return rep_uuid


def get_filter_options(db_path: str) -> Dict[str, List[str]]:
    """Retrieves distinct values for dropdown filtering."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT communication_number FROM representations WHERE communication_number != '' ORDER BY communication_number")
        comm_numbers = [r["communication_number"] for r in cursor.fetchall()]

        cursor.execute("SELECT DISTINCT issue_type FROM representations WHERE issue_type != '' ORDER BY issue_type")
        issue_types = [r["issue_type"] for r in cursor.fetchall()]

        cursor.execute("SELECT DISTINCT processing_channel FROM representations WHERE processing_channel != '' ORDER BY processing_channel")
        channels = [r["processing_channel"] for r in cursor.fetchall()]

        cursor.execute("SELECT DISTINCT concerned_department FROM concerned_departments WHERE concerned_department != '' ORDER BY concerned_department")
        depts = [r["concerned_department"] for r in cursor.fetchall()]

        cursor.execute("SELECT DISTINCT atr_status FROM concerned_departments WHERE atr_status != '' ORDER BY atr_status")
        atr_statuses = [r["atr_status"] for r in cursor.fetchall()]

        return {
            "communication_numbers": comm_numbers,
            "issue_types": issue_types,
            "processing_channels": channels,
            "concerned_departments": depts,
            "atr_statuses": atr_statuses,
        }


def get_dashboard_metrics(db_path: str) -> Dict[str, int]:
    """
    Computes dynamic counts for the dashboard top metrics cards:
    - Total Records
    - Pending ATR
    - Under Process
    - Reply Received
    - Closed / Resolved
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                COUNT(*) as total_records,
                SUM(CASE 
                    WHEN (overall_atr_status IS NULL OR TRIM(overall_atr_status) = '' OR LOWER(overall_atr_status) LIKE '%pending%')
                         AND LOWER(remarks) NOT LIKE '%missing%'
                    THEN 1 ELSE 0 
                END) as pending_atr,
                SUM(CASE 
                    WHEN LOWER(overall_atr_status) LIKE '%under process%' 
                      OR LOWER(overall_atr_status) LIKE '%inside file%' 
                      OR LOWER(overall_atr_status) LIKE '%sent%' 
                    THEN 1 ELSE 0 
                END) as under_process,
                SUM(CASE 
                    WHEN LOWER(overall_atr_status) LIKE '%reply received%' 
                      OR LOWER(overall_atr_status) LIKE '%reply%' 
                    THEN 1 ELSE 0 
                END) as reply_received,
                SUM(CASE 
                    WHEN LOWER(overall_atr_status) LIKE '%closed%' 
                      OR LOWER(overall_atr_status) LIKE '%resolved%' 
                      OR LOWER(overall_atr_status) LIKE '%disposed%' 
                    THEN 1 ELSE 0 
                END) as closed_resolved
            FROM representations
        """)
        row = cursor.fetchone()
        if row:
            return {
                "total_records": row["total_records"] or 0,
                "pending_atr": row["pending_atr"] or 0,
                "under_process": row["under_process"] or 0,
                "reply_received": row["reply_received"] or 0,
                "closed_resolved": row["closed_resolved"] or 0,
            }
        return {
            "total_records": 0,
            "pending_atr": 0,
            "under_process": 0,
            "reply_received": 0,
            "closed_resolved": 0,
        }


# ==========================================
# MASTER DEPARTMENTS MANAGEMENT
# ==========================================

def get_departments(
    db_path: str,
    search_query: Optional[str] = None,
    sort_column: str = "department_name",
    sort_order: str = "ASC",
) -> List[Dict[str, Any]]:
    """Retrieves all master departments, optionally filtered by search text and sorted."""
    valid_cols = {
        "department_name": "LOWER(department_name)",
        "department_abbreviation": "LOWER(department_abbreviation)",
        "department_address": "department_address",
        "department_additional_address": "department_additional_address",
        "department_addressee": "department_addressee",
        "created_at": "created_at",
    }
    col = valid_cols.get(sort_column, "LOWER(department_name)")
    order = "DESC" if sort_order.upper() == "DESC" else "ASC"

    query = "SELECT * FROM departments WHERE 1=1"
    params: List[Any] = []

    if search_query:
        pattern = f"%{search_query.strip()}%"
        query += """ AND (
            department_name LIKE ? OR
            department_abbreviation LIKE ? OR
            department_address LIKE ? OR
            department_additional_address LIKE ? OR
            department_addressee LIKE ?
        )"""
        params.extend([pattern] * 5)

    query += f" ORDER BY {col} {order}"

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]


def get_department_by_uuid(db_path: str, dept_uuid: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single department record by UUID."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM departments WHERE uuid = ?", (dept_uuid,))
        row = cursor.fetchone()
        return dict(row) if row else None


def is_department_name_taken(db_path: str, name: str, exclude_uuid: Optional[str] = None) -> bool:
    """Checks if a department name already exists (case-insensitive and trimmed)."""
    name_clean = name.strip().lower()
    if not name_clean:
        return False
    query = "SELECT 1 FROM departments WHERE LOWER(TRIM(department_name)) = ?"
    params = [name_clean]
    if exclude_uuid:
        query += " AND uuid != ?"
        params.append(exclude_uuid)

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchone() is not None


def insert_department(db_path: str, dept_data: Dict[str, Any]) -> str:
    """Inserts a new department record into the master departments table."""
    dept_uuid = dept_data.get("uuid") or str(uuid.uuid4())
    now = dept_data.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO departments (
                uuid, department_name, department_abbreviation,
                department_address, department_additional_address,
                department_addressee, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dept_uuid,
            (dept_data.get("department_name") or "").strip(),
            (dept_data.get("department_abbreviation") or "").strip(),
            (dept_data.get("department_address") or "").strip(),
            (dept_data.get("department_additional_address") or "").strip(),
            (dept_data.get("department_addressee") or "").strip(),
            now,
            now,
        ))
        conn.commit()
    return dept_uuid


def update_department(db_path: str, dept_uuid: str, dept_data: Dict[str, Any]) -> bool:
    """Updates an existing department record."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE departments SET
                department_name = ?,
                department_abbreviation = ?,
                department_address = ?,
                department_additional_address = ?,
                department_addressee = ?,
                updated_at = ?
            WHERE uuid = ?
        """, (
            (dept_data.get("department_name") or "").strip(),
            (dept_data.get("department_abbreviation") or "").strip(),
            (dept_data.get("department_address") or "").strip(),
            (dept_data.get("department_additional_address") or "").strip(),
            (dept_data.get("department_addressee") or "").strip(),
            now,
            dept_uuid,
        ))
        conn.commit()
        return cursor.rowcount > 0


def delete_department(db_path: str, dept_uuid: str) -> bool:
    """Deletes a department from the master table."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM departments WHERE uuid = ?", (dept_uuid,))
        conn.commit()
        return cursor.rowcount > 0


def count_department_references(db_path: str, dept_name: str) -> int:
    """Counts how many concerned_departments records reference this department name."""
    if not dept_name:
        return 0
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM concerned_departments 
            WHERE LOWER(TRIM(concerned_department)) = ?
        """, (dept_name.strip().lower(),))
        row = cursor.fetchone()
        return row["cnt"] if row else 0


def seed_default_departments_if_empty(db_path: str) -> int:
    """Seeds default departments from mappings.DEPARTMENT_MAPPING if the table is empty."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM departments")
        count = cursor.fetchone()["cnt"]
        if count > 0:
            return 0

        try:
            from mappings import DEPARTMENT_MAPPING
            inserted = 0
            seen_names = set()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            for k, meta in DEPARTMENT_MAPPING.items():
                name = (meta.get("name") or "").strip()
                abbr = (meta.get("abbr") or "").strip()
                if not name or name.lower() in seen_names:
                    continue
                seen_names.add(name.lower())
                cursor.execute("""
                    INSERT INTO departments (
                        uuid, department_name, department_abbreviation,
                        department_address, department_additional_address,
                        department_addressee, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (str(uuid.uuid4()), name, abbr, "", "", "", now, now))
                inserted += 1

            conn.commit()
            return inserted
        except Exception as e:
            print(f"Failed to seed default departments: {e}")
            return 0

