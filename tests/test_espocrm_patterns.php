<?php

namespace Espo\Services;

class TestService {
    private $container;
    private $entityManager;
    
    public function __construct($container) {
        $this->container = $container;
        $this->entityManager = $container->get('entityManager');
    }
    
    public function testContainerResolution() {
        // Test container->get() with known services
        $config = $this->container->get('config');
        $metadata = $this->container->get('metadata');
        $hookManager = $this->container->get('hookManager');
        
        // Test entityFactory
        $user = $this->entityManager->getEntityFactory()->create('User');
        
        // Test serviceFactory
        $emailService = $this->container->get('serviceFactory')->create('Email');
        
        // Test injectableFactory with class constant
        $processor = $this->container->get('injectableFactory')->create(\Espo\Core\Job\JobProcessor::class);
    }
    
    public function testConstantPropagation() {
        // Test variable assignment and instantiation
        $className = 'User';
        $entity = new $className();
        
        $serviceName = 'Email';
        $service = $this->container->get('serviceFactory')->create($serviceName);
    }
    
    public function testEventHandling() {
        // Test event emission
        $this->trigger('entity.beforeSave', ['entity' => $user]);
        $this->emit('user.created', $user);
        
        // Test event listening
        $this->listenTo($user, 'change:status', function() {
            // Handle status change
        });
        
        $this->on('app:init', [$this, 'onAppInit']);
    }
}