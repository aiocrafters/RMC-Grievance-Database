from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from import_export import DepartmentImportSummary, validate_and_import_departments_csv


class ImportDepartmentsDialog(QDialog):
    """Dialog for importing master departments from a CSV file with validation and error reporting."""

    def __init__(self, db_path: str, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.import_summary: Optional[DepartmentImportSummary] = None

        self.setWindowTitle("Import Master Departments (CSV)")
        self.resize(600, 480)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header
        header_lbl = QLabel("Import Departments from CSV")
        header_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #1E3A8A;")
        layout.addWidget(header_lbl)

        desc_lbl = QLabel(
            "Select a CSV file containing department records. The system will validate headers, "
            "enforce required fields, and prevent accidental duplicates."
        )
        desc_lbl.setStyleSheet("color: #64748B; font-size: 12px;")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        # File Chooser Box
        file_frame = QFrame()
        file_frame.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        file_layout = QHBoxLayout(file_frame)
        file_layout.setContentsMargins(6, 6, 6, 6)

        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("Select CSV file to import...")
        self.file_input.setReadOnly(True)
        file_layout.addWidget(self.file_input)

        browse_btn = QPushButton("📁 Browse...")
        browse_btn.setStyleSheet("padding: 6px 14px; background-color: #E2E8F0; font-weight: bold;")
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn)

        layout.addWidget(file_frame)

        # Options Box
        self.update_existing_chk = QCheckBox("Update existing department records if duplicate name is found")
        self.update_existing_chk.setToolTip("If unchecked, records with matching names will be safely skipped to avoid overwriting.")
        self.update_existing_chk.setChecked(False)
        layout.addWidget(self.update_existing_chk)

        # Progress / Status
        self.status_lbl = QLabel("Ready to validate and import.")
        self.status_lbl.setStyleSheet("font-weight: 500; color: #334155;")
        layout.addWidget(self.status_lbl)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        layout.addWidget(self.progress_bar)

        # Summary / Log Box
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("Import results, statistics, and validation errors will appear here...")
        self.log_output.setStyleSheet("""
            QTextEdit {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                font-family: Consolas, monospace;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.log_output, stretch=1)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.close_btn = QPushButton("Close")
        self.close_btn.setStyleSheet("padding: 6px 14px;")
        self.close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.close_btn)

        self.import_btn = QPushButton("📥 Start Import")
        self.import_btn.setStyleSheet("""
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
            QPushButton:disabled {
                background-color: #94A3B8;
            }
        """)
        self.import_btn.clicked.connect(self._run_import)
        self.import_btn.setEnabled(False)
        btn_layout.addWidget(self.import_btn)

        layout.addLayout(btn_layout)

    def _browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Department CSV File",
            "",
            "CSV Files (*.csv)",
        )
        if file_path:
            self.file_input.setText(file_path)
            self.import_btn.setEnabled(True)
            self.status_lbl.setText(f"Selected: {Path(file_path).name}")
            self.log_output.clear()

    def _run_import(self):
        file_path = self.file_input.text().strip()
        if not file_path:
            return

        self.import_btn.setEnabled(False)
        self.progress_bar.setValue(30)
        self.status_lbl.setText("Validating and importing CSV...")

        update_existing = self.update_existing_chk.isChecked()

        try:
            summary = validate_and_import_departments_csv(
                file_path=file_path,
                db_path=self.db_path,
                update_existing=update_existing,
            )
            self.import_summary = summary
            self.progress_bar.setValue(100)

            # Build readable summary report
            report_lines = [
                "==================================================",
                "       DEPARTMENT CSV IMPORT REPORT",
                "==================================================",
                f"Total Rows in CSV:          {summary.total_rows}",
                f"New Departments Inserted:   {summary.inserted_count}",
                f"Existing Records Updated:   {summary.updated_count}",
                f"Duplicate Records Skipped:  {summary.skipped_duplicate_count}",
                f"Errors / Validation Issues: {summary.error_count}",
                "==================================================",
            ]

            if summary.errors:
                report_lines.append("\nDETAILS & ERRORS:")
                for err in summary.errors:
                    report_lines.append(f"  • {err}")
            else:
                report_lines.append("\n✓ All rows processed with zero validation errors.")

            self.log_output.setPlainText("\n".join(report_lines))

            if summary.inserted_count > 0 or summary.updated_count > 0:
                self.status_lbl.setText(
                    f"Completed: {summary.inserted_count} added, {summary.updated_count} updated."
                )
                self.close_btn.setText("Done")
            else:
                self.status_lbl.setText("Import completed with no new records added.")

        except Exception as e:
            self.progress_bar.setValue(0)
            self.status_lbl.setText("Import failed!")
            self.log_output.setPlainText(f"Fatal Import Error:\n{str(e)}")
            QMessageBox.critical(self, "Import Error", f"An unexpected error occurred: {str(e)}")
        finally:
            self.import_btn.setEnabled(True)
