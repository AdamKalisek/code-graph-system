#!/usr/bin/env node
/**
 * Babel-based JavaScript/TypeScript parser
 * Provides accurate AST parsing with proper source locations
 */

const parser = require('@babel/parser');
const traverse = require('@babel/traverse').default;
const fs = require('fs');
const path = require('path');

class JavaScriptParser {
    constructor() {
        this.parserOptions = {
            sourceType: 'unambiguous',
            plugins: [
                'jsx',
                'typescript',
                'decorators-legacy',
                'dynamicImport',
                'classProperties',
                'classPrivateProperties',
                'classPrivateMethods',
                'optionalChaining',
                'nullishCoalescingOperator',
                'exportDefaultFrom',
                'exportNamespaceFrom',
                'asyncGenerators',
                'functionBind',
                'functionSent',
                'objectRestSpread',
                'throwExpressions',
                'topLevelAwait'
            ],
            ranges: true,
            locations: true
        };
    }

    parseFile(filePath) {
        try {
            const code = fs.readFileSync(filePath, 'utf8');
            const ast = parser.parse(code, this.parserOptions);
            
            const result = {
                nodes: [],
                relationships: [],
                errors: []
            };

            // Create file node
            const fileName = path.basename(filePath);
            const fileNode = {
                type: 'file',
                id: this.generateId(filePath),
                name: fileName,
                qualified_name: filePath,
                kind: 'file',
                metadata: {
                    extension: path.extname(filePath),
                    module_type: this.detectModuleType(ast)
                },
                location: {
                    file_path: filePath,
                    start_line: 1,
                    end_line: code.split('\n').length
                }
            };
            result.nodes.push(fileNode);

            // Extract imports
            const imports = this.extractImports(ast, filePath);
            imports.forEach(imp => {
                result.nodes.push(imp.node);
                result.relationships.push({
                    type: 'IMPORTS',
                    source_id: fileNode.id,
                    target_id: imp.node.id,
                    metadata: { from: imp.from }
                });
            });

            // Extract exports
            const exports = this.extractExports(ast, filePath);
            exports.forEach(exp => {
                result.nodes.push(exp.node);
                result.relationships.push({
                    type: 'EXPORTS',
                    source_id: fileNode.id,
                    target_id: exp.node.id
                });
            });

            // Extract classes
            const classes = this.extractClasses(ast, filePath);
            classes.forEach(cls => {
                result.nodes.push(cls.node);
                result.relationships.push({
                    type: 'DEFINED_IN',
                    source_id: cls.node.id,
                    target_id: fileNode.id
                });
                
                // Add extends relationship if present
                if (cls.extends) {
                    result.relationships.push({
                        type: 'EXTENDS',
                        source_id: cls.node.id,
                        target_id: this.generateId(cls.extends),
                        metadata: { target_name: cls.extends }
                    });
                }
            });

            // Extract functions
            const functions = this.extractFunctions(ast, filePath);
            functions.forEach(func => {
                result.nodes.push(func.node);
                result.relationships.push({
                    type: 'DEFINED_IN',
                    source_id: func.node.id,
                    target_id: fileNode.id
                });
            });

            // Extract API calls
            const apiCalls = this.extractApiCalls(ast, code);
            if (apiCalls.length > 0) {
                fileNode.metadata.api_calls = JSON.stringify(apiCalls);
            }

            return result;

        } catch (error) {
            return {
                nodes: [],
                relationships: [],
                errors: [`Parse error in ${filePath}: ${error.message}`]
            };
        }
    }

    detectModuleType(ast) {
        let hasImport = false;
        let hasRequire = false;
        let hasExport = false;

        traverse(ast, {
            ImportDeclaration() {
                hasImport = true;
            },
            CallExpression(path) {
                if (path.node.callee.name === 'require') {
                    hasRequire = true;
                }
            },
            ExportDeclaration() {
                hasExport = true;
            }
        });

        if (hasImport || hasExport) return 'esm';
        if (hasRequire) return 'commonjs';
        return 'script';
    }

