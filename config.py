import json
import os
from pathlib import Path
from typing import Optional

CONFIG_FILE_NAME = "app_config.json"
DEFAULT_DB_NAME = "rmc_grievances.db"


def get_config_path() -> Path:
    """Returns the path to the app configuration file in the project directory."""
    base_dir = Path(__file__).resolve().parent
    return base_dir / CONFIG_FILE_NAME


def load_config() -> dict:
    """Loads configuration dictionary from disk."""
    config_file = get_config_path()
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(config: dict) -> None:
    """Saves configuration dictionary to disk."""
    config_file = get_config_path()
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def get_database_folder() -> Optional[str]:
    """Retrieves the stored database directory path, or None if not yet configured."""
    config = load_config()
    folder = config.get("db_folder")
    if folder and Path(folder).exists():
        return folder
    return None


def set_database_folder(folder_path: str) -> str:
    """
    Saves the chosen database directory path and returns the full path to the SQLite file.
    Creates directory if it doesn't exist.
    """
    folder = Path(folder_path).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    db_file = folder / DEFAULT_DB_NAME
    config = load_config()
    config["db_folder"] = str(folder)
    config["db_path"] = str(db_file)
    save_config(config)
    return str(db_file)


def get_database_path() -> Optional[str]:
    """Retrieves the full path to the SQLite database file if configured and folder exists."""
    folder = get_database_folder()
    if folder:
        return str(Path(folder) / DEFAULT_DB_NAME)
    return None
