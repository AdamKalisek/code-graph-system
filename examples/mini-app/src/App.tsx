import React, { useState } from 'react';
import { UserCard } from './components/UserCard';

interface User {
  id: number;
  name: string;
  email: string;
}

const App: React.FC = () => {
  const [users, setUsers] = useState<User[]>([
    { id: 1, name: 'Alice', email: 'alice@example.com' },
    { id: 2, name: 'Bob', email: 'bob@example.com' },
  ]);

  const handleEditUser = (userId: number) => {
    console.log(`App received edit request for user ${userId}`);
    // In a real app, this would navigate to edit page or open modal
  };

  return (
    <div className="app">
      <h1>Mini App Example</h1>
      <div className="users-list">
        {users.map(user => (
          <UserCard key={user.id} user={user} onEdit={handleEditUser} />
        ))}
      </div>
    </div>
  );
};

export default App;