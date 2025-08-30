// Frontend view for User management
import BaseView from './BaseView';
import UserModel from '../models/UserModel';
import UserService from '../services/UserService';

export default class UserView extends BaseView {
    constructor() {
        super();
        this.model = new UserModel();
        this.service = new UserService();
    }
    
    async loadUsers() {
        // Calls GET /api/users
        const users = await this.service.fetchUsers();
        this.render(users);
    }
    
    async createUser(data) {
        // Calls POST /api/users
        const user = await this.service.createUser(data);
        this.model.add(user);
    }
    
    async deleteUser(id) {
        // Calls DELETE /api/users/:id
        await this.service.deleteUser(id);
        this.model.remove(id);
    }
}