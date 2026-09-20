# RMC Grievance Data Extractor & Normalization Pipeline

An automated data extraction, parsing, and normalization pipeline designed to process grievance export files (from e-Office and related portals) into structured, standardized relational datasets.

---

## Overview

The pipeline ingests raw export files (`.xlsx`, `.xls`, `.csv`), performs intelligent subject-line regex parsing, standardizes department names and abbreviations, identifies sequence gaps, and exports two relational tables in both CSV and Microsoft Excel formats:

1. **`Representations`**: Consolidated representations capturing communication details, applicant info, issue type classification, grievance IDs, and concerned departments paired with e-Office receipt numbers.
2. **`Concerned Departments`**: Granular department-level routing records detailing specific receipt numbers, department names, abbreviations, locations, and ATR tracking fields.

---

## Project Structure

```text
.
├── input/                             # Place raw incoming export files (.xlsx, .xls, .csv) here
├── output/                            # Generated normalized CSV and Excel files
├── mappings.py                        # Output schemas, default values, and department mappings
├── script.py                          # Core extraction, normalization, and export logic
├── requirements.txt                   # Project dependencies
├── .gitignore                         # Git ignore rules (excludes data files and virtual envs)
└── README.md                          # Project documentation
```

---

## Features & Business Rules

- **Flexible Input Ingestion**: Supports `.xlsx` (via openpyxl), legacy `.xls` (via xlrd), and `.csv` files with multiple character encoding fallbacks (`utf-8`, `utf-8-sig`, `latin1`, `cp1252`).
- **Subject-Line Regex Extraction**:
  - **Communication Number**: Extracts references like `LGS-1(GR)26/3976`.
  - **Communication Date**: Standardizes dates extracted from subject references into full date format (`DD MMMM YYYY`).
  - **Representation Serial Number**: Extracts serial numbers (e.g., `01`, `02`) with natural alphanumeric sorting.
- **Sequence Gap Detection**: Identifies missing representation numbers within each communication sequence and inserts placeholder records marked with `"Missing representation number"`.
- **Department Normalization & Fuzzy Resolution**: Matches raw department variations against canonical department names and standardized abbreviations using exact aliases, dictionary lookups, and sequence similarity matching.
- **Concerned Department(s) Formatting**:
  - **Single Department**: Displayed as a single entry:  
    `{Department Name} vide E-Office Receipt Number {Receipt Number}`
  - **Multiple Departments**: Numbered sequentially using lowercase Roman numerals with line breaks (`\n`) within the same cell:  
    ```text
    (i) Home Department vide E-Office Receipt Number 6928830/2026/Ref Mon Cell GAD
    (ii) Deputy Commissioner vide E-Office Receipt Number 6928830(1)/2026/Ref Mon Cell GAD
    ```
- **Excel Cell Formatting**: Automatically enables text wrapping (`wrap_text=True`) and top vertical alignment in the Excel workbook so multi-line entries render cleanly.
- **Overall ATR Status**: Retained in the schema header while keeping values completely unpopulated per reporting requirements.

---

## Output Data Schemas

### 1. Representations (`Representations.csv` & Excel Sheet: `Representations`)

| Column Name | Description |
| :--- | :--- |
| `Communication Number` | Extracted communication / reference identifier |
| `Communication Date` | Extracted date of the communication |
| `Representation Serial Number` | Serial number (e.g. `01`, `02`) |
| `Applicant Name` | Preserved column (blank if not provided in raw data) |
| `Subject` | Preserved column |
| `Applicant Name On Portal` | Sender name / email extracted from portal data |
| `Representation Subject On Portal` | Raw representation subject text |
| `Issue Type (Single / Multiple)` | `"Single"` if 1 department, `"Multiple"` if > 1 |
| `Remarks` | Remarks such as `"Missing representation number"` for gaps |
| `Processing Channel` | Default: `"E-Office"` |
| `Concerned Department(s)` | Paired department(s) and E-Office receipt numbers |
| `Grievance ID / Computer Number` | Computer number / Grievance ID |
| `Sent On` | Dispatch / Sent date formatted as `DD MMMM YYYY` |
| `Letter Number` | Letter reference number |
| `Letter Date` | Letter date formatted as `DD MMMM YYYY` |
| `Overall ATR Status` | Blank per requirement |

### 2. Concerned Departments (`Concerned Departments.csv` & Excel Sheet: `Concerned Departments`)

| Column Name | Description |
| :--- | :--- |
| `Communication Number` | Communication reference identifier |
| `Communication Date` | Communication date |
| `Representation Serial Number` | Representation serial number |
| `Grievance ID / Computer Number` | Computer / Grievance ID |
| `E-Office Receipt Number` | Specific e-Office receipt number for this department dispatch |
| `Concerned Department Abbreviation` | Canonical department abbreviation (e.g., `HOME`, `DC`, `APD`) |
| `Concerned Department` | Standardized canonical department name |
| `Location` | File / Receipt path in e-Office (e.g. `File/Inbox/...`, `Receipt/Sent`) |
| `ATR Status` | Action Taken Report status (blank per requirement) |
| `ATR Number` | Action Taken Report reference number |
| `ATR Date` | Action Taken Report date |
| `ATR Computer Number` | ATR computer reference number |

---

## Installation & Setup

### 1. Prerequisites
- Python 3.9 or higher

### 2. Clone Repository
```bash
git clone https://github.com/aiocrafters/RMC-Grievance-Database.git
cd RMC-Grievance-Database
```

### 3. Create & Activate Virtual Environment (Optional but Recommended)
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## Usage

1. **Place Raw Input Files**: Copy one or more `.xlsx`, `.xls`, or `.csv` export files into the `input/` folder.
2. **Execute Pipeline**:
   ```bash
   python script.py
   ```
3. **Retrieve Generated Output**: Processed outputs are saved to `output/`:
   - `output/Representations.csv`
   - `output/Concerned Departments.csv`
   - `output/Representations_and_Departments.xlsx`
