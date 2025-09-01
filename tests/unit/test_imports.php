<?php
namespace App\Controllers;

use App\Models\User;
use App\Services\EmailService;
use App\Repositories\UserRepository as UserRepo;

class UserController {
    private User $user;
    private EmailService $emailService;
    private UserRepo $repository;
    
    public function __construct(User $user, EmailService $service, UserRepo $repo) {
        $this->user = $user;
        $this->emailService = $service;
        $this->repository = $repo;
    }
}