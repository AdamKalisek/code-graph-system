// Configuration Reference Import Queries

MERGE (f:ConfigFile {path: 'application/Espo/Resources/metadata/app/authentication.json', type: 'json'});

MATCH (c:PHPClass {name: 'Espo\\Core\\Authentication\\Hook\\Hooks\\FailedAttemptsLimit'})
        MATCH (f:ConfigFile {path: 'application/Espo/Resources/metadata/app/authentication.json'})
        MERGE (c)-[:REGISTERED_IN {config_key: 'beforeLoginHookClassNameList', registration_type: 'AUTHENTICATION_HOOK'}]->(f)
        SET c.requires_registration = true,
            c.registration_file = 'application/Espo/Resources/metadata/app/authentication.json',
            c.registration_key = 'beforeLoginHookClassNameList';

MATCH (c:PHPClass {name: 'Espo\\Core\\Authentication\\Hook\\Hooks\\FailedCodeAttemptsLimit'})
        MATCH (f:ConfigFile {path: 'application/Espo/Resources/metadata/app/authentication.json'})
        MERGE (c)-[:REGISTERED_IN {config_key: 'beforeLoginHookClassNameList', registration_type: 'AUTHENTICATION_HOOK'}]->(f)
        SET c.requires_registration = true,
            c.registration_file = 'application/Espo/Resources/metadata/app/authentication.json',
            c.registration_key = 'beforeLoginHookClassNameList';

MATCH (c:PHPClass {name: 'Espo\\Core\\Authentication\\Hook\\Hooks\\IpAddressWhitelist'})
        MATCH (f:ConfigFile {path: 'application/Espo/Resources/metadata/app/authentication.json'})
        MERGE (c)-[:REGISTERED_IN {config_key: 'onLoginHookClassNameList', registration_type: 'AUTHENTICATION_HOOK'}]->(f)
        SET c.requires_registration = true,
            c.registration_file = 'application/Espo/Resources/metadata/app/authentication.json',
            c.registration_key = 'onLoginHookClassNameList';

MATCH (m:PHPClass {name: 'Espo\\Core\\Authentication\\Hook\\Manager'})
        MATCH (h:PHPClass {name: 'Espo\\Core\\Authentication\\Hook\\Hooks\\FailedAttemptsLimit'})
        MERGE (m)-[:LOADS_VIA_CONFIG {config_key: 'beforeLoginHookClassNameList', mechanism: 'metadata'}]->(h);

MATCH (m:PHPClass {name: 'Espo\\Core\\Authentication\\Hook\\Manager'})
        MATCH (h:PHPClass {name: 'Espo\\Core\\Authentication\\Hook\\Hooks\\FailedCodeAttemptsLimit'})
        MERGE (m)-[:LOADS_VIA_CONFIG {config_key: 'beforeLoginHookClassNameList', mechanism: 'metadata'}]->(h);

MATCH (m:PHPClass {name: 'Espo\\Core\\Authentication\\Hook\\Manager'})
        MATCH (h:PHPClass {name: 'Espo\\Core\\Authentication\\Hook\\Hooks\\IpAddressWhitelist'})
        MERGE (m)-[:LOADS_VIA_CONFIG {config_key: 'onLoginHookClassNameList', mechanism: 'metadata'}]->(h);

MATCH (m:PHPMethod)
    WHERE m.class_name = 'Espo\\Core\\Authentication\\Hook\\Manager'
    AND m.name IN ['getHookClassNameList', 'getBeforeLoginHookList', 'getOnLoginHookList']
    SET m.uses_dynamic_loading = true,
        m.loading_mechanism = 'metadata_config';

