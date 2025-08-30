#!/usr/bin/env python3
"""
JavaScript API Call Parser for EspoCRM
Extracts API calls, model operations, and WebSocket usage from JavaScript code
"""

import re
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Set

class JavaScriptAPIParser:
    """Parse JavaScript files for API calls to EspoCRM backend"""
    
    def __init__(self):
        self.api_calls = []
        self.model_operations = []
        self.websocket_operations = []
        self.relationships = []
        
        # Patterns for different API call types
        self.patterns = {
            # Espo.Ajax calls
            'ajax_get': r"Espo\.Ajax\.getRequest\s*\(\s*['\"`]([^'\"`)]+)['\"`]",
            'ajax_post': r"Espo\.Ajax\.postRequest\s*\(\s*['\"`]([^'\"`)]+)['\"`]",
            'ajax_put': r"Espo\.Ajax\.putRequest\s*\(\s*['\"`]([^'\"`)]+)['\"`]",
            'ajax_delete': r"Espo\.Ajax\.deleteRequest\s*\(\s*['\"`]([^'\"`)]+)['\"`]",
            'ajax_patch': r"Espo\.Ajax\.patchRequest\s*\(\s*['\"`]([^'\"`)]+)['\"`]",
            
            # Fetch API
            'fetch': r"fetch\s*\(\s*['\"`](/api/[^'\"`)]+)['\"`]",
            'fetch_dynamic': r"fetch\s*\(\s*['\"`]\$\{[^}]+\}['\"`]",
            
            # Model operations
            'model_fetch': r"model\.fetch\s*\(",
            'model_save': r"model\.save\s*\(",
            'model_destroy': r"model\.destroy\s*\(",
            'model_sync': r"model\.sync\s*\(",
            
            # Collection operations
            'collection_fetch': r"collection\.fetch\s*\(",
            'collection_create': r"collection\.create\s*\(",
            'collection_sync': r"collection\.sync\s*\(",
            
            # Factory methods
            'model_factory': r"getModelFactory\(\)\.create\s*\(\s*['\"`](\w+)['\"`]",
            'collection_factory': r"getCollectionFactory\(\)\.create\s*\(\s*['\"`](\w+)['\"`]",
            
            # WebSocket
            'websocket_subscribe': r"webSocketManager\.subscribe\s*\(\s*['\"`]([^'\"`)]+)['\"`]",
            'websocket_emit': r"webSocketManager\.emit\s*\(\s*['\"`]([^'\"`)]+)['\"`]",
            'websocket_send': r"webSocket\.send\s*\(",
            
            # API endpoint patterns
            'entity_pattern': r"['\"`]/?([\w]+)/([a-zA-Z0-9]+)['\"`]",
            'action_pattern': r"['\"`]/?([\w]+)/action/(\w+)['\"`]",
            'relationship_pattern': r"['\"`]/?([\w]+)/([a-zA-Z0-9]+)/([\w]+)['\"`]",
        }
    
    def parse_file(self, file_path: str) -> Dict:
        """Parse a JavaScript file for API calls"""
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return {'error': str(e), 'file': file_path}
        
        file_id = hashlib.md5(file_path.encode()).hexdigest()
        
        # Extract all API calls
        api_calls = self.extract_api_calls(content, file_path)
        
        # Extract model operations
        model_ops = self.extract_model_operations(content, file_path)
        
        # Extract WebSocket operations
        ws_ops = self.extract_websocket_operations(content, file_path)
        
        # Create relationships
        self.create_relationships(file_id, api_calls, model_ops, ws_ops)
        
        return {
            'file': file_path,
            'api_calls': api_calls,
            'model_operations': model_ops,
            'websocket_operations': ws_ops,
            'stats': {
                'total_api_calls': len(api_calls),
                'total_model_ops': len(model_ops),
                'total_websocket_ops': len(ws_ops),
                'unique_endpoints': len(set(call.get('endpoint') for call in api_calls if call.get('endpoint')))
            }
        }
    
    def extract_api_calls(self, content: str, file_path: str) -> List[Dict]:
        """Extract API calls from JavaScript content"""
        
        calls = []
        
        # Espo.Ajax.getRequest
        for match in re.finditer(self.patterns['ajax_get'], content):
            endpoint = match.group(1)
            calls.append({
                'type': 'AJAX_GET',
                'method': 'GET',
                'endpoint': endpoint,
                'entity': self.extract_entity_from_endpoint(endpoint),
                'line': content[:match.start()].count('\n') + 1
            })
        
        # Espo.Ajax.postRequest
        for match in re.finditer(self.patterns['ajax_post'], content):
            endpoint = match.group(1)
            calls.append({
                'type': 'AJAX_POST',
                'method': 'POST',
                'endpoint': endpoint,
                'entity': self.extract_entity_from_endpoint(endpoint),
                'line': content[:match.start()].count('\n') + 1
            })
        
        # Espo.Ajax.putRequest
        for match in re.finditer(self.patterns['ajax_put'], content):
            endpoint = match.group(1)
            calls.append({
                'type': 'AJAX_PUT',
                'method': 'PUT',
                'endpoint': endpoint,
                'entity': self.extract_entity_from_endpoint(endpoint),
                'line': content[:match.start()].count('\n') + 1
            })
        
        # Espo.Ajax.deleteRequest
        for match in re.finditer(self.patterns['ajax_delete'], content):
            endpoint = match.group(1)
            calls.append({
                'type': 'AJAX_DELETE',
                'method': 'DELETE',
                'endpoint': endpoint,
                'entity': self.extract_entity_from_endpoint(endpoint),
                'line': content[:match.start()].count('\n') + 1
            })
        
        # Fetch API
        for match in re.finditer(self.patterns['fetch'], content):
            endpoint = match.group(1)
            
            # Try to determine method from context
            method = 'GET'
            context = content[max(0, match.start()-100):match.end()+200]
            if 'method:' in context or 'method :' in context:
                method_match = re.search(r"method\s*:\s*['\"](\w+)['\"]", context)
                if method_match:
                    method = method_match.group(1).upper()
            
            calls.append({
                'type': 'FETCH',
                'method': method,
                'endpoint': endpoint,
                'entity': self.extract_entity_from_endpoint(endpoint),
                'line': content[:match.start()].count('\n') + 1
            })
        
        # Detect action endpoints
        for match in re.finditer(self.patterns['action_pattern'], content):
            entity, action = match.groups()
            calls.append({
                'type': 'ACTION',
                'method': 'POST',
                'endpoint': f"{entity}/action/{action}",
                'entity': entity,
                'action': action,
                'line': content[:match.start()].count('\n') + 1
            })
        
        self.api_calls.extend(calls)
        return calls
    
    def extract_model_operations(self, content: str, file_path: str) -> List[Dict]:
        """Extract Backbone model operations"""
        
        operations = []
        
        # Model fetch
        for match in re.finditer(self.patterns['model_fetch'], content):
            operations.append({
                'type': 'MODEL_FETCH',
                'operation': 'fetch',
                'line': content[:match.start()].count('\n') + 1
            })
        
        # Model save
        for match in re.finditer(self.patterns['model_save'], content):
            operations.append({
                'type': 'MODEL_SAVE',
                'operation': 'save',
                'line': content[:match.start()].count('\n') + 1
            })
        
        # Model destroy
        for match in re.finditer(self.patterns['model_destroy'], content):
            operations.append({
                'type': 'MODEL_DESTROY',
                'operation': 'destroy',
                'line': content[:match.start()].count('\n') + 1
            })
        
        # Collection fetch
        for match in re.finditer(self.patterns['collection_fetch'], content):
            operations.append({
                'type': 'COLLECTION_FETCH',
                'operation': 'fetch',
                'line': content[:match.start()].count('\n') + 1
            })
        
        # Model factory
        for match in re.finditer(self.patterns['model_factory'], content):
            entity = match.group(1)
            operations.append({
                'type': 'MODEL_CREATE',
                'operation': 'create',
                'entity': entity,
                'line': content[:match.start()].count('\n') + 1
            })
        
        # Collection factory
        for match in re.finditer(self.patterns['collection_factory'], content):
            entity = match.group(1)
            operations.append({
                'type': 'COLLECTION_CREATE',
                'operation': 'create',
                'entity': entity,
                'line': content[:match.start()].count('\n') + 1
            })
        
        self.model_operations.extend(operations)
        return operations
    
    def extract_websocket_operations(self, content: str, file_path: str) -> List[Dict]:
        """Extract WebSocket operations"""
        
        operations = []
        
        # WebSocket subscribe
        for match in re.finditer(self.patterns['websocket_subscribe'], content):
            topic = match.group(1)
            operations.append({
                'type': 'WS_SUBSCRIBE',
                'topic': topic,
                'line': content[:match.start()].count('\n') + 1
            })
        
        # WebSocket emit
        for match in re.finditer(self.patterns['websocket_emit'], content):
            event = match.group(1)
            operations.append({
                'type': 'WS_EMIT',
                'event': event,
                'line': content[:match.start()].count('\n') + 1
            })
        
        # WebSocket send
        for match in re.finditer(self.patterns['websocket_send'], content):
            operations.append({
                'type': 'WS_SEND',
                'line': content[:match.start()].count('\n') + 1
            })
        
        self.websocket_operations.extend(operations)
        return operations
    
    def extract_entity_from_endpoint(self, endpoint: str) -> str:
        """Extract entity name from API endpoint"""
        
        # Remove leading slash and API prefix
        endpoint = endpoint.lstrip('/').replace('api/v1/', '')
        
        # Split by slash and get first part
        parts = endpoint.split('/')
        if parts:
            # Handle special cases
            if parts[0] == 'action' and len(parts) > 1:
                return parts[1]
            return parts[0]
        
        return None
    
    def create_relationships(self, file_id: str, api_calls: List, model_ops: List, ws_ops: List):
        """Create relationships from JavaScript to backend"""
        
        # Create relationships for API calls
        for call in api_calls:
            if call.get('entity'):
                self.relationships.append({
                    'type': 'JS_CALLS_API',
                    'source_id': file_id,
                    'target_entity': call['entity'],
                    'method': call['method'],
                    'endpoint': call.get('endpoint')
                })
            
            if call.get('action'):
                self.relationships.append({
                    'type': 'JS_CALLS_ACTION',
                    'source_id': file_id,
                    'target_entity': call['entity'],
                    'action': call['action']
                })
        
        # Create relationships for model operations
        for op in model_ops:
            if op.get('entity'):
                self.relationships.append({
                    'type': 'JS_USES_MODEL',
                    'source_id': file_id,
                    'target_entity': op['entity'],
                    'operation': op['operation']
                })
        
        # Create relationships for WebSocket operations
        for op in ws_ops:
            if op.get('topic'):
                self.relationships.append({
                    'type': 'JS_SUBSCRIBES_TOPIC',
                    'source_id': file_id,
                    'topic': op['topic']
                })
            elif op.get('event'):
                self.relationships.append({
                    'type': 'JS_EMITS_EVENT',
                    'source_id': file_id,
                    'event': op['event']
                })
    
    def parse_directory(self, directory: str) -> Dict:
        """Parse all JavaScript files in a directory"""
        
        js_files = []
        for ext in ['*.js', '*.jsx', '*.ts', '*.tsx']:
            js_files.extend(Path(directory).rglob(ext))
        
        results = []
        for file_path in js_files:
            result = self.parse_file(str(file_path))
            if not result.get('error'):
                results.append(result)
        
        return {
            'files_parsed': len(results),
            'total_api_calls': sum(r['stats']['total_api_calls'] for r in results),
            'total_model_ops': sum(r['stats']['total_model_ops'] for r in results),
            'total_websocket_ops': sum(r['stats']['total_websocket_ops'] for r in results),
            'relationships': self.relationships
        }


