import os
import sys
import pytest

# Add the test directory to path so we can import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../executable_test')))

from api import ScriptAPI

def test_script_api_bindings():
    """
    Test that the composite ScriptAPI class has all the methods
    expected by the JavaScript bridge in executable_test/js/
    """
    # Create a mock window
    class MockWindow:
        pass
        
    api = ScriptAPI()
    api._window = MockWindow()
    
    expected_methods = [
        # schedule_roster.py
        'browse_schedule',
        'clear_schedule',
        'inspect_schedule',
        'browse_rosters',
        'clear_rosters',
        'remove_roster',
        'inspect_roster',
        'validate_rosters',
        'detect_classes',
        
        # templates.py
        'get_custom_templates',
        'browse_custom_template',
        'save_custom_template',
        'toggle_custom_template',
        'delete_custom_template',
        
        # generation.py
        'cancel_generation',
        'run_generation',
        
        # system.py
        'browse_output',
        'open_output_folder',
        'open_file',
        'get_recent_logs',
        'open_log_folder',
        
        # config.py
        'get_parser_config',
        'save_parser_config',
        'reset_parser_config',
        'import_parser_config',
        'export_parser_config'
    ]
    
    missing_methods = []
    for method_name in expected_methods:
        if not hasattr(api, method_name) or not callable(getattr(api, method_name)):
            missing_methods.append(method_name)
            
    assert not missing_methods, f"ScriptAPI is missing the following JS-bound methods: {missing_methods}"
