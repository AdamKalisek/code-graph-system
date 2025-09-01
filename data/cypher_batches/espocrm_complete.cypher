MATCH (n) DETACH DELETE n;

CREATE INDEX symbol_id IF NOT EXISTS FOR (s:Symbol) ON (s.id);
CREATE INDEX php_class IF NOT EXISTS FOR (c:PHPClass) ON (c.name);
CREATE INDEX js_module IF NOT EXISTS FOR (m:JSModule) ON (m.name);

