from typing import Any, Dict, List
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
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
    QVBoxLayout,
    QWidget,
)

import database
from core_logic import format_to_full_date


class AtrManagementDialog(QDialog):
    """Dialog for viewing, adding, and managing Action Taken Reports (ATR) for each concerned department."""

    def __init__(self, db_path: str, rep_record: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.rep_record = rep_record
        self.rep_uuid = rep_record["uuid"]

        self.setWindowTitle(f"ATR Management - S.No. {rep_record.get('representation_serial_number', '')} ({rep_record.get('communication_number', '')})")
        self.resize(800, 560)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)

        # Header Info Banner
        header_group = QGroupBox("Representation Details")
        header_layout = QFormLayout(header_group)
        header_layout.setContentsMargins(12, 12, 12, 12)

        comm_str = f"{rep_record.get('communication_number', '')} | Serial: {rep_record.get('representation_serial_number', '')}"
        header_layout.addRow("Communication & Serial:", QLabel(comm_str))

        subj = rep_record.get("representation_subject_on_portal") or rep_record.get("subject") or "N/A"
        subj_lbl = QLabel(subj)
        subj_lbl.setWordWrap(True)
        subj_lbl.setMaximumHeight(60)
        header_layout.addRow("Subject:", subj_lbl)

        self.overall_status_lbl = QLabel(rep_record.get("overall_atr_status") or "<i>(Empty)</i>")
        self.overall_status_lbl.setTextFormat(Qt.RichText)
        self.overall_status_lbl.setStyleSheet("font-weight: bold; color: #1E3A8A;")
        header_layout.addRow("Current Overall ATR Status:", self.overall_status_lbl)

        main_layout.addWidget(header_group)

        # Concerned Departments ATR List
        main_layout.addWidget(QLabel("<b>Concerned Departments & ATR Actions:</b>"))

        self.departments = database.get_departments_for_representation(self.db_path, self.rep_uuid)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        self.dept_cards_layout = QVBoxLayout(scroll_content)
        self.dept_cards_layout.setSpacing(10)

        self.dept_widgets = []
        common_statuses = [
            "",
            "Sent",
            "Inside File",
            "Under Process",
            "Resolved",
            "Disposed",
            "Closed",
            "Rejected",
            "Pending",
        ]

        if not self.departments:
            empty_lbl = QLabel("No concerned departments are associated with this representation.")
            empty_lbl.setStyleSheet("color: #64748B; font-style: italic;")
            self.dept_cards_layout.addWidget(empty_lbl)
        else:
            for dept in self.departments:
                dept_group = QGroupBox(f"{dept.get('concerned_department', 'Unknown Dept')} ({dept.get('concerned_department_abbreviation', '')})")
                form = QFormLayout(dept_group)
                form.setContentsMargins(12, 10, 12, 10)

                receipt_lbl = QLabel(dept.get("eoffice_receipt_number") or "N/A")
                form.addRow("E-Office Receipt No:", receipt_lbl)

                status_combo = QComboBox()
                status_combo.setEditable(True)
                status_combo.addItems(common_statuses)
                current_status = dept.get("atr_status") or ""
                if current_status not in common_statuses:
                    status_combo.addItem(current_status)
                status_combo.setCurrentText(current_status)
                form.addRow("ATR Status:", status_combo)

                atr_no_input = QLineEdit(dept.get("atr_number") or "")
                form.addRow("ATR Number:", atr_no_input)

                atr_date_input = QLineEdit(dept.get("atr_date") or "")
                atr_date_input.setPlaceholderText("DD MMMM YYYY (e.g. 15 October 2026)")
                form.addRow("ATR Date:", atr_date_input)

                atr_comp_input = QLineEdit(dept.get("atr_computer_number") or "")
                form.addRow("ATR Computer Number:", atr_comp_input)

                location_input = QLineEdit(dept.get("location") or "")
                form.addRow("Location:", location_input)

                self.dept_cards_layout.addWidget(dept_group)
                self.dept_widgets.append({
                    "dept_uuid": dept["uuid"],
                    "status_combo": status_combo,
                    "atr_no_input": atr_no_input,
                    "atr_date_input": atr_date_input,
                    "atr_comp_input": atr_comp_input,
                    "location_input": location_input,
                })

        self.dept_cards_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save ATR Information")
        save_btn.setDefault(True)
        save_btn.setStyleSheet("background-color: #1E3A8A; color: white; font-weight: bold; padding: 6px 18px;")
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        main_layout.addLayout(btn_layout)

    def _on_save(self):
        try:
            for w in self.dept_widgets:
                raw_date = w["atr_date_input"].text().strip()
                formatted_date = format_to_full_date(raw_date) if raw_date else ""

                atr_data = {
                    "atr_status": w["status_combo"].currentText().strip(),
                    "atr_number": w["atr_no_input"].text().strip(),
                    "atr_date": formatted_date,
                    "atr_computer_number": w["atr_comp_input"].text().strip(),
                    "location": w["location_input"].text().strip(),
                }
                database.update_department_atr(self.db_path, w["dept_uuid"], atr_data)

            QMessageBox.information(self, "Success", "ATR information saved and Overall ATR Status recalculated successfully.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save ATR details: {str(e)}")
