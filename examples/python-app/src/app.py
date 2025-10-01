"""Main application entry point."""

import sys
from .database import Database
from .services import UserService, PostService


class Application:
    """Main application class"""

    def __init__(self, db_connection: str):
        self.db = Database(db_connection)
        self.user_service = UserService(self.db)
        self.post_service = PostService(self.db, self.user_service)

    def run(self) -> None:
        """Run the application"""
        self.db.connect()
        try:
            self._main_loop()
        finally:
            self.db.disconnect()

    def _main_loop(self) -> None:
        """Main application loop"""
        print("Application started")

        # Create a user
        user = self.user_service.create_user("john_doe", "john@example.com")
        print(f"Created user: {user.username}")

        # Create a post
        post = self.post_service.create_post(
            title="Hello World",
            content="This is my first post",
            author_id=user.id
        )
        print(f"Created post: {post.title}")


def main():
    """Entry point"""
    app = Application("postgresql://localhost/mydb")
    app.run()


if __name__ == "__main__":
    main()
