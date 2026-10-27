import os
import sys
import json
import re
import shutil
import tempfile
from datetime import datetime
from copy import deepcopy
from modules.common.logger import logger
from modules.common.path_utils import validate_output_folder


# ═══════════════════════════════════════════════════════════════════════════════
# Built-in University Presets (Factory Defaults)
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_CEIT_PREFIX_MAP = {
    "AGEN": {
        "name": "Agricultural and Biosystems Engineering",
        "dept": "Department of Agricultural and Food Engineering",
        "dept_code": "DAFE",
        "icon": "🌱",
        "badge": "🌱 DAFE"
    },
    "ABEN": {
        "name": "Agricultural and Biosystems Engineering",
        "dept": "Department of Agricultural and Food Engineering",
        "dept_code": "DAFE",
        "icon": "🌱",
        "badge": "🌱 DAFE"
    },
    "ARCH": {
        "name": "Architecture",
        "dept": "Department of Civil Engineering",
        "dept_code": "DCE",
        "icon": "📐",
        "badge": "📐 Architecture"
    },
    "CENG": {
        "name": "Civil Engineering",
        "dept": "Department of Civil Engineering",
        "dept_code": "DCE",
        "icon": "🏛️",
        "badge": "🏛️ Civil Eng"
    },
    "CIVL": {
        "name": "Civil Engineering",
        "dept": "Department of Civil Engineering",
        "dept_code": "DCE",
        "icon": "🏛️",
        "badge": "🏛️ Civil Eng"
    },
    "COSC": {
        "name": "Computer Science",
        "dept": "Department of Information Technology",
        "dept_code": "DIT",
        "icon": "🖥️",
        "badge": "🖥️ Computer Science"
    },
    "CPEN": {
        "name": "Computer Engineering",
        "dept": "Department of Computer and Electronics Engineering",
        "dept_code": "DCEE",
        "icon": "⚡",
        "badge": "⚡ Computer Eng"
    },
    "DCEE": {
        "name": "Computer Engineering",
        "dept": "Department of Computer and Electronics Engineering",
        "dept_code": "DCEE",
        "icon": "⚡",
        "badge": "⚡ Computer Eng"
    },
    "DCIT": {
        "name": "DIT Core / Common IT",
        "dept": "Department of Information Technology",
        "dept_code": "DIT",
        "icon": "💻",
        "badge": "💻 DIT Core"
    },
    "ECEN": {
        "name": "Electronics Engineering",
        "dept": "Department of Computer and Electronics Engineering",
        "dept_code": "DCEE",
        "icon": "📡",
        "badge": "📡 Electronics Eng"
    },
    "EENG": {
        "name": "Electrical Engineering",
        "dept": "Department of Computer and Electronics Engineering",
        "dept_code": "DCEE",
        "icon": "🔌",
        "badge": "🔌 Electrical Eng"
    },
    "IENG": {
        "name": "Industrial Engineering",
        "dept": "Department of Industrial Engineering and Technology",
        "dept_code": "DIET",
        "icon": "🏭",
        "badge": "🏭 Industrial Eng"
    },
    "INDT": {
        "name": "Industrial Technology",
        "dept": "Department of Industrial Engineering and Technology",
        "dept_code": "DIET",
        "icon": "🔧",
        "badge": "🔧 Industrial Tech"
    },
    "SMT": {
        "name": "Industrial Technology",
        "dept": "Department of Industrial Engineering and Technology",
        "dept_code": "DIET",
        "icon": "🔧",
        "badge": "🔧 Industrial Tech"
    },
    "ITEC": {
        "name": "Information Technology",
        "dept": "Department of Information Technology",
        "dept_code": "DIT",
        "icon": "🌐",
        "badge": "🌐 Info Tech"
    }
}

DEFAULT_BASE_SUBJECT_PREFIXES = [
    "CVSU", "DCIT", "COSC", "ITEC", "INSY", "GNED", "MATH", "STAT",
    "FITT", "NSTP", "PHYS", "PHED", "ECON", "BAMG", "ENGR", "BSCE",
    "COEN", "ELET", "MECH", "AENG", "CHEM", "BIOL", "FILI", "HIST",
    "COMM", "SOCS", "HUMA", "AGRI", "CRIM", "BMGT"
]