    extractImports(ast, filePath) {
        const imports = [];
        
        traverse(ast, {
            ImportDeclaration(path) {
                const source = path.node.source.value;
                const items = [];
                
                path.node.specifiers.forEach(spec => {
                    if (spec.type === 'ImportDefaultSpecifier') {
                        items.push(spec.local.name);
                    } else if (spec.type === 'ImportSpecifier') {
                        items.push(spec.imported.name);
                    } else if (spec.type === 'ImportNamespaceSpecifier') {
                        items.push(`* as ${spec.local.name}`);
                    }
                });

                const nodeId = require('crypto').createHash('md5')
                    .update(`${filePath}:import:${source}`).digest('hex');
                
                imports.push({
                    from: source,
                    node: {
                        type: 'import',
                        id: nodeId,
                        name: source,
                        qualified_name: `${filePath}:import:${source}`,
                        kind: 'import',
                        metadata: {
                            module_type: 'es6',
                            items: items
                        },
                        location: {
                            file_path: filePath,
                            start_line: path.node.loc.start.line,
                            end_line: path.node.loc.end.line
                        }
                    }
                });
            },
            
            CallExpression(path) {
                // Handle require()
                if (path.node.callee.name === 'require' && 
                    path.node.arguments.length > 0 &&
                    path.node.arguments[0].type === 'StringLiteral') {
                    
                    const source = path.node.arguments[0].value;
                    imports.push({
                        from: source,
                        node: {
                            type: 'import',
                            id: this.generateId(`${filePath}:require:${source}`),
                            name: source,
                            qualified_name: `${filePath}:require:${source}`,
                            kind: 'import',
                            metadata: {
                                module_type: 'commonjs'
                            },
                            location: {
                                file_path: filePath,
                                start_line: path.node.loc.start.line,
                                end_line: path.node.loc.end.line
                            }
                        }
                    });
                }
            }
        });
        
        return imports;
    }

    extractExports(ast, filePath) {
        const exports = [];
        
        traverse(ast, {
            ExportNamedDeclaration(path) {
                if (path.node.declaration) {
                    // export const/let/function
                    const decl = path.node.declaration;
                    let name = '';
                    
                    if (decl.type === 'FunctionDeclaration') {
                        name = decl.id.name;
                    } else if (decl.type === 'VariableDeclaration') {
                        name = decl.declarations[0].id.name;
                    }
                    
                    if (name) {
                        exports.push({
                            node: {
                                type: 'export',
                                id: this.generateId(`${filePath}:export:${name}`),
                                name: name,
                                qualified_name: `${filePath}:export:${name}`,
                                kind: 'export',
                                metadata: { named: true },
                                location: {
                                    file_path: filePath,
                                    start_line: path.node.loc.start.line,
                                    end_line: path.node.loc.end.line
                                }
                            }
                        });
                    }
                }
            },
            
            ExportDefaultDeclaration(path) {
                exports.push({
                    node: {
                        type: 'export',
                        id: this.generateId(`${filePath}:export:default`),
                        name: 'default',
                        qualified_name: `${filePath}:export:default`,
                        kind: 'export',
                        metadata: { default: true },
                        location: {
                            file_path: filePath,
                            start_line: path.node.loc.start.line,
                            end_line: path.node.loc.end.line
                        }
                    }
                });
            }
        });
        
        return exports;
    }

    extractClasses(ast, filePath) {
        const classes = [];
        
        traverse(ast, {
            ClassDeclaration(path) {
                const className = path.node.id ? path.node.id.name : '<anonymous>';
                const methods = [];
                const properties = [];
                
                // Extract methods and properties
                path.node.body.body.forEach(member => {
                    if (member.type === 'ClassMethod') {
                        methods.push(member.key.name);
                    } else if (member.type === 'ClassProperty') {
                        properties.push(member.key.name);
                    }
                });
                
                classes.push({
                    node: {
                        type: 'class',
                        id: this.generateId(`${filePath}:class:${className}`),
                        name: className,
                        qualified_name: `${filePath}:${className}`,
                        kind: 'class',
                        metadata: {
                            methods: methods,
                            properties: properties
                        },
                        location: {
                            file_path: filePath,
                            start_line: path.node.loc.start.line,
                            end_line: path.node.loc.end.line
                        }
                    },
                    extends: path.node.superClass ? 
                        (path.node.superClass.name || '<complex>') : null
                });
            }
        });
        
        return classes;
    }

    extractFunctions(ast, filePath) {
        const functions = [];
        
        traverse(ast, {
            FunctionDeclaration(path) {
                const funcName = path.node.id ? path.node.id.name : '<anonymous>';
                const params = path.node.params.map(p => p.name || '<complex>');
                
                functions.push({
                    node: {
                        type: 'function',
                        id: this.generateId(`${filePath}:function:${funcName}`),
                        name: funcName,
                        qualified_name: `${filePath}:${funcName}`,
                        kind: 'function',
                        metadata: {
                            params: params,
                            async: path.node.async,
                            generator: path.node.generator
                        },
                        location: {
                            file_path: filePath,
                            start_line: path.node.loc.start.line,
                            end_line: path.node.loc.end.line
                        }
                    }
                });
            },
            
            ArrowFunctionExpression(path) {
                // Only capture named arrow functions
                if (path.parent.type === 'VariableDeclarator' && path.parent.id) {
                    const funcName = path.parent.id.name;
                    const params = path.node.params.map(p => p.name || '<complex>');
                    
                    functions.push({
                        node: {
                            type: 'function',
                            id: this.generateId(`${filePath}:arrow:${funcName}`),
                            name: funcName,
                            qualified_name: `${filePath}:${funcName}`,
                            kind: 'function',
                            metadata: {
                                params: params,
                                async: path.node.async,
                                arrow: true
                            },
                            location: {
                                file_path: filePath,
                                start_line: path.node.loc.start.line,
                                end_line: path.node.loc.end.line
                            }
                        }
                    });
                }
            }
        });
        
        return functions;
    }

