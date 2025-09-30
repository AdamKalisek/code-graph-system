import React from 'react';
import { Button } from './Button';

interface User {
  id: number;
  name: string;
  email: string;
}

interface UserCardProps {
  user: User;
  onEdit: (userId: number) => void;
}

export const UserCard: React.FC<UserCardProps> = ({ user, onEdit }) => {
  const handleEdit = () => {
    console.log(`Editing user: ${user.name}`);
    onEdit(user.id);
  };

  return (
    <div className="user-card">
      <h3>{user.name}</h3>
      <p>{user.email}</p>
      <Button label="Edit" onClick={handleEdit} />
    </div>
  );
};

export default UserCard;