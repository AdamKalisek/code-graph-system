#!/usr/bin/env python3
"""
Comprehensive tests for enhanced JavaScript parser
Tests all patterns: ES6, AMD, CommonJS, Backbone, API calls
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import tempfile
from pathlib import Path
from plugins.javascript.tree_sitter_enhanced import EnhancedJavaScriptParser

def test_es6_class():
    """Test ES6 class parsing with inheritance"""
    code = """
    class UserView extends BaseView {
        constructor(options) {
            super(options);
            this.name = 'UserView';
        }
        
        render() {
            console.log('Rendering user view');
            return this;
        }
        
        static VERSION = '1.0.0';
    }
    """
    
    parser = EnhancedJavaScriptParser()
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
        f.write(code)
        f.flush()
        
        result = parser.parse_file(f.name)
        
    # Check nodes
    node_types = {node.kind for node in result.nodes}
    assert 'file' in node_types
    assert 'class' in node_types
    assert 'method' in node_types
    
    # Find the class
    class_node = next((n for n in result.nodes if n.kind == 'class'), None)
    assert class_node is not None
    assert class_node.name == 'UserView'
    assert class_node.metadata.get('extends') == 'BaseView'
    
    # Check methods
    methods = [n for n in result.nodes if n.kind == 'method']
    method_names = {m.name for m in methods}
    assert 'constructor' in method_names
    assert 'render' in method_names
    
    # Check relationships
    rel_types = {rel.type for rel in result.relationships}
    assert 'EXTENDS' in rel_types
    assert 'HAS_METHOD' in rel_types
    assert 'DEFINED_IN' in rel_types
    
    print("✅ ES6 class test passed")
    return True

def test_functions():
    """Test various function types"""
    code = """
    // Named function
    function processUser(id) {
        return fetch('/api/user/' + id);
    }
    
    // Arrow function
    const fetchData = async (url) => {
        const response = await fetch(url);
        return response.json();
    };
    
    // Function expression
    const handler = function(event) {
        console.log(event);
    };
    """
    
    parser = EnhancedJavaScriptParser()
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
        f.write(code)
        f.flush()
        
        result = parser.parse_file(f.name)
    
    # Check functions
    functions = [n for n in result.nodes if n.kind == 'function']
    func_names = {f.name for f in functions}
    assert 'processUser' in func_names
    assert 'fetchData' in func_names
    assert 'handler' in func_names
    
    # Check async function
    async_func = next((f for f in functions if f.name == 'fetchData'), None)
    assert async_func is not None
    assert async_func.metadata.get('async') == True or async_func.metadata.get('arrow') == True
    
    print("✅ Functions test passed")
    return True

def test_amd_module():
    """Test AMD define pattern"""
    code = """
    define(['views/base', 'models/user', 'utils/helpers'], function(BaseView, UserModel, helpers) {
        
        const ListView = BaseView.extend({
            model: UserModel,
            
            initialize: function() {
                this.listenTo(this.model, 'change', this.render);
            },
            
            render: function() {
                helpers.log('Rendering list');
                return this;
            }
        });
        
        return ListView;
    });
    """
    
    parser = EnhancedJavaScriptParser()
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
        f.write(code)
        f.flush()
        
        result = parser.parse_file(f.name)
    
    # Check AMD module
    amd_modules = [n for n in result.nodes if n.kind == 'amd_module']
    assert len(amd_modules) > 0
    
    # Check dependencies
    imports = [n for n in result.nodes if n.kind == 'import']
    import_names = {i.name for i in imports}
    assert 'views/base' in import_names
    assert 'models/user' in import_names
    assert 'utils/helpers' in import_names
    
    # Check import relationships
    import_rels = [r for r in result.relationships if r.type == 'IMPORTS']
    assert len(import_rels) >= 3
    
    print("✅ AMD module test passed")
    return True

def test_commonjs():
    """Test CommonJS patterns"""
    code = """
    const fs = require('fs');
    const path = require('path');
    const { EventEmitter } = require('events');
    
    class FileWatcher extends EventEmitter {
        watch(filepath) {
            fs.watch(filepath, (event, filename) => {
                this.emit('change', filename);
            });
        }
    }
    
    module.exports = FileWatcher;
    exports.version = '1.0.0';
    """
    
    parser = EnhancedJavaScriptParser()
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
        f.write(code)
        f.flush()
        
        result = parser.parse_file(f.name)
    
    # Check requires
    imports = [n for n in result.nodes if n.kind == 'import' and n.metadata.get('module_type') == 'commonjs']
    import_names = {i.name for i in imports}
    assert 'fs' in import_names
    assert 'path' in import_names
    assert 'events' in import_names
    
    print("✅ CommonJS test passed")
    return True

def test_es6_modules():
    """Test ES6 import/export"""
    code = """
    import React from 'react';
    import { Component, useState } from 'react';
    import * as utils from './utils';
    
    export class UserComponent extends Component {
        render() {
            return <div>User</div>;
        }
    }
    
    export default UserComponent;
    export { utils };
    """
    
    parser = EnhancedJavaScriptParser()
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
        f.write(code)
        f.flush()
        
        result = parser.parse_file(f.name)
    
    # Check imports
    imports = [n for n in result.nodes if n.kind == 'import' and n.metadata.get('module_type') == 'es6']
    import_names = {i.name for i in imports}
    assert 'react' in import_names
    assert './utils' in import_names
    
    print("✅ ES6 modules test passed")
    return True

def test_backbone_components():
    """Test Backbone.js patterns"""
    code = """
    const UserView = Backbone.View.extend({
        tagName: 'div',
        className: 'user-view',
        
        events: {
            'click .save': 'saveUser',
            'click .delete': 'deleteUser'
        },
        
        initialize: function(options) {
            this.model = new UserModel(options.data);
            this.listenTo(this.model, 'change', this.render);
        },
        
        saveUser: function() {
            this.model.save();
        }
    });
    
    const UserModel = Backbone.Model.extend({
        urlRoot: '/api/users',
        
        defaults: {
            name: '',
            email: ''
        }
    });
    
    const UserCollection = Backbone.Collection.extend({
        model: UserModel,
        url: '/api/users'
    });
    """
    
    parser = EnhancedJavaScriptParser()
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
        f.write(code)
        f.flush()
        
        result = parser.parse_file(f.name)
    
    # Check Backbone components
    backbone_nodes = [n for n in result.nodes if 'backbone' in n.kind]
    assert len(backbone_nodes) >= 3
    
    # Check component types
    component_types = {n.metadata.get('backbone_type') for n in backbone_nodes if n.metadata.get('backbone_type')}
    assert 'View' in component_types
    assert 'Model' in component_types
    assert 'Collection' in component_types
    
    print("✅ Backbone components test passed")
    return True

def test_api_calls():
    """Test API call extraction"""
    code = """
    // Espo.Ajax calls
    Espo.Ajax.getRequest('User/action/list').then(response => {
        console.log(response);
    });
    
    Espo.Ajax.postRequest('Lead/action/convert', {
        id: leadId,
        data: convertData
    });
    
    Espo.Ajax.deleteRequest('Task/' + taskId);
    
    // Fetch API
    fetch('/api/v1/users')
        .then(res => res.json())
        .then(data => console.log(data));
    
    fetch('/api/v1/user/' + userId, {
        method: 'PUT',
        body: JSON.stringify(userData)
    });
    
    // jQuery Ajax
    $.ajax({
        url: '/api/v1/settings',
        method: 'GET',
        success: function(data) {
            console.log(data);
        }
    });
    """
    
    parser = EnhancedJavaScriptParser()
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
        f.write(code)
        f.flush()
        
        result = parser.parse_file(f.name)
    
    # Check endpoint nodes
    endpoints = [n for n in result.nodes if n.kind == 'endpoint']
    assert len(endpoints) >= 5
    
    # Check endpoint URLs
    urls = {e.metadata.get('url') for e in endpoints}
    assert 'User/action/list' in urls
    assert 'Lead/action/convert' in urls
    assert '/api/v1/users' in urls
    
    # Check API call relationships
    api_rels = [r for r in result.relationships if r.type == 'CALLS_API']
    assert len(api_rels) >= 5
    
    print("✅ API calls test passed")
    return True

def test_relationships():
    """Test relationship extraction"""
    code = """
    class UserService {
        constructor() {
            this.api = new ApiClient();
        }
        
        async getUser(id) {
            const user = await this.api.fetch('/users/' + id);
            return this.processUser(user);
        }
        
        processUser(user) {
            const validator = new UserValidator();
            return validator.validate(user);
        }
    }
    
    function createService() {
        return new UserService();
    }
    
    const service = createService();
    service.getUser(123);
    """
    
    parser = EnhancedJavaScriptParser()
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
        f.write(code)
        f.flush()
        
        result = parser.parse_file(f.name)
    
    # Check relationship types
    rel_types = {rel.type for rel in result.relationships}
    assert 'INSTANTIATES' in rel_types  # new ApiClient, new UserValidator, new UserService
    assert 'CALLS' in rel_types  # Various method calls
    assert 'HAS_METHOD' in rel_types  # Class methods
    assert 'DEFINED_IN' in rel_types  # All entities defined in file
    
    # Check instantiation relationships
    instantiates = [r for r in result.relationships if r.type == 'INSTANTIATES']
    assert len(instantiates) >= 2  # At least ApiClient and UserValidator
    
    print("✅ Relationships test passed")
    return True

def test_espocrm_patterns():
    """Test real EspoCRM patterns"""
    code = """
    define('views/user/detail', ['views/detail'], function (Dep) {
        
        return Dep.extend({
            
            setup: function () {
                Dep.prototype.setup.call(this);
                
                this.setupTitle();
                this.setupMenu();
            },
            
            setupTitle: function () {
                this.title = this.model.get('name');
            },
            
            setupMenu: function () {
                this.menu = {
                    'buttons': [
                        {
                            'label': 'Edit',
                            'action': 'edit',
                            'style': 'primary'
                        }
                    ]
                };
            },
            
            actionEdit: function () {
                Espo.Ajax.getRequest('User/' + this.model.id).then(function (user) {
                    this.model.set(user);
                    this.notify('Loaded', 'success');
                }.bind(this));
            }
        });
    });
    """
    
    parser = EnhancedJavaScriptParser()
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
        f.write(code)
        f.flush()
        
        result = parser.parse_file(f.name)
    
    # Check AMD module
    amd_modules = [n for n in result.nodes if n.kind == 'amd_module']
    assert len(amd_modules) > 0
    
    # Check dependencies
    imports = [n for n in result.nodes if n.kind == 'import']
    import_names = {i.name for i in imports}
    assert 'views/detail' in import_names
    
    # Check API endpoint
    endpoints = [n for n in result.nodes if n.kind == 'endpoint']
    assert len(endpoints) >= 1
    
    print("✅ EspoCRM patterns test passed")
    return True

def run_all_tests():
    """Run all parser tests"""
    print("\n" + "="*60)
    print("JAVASCRIPT ENHANCED PARSER TESTS")
    print("="*60)
    
    tests = [
        ("ES6 Classes", test_es6_class),
        ("Functions", test_functions),
        ("AMD Modules", test_amd_module),
        ("CommonJS", test_commonjs),
        ("ES6 Modules", test_es6_modules),
        ("Backbone Components", test_backbone_components),
        ("API Calls", test_api_calls),
        ("Relationships", test_relationships),
        ("EspoCRM Patterns", test_espocrm_patterns)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            print(f"\nTesting {test_name}...")
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} failed: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    if failed == 0:
        print("✅ ALL TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED")
    print("="*60)
    
    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)