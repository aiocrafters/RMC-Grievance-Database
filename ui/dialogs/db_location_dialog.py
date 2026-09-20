from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

import config


class DbLocationDialog(QDialog):
    """Dialog for choosing or updating the local database storage folder."""

    def __init__(self, parent=None, is_initial_setup: bool = False):
        super().__init__(parent)
        self.is_initial_setup = is_initial_setup
        self.setWindowTitle("Database Storage Location" if not is_initial_setup else "Initial Setup: Choose Database Location")
        self.setMinimumWidth(540)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        desc_text = (
            "<b>Welcome to RMC Grievance Management System.</b><br><br>"
            "Please select the folder where the local database file (<code>rmc_grievances.db</code>) will be stored.<br>"
            "The application will remember this location and run locally without requiring any external server."
        )
        desc_label = QLabel(desc_text)
        desc_label.setTextFormat(Qt.RichText)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Folder selection field
        folder_layout = QHBoxLayout()
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Select database directory...")

        current_folder = config.get_database_folder()
        if current_folder:
            self.folder_input.setText(current_folder)
        else:
            default_dir = str(Path(__file__).resolve().parent.parent.parent / "database")
            self.folder_input.setText(default_dir)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._on_browse)
        folder_layout.addWidget(self.folder_input)
        folder_layout.addWidget(browse_btn)
        layout.addLayout(folder_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        if not is_initial_setup:
            cancel_btn = QPushButton("Cancel")
            cancel_btn.clicked.connect(self.reject)
            btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save & Connect" if not is_initial_setup else "Continue")
        save_btn.setDefault(True)
        save_btn.setStyleSheet("background-color: #1E3A8A; color: white; font-weight: bold; padding: 6px 16px;")
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _on_browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Database Folder", self.folder_input.text())
        if folder:
            self.folder_input.setText(folder)

    def _on_save(self):
        chosen_folder = self.folder_input.text().strip()
        if not chosen_folder:
            QMessageBox.warning(self, "Validation Error", "Please specify a valid folder path.")
            return

        try:
            db_path = config.set_database_folder(chosen_folder)
            self.selected_db_path = db_path
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to set database folder: {str(e)}")
