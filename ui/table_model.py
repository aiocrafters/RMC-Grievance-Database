from typing import Any, Dict, List, Optional
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor

COLUMNS = [
    "Communication Number",
    "Communication Date",
    "Representation Serial Number",
    "Applicant Name",
    "Subject",
    "Applicant Name On Portal",
    "Representation Subject On Portal",
    "Issue Type (Single / Multiple)",
    "Remarks",
    "Processing Channel",
    "Concerned Department(s)",
    "Grievance ID / Computer Number",
    "Sent On",
    "Letter Number",
    "Letter Date",
    "Overall ATR Status",
    "Actions",
]

COLUMN_KEYS = [
    "communication_number",
    "communication_date",
    "representation_serial_number",
    "applicant_name",
    "subject",
    "applicant_name_on_portal",
    "representation_subject_on_portal",
    "issue_type",
    "remarks",
    "processing_channel",
    "concerned_departments",
    "grievance_id_computer_number",
    "sent_on",
    "letter_number",
    "letter_date",
    "overall_atr_status",
    "_actions",
]


class RepresentationTableModel(QAbstractTableModel):
    """Data model for the Representations table view."""

    def __init__(self, data: Optional[List[Dict[str, Any]]] = None):
        super().__init__()
        self._data: List[Dict[str, Any]] = data or []

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._data)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLUMNS)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        if row >= len(self._data) or col >= len(COLUMNS):
            return None

        record = self._data[row]
        key = COLUMN_KEYS[col]

        if role == Qt.DisplayRole:
            if key == "_actions":
                return "⋮"
            val = record.get(key, "")
            return "" if val is None else str(val)

        elif role == Qt.TextAlignmentRole:
            # Numbers and status centered; text left-aligned
            if key in ("representation_serial_number", "_actions"):
                return Qt.AlignCenter
            elif key in ("communication_date", "sent_on", "letter_date", "issue_type", "grievance_id_computer_number"):
                return Qt.AlignCenter
            return Qt.AlignLeft | Qt.AlignTop

        elif role == Qt.BackgroundRole:
            # Highlight missing gap rows with a subtle soft tint
            remarks = str(record.get("remarks", "")).lower()
            if "missing" in remarks:
                return QColor("#FEF2F2")  # Light subtle red/pink
            # Alternating row background handled by QTableView or default
            return None

        elif role == Qt.ToolTipRole:
            if key == "_actions":
                return "Click to view actions (ATR, Edit, Update, Delete)"
            val = record.get(key, "")
            return str(val) if val else None

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return COLUMNS[section]
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            return str(section + 1)
        return None

    def set_data(self, new_data: List[Dict[str, Any]]) -> None:
        """Updates the table data and refreshes view."""
        self.beginResetModel()
        self._data = new_data
        self.endResetModel()

    def get_record(self, row: int) -> Optional[Dict[str, Any]]:
        """Returns the dictionary for the specified row index."""
        if 0 <= row < len(self._data):
            return self._data[row]
        return None
