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

## How to Run (Development Mode)

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

---

## Packaging into a Standalone Windows Executable (.exe)

You can package this application into a standalone `.exe` so that **other Windows computers can run it without installing Python, pip, or any dependencies**.

### Step 1: Install PyInstaller

Run the install command using `python -m pip`:

```bash
# If using the project's virtual environment (recommended):
.\.venv\Scripts\activate
python -m pip install pyinstaller

# Or globally:
python -m pip install pyinstaller
```

> [!NOTE]
> Always run `python -m pip install` and `python -m PyInstaller` on Windows. This prevents the common PowerShell error:  
> *`pyinstaller : The term 'pyinstaller' is not recognized as the name of a cmdlet`* when Python's `Scripts` directory is not in your system's `PATH`.

---

### Step 2: Build the Standalone Application

Navigate into the `Desktop Application` directory and run:

```bash
cd "Desktop Application"
python -m PyInstaller --noconsole --name "RMC_Grievance_App" --add-data "mappings.py;." app.py
```

*Or from the root directory:*

```bash
python -m PyInstaller --noconsole --name "RMC_Grievance_App" --add-data "Desktop Application/mappings.py;." "Desktop Application/app.py"
```

#### Explanation of Flags:
- `--noconsole`: Suppresses the black command prompt terminal window, launching only the clean graphical desktop window.
- `--name "RMC_Grievance_App"`: Sets the name of the executable to `RMC_Grievance_App.exe`.
- `--add-data "mappings.py;."`: Bundles the department mapping configurations and schema definitions directly into the application bundle.
- *(Optional)* `--onefile`: Add this flag if you want a single portable `.exe` file instead of a distribution folder:
  ```bash
  python -m PyInstaller --noconsole --onefile --name "RMC_Grievance_App" --add-data "mappings.py;." app.py
  ```

---

### Step 3: Locate & Distribute the Application

Once the build finishes:
1. Open the generated `dist/` directory:
   - **Folder build**: `dist/RMC_Grievance_App/` (contains `RMC_Grievance_App.exe` and necessary runtime DLLs).
   - **Single-file build**: `dist/RMC_Grievance_App.exe`.
2. **Distribute to other computers**:
   - Zip the `dist/RMC_Grievance_App` folder (or copy `RMC_Grievance_App.exe` if built with `--onefile`) and send it to any Windows 10 or Windows 11 computer.
   - **No Python setup needed**: The end user can simply double-click `RMC_Grievance_App.exe` to run the application immediately.
