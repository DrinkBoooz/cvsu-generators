import os
import sys
import pytest
from unittest.mock import MagicMock, patch

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from executable_test.native.dnd import setup_window_drag_and_drop

class MockDOMEvent:
    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def trigger(self, event_data):
        for h in self.handlers:
            if hasattr(h, 'callback'):
                h.callback(event_data)
            else:
                h(event_data)

class MockElement:
    def __init__(self):
        self.events = MagicMock()
        self.events.dragenter = MockDOMEvent()
        self.events.dragover = MockDOMEvent()
        self.events.drop = MockDOMEvent()
        self.events.dragleave = MockDOMEvent()

class MockWindow:
    def __init__(self):
        self.native = None
        self.events = MagicMock()
        self.events.loaded.wait = MagicMock()
        
        self.doc_element = MockElement()
        self.sched_element = MockElement()
        self.rosters_element = MockElement()
        self.template_element = MockElement()

        self.dom = MagicMock()
        self.dom.document = self.doc_element
        
        def get_elem(selector):
            if selector == '#scheduleDropzone': return self.sched_element
            if selector == '#rostersDropzone': return self.rosters_element
            if selector == '#templateDropzone': return self.template_element
            return None
            
        self.dom.get_element = MagicMock(side_effect=get_elem)
        self.evaluate_js = MagicMock()

@pytest.fixture
def dnd_setup(monkeypatch):
    window = MockWindow()
    api = MagicMock()
    api.schedule_path = None
    
    import webview.dom
    
    class FakeDOMEventHandler:
        def __init__(self, callback, *args, **kwargs):
            self.callback = callback
            
    monkeypatch.setattr(webview.dom, 'DOMEventHandler', FakeDOMEventHandler)
    
    setup_window_drag_and_drop(window, api)
        
    return window, api

def test_dnd_routing_3_roster_files(dnd_setup):
    window, api = dnd_setup
    api.handle_dropped_rosters.return_value = {"status": "ok"}
    event_data = {
        'dataTransfer': {
            'files': [
                {'pywebviewFullPath': 'C:\\temp\\roster1.csv'},
                {'pywebviewFullPath': 'C:\\temp\\roster2.xlsx'},
                {'pywebviewFullPath': 'C:\\temp\\roster3.xls'}
            ]
        }
    }
    
    with patch('os.path.isfile', return_value=True):
        window.rosters_element.events.drop.trigger(event_data)
        
        api.handle_dropped_rosters.assert_called_once()
        payloads = api.handle_dropped_rosters.call_args[0][0]
        assert len(payloads) == 3
        assert payloads[0]['path'] == 'C:\\temp\\roster1.csv'
        assert payloads[1]['path'] == 'C:\\temp\\roster2.xlsx'
        assert payloads[2]['path'] == 'C:\\temp\\roster3.xls'

def test_dnd_routing_schedule_xlsx(dnd_setup):
    window, api = dnd_setup
    api.handle_dropped_schedule.return_value = {"status": "ok"}
    event_data = {
        'dataTransfer': {
            'files': [
                {'pywebviewFullPath': 'C:\\temp\\schedule.xlsx'}
            ]
        }
    }
    with patch('os.path.isfile', return_value=True):
        window.sched_element.events.drop.trigger(event_data)
        api.handle_dropped_schedule.assert_called_once_with('schedule.xlsx', original_path='C:\\temp\\schedule.xlsx')

def test_dnd_routing_mixed_excel_document_level(dnd_setup):
    window, api = dnd_setup
    api.handle_dropped_schedule.return_value = {"status": "ok"}
    api.handle_dropped_rosters.return_value = {"status": "ok"}
    
    def fake_inspect(path):
        if 'schedule' in path.lower():
            return {'total_slots': 10}
        return {'total_slots': 0}
        
    with patch('os.path.isfile', return_value=True), patch('executable_test.native.dnd.inspect_schedule_file', side_effect=fake_inspect):
        event_data = {
            'dataTransfer': {
                'files': [
                    {'pywebviewFullPath': 'C:\\temp\\My_Schedule.xlsx'},
                    {'pywebviewFullPath': 'C:\\temp\\Some_Roster.xlsx'}
                ]
            }
        }
        
        window.doc_element.events.drop.trigger(event_data)
        
        api.handle_dropped_schedule.assert_called_once_with('My_Schedule.xlsx', original_path='C:\\temp\\My_Schedule.xlsx')
        
        api.handle_dropped_rosters.assert_called_once()
        payloads = api.handle_dropped_rosters.call_args[0][0]
        assert len(payloads) == 1
        assert payloads[0]['path'] == 'C:\\temp\\Some_Roster.xlsx'