DEFAULT_KNOWN_LAB_SUBJECT_CODES = [
    "DCIT 21", "DCIT 21A", "DCIT 22", "DCIT 23", "DCIT 24", "DCIT 25", "DCIT 26",
    "DCIT21", "DCIT21A", "DCIT22", "DCIT23", "DCIT24", "DCIT25", "DCIT26",
    "COSC 111", "COSC 111A", "COSC 55", "COSC 60", "COSC 65", "COSC 70", "COSC 75", "COSC 80", "COSC 85", "COSC 101",
    "COSC111", "COSC111A", "COSC55", "COSC60", "COSC65", "COSC70", "COSC75", "COSC80", "COSC85", "COSC101",
    "ITEC 50", "ITEC 55", "ITEC 60", "ITEC 65", "ITEC 70", "ITEC 75", "ITEC 80", "ITEC 85", "ITEC 90",
    "ITEC50", "ITEC55", "ITEC60", "ITEC65", "ITEC70", "ITEC75", "ITEC80", "ITEC85", "ITEC90"
]

DEFAULT_PROGRAM_ALIASES = {
    "CS": "BSCS",
    "IT": "BSIT",
    "CPE": "BSCPE",
    "CPEN": "BSCPE",
    "CE": "BSCE",
    "CIVL": "BSCE",
    "CENG": "BSCE",
    "EE": "BSEE",
    "EENG": "BSEE",
    "ECE": "BSECE",
    "ECEN": "BSECE",
    "ABE": "BSABE",
    "ABEN": "BSABE",
    "AGEN": "BSABE"
}

DEFAULT_ROSTER_KEYWORDS = {
    "id_tokens": [
        "studentnumber", "studentno", "studentnum", "studentid",
        "idnumber", "idno", "studno", "studnumber", "studnum",
        "student#", "stud#", "id#", "id", "studid", "student_no", "student_id",
        "lrn", "studentkey", "matricula", "registrationno", "Student Number"
    ],
    "name_tokens": [
        "name", "studentname", "fullname", "studentsname", "names",
        "student", "lastname", "studentfullname", "completename", "pangalan", "Student Name"
    ]
}

DEFAULT_SCHEDULE_CONFIG = {
    "default_instructor": "DAN JOSEPH A. ORTEGA",
    "default_semester": "FIRST SEMESTER, AY 2026 - 2027",
    "default_college": "COLLEGE OF ENGINEERING AND INFORMATION TECHNOLOGY",
    "start_row": 18,
    "end_row": 46
}


def get_default_config_dict() -> dict:
    return {
        "version": "1.0",
        "ceit_prefix_map": deepcopy(DEFAULT_CEIT_PREFIX_MAP),
        "base_subject_prefixes": list(DEFAULT_BASE_SUBJECT_PREFIXES),
        "known_lab_subjects": list(DEFAULT_KNOWN_LAB_SUBJECT_CODES),
        "program_aliases": dict(DEFAULT_PROGRAM_ALIASES),
        "roster_keywords": deepcopy(DEFAULT_ROSTER_KEYWORDS),
        "schedule_config": dict(DEFAULT_SCHEDULE_CONFIG),
        "calendar_config": {
            "enabled": False,
            "default_mode": "OMIT_COLUMN",
            "rules": [
                {"rule_type": "fixed_date", "name": "New Year's Day", "category": "HOLIDAY", "month": 1, "day": 1, "weekday": None, "nth": None, "mode": None},
                {"rule_type": "fixed_date", "name": "Araw ng Kagitingan", "category": "HOLIDAY", "month": 4, "day": 9, "weekday": None, "nth": None, "mode": None},
                {"rule_type": "fixed_date", "name": "Labor Day", "category": "HOLIDAY", "month": 5, "day": 1, "weekday": None, "nth": None, "mode": None},
                {"rule_type": "fixed_date", "name": "Independence Day", "category": "HOLIDAY", "month": 6, "day": 12, "weekday": None, "nth": None, "mode": None},
                {"rule_type": "fixed_date", "name": "Ninoy Aquino Day", "category": "HOLIDAY", "month": 8, "day": 21, "weekday": None, "nth": None, "mode": None},
                {"rule_type": "fixed_date", "name": "Cavite Day", "category": "HOLIDAY", "month": 3, "day": 22, "weekday": None, "nth": None, "mode": None},
                {"rule_type": "fixed_date", "name": "All Saints' Day", "category": "HOLIDAY", "month": 11, "day": 1, "weekday": None, "nth": None, "mode": None},
                {"rule_type": "fixed_date", "name": "All Souls' Day", "category": "HOLIDAY", "month": 11, "day": 2, "weekday": None, "nth": None, "mode": None},
                {"rule_type": "fixed_date", "name": "Bonifacio Day", "category": "HOLIDAY", "month": 11, "day": 30, "weekday": None, "nth": None, "mode": None},
                {"rule_type": "fixed_date", "name": "Feast of the Immaculate Conception", "category": "HOLIDAY", "month": 12, "day": 8, "weekday": None, "nth": None, "mode": None},
                {"rule_type": "fixed_date", "name": "Christmas Eve", "category": "HOLIDAY", "month": 12, "day": 24, "weekday": None, "nth": None, "mode": None},
                {"rule_type": "fixed_date", "name": "Christmas Day", "category": "HOLIDAY", "month": 12, "day": 25, "weekday": None, "nth": None, "mode": None},
                {"rule_type": "fixed_date", "name": "Rizal Day", "category": "HOLIDAY", "month": 12, "day": 30, "weekday": None, "nth": None, "mode": None},
                {"rule_type": "fixed_date", "name": "New Year's Eve", "category": "HOLIDAY", "month": 12, "day": 31, "weekday": None, "nth": None, "mode": None},
                {"rule_type": "nth_weekday", "name": "National Heroes Day", "category": "HOLIDAY", "month": 8, "day": None, "weekday": 0, "nth": "last", "mode": None},
            ],
            "exceptions": [],
            "overrides": {},
        },
    }


