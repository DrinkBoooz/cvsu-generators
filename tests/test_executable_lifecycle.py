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
        evaluate_calls.append((time.time(), js_code))
    
    api._window.evaluate_js = MagicMock(side_effect=fake_evaluate)
    
    def on_window_closing():
        api._is_window_closed = True
        api.cancel_generation()
        
    closure_time = None
    
    def fake_process_all(*args, progress_callback=None, cancel_event=None, **kwargs):
        for i in range(10):
            progress_callback({"step": i, "total": 10})
            time.sleep(0.05)
            if cancel_event and cancel_event.is_set():
                break
                
        return {
            "generated": {"ceit": [], "attendance": [], "grades": []},
            "skipped": {"ceit": [], "attendance": [], "grades": [], "rosters": []},
            "errors": {"ceit": [], "attendance": [], "grades": [], "rosters": []},
            "cancelled": cancel_event.is_set() if cancel_event else False
        }

    def trigger_closure():
        nonlocal closure_time
        time.sleep(0.15)
        closure_time = time.time()
        on_window_closing()

    with patch('executable_test.api.generation.process_all', side_effect=fake_process_all):
        closure_thread = threading.Thread(target=trigger_closure)
        closure_thread.start()
        
        api.run_generation()
        
        timeout = time.time() + 2
        while api._is_processing and time.time() < timeout:
            time.sleep(0.01)
            
        closure_thread.join(timeout=1.0)
        
        assert not api._is_processing
        assert closure_time is not None
        
        # Verify that no evaluate_js calls happen after closure
        for call_time, js_code in evaluate_calls:
            assert call_time <= closure_time, f"evaluate_js called after window closed: {js_code}"
            
        assert len(evaluate_calls) > 0
