from fastapi import APIRouter

from app.api.v1 import auth, books, favorites, library, progress, subscriptions, users


router = APIRouter(prefix="/api/v1")
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(library.router, prefix="/library", tags=["library"])
router.include_router(books.router, prefix="/books", tags=["books"])
router.include_router(progress.router, prefix="/progress", tags=["progress"])
router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(favorites.router, prefix="/favorites", tags=["favorites"])
router.include_router(subscriptions.router, prefix="/subscriptions", tags=["subscriptions"])