def test_js_api_parser():
    """Test the JavaScript API parser"""
    
    parser = JavaScriptAPIParser()
    
    print("\n" + "="*70)
    print("JAVASCRIPT API PARSER TEST")
    print("="*70)
    
    # Test with our test file
    result = parser.parse_file('tests/test_js_api.js')
    
    if result.get('error'):
        print(f"Error: {result['error']}")
        return
    
    print(f"\n📁 File: {result['file']}")
    print("-" * 40)
    
    print(f"\n📊 Statistics:")
    for key, value in result['stats'].items():
        print(f"  {key}: {value}")
    
    print(f"\n🌐 API Calls Found:")
    for call in result['api_calls'][:10]:  # Show first 10
        print(f"  {call['method']:6} {call.get('endpoint', 'N/A'):30} (line {call['line']})")
    
    if len(result['api_calls']) > 10:
        print(f"  ... and {len(result['api_calls']) - 10} more")
    
    print(f"\n📦 Model Operations:")
    op_types = {}
    for op in result['model_operations']:
        op_type = op['type']
        op_types[op_type] = op_types.get(op_type, 0) + 1
    
    for op_type, count in op_types.items():
        print(f"  {op_type}: {count}")
    
    print(f"\n🔌 WebSocket Operations:")
    ws_types = {}
    for op in result['websocket_operations']:
        ws_type = op['type']
        ws_types[ws_type] = ws_types.get(ws_type, 0) + 1
    
    for ws_type, count in ws_types.items():
        print(f"  {ws_type}: {count}")
    
    # Show relationships
    print(f"\n🔗 Relationships Created:")
    rel_types = {}
    for rel in parser.relationships:
        rel_type = rel['type']
        rel_types[rel_type] = rel_types.get(rel_type, 0) + 1
    
    for rel_type, count in rel_types.items():
        print(f"  {rel_type}: {count}")
    
    return result


if __name__ == "__main__":
    test_js_api_parser()