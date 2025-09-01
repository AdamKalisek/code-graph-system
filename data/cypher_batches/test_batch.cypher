// Test batch - 10 nodes, 10 relationships

// Nodes
CREATE (:Namespace {id: "acac43f2a5345ee40ae1daf2c4500404", name: "Espo", type: "namespace", file: "espocrm/application/Espo/Binding.php", line: 30});
CREATE (:Class {id: "9904beec11b30b065df0d613c80e0c9f", name: "Espo\\Binding", type: "class", file: "espocrm/application/Espo/Binding.php", line: 42, namespace: "Espo"});
CREATE (:Method {id: "bac9329b06eeda2a8df5d020b315899b", name: "process", type: "method", file: "espocrm/application/Espo/Binding.php", line: 44, namespace: "Espo"});
CREATE (:Method {id: "9a5055cdc04318e02c5f7fb983c65e5a", name: "bindServices", type: "method", file: "espocrm/application/Espo/Binding.php", line: 54, namespace: "Espo"});
CREATE (:Method {id: "e937a57e7363812f0bf892f6d04979a9", name: "bindCore", type: "method", file: "espocrm/application/Espo/Binding.php", line: 247, namespace: "Espo"});
CREATE (:Method {id: "389bf930c68670ef34c44e7e37612644", name: "bindMisc", type: "method", file: "espocrm/application/Espo/Binding.php", line: 265, namespace: "Espo"});
CREATE (:Method {id: "94fecf821b2433de659c451df2470c08", name: "bindAcl", type: "method", file: "espocrm/application/Espo/Binding.php", line: 327, namespace: "Espo"});
CREATE (:Method {id: "173fe2273ce695e153ad83423ea54f9e", name: "bindWebSocket", type: "method", file: "espocrm/application/Espo/Binding.php", line: 335, namespace: "Espo"});
CREATE (:Method {id: "cb72d5072a0db29b03ad0a2eae93c17f", name: "bindEmailAccount", type: "method", file: "espocrm/application/Espo/Binding.php", line: 348, namespace: "Espo"});
CREATE (:Namespace {id: "70dfdc73da03b53eab2bb963ccdde95f", name: "Espo\\Repositories", type: "namespace", file: "espocrm/application/Espo/Repositories/Integration.php", line: 30});

// Relationships
MATCH (s {id: 'acac43f2a5345ee40ae1daf2c4500404'}), (t {id: 'efede5421e50b9ad41456c80623e424b'}) CREATE (s)-[:IMPORTS]->(t);
MATCH (s {id: 'acac43f2a5345ee40ae1daf2c4500404'}), (t {id: 'fb0bf3cca63f82e73487322dd20828ae'}) CREATE (s)-[:IMPORTS]->(t);
MATCH (s {id: 'acac43f2a5345ee40ae1daf2c4500404'}), (t {id: '06739658104a73b2283dcf6c572f2e90'}) CREATE (s)-[:IMPORTS]->(t);
MATCH (s {id: 'bac9329b06eeda2a8df5d020b315899b'}), (t {id: '9a5055cdc04318e02c5f7fb983c65e5a'}) CREATE (s)-[:CALLS]->(t);
MATCH (s {id: 'bac9329b06eeda2a8df5d020b315899b'}), (t {id: 'e937a57e7363812f0bf892f6d04979a9'}) CREATE (s)-[:CALLS]->(t);
MATCH (s {id: 'bac9329b06eeda2a8df5d020b315899b'}), (t {id: '389bf930c68670ef34c44e7e37612644'}) CREATE (s)-[:CALLS]->(t);
MATCH (s {id: 'bac9329b06eeda2a8df5d020b315899b'}), (t {id: '94fecf821b2433de659c451df2470c08'}) CREATE (s)-[:CALLS]->(t);
MATCH (s {id: 'bac9329b06eeda2a8df5d020b315899b'}), (t {id: '173fe2273ce695e153ad83423ea54f9e'}) CREATE (s)-[:CALLS]->(t);
MATCH (s {id: 'bac9329b06eeda2a8df5d020b315899b'}), (t {id: 'cb72d5072a0db29b03ad0a2eae93c17f'}) CREATE (s)-[:CALLS]->(t);
MATCH (s {id: '70dfdc73da03b53eab2bb963ccdde95f'}), (t {id: '8110d5c1b4d090f731a8393fadf8cbb6'}) CREATE (s)-[:IMPORTS]->(t);
