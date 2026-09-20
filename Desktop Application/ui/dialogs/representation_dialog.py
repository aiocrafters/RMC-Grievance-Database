import uuid
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import database
from core_logic import format_concerned_departments, format_to_full_date


class RepresentationDialog(QDialog):
    """Dialog for Adding or Editing a Representation and its Concerned Departments."""

    def __init__(self, db_path: str, rep_record: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.rep_record = rep_record
        self.is_edit_mode = rep_record is not None

        # Load master departments directory for autocompletion & mapping
        try:
            self.master_depts = database.get_departments(self.db_path)
            self.dept_name_to_abbr = {
                d["department_name"].strip().lower(): (d.get("department_abbreviation") or "").strip()
                for d in self.master_depts if d.get("department_name")
            }
        except Exception:
            self.master_depts = []
            self.dept_name_to_abbr = {}

        self.setWindowTitle("Edit Representation" if self.is_edit_mode else "Add Representation")
        self.resize(1000, 720)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(12)

        # 1. Primary Information Group
        primary_group = QGroupBox("Primary Representation Details")
        form1 = QFormLayout(primary_group)
        form1.setSpacing(8)

        self.comm_no_input = QLineEdit(rep_record.get("communication_number", "") if rep_record else "")
        self.comm_date_input = QLineEdit(rep_record.get("communication_date", "") if rep_record else "")
        self.comm_date_input.setPlaceholderText("DD MMMM YYYY (e.g. 02 September 2026)")
        self.serial_no_input = QLineEdit(rep_record.get("representation_serial_number", "") if rep_record else "")

        form1.addRow("Communication Number *:", self.comm_no_input)
        form1.addRow("Communication Date:", self.comm_date_input)
        form1.addRow("Representation Serial No *:", self.serial_no_input)

        self.channel_combo = QComboBox()
        self.channel_combo.addItems(["E-Office", "Manual / Hardcopy", "CPGRAMS", "Email", "Other"])
        if rep_record and rep_record.get("processing_channel"):
            self.channel_combo.setCurrentText(rep_record["processing_channel"])
        form1.addRow("Processing Channel:", self.channel_combo)

        self.grievance_id_input = QLineEdit(rep_record.get("grievance_id_computer_number", "") if rep_record else "")
        form1.addRow("Grievance ID / Comp No:", self.grievance_id_input)

        self.sent_on_input = QLineEdit(rep_record.get("sent_on", "") if rep_record else "")
        self.sent_on_input.setPlaceholderText("DD MMMM YYYY (e.g. 16 September 2026)")
        form1.addRow("Sent On Date:", self.sent_on_input)

        self.letter_no_input = QLineEdit(rep_record.get("letter_number", "") if rep_record else "")
        self.letter_date_input = QLineEdit(rep_record.get("letter_date", "") if rep_record else "")
        self.letter_date_input.setPlaceholderText("DD MMMM YYYY")
        form1.addRow("Letter Number:", self.letter_no_input)
        form1.addRow("Letter Date:", self.letter_date_input)

        self.remarks_input = QLineEdit(rep_record.get("remarks", "") if rep_record else "")
        form1.addRow("Remarks:", self.remarks_input)

        layout.addWidget(primary_group)

        # 2. Applicant & Subject Group
        applicant_group = QGroupBox("Applicant & Subject Details")
        form2 = QFormLayout(applicant_group)
        form2.setSpacing(8)

        self.applicant_name_input = QLineEdit(rep_record.get("applicant_name", "") if rep_record else "")
        form2.addRow("Applicant Name:", self.applicant_name_input)

        self.applicant_portal_input = QLineEdit(rep_record.get("applicant_name_on_portal", "") if rep_record else "")
        form2.addRow("Applicant On Portal (Email/Name):", self.applicant_portal_input)

        self.subject_portal_input = QTextEdit()
        self.subject_portal_input.setMaximumHeight(70)
        if rep_record:
            self.subject_portal_input.setPlainText(rep_record.get("representation_subject_on_portal", "") or "")
        form2.addRow("Representation Subject On Portal:", self.subject_portal_input)

        self.subject_input = QTextEdit()
        self.subject_input.setMaximumHeight(60)
        if rep_record:
            self.subject_input.setPlainText(rep_record.get("subject", "") or "")
        form2.addRow("Subject:", self.subject_input)

        layout.addWidget(applicant_group)

        # 3. Concerned Departments Table
        dept_group = QGroupBox("Concerned Department(s)")
        dept_layout = QVBoxLayout(dept_group)
        dept_layout.setSpacing(8)

        dept_toolbar = QHBoxLayout()
        dept_toolbar.addWidget(QLabel("Manage associated departments and E-Office receipt numbers:"))
        dept_toolbar.addStretch()

        add_dept_btn = QPushButton("+ Add Department")
        add_dept_btn.clicked.connect(self._add_dept_row)
        remove_dept_btn = QPushButton("- Remove Selected")
        remove_dept_btn.clicked.connect(self._remove_dept_row)

        dept_toolbar.addWidget(add_dept_btn)
        dept_toolbar.addWidget(remove_dept_btn)
        dept_layout.addLayout(dept_toolbar)

        self.dept_table = QTableWidget(0, 4)
        self.dept_table.setHorizontalHeaderLabels([
            "Concerned Department *",
            "Abbreviation",
            "E-Office Receipt Number *",
            "Location",
        ])
        self.dept_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.dept_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.dept_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.dept_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.dept_table.setMinimumHeight(140)
        self.dept_table.cellChanged.connect(self._on_dept_cell_changed)
        dept_layout.addWidget(self.dept_table)

        layout.addWidget(dept_group)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # Populate departments if editing
        if self.is_edit_mode and rep_record:
            existing_depts = database.get_departments_for_representation(self.db_path, rep_record["uuid"])
            for d in existing_depts:
                self._insert_dept_row_data(
                    d.get("concerned_department", ""),
                    d.get("concerned_department_abbreviation", ""),
                    d.get("eoffice_receipt_number", ""),
                    d.get("location", ""),
                    d.get("uuid"),
                )

        # Bottom Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save Representation")
        save_btn.setDefault(True)
        save_btn.setStyleSheet("background-color: #1E3A8A; color: white; font-weight: bold; padding: 6px 20px;")
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        main_layout.addLayout(btn_layout)

    def _on_dept_cell_changed(self, row: int, col: int):
        if col == 0:
            item_name = self.dept_table.item(row, 0)
            item_abbr = self.dept_table.item(row, 1)
            if item_name and item_abbr:
                raw_name = item_name.text().strip().lower()
                if raw_name in self.dept_name_to_abbr:
                    matched_abbr = self.dept_name_to_abbr[raw_name]
                    if matched_abbr and not item_abbr.text().strip():
                        self.dept_table.blockSignals(True)
                        item_abbr.setText(matched_abbr)
                        self.dept_table.blockSignals(False)

    def _add_dept_row(self):
        self._insert_dept_row_data("", "", "", "", None)

    def _insert_dept_row_data(self, dept_name: str, dept_abbr: str, receipt_no: str, location: str, dept_uuid: Optional[str]):
        row_idx = self.dept_table.rowCount()
        self.dept_table.blockSignals(True)
        self.dept_table.insertRow(row_idx)

        item_name = QTableWidgetItem(dept_name)
        item_abbr = QTableWidgetItem(dept_abbr)
        item_receipt = QTableWidgetItem(receipt_no)
        item_loc = QTableWidgetItem(location)

        if dept_uuid:
            item_name.setData(Qt.UserRole, dept_uuid)

        self.dept_table.setItem(row_idx, 0, item_name)
        self.dept_table.setItem(row_idx, 1, item_abbr)
        self.dept_table.setItem(row_idx, 2, item_receipt)
        self.dept_table.setItem(row_idx, 3, item_loc)
        self.dept_table.blockSignals(False)

    def _remove_dept_row(self):
        current_row = self.dept_table.currentRow()
        if current_row >= 0:
            self.dept_table.removeRow(current_row)

    def _on_save(self):
        comm_no = self.comm_no_input.text().strip()
        serial_no = self.serial_no_input.text().strip()

        if not comm_no:
            QMessageBox.warning(self, "Validation Error", "Communication Number is required.")
            return

        if not serial_no:
            QMessageBox.warning(self, "Validation Error", "Representation Serial Number is required.")
            return

        # Harvest departments
        depts_data = []
        for row in range(self.dept_table.rowCount()):
            name_item = self.dept_table.item(row, 0)
            abbr_item = self.dept_table.item(row, 1)
            receipt_item = self.dept_table.item(row, 2)
            loc_item = self.dept_table.item(row, 3)

            d_name = name_item.text().strip() if name_item else ""
            d_abbr = abbr_item.text().strip() if abbr_item else ""
            r_no = receipt_item.text().strip() if receipt_item else ""
            loc = loc_item.text().strip() if loc_item else ""

            if not d_name and not r_no:
                continue

            if not d_name:
                QMessageBox.warning(self, "Validation Error", f"Row {row+1}: Concerned Department is required.")
                return

            if not r_no:
                QMessageBox.warning(self, "Validation Error", f"Row {row+1}: E-Office Receipt Number is required.")
                return

            # Auto-map abbreviation from master table if missing
            if not d_abbr:
                d_abbr = self.dept_name_to_abbr.get(d_name.lower(), "")

            dept_uuid = name_item.data(Qt.UserRole) if name_item else None
            depts_data.append({
                "uuid": dept_uuid or str(uuid.uuid4()),
                "concerned_department": d_name,
                "concerned_department_abbreviation": d_abbr,
                "eoffice_receipt_number": r_no,
                "location": loc,
                "communication_number": comm_no,
                "communication_date": format_to_full_date(self.comm_date_input.text().strip()),
                "representation_serial_number": serial_no,
                "grievance_id_computer_number": self.grievance_id_input.text().strip(),
            })

        issue_type = "Multiple" if len(depts_data) > 1 else ("Single" if depts_data else "")
        concerned_depts_formatted = format_concerned_departments(depts_data)

        rep_data = {
            "communication_number": comm_no,
            "communication_date": format_to_full_date(self.comm_date_input.text().strip()),
            "representation_serial_number": serial_no,
            "applicant_name": self.applicant_name_input.text().strip(),
            "subject": self.subject_input.toPlainText().strip(),
            "applicant_name_on_portal": self.applicant_portal_input.text().strip(),
            "representation_subject_on_portal": self.subject_portal_input.toPlainText().strip(),
            "issue_type": issue_type,
            "remarks": self.remarks_input.text().strip(),
            "processing_channel": self.channel_combo.currentText(),
            "concerned_departments": concerned_depts_formatted,
            "grievance_id_computer_number": self.grievance_id_input.text().strip(),
            "sent_on": format_to_full_date(self.sent_on_input.text().strip()),
            "letter_number": self.letter_no_input.text().strip(),
            "letter_date": format_to_full_date(self.letter_date_input.text().strip()),
            "overall_atr_status": self.rep_record.get("overall_atr_status", "") if self.rep_record else "",
        }

        try:
            if self.is_edit_mode:
                rep_uuid = self.rep_record["uuid"]
                database.update_representation(self.db_path, rep_uuid, rep_data, depts_data)
            else:
                database.insert_representation_with_departments(self.db_path, rep_data, depts_data)

            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save representation: {str(e)}")
