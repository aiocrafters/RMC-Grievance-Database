import os
import sys
from pathlib import Path

# Ensure Desktop Application folder is on Python path
app_dir = Path(__file__).resolve().parent
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import QApplication

import config
import database
from ui.dialogs.db_location_dialog import DbLocationDialog
from ui.main_window import MainWindow


def main():
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    app.setApplicationName("RMC Grievance Management System")
    app.setOrganizationName("RMC")

    # Set default modern clean font
    app_font = QFont("Segoe UI", 9)
    app.setFont(app_font)

    # Clean modern stylesheet
    app.setStyleSheet("""
        QMainWindow {
            background-color: #FFFFFF;
        }
        QTableView {
            background-color: #FFFFFF;
            alternate-background-color: #F8FAFC;
            gridline-color: #E2E8F0;
            selection-background-color: #DBEAFE;
            selection-color: #1E3A8A;
            border: 1px solid #CBD5E1;
            border-radius: 4px;
        }
        QLineEdit, QTextEdit, QComboBox {
            border: 1px solid #CBD5E1;
            border-radius: 4px;
            padding: 5px 8px;
            background-color: #FFFFFF;
        }
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
            border: 1.5px solid #2563EB;
        }
        QPushButton {
            border: 1px solid #CBD5E1;
            border-radius: 4px;
            padding: 5px 12px;
            background-color: #F8FAFC;
        }
        QPushButton:hover {
            background-color: #F1F5F9;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #E2E8F0;
            border-radius: 6px;
            margin-top: 10px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 10px;
            padding: 0 4px;
            color: #1E3A8A;
        }
    """)

    # 1. Determine Database Path
    db_path = config.get_database_path()

    # If first launch or db folder not set, prompt user
    if not db_path:
        setup_dlg = DbLocationDialog(is_initial_setup=True)
        if setup_dlg.exec():
            db_path = getattr(setup_dlg, "selected_db_path", None)
        else:
            sys.exit(0)

    if not db_path:
        sys.exit(0)

    # 2. Initialize Database Schema & Connection
    try:
        database.init_db(db_path)
    except Exception as e:
        print(f"Error initializing database: {e}")
        sys.exit(1)

    # 3. Launch Main Dashboard
    window = MainWindow(db_path)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
