from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

import database
from import_export import export_to_csv, export_to_excel, export_to_pdf


class ExportDialog(QDialog):
    """Dialog for exporting representations data to CSV, Excel, or PDF."""

    def __init__(
        self,
        db_path: str,
        filtered_reps: Optional[List[Dict[str, Any]]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.db_path = db_path
        self.filtered_reps = filtered_reps or []

        self.setWindowTitle("Export Representations Data")
        self.resize(520, 360)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        # 1. Format Selection
        format_group = QGroupBox("Select Export Format")
        fmt_layout = QVBoxLayout(format_group)
        self.rb_excel = QRadioButton("Excel Workbook (.xlsx) - Includes Representations and Departments sheets")
        self.rb_csv = QRadioButton("Comma Separated Values (.csv)")
        self.rb_pdf = QRadioButton("PDF Document (.pdf) - Professional multi-page report")

        self.rb_excel.setChecked(True)
        fmt_layout.addWidget(self.rb_excel)
        fmt_layout.addWidget(self.rb_csv)
        fmt_layout.addWidget(self.rb_pdf)
        layout.addWidget(format_group)

        # 2. Scope Selection
        scope_group = QGroupBox("Select Data Scope")
        scope_layout = QVBoxLayout(scope_group)
        self.rb_all = QRadioButton("Export all records in the database")
        self.rb_filtered = QRadioButton(f"Export currently filtered / searched records ({len(self.filtered_reps)} records)")

        if self.filtered_reps:
            self.rb_filtered.setChecked(True)
        else:
            self.rb_all.setChecked(True)
            self.rb_filtered.setEnabled(False)

        scope_layout.addWidget(self.rb_all)
        scope_layout.addWidget(self.rb_filtered)
        layout.addWidget(scope_group)

        # 3. Output Path
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Choose destination file path...")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._on_browse)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)

        # Set default path in user documents or default output dir
        default_dir = Path(__file__).resolve().parent.parent.parent / "output"
        default_dir.mkdir(parents=True, exist_ok=True)
        self.path_input.setText(str(default_dir / "Representations_Export.xlsx"))

        self.rb_excel.toggled.connect(self._update_extension)
        self.rb_csv.toggled.connect(self._update_extension)
        self.rb_pdf.toggled.connect(self._update_extension)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        export_btn = QPushButton("Export Now")
        export_btn.setDefault(True)
        export_btn.setStyleSheet("background-color: #1E3A8A; color: white; font-weight: bold; padding: 6px 20px;")
        export_btn.clicked.connect(self._on_export)
        btn_layout.addWidget(export_btn)

        layout.addLayout(btn_layout)

    def _update_extension(self):
        cur_path = self.path_input.text().strip()
        if not cur_path:
            return
        p = Path(cur_path)
        stem = p.stem
        parent = p.parent

        if self.rb_excel.isChecked():
            new_path = parent / f"{stem}.xlsx"
        elif self.rb_csv.isChecked():
            new_path = parent / f"{stem}.csv"
        else:
            new_path = parent / f"{stem}.pdf"

        self.path_input.setText(str(new_path))

    def _on_browse(self):
        if self.rb_excel.isChecked():
            file_filter = "Excel Files (*.xlsx);;All Files (*.*)"
            default_ext = "xlsx"
        elif self.rb_csv.isChecked():
            file_filter = "CSV Files (*.csv);;All Files (*.*)"
            default_ext = "csv"
        else:
            file_filter = "PDF Documents (*.pdf);;All Files (*.*)"
            default_ext = "pdf"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Export File As",
            self.path_input.text(),
            file_filter,
        )
        if file_path:
            if not file_path.lower().endswith(f".{default_ext}"):
                file_path += f".{default_ext}"
            self.path_input.setText(file_path)

    def _on_export(self):
        target_path = self.path_input.text().strip()
        if not target_path:
            QMessageBox.warning(self, "Missing Path", "Please select a destination file path.")
            return

        # Fetch records based on scope
        if self.rb_filtered.isChecked() and self.filtered_reps:
            records_to_export = self.filtered_reps
        else:
            records_to_export = database.get_representations(self.db_path)

        if not records_to_export:
            QMessageBox.warning(self, "No Records", "There are no records to export.")
            return

        try:
            if self.rb_excel.isChecked():
                export_to_excel(records_to_export, target_path, db_path=self.db_path)
            elif self.rb_csv.isChecked():
                export_to_csv(records_to_export, target_path, include_departments=True, db_path=self.db_path)
            else:
                export_to_pdf(records_to_export, target_path)

            QMessageBox.information(
                self,
                "Export Successful",
                f"Successfully exported {len(records_to_export)} records to:\n{target_path}",
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export data: {str(e)}")
