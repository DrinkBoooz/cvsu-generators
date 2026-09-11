"""
Modular API Layer for CvSU Document Generator (executable_test).
Exposes the composite ScriptAPI consumed by pywebview JavaScript bridge.
"""

from .base import BaseAPI, sanitize_filename, get_resource_path
from .schedule_roster import ScheduleRosterMixin
from .config import ConfigMixin
from .templates import TemplateMixin
from .system import SystemMixin
from .generation import GenerationMixin

class ScriptAPI(
    ScheduleRosterMixin,
    ConfigMixin,
    TemplateMixin,
    SystemMixin,
    GenerationMixin,
    BaseAPI
):
    """
    Composite API class exposed to the UI layer via pywebview js_api.
    Integrates schedule, roster, configuration, template, system, and generation subsystems.
    """
    pass

__all__ = [
    "ScriptAPI",
    "BaseAPI",
    "sanitize_filename",
    "get_resource_path",
]
