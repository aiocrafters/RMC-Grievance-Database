from pathlib import Path
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from import_export import ImportSummary, import_file_to_database


class ImportWorker(QThread):
    finished_summary = Signal(object)  # ImportSummary
    failed = Signal(str)

    def __init__(self, file_path: str, db_path: str):
        super().__init__()
        self.file_path = file_path
        self.db_path = db_path

    def run(self):
        try:
            summary = import_file_to_database(self.file_path, self.db_path)
            self.finished_summary.emit(summary)
        except Exception as e:
            self.failed.emit(str(e))


class ImportDialog(QDialog):
    """Dialog for selecting and importing raw Excel / CSV grievance files."""

    def __init__(self, db_path: str, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.worker = None

        self.setWindowTitle("Import Grievance Data")
        self.resize(620, 480)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        desc = QLabel(
            "<b>Import Grievance Records</b><br>"
            "Select an Excel (<code>.xlsx</code>, <code>.xls</code>) or CSV file to extract, normalize, and update records."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # File Selection Bar
        file_layout = QHBoxLayout()
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("Select file to import...")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._on_browse)
        file_layout.addWidget(self.file_input)
        file_layout.addWidget(browse_btn)
        layout.addLayout(file_layout)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Summary / Logs Box
        summary_group = QGroupBox("Import Results & Logs")
        summary_layout = QVBoxLayout(summary_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("Import statistics and logs will appear here after processing...")
        summary_layout.addWidget(self.log_text)
        layout.addWidget(summary_group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)

        self.import_btn = QPushButton("Start Import")
        self.import_btn.setDefault(True)
        self.import_btn.setStyleSheet("background-color: #1E3A8A; color: white; font-weight: bold; padding: 6px 18px;")
        self.import_btn.clicked.connect(self._on_start_import)

        btn_layout.addWidget(self.close_btn)
        btn_layout.addWidget(self.import_btn)
        layout.addLayout(btn_layout)

    def _on_browse(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Grievance Export File",
            "",
            "Excel & CSV Files (*.xlsx *.xls *.csv);;Excel Files (*.xlsx *.xls);;CSV Files (*.csv);;All Files (*.*)",
        )
        if file_path:
            self.file_input.setText(file_path)

    def _on_start_import(self):
        target_file = self.file_input.text().strip()
        if not target_file:
            QMessageBox.warning(self, "No File", "Please select an input file to import.")
            return

        p = Path(target_file)
        if not p.exists():
            QMessageBox.critical(self, "File Not Found", f"The file '{target_file}' does not exist.")
            return

        self.import_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.log_text.setPlainText("Processing file and executing normalization pipeline...\nPlease wait...")

        self.worker = ImportWorker(target_file, self.db_path)
        self.worker.finished_summary.connect(self._on_import_finished)
        self.worker.failed.connect(self._on_import_failed)
        self.worker.start()

    def _on_import_finished(self, summary: ImportSummary):
        self.progress_bar.setVisible(False)
        self.import_btn.setEnabled(True)

        lines = [
            "==================================================",
            "IMPORT COMPLETED",
            "==================================================",
            f"Total Raw Rows Read:             {summary.total_input_rows}",
            f"Representations Inserted (New):  {summary.representations_inserted}",
            f"Representations Updated:         {summary.representations_updated}",
            f"Concerned Departments Created:   {summary.departments_processed}",
            f"Skipped Rows:                    {summary.skipped_count}",
        ]

        if summary.errors:
            lines.append("\nErrors / Warnings Encountered:")
            for err in summary.errors:
                lines.append(f"  • {err}")
        else:
            lines.append("\nStatus: All records imported and normalized successfully!")

        self.log_text.setPlainText("\n".join(lines))

        if not summary.errors:
            QMessageBox.information(
                self,
                "Import Successful",
                f"Successfully imported {summary.representations_inserted + summary.representations_updated} representations.",
            )
        else:
            QMessageBox.warning(
                self,
                "Import Finished with Warnings",
                "Import completed, but some warnings or errors occurred. Please check the log window.",
            )

    def _on_import_failed(self, err_msg: str):
        self.progress_bar.setVisible(False)
        self.import_btn.setEnabled(True)
        self.log_text.setPlainText(f"IMPORT FAILED:\n{err_msg}")
        QMessageBox.critical(self, "Import Error", f"An unexpected error occurred during import:\n{err_msg}")
