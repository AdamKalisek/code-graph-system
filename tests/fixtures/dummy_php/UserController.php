<?php
namespace App\Controllers;

use App\Services\UserService;
use App\Models\User;
use App\Interfaces\ControllerInterface;

class UserController extends BaseController implements ControllerInterface
{
    private $userService;
    
    public function __construct(UserService $service) {
        $this->userService = $service;
    }
    
    // GET /api/users
    public function list() {
        return $this->userService->getAllUsers();
    }
    
    // POST /api/users
    public function create($data) {
        $user = new User($data);
        return $this->userService->saveUser($user);
    }
    
    // DELETE /api/users/:id
    public function delete($id) {
        return $this->userService->deleteUser($id);
    }
}