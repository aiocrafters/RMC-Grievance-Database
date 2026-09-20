from typing import Any, Dict, List, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

import database
from import_export import export_departments_to_csv
from ui.dialogs.department_dialog import DepartmentDialog
from ui.dialogs.import_departments_dialog import ImportDepartmentsDialog

DEPT_COLUMNS = [
    ("department_name", "Department Name"),
    ("department_abbreviation", "Abbreviation"),
    ("department_address", "Address"),
    ("department_additional_address", "Additional Address"),
    ("department_addressee", "Addressee"),
    ("created_at", "Created At"),
]


class DepartmentTableModel(QAbstractTableModel):
    """Table Model for Master Departments Directory."""

    def __init__(self, data: List[Dict[str, Any]]):
        super().__init__()
        self._data = data

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(DEPT_COLUMNS) + 1  # +1 for Actions column

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        if role == Qt.DisplayRole:
            if col < len(DEPT_COLUMNS):
                key = DEPT_COLUMNS[col][0]
                val = self._data[row].get(key, "")
                return str(val) if val is not None else ""
            elif col == len(DEPT_COLUMNS):
                return "⋮"

        elif role == Qt.TextAlignmentRole:
            if col == len(DEPT_COLUMNS):
                return Qt.AlignCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        elif role == Qt.FontRole:
            if col == 0:
                font = QFont()
                font.setBold(True)
                return font

        elif role == Qt.BackgroundRole:
            if row % 2 == 1:
                return QColor("#F8FAFC")

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if section < len(DEPT_COLUMNS):
                return DEPT_COLUMNS[section][1]
            elif section == len(DEPT_COLUMNS):
                return "Actions"
        return None

    def set_data(self, data: List[Dict[str, Any]]):
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def get_record(self, row: int) -> Optional[Dict[str, Any]]:
        if 0 <= row < len(self._data):
            return self._data[row]
        return None


