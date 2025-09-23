# Data Model Reference

## Overview

The Code Graph System uses a property graph model with typed nodes and relationships. Each node represents a code entity (file, class, function, etc.), and edges represent relationships between them (imports, calls, renders, etc.).

## Node Types

### Core Node Types

#### File
Represents a source code file.
```cypher
(:File {
  id: String,          // Unique identifier
  path: String,        // Absolute file path
  name: String,        // Filename with extension
  extension: String,   // File extension (.ts, .tsx, .php, etc.)
  size: Integer        // File size in bytes
})
```

#### Directory
Represents a filesystem directory.
```cypher
(:Directory {
  id: String,          // Unique identifier
  path: String,        // Absolute directory path
  name: String         // Directory name
})
```

### TypeScript/JavaScript Node Types

#### ReactComponent
React functional or class component.
```cypher
(:ReactComponent {
  id: String,          // Unique identifier
  name: String,        // Component name
  file_path: String,   // Source file path
  line_number: Integer,// Definition line
  type: "ReactComponent",
  is_default_export: Boolean,
  has_props: Boolean,
  has_state: Boolean
})
```

#### TSFunction
TypeScript/JavaScript function.
```cypher
(:TSFunction {
  id: String,
  name: String,
  file_path: String,
  line_number: Integer,
  type: "TSFunction",
  is_async: Boolean,
  is_generator: Boolean,
  is_arrow: Boolean,
  parameters_count: Integer
})
```

#### TSInterface
TypeScript interface definition.
```cypher
(:TSInterface {
  id: String,
  name: String,
  file_path: String,
  line_number: Integer,
  type: "TSInterface",
  is_exported: Boolean,
  extends: String[]    // Parent interfaces
})
```

#### TSType
TypeScript type alias.
```cypher
(:TSType {
  id: String,
  name: String,
  file_path: String,
  line_number: Integer,
  type: "TSType",
  is_exported: Boolean
})
```

#### TSClass
TypeScript/JavaScript class.
```cypher
(:TSClass {
  id: String,
  name: String,
  file_path: String,
  line_number: Integer,
  type: "TSClass",
  is_abstract: Boolean,
  extends: String,     // Parent class
  implements: String[] // Implemented interfaces
})
```

#### APIRoute
Next.js API route handler.
```cypher
(:APIRoute {
  id: String,
  name: String,
  file_path: String,
  line_number: Integer,
  type: "APIRoute",
  method: String,      // GET, POST, PUT, DELETE, etc.
  path: String         // API endpoint path
})
```

#### JSXElement
JSX/HTML element in React code.
```cypher
(:JSXElement {
  id: String,
  name: String,        // Element/Component name
  file_path: String,
  line_number: Integer,
  type: "JSXElement",
  is_component: Boolean // True if custom component
})
```

### PHP Node Types

#### PHPClass
PHP class definition.
```cypher
(:PHPClass {
  id: String,
  name: String,
  namespace: String,
  file_path: String,
  line_number: Integer,
  type: "class",
  is_abstract: Boolean,
  is_final: Boolean
})
```

#### PHPMethod
PHP class method.
```cypher
(:PHPMethod {
  id: String,
  name: String,
  class_name: String,
  file_path: String,
  line_number: Integer,
  type: "method",
  visibility: String,  // public, private, protected
  is_static: Boolean
})
```

## Relationship Types

### File System Relationships

#### CONTAINS
Directory contains file or subdirectory.
```cypher
(:Directory)-[:CONTAINS]->(:File|:Directory)
```

### Import/Export Relationships

#### IMPORTS
One module imports another.
```cypher
(:File|:Component)-[:IMPORTS {
  alias: String,       // Import alias if renamed
  is_default: Boolean, // Default import
  specifiers: String[] // Named imports
}]->(:File|:Component|:Function)
```

#### EXPORTS
Module exports a symbol.
```cypher
(:File|:Component)-[:EXPORTS {
  is_default: Boolean,
  name: String
}]->(:Component|:Function|:Type)
```

### React-Specific Relationships

#### RENDERS
Component renders JSX element or another component.
```cypher
(:ReactComponent)-[:RENDERS {
  is_conditional: Boolean, // Inside if/ternary
  is_mapped: Boolean       // Inside map/loop
}]->(:JSXElement|:ReactComponent)
```

#### HAS_PROP
Component has a prop type definition.
```cypher
(:ReactComponent)-[:HAS_PROP {
  name: String,
  type: String,        // TypeScript type
  is_required: Boolean,
  has_default: Boolean
}]->(:TSInterface|:TSType)
```

#### HAS_STATE
Component uses state variable.
```cypher
(:ReactComponent)-[:HAS_STATE {
  name: String,
  initial_value: String,
  setter_name: String
}]->(:Variable)
```

### Function Relationships

#### CALLS
Function calls another function.
```cypher
(:Function)-[:CALLS {
  is_async_await: Boolean,
  argument_count: Integer
}]->(:Function)
```

#### RETURNS
Function returns a type or component.
```cypher
(:Function)-[:RETURNS]->(:Type|:Component)
```

#### USES
General usage relationship.
```cypher
(:Component|:Function)-[:USES]->(:Variable|:Constant|:Type)
```

### Inheritance Relationships

#### EXTENDS
Class/interface extends another.
```cypher
(:Class|:Interface)-[:EXTENDS]->(:Class|:Interface)
```

#### IMPLEMENTS
Class implements interface.
```cypher
(:Class)-[:IMPLEMENTS]->(:Interface)
```

### PHP-Specific Relationships

#### INSTANTIATES
Creates instance of class.
```cypher
(:Method)-[:INSTANTIATES]->(:Class)
```

#### DEFINES
File defines a class/function.
```cypher
(:File)-[:DEFINES]->(:Class|:Function)
```

## Query Examples

### Find all React components that render a specific element
```cypher
MATCH (c:ReactComponent)-[:RENDERS*1..3]->(e:JSXElement {name: 'Button'})
RETURN c.name, c.file_path
```

### Find circular dependencies
```cypher
MATCH path = (m1)-[:IMPORTS*2..5]->(m1)
RETURN path
```

### Find unused exported components
```cypher
MATCH (c:ReactComponent)-[:EXPORTS]->()
WHERE NOT EXISTS(()-[:IMPORTS]->(c))
RETURN c.name, c.file_path
```

### Find high-coupling components
```cypher
MATCH (c:ReactComponent)
WITH c, COUNT {(c)-[:RENDERS|USES|CALLS]->()} as dependencies
WHERE dependencies > 15
RETURN c.name, dependencies
ORDER BY dependencies DESC
```

## Schema Versioning

Current schema version: **1.0.0**

### Version History
- 1.0.0 - Initial schema with TypeScript/React/PHP support

### Migration Notes
When schema changes:
1. Increment version in config
2. Add migration script in `migrations/`
3. Update this documentation
4. Test with existing databases