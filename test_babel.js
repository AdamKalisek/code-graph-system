
// Test API calls with different patterns
import axios from 'axios';
import { fetchUser } from './api';

const API_BASE = '/api/v1';

async function loadUser(userId) {
    // Simple fetch
    const res1 = await fetch('/api/v1/User/' + userId);
    
    // Template literal
    const res2 = await fetch(`${API_BASE}/User/${userId}`);
    
    // $.ajax with object
    $.ajax({
        url: '/api/v1/Lead',
        method: 'POST',
        data: {name: 'Test'}
    });
    
    // axios methods
    await axios.get('/api/v1/Account');
    await axios.post('/api/v1/Account', data);
    
    // Complex Ajax call
    Espo.Ajax.postRequest('Layout/action/resetToDefault', {
        scope: this.scope,
        name: this.name
    });
}

class UserManager {
    constructor() {
        this.users = [];
    }
    
    async loadAll() {
        return fetch('/api/v1/User');
    }
}

export default UserManager;
