# RMC Grievance Management Desktop Application

A standalone Python desktop application for grievance data extraction, normalization, database management, and reporting.

---

## Features

- **Local Database**: Built with SQLite (zero external server setup), WAL mode, and cascading relationships.
- **Configurable Location**: Choose your own database folder; the application automatically remembers your selection.
- **Interactive Dashboard**:
  - Full-text search across all fields.
  - Dropdown filters for Communication Number, Issue Type, Concerned Department, and ATR Status.
  - Responsive table with multi-line text wrapping for subjects and departments.
- **Three-Dot (`⋮`) Actions Menu**:
  - **ATR Management**: View, add, and update Action Taken Reports per department, automatically recalculating the parent representation's Overall ATR Status.
  - **Edit Representation**: Edit communication details, remarks, and modify associated departments in a sub-table.
  - **Quick Update**: Save updates directly.
  - **Delete Record**: Safely delete a representation with confirmation and automatic cascade removal of child department records.
- **Import Engine**: Import `.xlsx`, `.xls`, or `.csv` files with intelligent regex parsing, department fuzzy resolution, Roman numeral multi-line formatting, and sequence gap detection. Runs in a background thread with progress indicator and review logs.
- **Export Engine**: Export records to **Excel (`.xlsx`)**, **CSV**, or **PDF** (multi-page landscape report via ReportLab).

---

## How to Run

### From the Project Root:
```bash
python "Desktop Application/app.py"
```

### Or from within this directory:
```bash
cd "Desktop Application"
python app.py
```

---

## Architecture & Structure

```text
Desktop Application/
├── app.py                     # Application entry point (PySide6 / Qt6)
├── config.py                  # Local database path persistence (app_config.json)
├── database.py                # SQLite schema, queries, cascade deletions & CRUD
├── core_logic.py              # Data extraction, subject regex parsing, department resolver
├── import_export.py           # Importers (CSV/Excel) and Exporters (CSV, Excel, PDF)
├── mappings.py                # Department mappings, columns, and default static values
├── README.md                  # Desktop application documentation
└── ui/
    ├── main_window.py         # Main dashboard, search/filter controls, table view
    ├── table_model.py         # QAbstractTableModel for fast tabular rendering
    ├── action_delegate.py     # Custom delegate for three-dot (⋮) Actions menu
    └── dialogs/
        ├── db_location_dialog.py      # Dialog to configure/change database storage folder
        ├── representation_dialog.py   # Dialog to Add/Edit representations & departments
        ├── atr_dialog.py              # Dialog for ATR management and status recalculation
        ├── import_dialog.py           # Background import dialog with progress and summary
        └── export_dialog.py           # Export dialog for CSV, Excel (.xlsx), and PDF
```
