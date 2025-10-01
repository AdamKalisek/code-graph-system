"""Data models for the application."""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class User:
    """User model"""
    id: int
    username: str
    email: str
    created_at: datetime
    is_active: bool = True

    def activate(self) -> None:
        """Activate the user"""
        self.is_active = True

    def deactivate(self) -> None:
        """Deactivate the user"""
        self.is_active = False

    def update_email(self, new_email: str) -> None:
        """Update user email"""
        self.email = new_email


@dataclass
class Post:
    """Blog post model"""
    id: int
    title: str
    content: str
    author_id: int
    created_at: datetime
    published: bool = False

    def publish(self) -> None:
        """Publish the post"""
        self.published = True

    def unpublish(self) -> None:
        """Unpublish the post"""
        self.published = False
