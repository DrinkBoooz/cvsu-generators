import os
import sys
import json
import re
import shutil
import tempfile
from datetime import datetime
from copy import deepcopy
from modules.common.logger import logger


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
        "schedule_config": dict(DEFAULT_SCHEDULE_CONFIG)
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


# Global singleton instance
config_manager = ParserConfigManager()
ConfigManager = ParserConfigManager

