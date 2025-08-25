#!/usr/bin/env node

/**
 * JavaScript/TypeScript Parser for Code Graph System
 * 
 * Parses JS/TS files and outputs JSON structure for the graph.
 * Uses regex-based parsing for simplicity (production should use @babel/parser or acorn)
 */

const fs = require('fs');
const path = require('path');

class SimpleJSParser {
    constructor(filePath) {
        this.filePath = filePath;
        this.content = fs.readFileSync(filePath, 'utf8');
        this.modules = [];
        this.classes = [];
        this.functions = [];
        this.imports = [];
        this.exports = [];
    }

    parse() {
        this.parseImports();
        this.parseExports();
        this.parseClasses();
        this.parseFunctions();
        this.detectModuleType();

        return {
            file: this.filePath,
            module_type: this.moduleType,
            imports: this.imports,
            exports: this.exports,
            classes: this.classes,
            functions: this.functions
        };
    }

    detectModuleType() {
        if (this.content.includes('import ') || this.content.includes('export ')) {
            this.moduleType = 'es6';
        } else if (this.content.includes('require(') || this.content.includes('module.exports')) {
            this.moduleType = 'commonjs';
        } else if (this.content.includes('define(')) {
            this.moduleType = 'amd';
        } else {
            this.moduleType = 'script';
        }
    }

    parseImports() {
        // ES6 imports
        const es6ImportRegex = /import\s+(?:(\w+)|\{([^}]+)\}|\*\s+as\s+(\w+))\s+from\s+['"]([^'"]+)['"]/g;
        let match;
        
        while ((match = es6ImportRegex.exec(this.content)) !== null) {
            const importData = {
                type: 'es6',
                from: match[4],
                default: match[1] || null,
                named: match[2] ? match[2].split(',').map(s => s.trim()) : [],
                namespace: match[3] || null
            };
            this.imports.push(importData);
        }

        // CommonJS requires
        const requireRegex = /(?:const|let|var)\s+(\w+)\s*=\s*require\(['"]([^'"]+)['"]\)/g;
        
        while ((match = requireRegex.exec(this.content)) !== null) {
            const importData = {
                type: 'commonjs',
                from: match[2],
                variable: match[1]
            };
            this.imports.push(importData);
        }

        // Dynamic imports
        const dynamicImportRegex = /import\(['"]([^'"]+)['"]\)/g;
        
        while ((match = dynamicImportRegex.exec(this.content)) !== null) {
            const importData = {
                type: 'dynamic',
                from: match[1]
            };
            this.imports.push(importData);
        }
    }

    parseExports() {
        // ES6 named exports
        const namedExportRegex = /export\s+(?:const|let|var|function|class)\s+(\w+)/g;
        let match;
        
        while ((match = namedExportRegex.exec(this.content)) !== null) {
            this.exports.push({
                type: 'named',
                name: match[1]
            });
        }

        // ES6 default export
        const defaultExportRegex = /export\s+default\s+(?:class\s+)?(\w+)/g;
        
        while ((match = defaultExportRegex.exec(this.content)) !== null) {
            this.exports.push({
                type: 'default',
                name: match[1]
            });
        }

        // CommonJS exports
        const commonjsExportRegex = /module\.exports\s*=\s*(\w+)/g;
        
        while ((match = commonjsExportRegex.exec(this.content)) !== null) {
            this.exports.push({
                type: 'commonjs',
                name: match[1]
            });
        }
    }

    parseClasses() {
        // ES6 classes
        const classRegex = /class\s+(\w+)(?:\s+extends\s+(\w+))?\s*\{/g;
        let match;
        
        while ((match = classRegex.exec(this.content)) !== null) {
            const classData = {
                name: match[1],
                extends: match[2] || null,
                type: 'class',
                methods: [],
                properties: []
            };

            // Find class body
            const startIndex = match.index + match[0].length;
            const classBody = this.extractBlock(startIndex);
            
            // Parse methods in class
            const methodRegex = /(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{/g;
            let methodMatch;
            
            while ((methodMatch = methodRegex.exec(classBody)) !== null) {
                if (methodMatch[1] !== 'constructor') {
                    classData.methods.push({
                        name: methodMatch[1],
                        is_async: classBody.substring(0, methodMatch.index).includes('async')
                    });
                }
            }

            this.classes.push(classData);
        }

        // Backbone-style classes
        const backboneRegex = /(\w+)\s*=\s*Backbone\.(View|Model|Collection|Router)\.extend\(\{/g;
        
        while ((match = backboneRegex.exec(this.content)) !== null) {
            const classData = {
                name: match[1],
                extends: `Backbone.${match[2]}`,
                type: 'backbone',
                methods: []
            };
            this.classes.push(classData);
        }
    }

    parseFunctions() {
        // Named functions
        const functionRegex = /(?:async\s+)?function\s+(\w+)\s*\([^)]*\)/g;
        let match;
        
        while ((match = functionRegex.exec(this.content)) !== null) {
            const funcData = {
                name: match[1],
                type: 'function',
                is_async: match[0].includes('async'),
                is_generator: match[0].includes('*')
            };
            this.functions.push(funcData);
        }

        // Arrow functions assigned to variables
        const arrowRegex = /(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>/g;
        
        while ((match = arrowRegex.exec(this.content)) !== null) {
            const funcData = {
                name: match[1],
                type: 'arrow',
                is_async: match[0].includes('async')
            };
            this.functions.push(funcData);
        }
    }

    extractBlock(startIndex) {
        let braceCount = 1;
        let i = startIndex;
        let inString = false;
        let stringChar = null;
        
        while (i < this.content.length && braceCount > 0) {
            const char = this.content[i];
            const prevChar = i > 0 ? this.content[i - 1] : '';
            
            // Handle strings
            if ((char === '"' || char === "'" || char === '`') && prevChar !== '\\') {
                if (!inString) {
                    inString = true;
                    stringChar = char;
                } else if (char === stringChar) {
                    inString = false;
                    stringChar = null;
                }
            }
            
            // Count braces only outside strings
            if (!inString) {
                if (char === '{') {
                    braceCount++;
                } else if (char === '}') {
                    braceCount--;
                }
            }
            
            i++;
        }
        
        return this.content.substring(startIndex, i - 1);
    }
}

// Main execution
const args = process.argv.slice(2);
if (args.length === 0) {
    console.error(JSON.stringify({ error: 'No file specified' }));
    process.exit(1);
}

const filePath = args[0];

if (!fs.existsSync(filePath)) {
    console.error(JSON.stringify({ error: `File not found: ${filePath}` }));
    process.exit(1);
}

try {
    const parser = new SimpleJSParser(filePath);
    const result = parser.parse();
    console.log(JSON.stringify(result, null, 2));
} catch (error) {
    console.error(JSON.stringify({ error: error.message }));
    process.exit(1);
}