// Comprehensive WebSlicer Codebase Visualization Query
// This query shows the complete picture: files, folders, components, APIs, and all relationships

MATCH (n)
WHERE n.file_path CONTAINS 'webSlicer'
   OR n.name CONTAINS 'webSlicer'
   OR n.id CONTAINS 'webSlicer'
   OR NOT EXISTS(n.file_path)
WITH n
LIMIT 1000

OPTIONAL MATCH (n)-[r]-(connected)
WHERE connected.file_path CONTAINS 'webSlicer'
   OR connected.name CONTAINS 'webSlicer'
   OR connected.id CONTAINS 'webSlicer'
   OR NOT EXISTS(connected.file_path)

RETURN n, r, connected
LIMIT 1000
