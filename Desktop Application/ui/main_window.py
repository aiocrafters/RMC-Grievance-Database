from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTableView,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

import config
import database
from ui.action_delegate import ActionDelegate
from ui.dialogs.atr_dialog import AtrManagementDialog
from ui.dialogs.db_location_dialog import DbLocationDialog
from ui.dialogs.export_dialog import ExportDialog
from ui.dialogs.import_dialog import ImportDialog
from ui.dialogs.representation_dialog import RepresentationDialog
from ui.table_model import COLUMNS, RepresentationTableModel


class MainWindow(QMainWindow):
    """Main Application Dashboard Window for RMC Grievance Management."""

    def __init__(self, db_path: str):
        super().__init__()
        self.db_path = db_path

        self.setWindowTitle("RMC Grievance Management System - Dashboard")
        self.resize(1340, 780)

        self._setup_ui()
        self._load_filter_options()
        self.refresh_data()

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(12)

        # 1. Top Action Bar
        top_bar_layout = QHBoxLayout()
        top_bar_layout.setSpacing(10)

        app_title = QLabel("RMC Grievance Dashboard")
        app_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1E3A8A;")
        top_bar_layout.addWidget(app_title)
        top_bar_layout.addStretch()

        self.import_btn = QPushButton("📥  Import Data (CSV/Excel)")
        self.import_btn.setStyleSheet("background-color: #1E3A8A; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px;")
        self.import_btn.clicked.connect(self._open_import_dialog)

        self.export_btn = QPushButton("📤  Export (CSV/Excel/PDF)")
        self.export_btn.setStyleSheet("background-color: #047857; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px;")
        self.export_btn.clicked.connect(self._open_export_dialog)

        self.add_rep_btn = QPushButton("➕  Add Representation")
        self.add_rep_btn.setStyleSheet("background-color: #2563EB; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px;")
        self.add_rep_btn.clicked.connect(self._open_add_dialog)

        self.refresh_btn = QPushButton("🔄  Refresh")
        self.refresh_btn.clicked.connect(self.refresh_data)

        self.db_settings_btn = QPushButton("📁  Database Location")
        self.db_settings_btn.clicked.connect(self._open_db_location_dialog)

        top_bar_layout.addWidget(self.import_btn)
        top_bar_layout.addWidget(self.export_btn)
        top_bar_layout.addWidget(self.add_rep_btn)
        top_bar_layout.addWidget(self.refresh_btn)
        top_bar_layout.addWidget(self.db_settings_btn)

        main_layout.addLayout(top_bar_layout)

        # 2. Filter & Search Bar
        filter_frame = QFrame()
        filter_frame.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(10, 8, 10, 8)
        filter_layout.setSpacing(10)

        # Search Bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍  Search Communication No, Serial No, Applicant, Subject, Grievance ID, ATR...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._on_search_changed)
        filter_layout.addWidget(self.search_input, stretch=3)

        # Filter: Comm No
        self.comm_combo = QComboBox()
        self.comm_combo.addItem("All Comm Numbers", "")
        self.comm_combo.currentIndexChanged.connect(self.refresh_data)
        filter_layout.addWidget(self.comm_combo, stretch=1)

        # Filter: Issue Type
        self.issue_combo = QComboBox()
        self.issue_combo.addItem("All Issue Types", "")
        self.issue_combo.addItem("Single", "Single")
        self.issue_combo.addItem("Multiple", "Multiple")
        self.issue_combo.currentIndexChanged.connect(self.refresh_data)
        filter_layout.addWidget(self.issue_combo, stretch=1)

        # Filter: Department
        self.dept_combo = QComboBox()
        self.dept_combo.addItem("All Departments", "")
        self.dept_combo.currentIndexChanged.connect(self.refresh_data)
        filter_layout.addWidget(self.dept_combo, stretch=2)

        # Clear Filters Button
        clear_btn = QPushButton("Reset Filters")
        clear_btn.clicked.connect(self._clear_filters)
        filter_layout.addWidget(clear_btn)

        main_layout.addWidget(filter_frame)

        # 3. Representations Table View
        self.table_view = QTableView()
        self.table_model = RepresentationTableModel([])
        self.table_view.setModel(self.table_model)

        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QTableView.SelectRows)
        self.table_view.setSelectionMode(QTableView.SingleSelection)
        self.table_view.setWordWrap(True)
        self.table_view.verticalHeader().setDefaultSectionSize(42)

        # Setup Action Delegate for the 3-dot (⋮) menu column (index 16)
        self.action_delegate = ActionDelegate(self)
        self.action_delegate.action_triggered.connect(self._handle_action)
        self.table_view.setItemDelegateForColumn(16, self.action_delegate)

        # Double click to edit
        self.table_view.doubleClicked.connect(self._on_row_double_clicked)

        # Header styling and resizing
        header = self.table_view.horizontalHeader()
        header.setStretchLastSection(False)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setStyleSheet("""
            QHeaderView::section {
                background-color: #1E3A8A;
                color: white;
                font-weight: bold;
                padding: 6px 8px;
                border: none;
                border-right: 1px solid #3B82F6;
            }
        """)

        main_layout.addWidget(self.table_view)

        # 4. Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.db_status_lbl = QLabel(f"Database: {self.db_path}")
        self.count_status_lbl = QLabel("Records: 0")
        self.status_bar.addWidget(self.count_status_lbl, 1)
        self.status_bar.addPermanentWidget(self.db_status_lbl)

        # Debounce timer for search
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.refresh_data)

    def _on_search_changed(self):
        self.search_timer.start(300)

    def _clear_filters(self):
        self.search_input.clear()
        self.comm_combo.setCurrentIndex(0)
        self.issue_combo.setCurrentIndex(0)
        self.dept_combo.setCurrentIndex(0)
        self.refresh_data()

    def _load_filter_options(self):
        try:
            options = database.get_filter_options(self.db_path)
            self.comm_combo.blockSignals(True)
            self.comm_combo.clear()
            self.comm_combo.addItem("All Comm Numbers", "")
            for c in options.get("communication_numbers", []):
                self.comm_combo.addItem(c, c)
            self.comm_combo.blockSignals(False)

            self.dept_combo.blockSignals(True)
            self.dept_combo.clear()
            self.dept_combo.addItem("All Departments", "")
            for d in options.get("concerned_departments", []):
                self.dept_combo.addItem(d, d)
            self.dept_combo.blockSignals(False)
        except Exception:
            pass

    def refresh_data(self):
        search_query = self.search_input.text().strip() or None
        filters = {}

        comm_no = self.comm_combo.currentData()
        if comm_no:
            filters["communication_number"] = comm_no

        issue_type = self.issue_combo.currentData()
        if issue_type:
            filters["issue_type"] = issue_type

        dept = self.dept_combo.currentData()
        if dept:
            filters["concerned_department"] = dept

        try:
            records = database.get_representations(self.db_path, search_query=search_query, filters=filters)
            self.current_records = records
            self.table_model.set_data(records)

            total_in_db = database.count_representations(self.db_path)
            self.count_status_lbl.setText(f"Showing {len(records)} of {total_in_db} records")

            # Apply column widths
            self._adjust_column_widths()
        except Exception as e:
            self.status_bar.showMessage(f"Error loading records: {str(e)}", 5000)

    def _adjust_column_widths(self):
        widths = {
            0: 150,  # Communication Number
            1: 110,  # Communication Date
            2: 70,   # S.No
            3: 140,  # Applicant Name
            4: 180,  # Subject
            5: 180,  # Applicant On Portal
            6: 280,  # Subject On Portal
            7: 90,   # Issue Type
            8: 140,  # Remarks
            9: 100,  # Processing Channel
            10: 320, # Concerned Department(s)
            11: 110, # Grievance ID
            12: 110, # Sent On
            13: 110, # Letter Number
            14: 110, # Letter Date
            15: 110, # Overall ATR Status
            16: 60,  # Actions (⋮)
        }
        for col_idx, width in widths.items():
            self.table_view.setColumnWidth(col_idx, width)
        self.table_view.resizeRowsToContents()

    def _handle_action(self, action_name: str, row_index: int):
        record = self.table_model.get_record(row_index)
        if not record:
            return

        if action_name == "atr":
            dlg = AtrManagementDialog(self.db_path, record, self)
            if dlg.exec():
                self.refresh_data()
                self._load_filter_options()

        elif action_name == "edit" or action_name == "update":
            dlg = RepresentationDialog(self.db_path, record, self)
            if dlg.exec():
                self.refresh_data()
                self._load_filter_options()

        elif action_name == "delete":
            serial = record.get("representation_serial_number", "")
            comm = record.get("communication_number", "")
            confirm = QMessageBox.question(
                self,
                "Confirm Deletion",
                f"Are you sure you want to delete Representation Serial '{serial}' ({comm})?\n\n"
                "This action will also delete all associated Concerned Department records permanently.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if confirm == QMessageBox.Yes:
                success = database.delete_representation(self.db_path, record["uuid"])
                if success:
                    self.refresh_data()
                    self._load_filter_options()
                    self.status_bar.showMessage("Record deleted successfully.", 3000)
                else:
                    QMessageBox.warning(self, "Error", "Failed to delete record.")

    def _on_row_double_clicked(self, index):
        if index.isValid() and index.column() != 16:
            record = self.table_model.get_record(index.row())
            if record:
                dlg = RepresentationDialog(self.db_path, record, self)
                if dlg.exec():
                    self.refresh_data()
                    self._load_filter_options()

    def _open_add_dialog(self):
        dlg = RepresentationDialog(self.db_path, None, self)
        if dlg.exec():
            self.refresh_data()
            self._load_filter_options()

    def _open_import_dialog(self):
        dlg = ImportDialog(self.db_path, self)
        dlg.exec()
        self.refresh_data()
        self._load_filter_options()

    def _open_export_dialog(self):
        dlg = ExportDialog(self.db_path, getattr(self, "current_records", []), self)
        dlg.exec()

    def _open_db_location_dialog(self):
        dlg = DbLocationDialog(self, is_initial_setup=False)
        if dlg.exec():
            new_path = getattr(dlg, "selected_db_path", None)
            if new_path:
                self.db_path = new_path
                database.init_db(self.db_path)
                self.db_status_lbl.setText(f"Database: {self.db_path}")
                self._load_filter_options()
                self.refresh_data()
                QMessageBox.information(self, "Database Changed", f"Connected to database at:\n{self.db_path}")