class ParserConfigManager:
    """
    Manages persistent curriculum, department, and parser configuration.
    Merges factory defaults with user overrides stored in APPDATA/CVSU_Generators/config.
    """

    def __init__(self, config_dir: str = None):
        if config_dir:
            self.config_dir = config_dir
            self.base_dir = os.path.dirname(config_dir)
        else:
            app_data = os.getenv('APPDATA') or os.path.expanduser("~")
            self.base_dir = os.path.join(app_data, "CVSU_Generators")
            self.config_dir = os.path.join(self.base_dir, "config")

        self.custom_templates_dir = os.path.join(self.base_dir, "custom_templates")
        self.custom_templates_index = os.path.join(self.custom_templates_dir, "templates.json")
        self.workspaces_dir = os.path.join(self.base_dir, "workspaces")
        self.config_file = os.path.join(self.config_dir, "parser_settings.json")
        self._cached_config = None
        self._listeners = []
        self.load_config()


    def register_listener(self, callback):
        """Register a callback function to be called when configuration changes."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def _notify_listeners(self):
        for cb in self._listeners:
            try:
                cb(self._cached_config)
            except Exception as e:
                logger.error(f"Error in config listener callback: {e}")

    def load_config(self) -> dict:
        """Loads user configuration from disk, merged over factory defaults."""
        defaults = get_default_config_dict()
        if not os.path.exists(self.config_file):
            self._cached_config = defaults
            self._notify_listeners()
            return self._cached_config

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                user_data = json.load(f)

            merged = deepcopy(defaults)

            # 1. Merge CEIT prefix map
            if "ceit_prefix_map" in user_data and isinstance(user_data["ceit_prefix_map"], dict):
                merged["ceit_prefix_map"] = {
                    k.upper().strip(): v
                    for k, v in user_data["ceit_prefix_map"].items()
                    if k and isinstance(v, dict)
                }

            # 2. Merge base subject prefixes
            if "base_subject_prefixes" in user_data and isinstance(user_data["base_subject_prefixes"], list):
                merged["base_subject_prefixes"] = sorted(list(set(
                    [str(p).upper().strip() for p in user_data["base_subject_prefixes"] if str(p).strip()]
                )))

            # 3. Merge known lab subjects
            if "known_lab_subjects" in user_data and isinstance(user_data["known_lab_subjects"], list):
                merged["known_lab_subjects"] = sorted(list(set(
                    [str(p).upper().strip() for p in user_data["known_lab_subjects"] if str(p).strip()]
                )))

            # 4. Merge program aliases
            if "program_aliases" in user_data and isinstance(user_data["program_aliases"], dict):
                merged["program_aliases"] = {
                    k.upper().strip(): str(v).upper().strip()
                    for k, v in user_data["program_aliases"].items()
                    if k and v
                }

            # 5. Merge roster keywords
            if "roster_keywords" in user_data and isinstance(user_data["roster_keywords"], dict):
                rk = user_data["roster_keywords"]
                if "id_tokens" in rk and isinstance(rk["id_tokens"], list):
                    merged["roster_keywords"]["id_tokens"] = sorted(list(set(
                        [str(t).lower().strip() for t in rk["id_tokens"] if str(t).strip()]
                    )))
                if "name_tokens" in rk and isinstance(rk["name_tokens"], list):
                    merged["roster_keywords"]["name_tokens"] = sorted(list(set(
                        [str(t).lower().strip() for t in rk["name_tokens"] if str(t).strip()]
                    )))

            # 6. Merge schedule config
            if "schedule_config" in user_data and isinstance(user_data["schedule_config"], dict):
                for k, v in user_data["schedule_config"].items():
                    if v is not None and str(v).strip():
                        merged["schedule_config"][k] = v

            # 7. Merge organization preset
            if "organization_preset" in user_data and isinstance(user_data["organization_preset"], dict):
                merged["organization_preset"] = deepcopy(user_data["organization_preset"])

            # 8. Merge calendar config
            if "calendar_config" in user_data and isinstance(user_data["calendar_config"], dict):
                merged["calendar_config"] = deepcopy(user_data["calendar_config"])

            self._cached_config = merged
        except Exception as e:
            logger.error(f"Failed to load user config from {self.config_file}, using defaults: {e}")
            self._cached_config = defaults

        self._notify_listeners()
        return self._cached_config

    def save_config(self, new_config: dict) -> dict:
        """Validates, atomically writes to disk, and updates memory cache."""
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            defaults = get_default_config_dict()
            validated = deepcopy(defaults)

            if "ceit_prefix_map" in new_config and isinstance(new_config["ceit_prefix_map"], dict):
                cleaned_map = {}
                for k, v in new_config["ceit_prefix_map"].items():
                    prefix = str(k).upper().strip()
                    if prefix and isinstance(v, dict):
                        dept_code = str(v.get("dept_code") or v.get("department_code") or "").strip()
                        dept_name = str(v.get("dept") or v.get("department_name") or "").strip()
                        name = str(v.get("name") or dept_name).strip()
                        icon = str(v.get("icon") or "📚").strip()
                        badge = str(v.get("badge") or f"{icon} {dept_code or prefix}").strip()
                        cleaned_map[prefix] = {
                            "name": name,
                            "dept": dept_name,
                            "dept_code": dept_code,
                            "icon": icon,
                            "badge": badge
                        }
                validated["ceit_prefix_map"] = cleaned_map

            if "base_subject_prefixes" in new_config and isinstance(new_config["base_subject_prefixes"], list):
                validated["base_subject_prefixes"] = sorted(list(set(
                    [str(p).upper().strip() for p in new_config["base_subject_prefixes"] if str(p).strip()]
                )))

            if "known_lab_subjects" in new_config and isinstance(new_config["known_lab_subjects"], list):
                validated["known_lab_subjects"] = sorted(list(set(
                    [str(p).upper().strip() for p in new_config["known_lab_subjects"] if str(p).strip()]
                )))

            if "program_aliases" in new_config and isinstance(new_config["program_aliases"], dict):
                validated["program_aliases"] = {
                    str(k).upper().strip(): str(v).upper().strip()
                    for k, v in new_config["program_aliases"].items()
                    if str(k).strip() and str(v).strip()
                }

            if "roster_keywords" in new_config and isinstance(new_config["roster_keywords"], dict):
                rk = new_config["roster_keywords"]
                if "id_tokens" in rk and isinstance(rk["id_tokens"], list):
                    validated["roster_keywords"]["id_tokens"] = sorted(list(set(
                        [str(t).lower().strip() for t in rk["id_tokens"] if str(t).strip()]
                    )))
                if "name_tokens" in rk and isinstance(rk["name_tokens"], list):
                    validated["roster_keywords"]["name_tokens"] = sorted(list(set(
                        [str(t).lower().strip() for t in rk["name_tokens"] if str(t).strip()]
                    )))

            if "schedule_config" in new_config and isinstance(new_config["schedule_config"], dict):
                sc = new_config["schedule_config"]
                for k in ("default_instructor", "default_semester", "default_college"):
                    if k in sc and str(sc[k]).strip():
                        validated["schedule_config"][k] = str(sc[k]).strip()

            if "organization_preset" in new_config and isinstance(new_config["organization_preset"], dict):
                validated["organization_preset"] = deepcopy(new_config["organization_preset"])

            if "calendar_config" in new_config and isinstance(new_config["calendar_config"], dict):
                validated["calendar_config"] = deepcopy(new_config["calendar_config"])

            # Atomic write via tempfile
            temp_fd, temp_path = tempfile.mkstemp(dir=self.config_dir, prefix="cfg_tmp_", suffix=".json")
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(validated, f, indent=2, ensure_ascii=False)

            if os.path.exists(self.config_file):
                os.replace(temp_path, self.config_file)
            else:
                os.rename(temp_path, self.config_file)

            self._cached_config = validated
            self._notify_listeners()
            logger.info("Successfully updated and persisted user parser configuration.")
            return {"status": "success", "config": validated}
        except Exception as e:
            logger.error(f"Error saving parser config: {e}")
            return {"status": "error", "message": str(e)}

    def reset_to_defaults(self) -> dict:
        """Removes the custom overrides file and restores factory defaults."""
        try:
            if os.path.exists(self.config_file):
                os.remove(self.config_file)
            self._cached_config = get_default_config_dict()
            self._notify_listeners()
            logger.info("Reset parser configuration to factory defaults.")
            return {"status": "success", "config": self._cached_config}
        except Exception as e:
            logger.error(f"Error resetting parser config: {e}")
            return {"status": "error", "message": str(e)}

    def export_config(self, target_path: str) -> dict:
        """Exports the active configuration to a user-specified path."""
        try:
            cfg = self.get_config()
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            return {"status": "success", "path": target_path}
        except Exception as e:
            logger.error(f"Failed to export config to {target_path}: {e}")
            return {"status": "error", "message": str(e)}

    def import_config(self, source_path: str) -> dict:
        """Imports and activates configuration from an external JSON file."""
        if not os.path.exists(source_path):
            return {"status": "error", "message": f"File not found: {source_path}"}
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                imported_data = json.load(f)
            if not isinstance(imported_data, dict):
                return {"status": "error", "message": "Import file must contain a JSON object"}

            # If an explicit schema version is provided, ensure it is supported
            if "version" in imported_data and imported_data["version"] is not None:
                v_str = str(imported_data["version"]).strip()
                if v_str != "1.0":
                    return {
                        "status": "error",
                        "message": (
                            f"Unsupported parser configuration schema version '{v_str}'. "
                            "Only version '1.0' is supported."
                        )
                    }

            required_keys = {
                "ceit_prefix_map", "base_subject_prefixes", "known_lab_subjects",
                "program_aliases", "roster_keywords", "schedule_config"
            }
            missing_keys = required_keys - set(imported_data.keys())
            if missing_keys:
                return {
                    "status": "error",
                    "message": f"Incomplete parser configuration document. Missing required keys: {sorted(list(missing_keys))}"
                }

            if not isinstance(imported_data["ceit_prefix_map"], dict):
                return {"status": "error", "message": "Invalid parser configuration: 'ceit_prefix_map' must be a JSON object"}
            if not isinstance(imported_data["base_subject_prefixes"], list):
                return {"status": "error", "message": "Invalid parser configuration: 'base_subject_prefixes' must be a list"}
            if not isinstance(imported_data["known_lab_subjects"], list):
                return {"status": "error", "message": "Invalid parser configuration: 'known_lab_subjects' must be a list"}
            if not isinstance(imported_data["program_aliases"], dict):
                return {"status": "error", "message": "Invalid parser configuration: 'program_aliases' must be a JSON object"}
            if not isinstance(imported_data["roster_keywords"], dict):
                return {"status": "error", "message": "Invalid parser configuration: 'roster_keywords' must be a JSON object"}
            if not isinstance(imported_data["schedule_config"], dict):
                return {"status": "error", "message": "Invalid parser configuration: 'schedule_config' must be a JSON object"}

            return self.save_config(imported_data)
        except Exception as e:
            logger.error(f"Failed to import config from {source_path}: {e}")
            return {"status": "error", "message": str(e)}

    def get_config(self) -> dict:
        """Returns the current active configuration."""
        if self._cached_config is None:
            self.load_config()
        return deepcopy(self._cached_config)

    # ═══════════════════════════════════════════════════════════════════════════
    # Fast In-Memory Query Helpers for Parsers
    # ═══════════════════════════════════════════════════════════════════════════

    def get_ceit_prefix_map(self) -> dict:
        cfg = self.get_config()
        return cfg.get("ceit_prefix_map", DEFAULT_CEIT_PREFIX_MAP)

    def get_subject_prefixes(self) -> tuple:
        cfg = self.get_config()
        base = cfg.get("base_subject_prefixes", DEFAULT_BASE_SUBJECT_PREFIXES)
        prefix_map = cfg.get("ceit_prefix_map", DEFAULT_CEIT_PREFIX_MAP)
        all_prefixes = set(list(base) + list(prefix_map.keys()))
        return tuple(sorted(all_prefixes))

    def get_known_lab_subjects(self) -> set:
        cfg = self.get_config()
        raw = cfg.get("known_lab_subjects", DEFAULT_KNOWN_LAB_SUBJECT_CODES)
        return {str(s).upper().strip() for s in raw if s}

    def get_normalized_lab_subjects(self) -> set:
        lab_codes = self.get_known_lab_subjects()
        return {re.sub(r'[^A-Za-z0-9]', '', c).upper() for c in lab_codes}

    def is_lab_subject(self, subject_str: str) -> bool:
        if not subject_str:
            return False
        prefix = re.split(r'[-–—―−]', str(subject_str))[0].upper()
        prefix = re.sub(r'\(.*?\)', '', prefix).strip()
        norm = re.sub(r'[^A-Za-z0-9]', '', prefix)
        return norm in self.get_normalized_lab_subjects() or prefix in self.get_known_lab_subjects()

    def get_prefix_metadata(self, text: str) -> dict:
        if not text:
            return None
        cleaned = str(text).upper()
        prefix_map = self.get_ceit_prefix_map()
        for prefix, meta in prefix_map.items():
            if re.search(r'(?:^|[^A-Z])' + re.escape(prefix) + r'(?=$|[^A-Z])', cleaned):
                dept_code = meta.get("dept_code") or meta.get("department_code") or ""
                dept_name = meta.get("dept") or meta.get("department_name") or ""
                return {
                    "prefix": prefix,
                    "name": meta.get("name") or dept_name,
                    "dept": dept_name,
                    "dept_code": dept_code,
                    "department_name": dept_name,
                    "department_code": dept_code,
                    "icon": meta.get("icon", "📚"),
                    "badge": meta.get("badge", f"{meta.get('icon', '📚')} {dept_code or prefix}")
                }
        return None

    def get_program_aliases(self) -> dict:
        cfg = self.get_config()
        return cfg.get("program_aliases", DEFAULT_PROGRAM_ALIASES)

    def get_roster_keywords(self) -> dict:
        cfg = self.get_config()
        return cfg.get("roster_keywords", DEFAULT_ROSTER_KEYWORDS)

    def get_schedule_defaults(self) -> dict:
        cfg = self.get_config()
        return cfg.get("schedule_config", DEFAULT_SCHEDULE_CONFIG)

    # ═══════════════════════════════════════════════════════════════════════════
    # Custom Templates & Deterministic Heuristic Recipes
    # ═══════════════════════════════════════════════════════════════════════════

    def get_custom_templates_dir(self) -> str:
        os.makedirs(self.custom_templates_dir, exist_ok=True)
        return self.custom_templates_dir

    def get_custom_templates(self) -> list:
        """Returns list of registered custom templates whose files exist."""
        if not os.path.exists(self.custom_templates_index):
            return []
        try:
            with open(self.custom_templates_index, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                valid = []
                for item in data:
                    file_path = os.path.join(self.custom_templates_dir, item.get("filename", ""))
                    if os.path.exists(file_path):
                        item_copy = dict(item)
                        item_copy["file_path"] = file_path
                        valid.append(item_copy)
                return valid
        except Exception as e:
            logger.error(f"Error reading custom templates index {self.custom_templates_index}: {e}")
        return []

    def save_custom_template(
        self, source_path: str, title: str, suffix: str, recipe: dict, enabled: bool = True
    ) -> dict:
        """Saves a template file and its recipe into the custom templates store."""
        try:
            os.makedirs(self.custom_templates_dir, exist_ok=True)
            suffix_clean = re.sub(r"[^A-Za-z0-9_]", "", suffix.upper().strip()).strip("_") or "CUSTOM_FORM"
            template_id = suffix_clean.lower()
            dest_filename = f"{template_id}.docx"
            dest_path = os.path.join(self.custom_templates_dir, dest_filename)

            # Copy template file
            shutil.copy2(source_path, dest_path)

            # Ensure metadata exists and output_folder is valid and normalized
            if isinstance(recipe, dict):
                meta = recipe.setdefault("metadata", {})
                if isinstance(meta, dict):
                    raw_out = meta.get("output_folder")
                    meta["output_folder"] = validate_output_folder(raw_out, default="CEIT_Forms")
                # Strip any stray top-level output_folder from recipe
                recipe.pop("output_folder", None)

            templates = self.get_custom_templates()
            # Remove any existing entry with the same id
            templates = [t for t in templates if t.get("id") != template_id]

            entry = {
                "id": template_id,
                "title": title.strip() or suffix_clean.replace("_", " ").title(),
                "suffix": suffix_clean,
                "filename": dest_filename,
                "file_path": dest_path,
                "enabled": enabled,
                "recipe": recipe,
                "created_at": datetime.now().isoformat(),
            }
            templates.append(entry)

            # Write atomically
            with tempfile.NamedTemporaryFile("w", dir=self.custom_templates_dir, delete=False, encoding="utf-8") as tf:
                json.dump(templates, tf, indent=2)
                temp_name = tf.name
            os.replace(temp_name, self.custom_templates_index)

            logger.info(f"Saved custom template: {title} ({suffix_clean})")
            return {"status": "success", "template": entry}
        except Exception as e:
            logger.error(f"Failed to save custom template: {e}")
            return {"status": "error", "message": str(e)}

    def toggle_custom_template(self, template_id: str, enabled: bool) -> dict:
        """Toggles a custom template on or off."""
        try:
            templates = self.get_custom_templates()
            found = False
            for t in templates:
                if t.get("id") == template_id:
                    t["enabled"] = enabled
                    found = True
                    break
            if not found:
                return {"status": "error", "message": f"Template {template_id} not found"}

            with tempfile.NamedTemporaryFile("w", dir=self.custom_templates_dir, delete=False, encoding="utf-8") as tf:
                json.dump(templates, tf, indent=2)
                temp_name = tf.name
            os.replace(temp_name, self.custom_templates_index)

            return {"status": "success", "id": template_id, "enabled": enabled}
        except Exception as e:
            logger.error(f"Failed to toggle custom template {template_id}: {e}")
            return {"status": "error", "message": str(e)}

    def delete_custom_template(self, template_id: str) -> dict:
        """Deletes a custom template and its file."""
        try:
            templates = self.get_custom_templates()
            target = next((t for t in templates if t.get("id") == template_id), None)
            if not target:
                return {"status": "error", "message": f"Template {template_id} not found"}

            file_path = os.path.join(self.custom_templates_dir, target.get("filename", ""))
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    logger.warning(f"Could not remove custom template file {file_path}: {e}")

            templates = [t for t in templates if t.get("id") != template_id]
            with tempfile.NamedTemporaryFile("w", dir=self.custom_templates_dir, delete=False, encoding="utf-8") as tf:
                json.dump(templates, tf, indent=2)
                temp_name = tf.name
            os.replace(temp_name, self.custom_templates_index)

            logger.info(f"Deleted custom template: {template_id}")
            return {"status": "success", "deleted_id": template_id}
        except Exception as e:
            logger.error(f"Failed to delete custom template {template_id}: {e}")
            return {"status": "error", "message": str(e)}

    # ═══════════════════════════════════════════════════════════════════════════
    # Named Semester Workspaces (.cvsu-workspace.json)
    # ═══════════════════════════════════════════════════════════════════════════

    def get_workspaces_dir(self) -> str:
        os.makedirs(self.workspaces_dir, exist_ok=True)
        return self.workspaces_dir

    def list_workspaces(self) -> list:
        """Returns list of saved workspace summaries sorted by updated_at descending."""
        workspaces_dir = self.get_workspaces_dir()
        results = []
        try:
            for fname in os.listdir(workspaces_dir):
                if not fname.endswith(".json"):
                    continue
                fpath = os.path.join(workspaces_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        ws_id = data.get("workspace_id") or os.path.splitext(fname)[0]
                        name = data.get("name") or ws_id
                        results.append({
                            "workspace_id": ws_id,
                            "name": name,
                            "updated_at": data.get("updated_at", ""),
                            "created_at": data.get("created_at", ""),
                            "schedule_path": data.get("schedule_path", ""),
                            "rosters_count": len(data.get("rosters", [])),
                            "output_dir": data.get("output_dir", ""),
                            "active_template_set": data.get("active_template_set", ""),
                            "file_path": fpath,
                        })
                except Exception as read_err:
                    logger.warning(f"Failed to read workspace file {fpath}: {read_err}")
            results.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        except Exception as e:
            logger.error(f"Error listing workspaces: {e}")
        return results

    def get_workspace(self, workspace_id_or_name: str) -> dict | None:
        """Finds a workspace by its ID or human-readable name."""
        if not workspace_id_or_name:
            return None
        from modules.models.workspace import sanitize_workspace_id
        target_id = sanitize_workspace_id(workspace_id_or_name)
        workspaces_dir = self.get_workspaces_dir()
        direct_path = os.path.join(workspaces_dir, f"{target_id}.json")
        if os.path.isfile(direct_path):
            try:
                with open(direct_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error reading workspace {direct_path}: {e}")
                return None

        # Fallback: scan by name (case-insensitive) or workspace_id
        try:
            for fname in os.listdir(workspaces_dir):
                if not fname.endswith(".json"):
                    continue
                fpath = os.path.join(workspaces_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        if (data.get("workspace_id") == workspace_id_or_name or
                            str(data.get("name", "")).strip().lower() == str(workspace_id_or_name).strip().lower()):
                            return data
                except Exception:
                    continue
        except Exception as e:
            logger.error(f"Error scanning workspaces directory: {e}")
        return None

    def save_workspace(self, name: str, workspace_dict: dict = None) -> dict:
        """Saves or updates a semester workspace snapshot atomically."""
        from modules.models.workspace import SemesterWorkspace, sanitize_workspace_id
        try:
            ws_dir = self.get_workspaces_dir()
            payload = dict(workspace_dict or {})
            if name:
                payload["name"] = name.strip()
            ws_id = payload.get("workspace_id") or sanitize_workspace_id(payload.get("name", "workspace"))
            payload["workspace_id"] = ws_id
            payload["updated_at"] = datetime.now().isoformat()
            if not payload.get("created_at"):
                existing = self.get_workspace(ws_id)
                if existing and existing.get("created_at"):
                    payload["created_at"] = existing["created_at"]
                else:
                    payload["created_at"] = payload["updated_at"]

            ws = SemesterWorkspace.from_dict(payload)
            errors = ws.validate()
            if errors:
                return {"status": "error", "message": "; ".join(errors)}

            target_path = os.path.join(ws_dir, f"{ws.workspace_id}.json")
            with tempfile.NamedTemporaryFile("w", dir=ws_dir, delete=False, encoding="utf-8") as tf:
                json.dump(ws.to_dict(), tf, indent=2)
                temp_name = tf.name
            os.replace(temp_name, target_path)

            logger.info(f"Saved semester workspace: {ws.name} ({ws.workspace_id})")
            return {"status": "success", "workspace": ws.to_dict(), "file_path": target_path}
        except Exception as e:
            logger.error(f"Failed to save workspace: {e}")
            return {"status": "error", "message": str(e)}

    def delete_workspace(self, workspace_id_or_name: str) -> dict:
        """Deletes a saved workspace file."""
        from modules.models.workspace import sanitize_workspace_id
        try:
            ws = self.get_workspace(workspace_id_or_name)
            if not ws:
                return {"status": "error", "message": f"Workspace '{workspace_id_or_name}' not found"}
            ws_id = ws.get("workspace_id") or sanitize_workspace_id(workspace_id_or_name)
            target_path = os.path.join(self.get_workspaces_dir(), f"{ws_id}.json")
            if os.path.exists(target_path):
                os.remove(target_path)
                logger.info(f"Deleted semester workspace: {ws_id}")
                return {"status": "success", "deleted_id": ws_id}
            return {"status": "error", "message": f"Workspace file not found: {target_path}"}
        except Exception as e:
            logger.error(f"Failed to delete workspace: {e}")
            return {"status": "error", "message": str(e)}

    def export_workspace_file(self, file_path: str, workspace_id_or_name: str = None, workspace_dict: dict = None) -> dict:
        """Exports a workspace snapshot to an external file (.cvsu-workspace.json or .json)."""
        from modules.models.workspace import SemesterWorkspace
        if "\x00" in str(file_path):
            return {"status": "error", "message": "Invalid characters in file path"}
        lower_path = str(file_path).lower()
        if not lower_path.endswith(".json") and not lower_path.endswith(".cvsu-workspace.json"):
            return {"status": "error", "message": "Invalid file extension. Expected .json or .cvsu-workspace.json"}

        ws_data = None
        if workspace_dict:
            ws_data = workspace_dict
        elif workspace_id_or_name:
            ws_data = self.get_workspace(workspace_id_or_name)
            if not ws_data:
                return {"status": "error", "message": f"Workspace '{workspace_id_or_name}' not found"}
        else:
            return {"status": "error", "message": "No workspace data or ID provided for export"}

        try:
            ws = SemesterWorkspace.from_dict(ws_data)
            errors = ws.validate()
            if errors:
                return {"status": "error", "message": "; ".join(errors)}
            abs_path = os.path.abspath(file_path)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as f:
                json.dump(ws.to_dict(), f, indent=2)
            logger.info(f"Exported semester workspace to {abs_path}")
            return {"status": "success", "file_path": abs_path, "workspace": ws.to_dict()}
        except Exception as e:
            logger.error(f"Failed to export workspace to {file_path}: {e}")
            return {"status": "error", "message": str(e)}

    def import_workspace_file(self, file_path: str) -> dict:
        """Imports an external .cvsu-workspace.json file and persists it to local workspaces."""
        from modules.models.workspace import SemesterWorkspace
        if "\x00" in str(file_path):
            return {"status": "error", "message": "Invalid characters in file path"}
        lower_path = str(file_path).lower()
        if not lower_path.endswith(".json") and not lower_path.endswith(".cvsu-workspace.json"):
            return {"status": "error", "message": "Invalid file extension. Expected .json or .cvsu-workspace.json"}

        abs_path = os.path.abspath(file_path)
        if not os.path.isfile(abs_path):
            return {"status": "error", "message": f"File does not exist: {abs_path}"}

        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            if not isinstance(raw_data, dict):
                return {"status": "error", "message": "Workspace data must be a JSON object"}

            ws = SemesterWorkspace.from_dict(raw_data)
            errors = ws.validate()
            if errors:
                return {"status": "error", "message": "; ".join(errors)}

            save_res = self.save_workspace(ws.name, ws.to_dict())
            if save_res.get("status") == "success":
                return {"status": "success", "workspace": save_res["workspace"], "file_path": abs_path}
            return save_res
        except Exception as e:
            logger.error(f"Failed to import workspace from {file_path}: {e}")
            return {"status": "error", "message": str(e)}


# Global singleton instance
config_manager = ParserConfigManager()
ConfigManager = ParserConfigManager

