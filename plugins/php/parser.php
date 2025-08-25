<?php
/**
 * PHP Parser for Code Graph System
 * 
 * Parses PHP files and outputs JSON structure for the graph.
 */

// Simple parser without external dependencies
// For production, use nikic/php-parser

class SimplePhpParser {
    private $file;
    private $content;
    private $tokens;
    private $classes = [];
    private $currentNamespace = '';
    
    public function __construct($file) {
        $this->file = $file;
        $this->content = file_get_contents($file);
        $this->tokens = token_get_all($this->content);
    }
    
    public function parse() {
        $i = 0;
        $count = count($this->tokens);
        
        while ($i < $count) {
            $token = $this->tokens[$i];
            
            if (is_array($token)) {
                switch ($token[0]) {
                    case T_NAMESPACE:
                        $this->parseNamespace($i);
                        break;
                        
                    case T_CLASS:
                        $this->parseClass($i);
                        break;
                        
                    case T_INTERFACE:
                        $this->parseInterface($i);
                        break;
                        
                    case T_TRAIT:
                        $this->parseTrait($i);
                        break;
                }
            }
            
            $i++;
        }
        
        return [
            'file' => $this->file,
            'classes' => $this->classes
        ];
    }
    
    private function parseNamespace(&$i) {
        $namespace = '';
        $i++; // Skip T_NAMESPACE
        
        while (isset($this->tokens[$i])) {
            $token = $this->tokens[$i];
            
            if ($token === ';' || $token === '{') {
                break;
            }
            
            if (is_array($token) && $token[0] === T_STRING) {
                $namespace .= $token[1];
            } elseif (is_array($token) && $token[0] === T_NS_SEPARATOR) {
                $namespace .= '\\';
            }
            
            $i++;
        }
        
        $this->currentNamespace = trim($namespace);
    }
    
    private function parseClass(&$i) {
        $class = [
            'type' => 'class',
            'name' => '',
            'namespace' => $this->currentNamespace,
            'fqcn' => '',
            'is_abstract' => false,
            'is_final' => false,
            'is_interface' => false,
            'extends' => null,
            'implements' => [],
            'traits' => [],
            'methods' => [],
            'properties' => []
        ];
        
        // Check for modifiers before class
        $j = $i - 1;
        while ($j >= 0 && isset($this->tokens[$j])) {
            $token = $this->tokens[$j];
            if (is_array($token)) {
                if ($token[0] === T_ABSTRACT) {
                    $class['is_abstract'] = true;
                } elseif ($token[0] === T_FINAL) {
                    $class['is_final'] = true;
                } elseif ($token[0] !== T_WHITESPACE) {
                    break;
                }
            } else {
                break;
            }
            $j--;
        }
        
        // Get class name
        $i++; // Skip T_CLASS
        while (isset($this->tokens[$i])) {
            $token = $this->tokens[$i];
            
            if (is_array($token) && $token[0] === T_STRING) {
                $class['name'] = $token[1];
                $class['fqcn'] = $this->currentNamespace ? 
                    $this->currentNamespace . '\\' . $token[1] : $token[1];
                break;
            }
            
            $i++;
        }
        
        // Parse extends
        while (isset($this->tokens[$i]) && $this->tokens[$i] !== '{') {
            $token = $this->tokens[$i];
            
            if (is_array($token) && $token[0] === T_EXTENDS) {
                $i++;
                $extends = $this->parseClassName($i);
                if ($extends) {
                    $class['extends'] = $extends;
                }
            }
            
            if (is_array($token) && $token[0] === T_IMPLEMENTS) {
                $i++;
                $class['implements'] = $this->parseClassList($i);
            }
            
            $i++;
        }
        
        // Parse class body
        if (isset($this->tokens[$i]) && $this->tokens[$i] === '{') {
            $this->parseClassBody($i, $class);
        }
        
        $this->classes[] = $class;
    }
    
    private function parseInterface(&$i) {
        $interface = [
            'type' => 'interface',
            'name' => '',
            'namespace' => $this->currentNamespace,
            'fqcn' => '',
            'is_interface' => true,
            'extends' => [],
            'methods' => []
        ];
        
        // Get interface name
        $i++; // Skip T_INTERFACE
        while (isset($this->tokens[$i])) {
            $token = $this->tokens[$i];
            
            if (is_array($token) && $token[0] === T_STRING) {
                $interface['name'] = $token[1];
                $interface['fqcn'] = $this->currentNamespace ? 
                    $this->currentNamespace . '\\' . $token[1] : $token[1];
                break;
            }
            
            $i++;
        }
        
        $this->classes[] = $interface;
    }
    
    private function parseTrait(&$i) {
        $trait = [
            'type' => 'trait',
            'name' => '',
            'namespace' => $this->currentNamespace,
            'fqcn' => '',
            'methods' => [],
            'properties' => []
        ];
        
        // Get trait name
        $i++; // Skip T_TRAIT
        while (isset($this->tokens[$i])) {
            $token = $this->tokens[$i];
            
            if (is_array($token) && $token[0] === T_STRING) {
                $trait['name'] = $token[1];
                $trait['fqcn'] = $this->currentNamespace ? 
                    $this->currentNamespace . '\\' . $token[1] : $token[1];
                break;
            }
            
            $i++;
        }
        
        $this->classes[] = $trait;
    }
    
