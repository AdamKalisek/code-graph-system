<?php
/**
 * Test QueryBuilder Chain Detection
 * These patterns are used EVERYWHERE in EspoCRM for data access
 */

namespace Test\QueryBuilder;

class QueryBuilderTest {
    private $entityManager;
    private $repository;
    
    public function testSimpleQueries() {
        // Simple find
        $user = $this->entityManager
            ->getRepository('User')
            ->where(['isActive' => true])
            ->findOne();
        
        // Multiple conditions
        $emails = $this->entityManager
            ->getRepository('Email')
            ->where([
                'status' => 'Sent',
                'createdAt>' => '2024-01-01'
            ])
            ->order('createdAt', 'DESC')
            ->limit(0, 50)
            ->find();
    }
    
    public function testComplexQueries() {
        // Complex query with joins
        $opportunities = $this->entityManager
            ->getRepository('Opportunity')
            ->distinct()
            ->join('contacts')
            ->leftJoin('account')
            ->where([
                'stage!=' => 'Closed Lost',
                'account.type' => 'Customer'
            ])
            ->having([
                'SUM:(amount)>' => 10000
            ])
            ->groupBy('accountId')
            ->order('amount', 'DESC')
            ->find();
        
        // Subquery
        $leads = $this->repository
            ->where([
                'id=s' => [
                    'from' => 'Lead',
                    'select' => ['id'],
                    'whereClause' => [
                        'status' => 'New'
                    ]
                ]
            ])
            ->find();
    }
    
    public function testRepositoryMethods() {
        // Repository-specific methods
        $count = $this->repository->count();
        
        $exists = $this->repository
            ->where(['email' => 'test@example.com'])
            ->exists();
        
        // Get related
        $account = $this->repository->get($id);
        $contacts = $this->repository
            ->getRelation($account, 'contacts')
            ->where(['isActive' => true])
            ->find();
        
        // Clone query
        $query = $this->repository
            ->where(['type' => 'Customer'])
            ->limit(10);
        
        $cloned = clone $query;
        $results = $cloned->order('name')->find();
    }
    
    public function testQueryBuilderDirect() {
        // Direct QueryBuilder usage
        $queryBuilder = $this->entityManager->getQueryBuilder();
        
        $query = $queryBuilder
            ->select(['id', 'name', 'email'])
            ->from('User')
            ->where([
                'type' => 'regular',
                'isActive' => true
            ])
            ->order('createdAt', 'DESC')
            ->build();
        
        // Raw SQL builder
        $sql = $queryBuilder
            ->select()
            ->from('account')
            ->where(['type' => 'Customer'])
            ->getSql();
    }
    
    public function testOrmMethods() {
        // ORM save with relations
        $account = $this->entityManager->getEntity('Account', $id);
        $account->set('name', 'New Name');
        $this->entityManager->saveEntity($account);
        
        // Relate/unrelate
        $this->entityManager->getRelation($account, 'contacts')->relate($contact);
        $this->entityManager->getRelation($account, 'opportunities')->unrelate($opportunity);
        
        // Mass relate
        $this->entityManager
            ->getRelation($account, 'contacts')
            ->massRelate(['id1', 'id2', 'id3']);
    }
}