def test_dnd_routing_same_filename_different_dirs(dnd_setup):
    window, api = dnd_setup
    api.handle_dropped_rosters.return_value = {"status": "ok"}
    
    event_data = {
        'dataTransfer': {
            'files': [
                {'pywebviewFullPath': 'C:\\Section A\\IT 101.xlsx'},
                {'pywebviewFullPath': 'C:\\Section B\\IT 101.xlsx'}
            ]
        }
    }
    
    with patch('os.path.isfile', return_value=True):
        window.rosters_element.events.drop.trigger(event_data)
        
        api.handle_dropped_rosters.assert_called_once()
        payloads = api.handle_dropped_rosters.call_args[0][0]
        assert len(payloads) == 2
        assert payloads[0]['path'] == 'C:\\Section A\\IT 101.xlsx'
        assert payloads[1]['path'] == 'C:\\Section B\\IT 101.xlsx'
        assert payloads[0]['filename'] == 'IT 101.xlsx'
        assert payloads[1]['filename'] == 'IT 101.xlsx'

def test_dnd_routing_csv_always_roster(dnd_setup):
    window, api = dnd_setup
    api.handle_dropped_rosters.return_value = {"status": "ok"}
    
    event_data = {
        'dataTransfer': {
            'files': [
                {'pywebviewFullPath': 'C:\\temp\\data.csv'}
            ]
        }
    }
    
    with patch('os.path.isfile', return_value=True):
        window.doc_element.events.drop.trigger(event_data)
        
        api.handle_dropped_rosters.assert_called_once()
        payloads = api.handle_dropped_rosters.call_args[0][0]
        assert payloads[0]['path'] == 'C:\\temp\\data.csv'

def test_dnd_routing_docx_template(dnd_setup):
    window, api = dnd_setup
    api.inspect_custom_template.return_value = {"status": "ok"}
    
    event_data = {
        'dataTransfer': {
            'files': [
                {'pywebviewFullPath': 'C:\\temp\\template.docx'}
            ]
        }
    }
    
    with patch('os.path.isfile', return_value=True):
        window.template_element.events.drop.trigger(event_data)
        api.inspect_custom_template.assert_called_once_with('C:\\temp\\template.docx')

def test_dnd_routing_unsupported_file_ignored(dnd_setup):
    window, api = dnd_setup
    
    event_data = {
        'dataTransfer': {
            'files': [
                {'pywebviewFullPath': 'C:\\temp\\virus.exe'},
                {'pywebviewFullPath': 'C:\\temp\\image.png'}
            ]
        }
    }
    
    with patch('os.path.exists', return_value=True):
        window.doc_element.events.drop.trigger(event_data)
        window.sched_element.events.drop.trigger(event_data)
        window.rosters_element.events.drop.trigger(event_data)
        window.template_element.events.drop.trigger(event_data)
        
        api.handle_dropped_schedule.assert_not_called()
        api.handle_dropped_rosters.assert_not_called()
        api.inspect_custom_template.assert_not_called()

def test_dnd_routing_empty_event_no_crash(dnd_setup):
    window, api = dnd_setup
    
    window.doc_element.events.drop.trigger({})
    window.sched_element.events.drop.trigger({})
    window.doc_element.events.drop.trigger({'dataTransfer': {}})
    window.doc_element.events.drop.trigger({'dataTransfer': {'files': []}})
    
    api.handle_dropped_schedule.assert_not_called()