    private function parseClassBody(&$i, &$class) {
        $braceLevel = 0;
        
        while (isset($this->tokens[$i])) {
            $token = $this->tokens[$i];
            
            if ($token === '{') {
                $braceLevel++;
            } elseif ($token === '}') {
                $braceLevel--;
                if ($braceLevel === 0) {
                    break;
                }
            }
            
            if ($braceLevel === 1 && is_array($token)) {
                if ($token[0] === T_FUNCTION) {
                    $method = $this->parseMethod($i);
                    if ($method) {
                        $class['methods'][] = $method;
                    }
                } elseif (in_array($token[0], [T_PUBLIC, T_PROTECTED, T_PRIVATE, T_VAR, T_STATIC])) {
                    $property = $this->parseProperty($i);
                    if ($property) {
                        $class['properties'][] = $property;
                    }
                } elseif ($token[0] === T_USE) {
                    $trait = $this->parseTrait($i);
                    if ($trait) {
                        $class['traits'][] = $trait;
                    }
                }
            }
            
            $i++;
        }
    }
    
    private function parseMethod(&$i) {
        $method = [
            'name' => '',
            'visibility' => 'public',
            'is_static' => false,
            'is_abstract' => false,
            'is_final' => false
        ];
        
        // Check modifiers before function
        $j = $i - 1;
        while ($j >= 0 && isset($this->tokens[$j])) {
            $token = $this->tokens[$j];
            if (is_array($token)) {
                switch ($token[0]) {
                    case T_PUBLIC:
                        $method['visibility'] = 'public';
                        break;
                    case T_PROTECTED:
                        $method['visibility'] = 'protected';
                        break;
                    case T_PRIVATE:
                        $method['visibility'] = 'private';
                        break;
                    case T_STATIC:
                        $method['is_static'] = true;
                        break;
                    case T_ABSTRACT:
                        $method['is_abstract'] = true;
                        break;
                    case T_FINAL:
                        $method['is_final'] = true;
                        break;
                }
            }
            $j--;
        }
        
        // Get method name
        $i++; // Skip T_FUNCTION
        while (isset($this->tokens[$i])) {
            $token = $this->tokens[$i];
            
            if (is_array($token) && $token[0] === T_STRING) {
                $method['name'] = $token[1];
                return $method;
            }
            
            if ($token === '(') {
                break;
            }
            
            $i++;
        }
        
        return null;
    }
    
    private function parseProperty(&$i) {
        $property = [
            'name' => '',
            'visibility' => 'public',
            'is_static' => false
        ];
        
        // Parse visibility and modifiers
        while (isset($this->tokens[$i])) {
            $token = $this->tokens[$i];
            
            if (is_array($token)) {
                switch ($token[0]) {
                    case T_PUBLIC:
                        $property['visibility'] = 'public';
                        break;
                    case T_PROTECTED:
                        $property['visibility'] = 'protected';
                        break;
                    case T_PRIVATE:
                        $property['visibility'] = 'private';
                        break;
                    case T_STATIC:
                        $property['is_static'] = true;
                        break;
                    case T_VARIABLE:
                        $property['name'] = substr($token[1], 1); // Remove $
                        return $property;
                }
            }
            
            if ($token === ';') {
                break;
            }
            
            $i++;
        }
        
        return null;
    }
    
    private function parseClassName(&$i) {
        $className = '';
        
        while (isset($this->tokens[$i])) {
            $token = $this->tokens[$i];
            
            if (is_array($token)) {
                if ($token[0] === T_STRING) {
                    $className .= $token[1];
                } elseif ($token[0] === T_NS_SEPARATOR) {
                    $className .= '\\';
                } elseif ($token[0] !== T_WHITESPACE) {
                    break;
                }
            } else {
                break;
            }
            
            $i++;
        }
        
        return $className ?: null;
    }
    
    private function parseClassList(&$i) {
        $classes = [];
        $currentClass = '';
        
        while (isset($this->tokens[$i])) {
            $token = $this->tokens[$i];
            
            if ($token === '{') {
                if ($currentClass) {
                    $classes[] = $currentClass;
                }
                break;
            }
            
            if (is_array($token)) {
                if ($token[0] === T_STRING) {
                    $currentClass .= $token[1];
                } elseif ($token[0] === T_NS_SEPARATOR) {
                    $currentClass .= '\\';
                }
            } elseif ($token === ',') {
                if ($currentClass) {
                    $classes[] = $currentClass;
                    $currentClass = '';
                }
            }
            
            $i++;
        }
        
        return $classes;
    }
}

// Main execution
if ($argc < 2) {
    echo json_encode(['error' => 'No file specified']);
    exit(1);
}

$file = $argv[1];

if (!file_exists($file)) {
    echo json_encode(['error' => 'File not found: ' . $file]);
    exit(1);
}

try {
    $parser = new SimplePhpParser($file);
    $result = $parser->parse();
    echo json_encode($result, JSON_PRETTY_PRINT);
} catch (Exception $e) {
    echo json_encode(['error' => $e->getMessage()]);
    exit(1);
}