    extractApiCalls(ast, code) {
        const apiCalls = [];
        
        traverse(ast, {
            CallExpression(path) {
                const callee = path.node.callee;
                let funcName = '';
                let isApiCall = false;
                
                // Identify API call functions
                if (callee.type === 'Identifier') {
                    funcName = callee.name;
                    isApiCall = ['fetch', 'axios'].includes(funcName);
                } else if (callee.type === 'MemberExpression') {
                    // Handle axios.get, $.ajax, etc.
                    const obj = this.getCalleeText(callee, code);
                    funcName = obj;
                    isApiCall = obj.includes('ajax') || obj.includes('axios') || obj.includes('fetch');
                }
                
                if (isApiCall && path.node.arguments.length > 0) {
                    const firstArg = path.node.arguments[0];
                    let url = null;
                    let method = 'GET';
                    
                    // Extract URL
                    if (firstArg.type === 'StringLiteral') {
                        url = firstArg.value;
                    } else if (firstArg.type === 'TemplateLiteral') {
                        // Handle template literals
                        url = this.extractTemplateString(firstArg, code);
                    } else if (firstArg.type === 'BinaryExpression') {
                        // Handle string concatenation
                        url = this.extractConcatenatedString(firstArg, code);
                    } else if (firstArg.type === 'ObjectExpression') {
                        // Handle $.ajax style with object parameter
                        const urlProp = firstArg.properties.find(p => p.key && p.key.name === 'url');
                        const methodProp = firstArg.properties.find(p => 
                            p.key && (p.key.name === 'method' || p.key.name === 'type'));
                        
                        if (urlProp && urlProp.value) {
                            if (urlProp.value.type === 'StringLiteral') {
                                url = urlProp.value.value;
                            } else if (urlProp.value.type === 'TemplateLiteral') {
                                url = this.extractTemplateString(urlProp.value, code);
                            }
                        }
                        
                        if (methodProp && methodProp.value && methodProp.value.type === 'StringLiteral') {
                            method = methodProp.value.value.toUpperCase();
                        }
                    }
                    
                    // Detect method from function name
                    if (funcName.includes('.post') || funcName.includes('Post')) {
                        method = 'POST';
                    } else if (funcName.includes('.put') || funcName.includes('Put')) {
                        method = 'PUT';
                    } else if (funcName.includes('.delete') || funcName.includes('Delete')) {
                        method = 'DELETE';
                    } else if (funcName.includes('.patch') || funcName.includes('Patch')) {
                        method = 'PATCH';
                    }
                    
                    // Check second argument for fetch options
                    if (path.node.arguments.length > 1 && funcName === 'fetch') {
                        const options = path.node.arguments[1];
                        if (options.type === 'ObjectExpression') {
                            const methodProp = options.properties.find(p => 
                                p.key && p.key.name === 'method');
                            if (methodProp && methodProp.value && methodProp.value.type === 'StringLiteral') {
                                method = methodProp.value.value.toUpperCase();
                            }
                        }
                    }
                    
                    if (url) {
                        apiCalls.push({
                            function: funcName,
                            url: url,
                            method: method,
                            line: path.node.loc.start.line
                        });
                    }
                }
            }
        });
        
        return apiCalls;
    }

    extractTemplateString(node, code) {
        let result = '';
        
        for (let i = 0; i < node.quasis.length; i++) {
            result += node.quasis[i].value.raw;
            if (i < node.expressions.length) {
                // Add placeholder for dynamic parts
                result += '{dynamic}';
            }
        }
        
        return result;
    }

    extractConcatenatedString(node, code) {
        // Best effort to extract left side of concatenation
        if (node.left && node.left.type === 'StringLiteral') {
            return node.left.value + '{dynamic}';
        } else if (node.left && node.left.type === 'BinaryExpression') {
            // Recursive case for chained concatenations
            return this.extractConcatenatedString(node.left, code) + '{dynamic}';
        }
        return null;
    }

    getCalleeText(node, code) {
        // Extract the full callee text (e.g., "axios.post", "$.ajax")
        const start = node.start || node.range[0];
        const end = node.end || node.range[1];
        return code.substring(start, end);
    }

    generateId(text) {
        // Simple hash function for ID generation
        const crypto = require('crypto');
        return crypto.createHash('md5').update(text).digest('hex');
    }
}

// CLI interface
if (require.main === module) {
    const filePath = process.argv[2];
    
    if (!filePath) {
        console.error('Usage: node babel_parser.js <file_path>');
        process.exit(1);
    }
    
    const parser = new JavaScriptParser();
    const result = parser.parseFile(filePath);
    
    // Output JSON to stdout for Python to consume
    console.log(JSON.stringify(result, null, 2));
}

module.exports = JavaScriptParser;