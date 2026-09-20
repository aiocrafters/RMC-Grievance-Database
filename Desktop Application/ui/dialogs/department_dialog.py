from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

import database


class DepartmentDialog(QDialog):
    """Dialog for creating or editing a master department record."""

    def __init__(self, db_path: str, dept_data: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.dept_data = dept_data or {}
        self.is_edit = bool(dept_data and dept_data.get("uuid"))
        self.saved_uuid: Optional[str] = None

        title = "Edit Department" if self.is_edit else "Add New Department"
        self.setWindowTitle(title)
        self.setMinimumWidth(500)
        self.resize(540, 420)

        self._setup_ui()
        if self.is_edit:
            self._populate_fields()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header Title
        title_text = "Edit Department Details" if self.is_edit else "Register New Department"
        header_lbl = QLabel(title_text)
        header_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #1E3A8A;")
        layout.addWidget(header_lbl)

        sub_lbl = QLabel("Manage master department names, abbreviations, and dispatch address information.")
        sub_lbl.setStyleSheet("color: #64748B; font-size: 12px; margin-bottom: 6px;")
        layout.addWidget(sub_lbl)

        # Form Layout
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form_layout.setSpacing(10)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Health and Medical Education Department (Required)")
        form_layout.addRow("Department Name *:", self.name_input)

        self.abbr_input = QLineEdit()
        self.abbr_input.setPlaceholderText("e.g. H&ME or HME")
        form_layout.addRow("Abbreviation:", self.abbr_input)

        self.addressee_input = QLineEdit()
        self.addressee_input.setPlaceholderText("e.g. Administrative Secretary / Commissioner")
        form_layout.addRow("Addressee:", self.addressee_input)

        self.address_input = QTextEdit()
        self.address_input.setPlaceholderText("e.g. Civil Secretariat, Jammu / Srinagar")
        self.address_input.setMaximumHeight(65)
        form_layout.addRow("Address:", self.address_input)

        self.add_address_input = QTextEdit()
        self.add_address_input.setPlaceholderText("Additional routing notes, pin code, or office details")
        self.add_address_input.setMaximumHeight(65)
        form_layout.addRow("Additional Address:", self.add_address_input)

        layout.addLayout(form_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet("padding: 6px 14px;")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Save Department")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #1E3A8A;
                color: white;
                font-weight: bold;
                padding: 6px 18px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
        """)
        self.save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(self.save_btn)

        layout.addLayout(btn_layout)

    def _populate_fields(self):
        self.name_input.setText(self.dept_data.get("department_name", ""))
        self.abbr_input.setText(self.dept_data.get("department_abbreviation", ""))
        self.addressee_input.setText(self.dept_data.get("department_addressee", ""))
        self.address_input.setPlainText(self.dept_data.get("department_address", ""))
        self.add_address_input.setPlainText(self.dept_data.get("department_additional_address", ""))

    def _on_save(self):
        name = self.name_input.text().strip()
        abbr = self.abbr_input.text().strip()
        addressee = self.addressee_input.text().strip()
        address = self.address_input.toPlainText().strip()
        add_address = self.add_address_input.toPlainText().strip()

        if not name:
            QMessageBox.warning(self, "Validation Error", "Department Name is required.")
            self.name_input.setFocus()
            return

        # Check for duplicates
        exclude_uuid = self.dept_data.get("uuid") if self.is_edit else None
        if database.is_department_name_taken(self.db_path, name, exclude_uuid=exclude_uuid):
            QMessageBox.warning(
                self,
                "Duplicate Department",
                f"A department named '{name}' already exists in the database.\n"
                "Please use a distinct name or edit the existing department record."
            )
            self.name_input.setFocus()
            return

        dept_payload = {
            "department_name": name,
            "department_abbreviation": abbr,
            "department_addressee": addressee,
            "department_address": address,
            "department_additional_address": add_address,
        }

        try:
            if self.is_edit:
                dept_uuid = self.dept_data["uuid"]
                success = database.update_department(self.db_path, dept_uuid, dept_payload)
                if success:
                    self.saved_uuid = dept_uuid
                    self.accept()
                else:
                    QMessageBox.warning(self, "Error", "Failed to update department.")
            else:
                new_uuid = database.insert_department(self.db_path, dept_payload)
                self.saved_uuid = new_uuid
                self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"An error occurred while saving: {str(e)}")