class DepartmentsPage(QWidget):
    """Dedicated Departments Management Screen."""

    department_changed = Signal()

    def __init__(self, db_path: str, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.current_departments: List[Dict[str, Any]] = []

        self._setup_ui()
        self.refresh_departments()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        # 1. Action Header Bar
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        title_lbl = QLabel("🏢  Master Departments Directory")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #1E3A8A;")
        header_layout.addWidget(title_lbl)

        header_layout.addStretch()

        self.add_btn = QPushButton("➕  Add Department")
        self.add_btn.setStyleSheet("background-color: #2563EB; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px;")
        self.add_btn.clicked.connect(self._open_add_dialog)
        header_layout.addWidget(self.add_btn)

        self.import_btn = QPushButton("📥  Import CSV")
        self.import_btn.setStyleSheet("background-color: #1E3A8A; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px;")
        self.import_btn.clicked.connect(self._open_import_dialog)
        header_layout.addWidget(self.import_btn)

        self.export_btn = QPushButton("📤  Export CSV")
        self.export_btn.setStyleSheet("background-color: #047857; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px;")
        self.export_btn.clicked.connect(self._export_csv)
        header_layout.addWidget(self.export_btn)

        self.seed_btn = QPushButton("🌱  Seed Defaults")
        self.seed_btn.setToolTip("Seed standard government departments from system dictionary if directory is empty.")
        self.seed_btn.clicked.connect(self._seed_defaults)
        header_layout.addWidget(self.seed_btn)

        self.refresh_btn = QPushButton("🔄  Refresh")
        self.refresh_btn.clicked.connect(self.refresh_departments)
        header_layout.addWidget(self.refresh_btn)

        layout.addLayout(header_layout)

        # 2. Search Bar Frame
        search_frame = QFrame()
        search_frame.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(10, 6, 10, 6)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍  Search by Department Name, Abbreviation, Address, or Addressee...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_input)

        clear_search_btn = QPushButton("Clear")
        clear_search_btn.clicked.connect(self.search_input.clear)
        search_layout.addWidget(clear_search_btn)

        layout.addWidget(search_frame)

        # 3. Table View
        self.table_view = QTableView()
        self.table_model = DepartmentTableModel([])
        self.table_view.setModel(self.table_model)

        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QTableView.SelectRows)
        self.table_view.setSelectionMode(QTableView.SingleSelection)
        self.table_view.setWordWrap(True)
        self.table_view.verticalHeader().setDefaultSectionSize(40)

        # Double click to edit
        self.table_view.doubleClicked.connect(self._on_row_double_clicked)
        self.table_view.clicked.connect(self._on_cell_clicked)

        # Header styling
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

        layout.addWidget(self.table_view)

        # 4. Status Bar / Count Footer
        self.status_lbl = QLabel("Showing 0 departments")
        self.status_lbl.setStyleSheet("color: #475569; font-size: 12px; font-weight: 500;")
        layout.addWidget(self.status_lbl)

        # Search debounce timer
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.refresh_departments)

    def _on_search_changed(self):
        self.search_timer.start(250)

    def refresh_departments(self):
        search_query = self.search_input.text().strip() or None
        try:
            records = database.get_departments(self.db_path, search_query=search_query)
            self.current_departments = records
            self.table_model.set_data(records)

            all_records = database.get_departments(self.db_path)
            self.status_lbl.setText(f"Showing {len(records)} of {len(all_records)} master departments")

            self._adjust_column_widths()
        except Exception as e:
            self.status_lbl.setText(f"Error loading departments: {str(e)}")

    def _adjust_column_widths(self):
        widths = {
            0: 280,  # Department Name
            1: 120,  # Abbreviation
            2: 240,  # Address
            3: 200,  # Additional Address
            4: 180,  # Addressee
            5: 140,  # Created At
            6: 60,   # Actions (⋮)
        }
        for col_idx, width in widths.items():
            self.table_view.setColumnWidth(col_idx, width)
        self.table_view.resizeRowsToContents()

    def _on_cell_clicked(self, index: QModelIndex):
        if index.column() == len(DEPT_COLUMNS):
            # Clicked on Actions column
            self._show_actions_menu(index.row())

    def _on_row_double_clicked(self, index: QModelIndex):
        if index.isValid() and index.column() != len(DEPT_COLUMNS):
            record = self.table_model.get_record(index.row())
            if record:
                self._edit_department(record)

    def _show_actions_menu(self, row: int):
        record = self.table_model.get_record(row)
        if not record:
            return

        menu = QMenu(self)
        edit_action = menu.addAction("✏️  Edit Department")
        delete_action = menu.addAction("🗑️  Delete Department")

        # Map to global position
        action = menu.exec(self.cursor().pos())
        if action == edit_action:
            self._edit_department(record)
        elif action == delete_action:
            self._delete_department(record)

    def _open_add_dialog(self):
        dlg = DepartmentDialog(self.db_path, None, self)
        if dlg.exec():
            self.refresh_departments()
            self.department_changed.emit()

    def _edit_department(self, record: Dict[str, Any]):
        dlg = DepartmentDialog(self.db_path, record, self)
        if dlg.exec():
            self.refresh_departments()
            self.department_changed.emit()

    def _delete_department(self, record: Dict[str, Any]):
        dept_name = record.get("department_name", "")
        dept_uuid = record.get("uuid", "")

        # Check references in concerned_departments
        ref_count = database.count_department_references(self.db_path, dept_name)
        warning_extra = ""
        if ref_count > 0:
            warning_extra = (
                f"\n\n⚠️ CAUTION: This department is currently referenced in {ref_count} "
                f"representation(s) in the database.\n"
                f"Existing representation records will retain their text, but this department "
                f"will be removed from the master directory."
            )

        confirm = QMessageBox.question(
            self,
            "Confirm Delete Department",
            f"Are you sure you want to delete '{dept_name}' from the master departments directory?{warning_extra}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if confirm == QMessageBox.Yes:
            success = database.delete_department(self.db_path, dept_uuid)
            if success:
                self.refresh_departments()
                self.department_changed.emit()
            else:
                QMessageBox.warning(self, "Delete Failed", "Could not delete the department record.")

    def _open_import_dialog(self):
        dlg = ImportDepartmentsDialog(self.db_path, self)
        dlg.exec()
        self.refresh_departments()
        self.department_changed.emit()

    def _export_csv(self):
        if not self.current_departments:
            QMessageBox.information(self, "Export", "No department records to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Departments to CSV",
            "Master_Departments.csv",
            "CSV Files (*.csv)",
        )
        if file_path:
            try:
                export_departments_to_csv(self.current_departments, file_path)
                QMessageBox.information(self, "Export Successful", f"Departments exported successfully to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export CSV: {str(e)}")

    def _seed_defaults(self):
        confirm = QMessageBox.question(
            self,
            "Seed Standard Departments",
            "Do you want to seed standard government departments into the directory from the system dictionary?\n\n"
            "Existing departments will not be overwritten.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if confirm == QMessageBox.Yes:
            count = database.seed_default_departments_if_empty(self.db_path)
            if count > 0:
                QMessageBox.information(self, "Seeding Complete", f"Successfully seeded {count} standard departments.")
            else:
                QMessageBox.information(self, "Seeding Info", "Departments directory already contains records.")
            self.refresh_departments()
            self.department_changed.emit()
