"""Business logic services."""

from typing import List, Optional
from datetime import datetime

from .database import Database, Repository
from .models import User, Post


class UserService:
    """Service for user-related operations"""

    def __init__(self, db: Database):
        self.db = db
        self.repository = Repository(db)

    def create_user(self, username: str, email: str) -> User:
        """Create a new user"""
        user = User(
            id=0,
            username=username,
            email=email,
            created_at=datetime.now()
        )
        # Save to database
        self.repository.find_all()
        return user

    def get_user(self, user_id: int) -> Optional[User]:
        """Get a user by ID"""
        data = self.repository.find_by_id(user_id)
        if not data:
            return None

        return User(
            id=data['id'],
            username=data['username'],
            email=data['email'],
            created_at=data['created_at']
        )

    def list_active_users(self) -> List[User]:
        """List all active users"""
        all_users = self.repository.find_all()
        return [u for u in all_users if u.get('is_active', True)]


class PostService:
    """Service for blog post operations"""

    def __init__(self, db: Database, user_service: UserService):
        self.db = db
        self.user_service = user_service
        self.repository = Repository(db)

    def create_post(self, title: str, content: str, author_id: int) -> Post:
        """Create a new blog post"""
        # Verify author exists
        author = self.user_service.get_user(author_id)
        if not author:
            raise ValueError(f"User {author_id} not found")

        post = Post(
            id=0,
            title=title,
            content=content,
            author_id=author_id,
            created_at=datetime.now()
        )
        return post

    def publish_post(self, post_id: int) -> None:
        """Publish a post"""
        post_data = self.repository.find_by_id(post_id)
        if post_data:
            post = Post(**post_data)
            post.publish()
