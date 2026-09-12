import pytest
from unittest.mock import MagicMock, patch
import threading
import time

from executable_test.main import ScriptAPI

def test_window_closed_prevents_js_callbacks():
    api = ScriptAPI()
    api.schedule_path = "C:\\fake\\schedule.xlsx"
    api.rosters = [{'path': 'C:\\fake\\roster.csv', 'filename': 'roster.csv'}]
    api.output_dir = "C:\\fake\\out"
    api._window = MagicMock()
    
    api._is_window_closed = True
    
    def fake_process_all(*args, progress_callback=None, **kwargs):
        if progress_callback:
            progress_callback({"step": 1, "total": 10})
            
        return {
            "generated": {"ceit": [], "attendance": [], "grades": []},
            "skipped": {"ceit": [], "attendance": [], "grades": [], "rosters": []},
            "errors": {"ceit": [], "attendance": [], "grades": [], "rosters": []},
            "cancelled": False
        }
        
    with patch('executable_test.api.generation.process_all', side_effect=fake_process_all):
        api.run_generation()
        
        timeout = time.time() + 2
        while api._is_processing and time.time() < timeout:
            time.sleep(0.01)
            
        assert not api._is_processing
        api._window.evaluate_js.assert_not_called()

def test_lifecycle_concurrency_race():
    api = ScriptAPI()
    api.schedule_path = "C:\\fake\\schedule.xlsx"
    api.rosters = [{'path': 'C:\\fake\\roster.csv', 'filename': 'roster.csv'}]
    api.output_dir = "C:\\fake\\out"
    api._window = MagicMock()
    
    evaluate_calls = []
    def fake_evaluate(js_code):
        evaluate_calls.append(js_code)
    
    api._window.evaluate_js = MagicMock(side_effect=fake_evaluate)
    
    def fake_process_all(*args, progress_callback=None, cancel_event=None, **kwargs):
        for i in range(10):
            if i == 5:
                api._is_window_closed = True
                cancel_event.set()
                
            progress_callback({"step": i, "total": 10})
            time.sleep(0.02)
            
        return {
            "generated": {"ceit": [], "attendance": [], "grades": []},
            "skipped": {"ceit": [], "attendance": [], "grades": [], "rosters": []},
            "errors": {"ceit": [], "attendance": [], "grades": [], "rosters": []},
            "cancelled": True
        }

    with patch('executable_test.api.generation.process_all', side_effect=fake_process_all):
        api.run_generation()
        
        timeout = time.time() + 2
        while api._is_processing and time.time() < timeout:
            time.sleep(0.01)
            
        assert not api._is_processing
        
        assert len(evaluate_calls) == 5
        
        for call in evaluate_calls:
            assert 'onGenerationComplete' not in call
            assert 'onGenerationError' not in call
            assert '"step": 5' not in call
            assert '"step": 6' not in call
            assert '"step": 7' not in call
            assert '"step": 8' not in call
            assert '"step": 9' not in call
