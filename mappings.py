# mappings.py

# Output CSV & Excel columns in exact required order
REPRESENTATIONS_COLUMNS = [
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
    "Unique ID",
]

CONCERNED_DEPARTMENTS_COLUMNS = [
    "Unique ID of Representations.csv",
    "Grievance ID / Computer Number",
    "E-Office Receipt Number",
    "Concerned Department Abbreviation",
    "Concerned Department",
    "Location",
    "ATR Status",
    "ATR Number",
    "ATR Date",
    "ATR Computer Number",
]

# Default static values
DEFAULT_VALUES = {
    "Processing Channel": "E-Office",
    "Dispatch Type": "e-Office Portal",
    "Dispatch Status": "Pending",
    "Missing Row Remarks": "Missing representation number",
}

# Maps incoming Excel department names/variations to standard Department Name and Abbreviation
DEPARTMENT_MAPPING = {
    "JKHOD": {
        "name": "Head of Department",
        "abbr": "HOD",
    },
    "JKDCOF": {
        "name": "Deputy Commissioner",
        "abbr": "DC",
    },
    "Agriculture Production Department": {
        "name": "Agriculture Production Department",
        "abbr": "APD",
    },
    "Agriculture Production and Farmers Welfare Department": {
        "name": "Agriculture Production Department",
        "abbr": "APD",
    },
    "Department of ARI Trainings": {
        "name": "ARI and Trainings Department",
        "abbr": "ARI",
    },
    "Civil aviation": {
        "name": "Civil Aviation Department",
        "abbr": "CAD",
    },
    "Office of Cooperative Department": {
        "name": "Cooperative Department",
        "abbr": "COOP",
    },
    "CULTURE DEPARMTENT": {
        "name": "Department of Culture",
        "abbr": "CUL",
    },
    "Department of Food, Civil Supplies & Consumer Affairs": {
        "name": "Department of Food, Civil Supplies and Consumer Affairs",
        "abbr": "FCSCA",
    },
    "Department of Law, Justice & Parliamentary Affairs": {
        "name": "Department of Law, Justice & Parliamentary Affairs",
        "abbr": "LJPA",
    },
    "Mining Department": {
        "name": "Department of Mining",
        "abbr": "MIN",
    },
    "DEPARTMENT OF PUBLIC GRIEVANCES": {
        "name": "Department of Public Grievances",
        "abbr": "DOPG",
    },
    "Office of skill development department": {
        "name": "Department of Skill Development",
        "abbr": "DSD",
    },
    "Disaster Management, Relief, Rehabilitation and Reconstruction Department": {
        "name": "Disaster Management, Relief, Rehabilitation and Reconstruction Department",
        "abbr": "DMRRR",
    },
    "ELECTION DEPARTMENT": {
        "name": "Election Department",
        "abbr": "ELEC",
    },
    "Estates Department": {
        "name": "Estates Department",
        "abbr": "ESD",
    },
    "FINANCE DEPARTMENT": {
        "name": "Finance Department",
        "abbr": "FIN",
    },
    "Forest Department": {
        "name": "Forest, Ecology and Environment Department",
        "abbr": "FED",
    },
    "General Administration Department": {
        "name": "General Administration Department",
        "abbr": "GAD",
    },
    "Department of Health and Medical Education": {
        "name": "Health & Medical Education Department",
        "abbr": "HME",
    },
    "Department of Higher Education": {
        "name": "Higher Education Department",
        "abbr": "HED",
    },
    "Home Department": {
        "name": "Home Department",
        "abbr": "HOME",
    },
    "DEPARTMENT OF HOSPITALITY & PROTOCOL": {
        "name": "Hospitality and Protocol Department",
        "abbr": "HPD",
    },
    "HOUSING AND  URBAN DEVELOPMENT DEPARTMENT": {
        "name": "Housing & Urban Development Department",
        "abbr": "HUDD",
    },
    "DEPARTMENT OF INDUSTRIES & COMMERCE": {
        "name": "Industries & Commerce Department",
        "abbr": "ICD",
    },
    "INFORMATION DEPARTMENT": {
        "name": "Information Department",
        "abbr": "INF",
    },
    "Information Technology Department": {
        "name": "Information Technology Department",
        "abbr": "ITD",
    },
    "PUBLIC HEALTH ENGINEERING, IRRIGATION AND FLOOD CONTROL": {
        "name": "Jal Shakti (PHE & I&FC) Department",
        "abbr": "JSD",
    },
    "Labour & Employment": {
        "name": "Labour and Employment Department",
        "abbr": "LED",
    },
    "LOK BHAVAN, J&K": {
        "name": "Lieutenant Governor's Secretariat, Lok Bhavan, Jammu and Kashmir",
        "abbr": "HLG",
    },
    "PLANNING DEVELOPMENT AND MONITORING DEPARTMENT": {
        "name": "Planning, Development and Monitoring Department",
        "abbr": "PDMD",
    },
    "Power Development Department": {
        "name": "Power Development Department (PDD)",
        "abbr": "PDD",
    },
    "Department of PWD R&B": {
        "name": "Public Works (R&B) Department",
        "abbr": "PWD",
    },
    "Revenue Department": {
        "name": "Revenue Department",
        "abbr": "REV",
    },
    "Department of Rural Development and PR": {
        "name": "Rural Development & Panchayati Raj",
        "abbr": "RDPR",
    },
    "O/o Department of School Education": {
        "name": "School Education Department",
        "abbr": "SED",
    },
    "Department of Science and Technology": {
        "name": "Science and Technology Department",
        "abbr": "STD",
    },
    "Department Of Social welfare": {
        "name": "Social Welfare Department",
        "abbr": "SWD",
    },
    "Department of Tourism": {
        "name": "Tourism Department",
        "abbr": "TOUR",
    },
    "Department of Transport": {
        "name": "Transport Department",
        "abbr": "TRP",
    },
    "Tribal Affairs Department": {
        "name": "Tribal Affairs Department",
        "abbr": "TAD",
    },
    "Department Of Youth Service & Sports": {
        "name": "Youth Services and Sports Department",
        "abbr": "YSS",
    },
}

# Regex patterns for fields extracted from the Subject column
EXTRACTION_PATTERNS = {
    "Communication No.": r"(?:ref(?:erence)?\.?(?:\s*no\.?)?|communication\s*(?:no\.?|number)?)\s*[:\-]?\s*([^\n\r,;]+?)(?=\s+(?:dated|dt\.?|date\b|$))",
    "Communication Date": r"(?:dated|date|dt\.?)\s*[:\-]?\s*([0-3]?[0-9][./\-][0-1]?[0-9][./\-](?:19|20)\d{2})",
    "Representation No.": r"(?:[\(\[\{]?\s*(?:s\s*\.?\s*no|sl\s*\.?\s*no|serial\s*no|representation\s*(?:no\.?|number)?)\.?\s*[:\-]?\s*([a-zA-Z0-9\-_/]+)\s*[\)\]\}]?)",
}