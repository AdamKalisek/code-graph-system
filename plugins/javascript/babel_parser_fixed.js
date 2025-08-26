#!/usr/bin/env node
/**
 * Fixed Babel-based JavaScript/TypeScript parser
 */

const parser = require('@babel/parser');
const traverse = require('@babel/traverse').default;
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

function generateId(text) {
    return crypto.createHash('md5').update(text).digest('hex');
}

function parseFile(filePath) {
    try {
        const code = fs.readFileSync(filePath, 'utf8');
        const ast = parser.parse(code, {
            sourceType: 'unambiguous',
            plugins: [
                'jsx',
                'typescript', 
                'decorators-legacy',
                'dynamicImport',
                'classProperties',
                'optionalChaining',
                'nullishCoalescingOperator'
            ],
            ranges: true,
            locations: true
        });
        
        const result = {
            nodes: [],
            relationships: [],
            errors: []
        };

        // Create file node
        const fileName = path.basename(filePath);
        const fileId = generateId(filePath);
        const fileNode = {
            type: 'file',
            id: fileId,
            name: fileName,
            qualified_name: filePath,
            kind: 'file',
            metadata: {
                extension: path.extname(filePath)
            },
            location: {
                file_path: filePath,
                start_line: 1,
                end_line: code.split('\n').length
            }
        };
        result.nodes.push(fileNode);

        // Track API calls
        const apiCalls = [];

        traverse(ast, {
            // Import declarations
            ImportDeclaration(nodePath) {
                const source = nodePath.node.source.value;
                const nodeId = generateId(`${filePath}:import:${source}`);
                
                const items = [];
                nodePath.node.specifiers.forEach(spec => {
                    if (spec.type === 'ImportDefaultSpecifier') {
                        items.push(spec.local.name);
                    } else if (spec.type === 'ImportSpecifier') {
                        items.push(spec.imported.name);
                    }
                });

                result.nodes.push({
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
                        start_line: nodePath.node.loc.start.line,
                        end_line: nodePath.node.loc.end.line
                    }
                });

                result.relationships.push({
                    type: 'IMPORTS',
                    source_id: fileId,
                    target_id: nodeId,
                    metadata: { from: source }
                });
            },

            // Classes
            ClassDeclaration(nodePath) {
                const className = nodePath.node.id ? nodePath.node.id.name : '<anonymous>';
                const nodeId = generateId(`${filePath}:class:${className}`);
                
                const methods = [];
                const properties = [];
                
                nodePath.node.body.body.forEach(member => {
                    if (member.type === 'ClassMethod' && member.key) {
                        methods.push(member.key.name || '<computed>');
                    } else if (member.type === 'ClassProperty' && member.key) {
                        properties.push(member.key.name || '<computed>');
                    }
                });

                result.nodes.push({
                    type: 'class',
                    id: nodeId,
                    name: className,
                    qualified_name: `${filePath}:${className}`,
                    kind: 'class',
                    metadata: {
                        methods: methods,
                        properties: properties
                    },
                    location: {
                        file_path: filePath,
                        start_line: nodePath.node.loc.start.line,
                        end_line: nodePath.node.loc.end.line
                    }
                });

                result.relationships.push({
                    type: 'DEFINED_IN',
                    source_id: nodeId,
                    target_id: fileId
                });

                // Handle extends
                if (nodePath.node.superClass) {
                    let superName = '<complex>';
                    if (nodePath.node.superClass.type === 'Identifier') {
                        superName = nodePath.node.superClass.name;
                    }
                    
                    result.relationships.push({
                        type: 'EXTENDS',
                        source_id: nodeId,
                        target_id: generateId(superName),
                        metadata: { target_name: superName }
                    });
                }
            },

            // Functions
            FunctionDeclaration(nodePath) {
                const funcName = nodePath.node.id ? nodePath.node.id.name : '<anonymous>';
                const nodeId = generateId(`${filePath}:function:${funcName}`);
                
                const params = nodePath.node.params.map(p => {
                    if (p.type === 'Identifier') return p.name;
                    return '<complex>';
                });

                result.nodes.push({
                    type: 'function',
                    id: nodeId,
                    name: funcName,
                    qualified_name: `${filePath}:${funcName}`,
                    kind: 'function',
                    metadata: {
                        params: params,
                        async: nodePath.node.async,
                        generator: nodePath.node.generator
                    },
                    location: {
                        file_path: filePath,
                        start_line: nodePath.node.loc.start.line,
                        end_line: nodePath.node.loc.end.line
                    }
                });

                result.relationships.push({
                    type: 'DEFINED_IN',
                    source_id: nodeId,
                    target_id: fileId
                });
            },

            // API Calls
            CallExpression(nodePath) {
                const callee = nodePath.node.callee;
                let funcName = '';
                let isApiCall = false;
                
                if (callee.type === 'Identifier') {
                    funcName = callee.name;
                    isApiCall = ['fetch', 'axios'].includes(funcName);
                } else if (callee.type === 'MemberExpression') {
                    // Get full member expression text
                    funcName = code.substring(callee.start, callee.end);
                    isApiCall = funcName.includes('ajax') || 
                                funcName.includes('axios') || 
                                funcName.includes('Ajax') ||
                                funcName.includes('fetch');
                }
                
                if (isApiCall && nodePath.node.arguments.length > 0) {
                    const firstArg = nodePath.node.arguments[0];
                    let url = null;
                    let method = 'GET';
                    
                    // Extract URL
                    if (firstArg.type === 'StringLiteral') {
                        url = firstArg.value;
                    } else if (firstArg.type === 'TemplateLiteral') {
                        // Handle template literals
                        url = '';
                        for (let i = 0; i < firstArg.quasis.length; i++) {
                            url += firstArg.quasis[i].value.raw || firstArg.quasis[i].value.cooked;
                            if (i < firstArg.expressions.length) {
                                url += '{dynamic}';
                            }
                        }
                    } else if (firstArg.type === 'BinaryExpression' && firstArg.operator === '+') {
                        // Handle string concatenation
                        if (firstArg.left && firstArg.left.type === 'StringLiteral') {
                            url = firstArg.left.value + '{dynamic}';
                        }
                    } else if (firstArg.type === 'ObjectExpression') {
                        // Handle $.ajax style
                        const urlProp = firstArg.properties.find(p => 
                            p.key && p.key.name === 'url');
                        const methodProp = firstArg.properties.find(p => 
                            p.key && (p.key.name === 'method' || p.key.name === 'type'));
                        
                        if (urlProp && urlProp.value) {
                            if (urlProp.value.type === 'StringLiteral') {
                                url = urlProp.value.value;
                            }
                        }
                        
                        if (methodProp && methodProp.value && methodProp.value.type === 'StringLiteral') {
                            method = methodProp.value.value.toUpperCase();
                        }
                    }
                    
                    // Detect method from function name
                    const funcLower = funcName.toLowerCase();
                    if (funcLower.includes('.post') || funcLower.includes('postrequest')) {
                        method = 'POST';
                    } else if (funcLower.includes('.put') || funcLower.includes('putrequest')) {
                        method = 'PUT';
                    } else if (funcLower.includes('.delete') || funcLower.includes('deleterequest')) {
                        method = 'DELETE';
                    } else if (funcLower.includes('.patch') || funcLower.includes('patchrequest')) {
                        method = 'PATCH';
                    } else if (funcLower.includes('.get') || funcLower.includes('getrequest')) {
                        method = 'GET';
                    }
                    
                    // Check second argument for fetch options
                    if (nodePath.node.arguments.length > 1 && funcName === 'fetch') {
                        const options = nodePath.node.arguments[1];
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
                            line: nodePath.node.loc.start.line
                        });
                    }
                }
            },

            // Export declarations
            ExportNamedDeclaration(nodePath) {
                if (nodePath.node.declaration) {
                    const decl = nodePath.node.declaration;
                    let name = '';
                    
                    if (decl.type === 'FunctionDeclaration' && decl.id) {
                        name = decl.id.name;
                    } else if (decl.type === 'VariableDeclaration' && decl.declarations[0]) {
                        name = decl.declarations[0].id.name;
                    } else if (decl.type === 'ClassDeclaration' && decl.id) {
                        name = decl.id.name;
                    }
                    
                    if (name) {
                        const nodeId = generateId(`${filePath}:export:${name}`);
                        result.nodes.push({
                            type: 'export',
                            id: nodeId,
                            name: name,
                            qualified_name: `${filePath}:export:${name}`,
                            kind: 'export',
                            metadata: { named: true },
                            location: {
                                file_path: filePath,
                                start_line: nodePath.node.loc.start.line,
                                end_line: nodePath.node.loc.end.line
                            }
                        });

                        result.relationships.push({
                            type: 'EXPORTS',
                            source_id: fileId,
                            target_id: nodeId
                        });
                    }
                }
            },

            ExportDefaultDeclaration(nodePath) {
                const nodeId = generateId(`${filePath}:export:default`);
                result.nodes.push({
                    type: 'export',
                    id: nodeId,
                    name: 'default',
                    qualified_name: `${filePath}:export:default`,
                    kind: 'export',
                    metadata: { default: true },
                    location: {
                        file_path: filePath,
                        start_line: nodePath.node.loc.start.line,
                        end_line: nodePath.node.loc.end.line
                    }
                });

                result.relationships.push({
                    type: 'EXPORTS',
                    source_id: fileId,
                    target_id: nodeId
                });
            }
        });

        // Add API calls to file metadata
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

// CLI interface
if (require.main === module) {
    const filePath = process.argv[2];
    
    if (!filePath) {
        console.error('Usage: node babel_parser_fixed.js <file_path>');
        process.exit(1);
    }
    
    const result = parseFile(filePath);
    console.log(JSON.stringify(result, null, 2));
}

module.exports = { parseFile };