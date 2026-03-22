import asyncio
import os
import tempfile

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import settings


bot = Bot(token=settings.bot_token)
dp = Dispatcher()


def _user_headers(telegram_id: int) -> dict:
    return {
        "Authorization": f"Bearer {settings.bot_api_token}",
        "X-Telegram-User-Id": str(telegram_id),
    }


async def _backend_request(
    method: str,
    path: str,
    telegram_id: int,
    *,
    json: dict | None = None,
    data: dict | None = None,
    files: dict | None = None,
) -> httpx.Response:
    async with httpx.AsyncClient(timeout=45) as client:
        return await client.request(
            method,
            f"{settings.backend_base_url}{path}",
            headers=_user_headers(telegram_id),
            json=json,
            data=data,
            files=files,
        )


async def _fetch_library(telegram_id: int, page_size: int = 30) -> list[dict]:
    resp = await _backend_request("GET", f"/api/v1/library?page=1&page_size={page_size}", telegram_id)
    if resp.status_code >= 400:
        return []
    return resp.json().get("items", [])


async def _fetch_me(telegram_id: int) -> dict | None:
    resp = await _backend_request("GET", "/api/v1/users/me", telegram_id)
    if resp.status_code >= 400:
        return None
    return resp.json()


def _library_keyboard(items: list[dict]) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    for item in items[:20]:
        icon = "⭐ " if item.get("favorite") else ""
        status = item.get("status", "?")
        title = str(item.get("title", "Untitled"))[:24]
        kb.button(text=f"{icon}{title} [{status}]", callback_data=f"book:{item['id']}")
    kb.button(text="🔄 Refresh", callback_data="lib:refresh")
    kb.adjust(1)
    return kb


def _book_keyboard(item: dict) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    book_id = item["id"]

    fav = bool(item.get("favorite"))
    kb.button(
        text="⭐ Remove favorite" if fav else "⭐ Add favorite",
        callback_data=f"fav:{book_id}:{0 if fav else 1}",
    )

    visibility = item.get("visibility", "private")
    next_vis = "shared" if visibility == "private" else "private"
    kb.button(
        text="🔓 Share" if visibility == "private" else "🔒 Make private",
        callback_data=f"vis:{book_id}:{next_vis}",
    )
    kb.button(text="⬅ Back to library", callback_data="lib:refresh")
    kb.adjust(1)
    return kb


async def _send_library_view(message: Message, telegram_id: int) -> None:
    items = await _fetch_library(telegram_id)
    me = await _fetch_me(telegram_id)
    if me is None:
        await message.answer("Backend auth failed. Check BOT_API_TOKEN.")
        return

    role = "admin" if me.get("is_admin") else "user"
    if not items:
        await message.answer(f"Library is empty for @{role}. Send a book file to upload.")
        return

    text = [f"Library ({role}):"]
    for item in items[:20]:
        text.append(
            f"- {item['title']} / {item['author']} | {item['status']} | {item['visibility']}"
        )

    await message.answer("\n".join(text), reply_markup=_library_keyboard(items).as_markup())


async def _find_book(telegram_id: int, book_id: str) -> dict | None:
    items = await _fetch_library(telegram_id, page_size=100)
    for item in items:
        if item.get("id") == book_id:
            return item
    return None


@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer(
        "Reader bot ready.\n"
        "Commands: /help, /library, /admin\n"
        "Send EPUB/FB2/PDF as document to import." 
    )


@dp.message(Command("help"))
async def help_handler(message: Message):
    await message.answer(
        "How to use:\n"
        "1) Send a book file to upload\n"
        "2) Use /library to browse\n"
        "3) Use buttons to favorite/share/private"
    )


@dp.message(Command("library"))
async def library_handler(message: Message):
    if not settings.bot_api_token:
        await message.answer("BOT_API_TOKEN not configured.")
        return
    await _send_library_view(message, message.from_user.id)


@dp.message(Command("admin"))
async def admin_handler(message: Message):
    if not settings.bot_api_token:
        await message.answer("BOT_API_TOKEN not configured.")
        return
    me = await _fetch_me(message.from_user.id)
    if not me:
        await message.answer("Cannot reach backend auth.")
        return
    if not me.get("is_admin"):
        await message.answer("You are not configured as Telegram admin.")
        return

    items = await _fetch_library(message.from_user.id, page_size=100)
    total = len(items)
    ready = len([x for x in items if x.get("status") == "ready"])
    await message.answer(f"Admin mode active. Total books visible: {total}, ready: {ready}")


@dp.callback_query(F.data == "lib:refresh")
async def library_refresh_callback(callback: CallbackQuery):
    if not callback.message:
        return
    items = await _fetch_library(callback.from_user.id)
    me = await _fetch_me(callback.from_user.id)
    role = "admin" if (me and me.get("is_admin")) else "user"

    if not items:
        await callback.message.edit_text(f"Library is empty for @{role}.")
        await callback.answer()
        return

    text = [f"Library ({role}):"]
    for item in items[:20]:
        text.append(f"- {item['title']} / {item['author']} | {item['status']} | {item['visibility']}")
    await callback.message.edit_text("\n".join(text), reply_markup=_library_keyboard(items).as_markup())
    await callback.answer("Updated")


@dp.callback_query(F.data.startswith("book:"))
async def book_callback(callback: CallbackQuery):
    if not callback.message:
        return
    _, book_id = callback.data.split(":", 1)
    item = await _find_book(callback.from_user.id, book_id)
    if not item:
        await callback.answer("Book not found")
        return

    text = (
        f"{item['title']}\n"
        f"Author: {item['author']}\n"
        f"Series: {item.get('series') or '-'}\n"
        f"Type: {item['file_type']}\n"
        f"Status: {item['status']}\n"
        f"Visibility: {item['visibility']}"
    )
    await callback.message.edit_text(text, reply_markup=_book_keyboard(item).as_markup())
    await callback.answer()


@dp.callback_query(F.data.startswith("fav:"))
async def favorite_callback(callback: CallbackQuery):
    if not callback.message:
        return
    _, book_id, flag = callback.data.split(":", 2)
    favorite = flag == "1"

    resp = await _backend_request(
        "POST",
        "/api/v1/favorites",
        callback.from_user.id,
        json={"book_id": book_id, "favorite": favorite},
    )
    if resp.status_code >= 400:
        await callback.answer("Favorite update failed")
        return

    item = await _find_book(callback.from_user.id, book_id)
    if not item:
        await callback.answer("Updated")
        return
    text = (
        f"{item['title']}\n"
        f"Author: {item['author']}\n"
        f"Series: {item.get('series') or '-'}\n"
        f"Type: {item['file_type']}\n"
        f"Status: {item['status']}\n"
        f"Visibility: {item['visibility']}"
    )
    await callback.message.edit_text(text, reply_markup=_book_keyboard(item).as_markup())
    await callback.answer("Favorite updated")


@dp.callback_query(F.data.startswith("vis:"))
async def visibility_callback(callback: CallbackQuery):
    if not callback.message:
        return
    _, book_id, visibility = callback.data.split(":", 2)

    resp = await _backend_request(
        "PATCH",
        f"/api/v1/books/{book_id}/visibility",
        callback.from_user.id,
        json={"visibility": visibility},
    )
    if resp.status_code >= 400:
        await callback.answer("Visibility update denied")
        return

    item = await _find_book(callback.from_user.id, book_id)
    if not item:
        await callback.answer("Visibility updated")
        return
    text = (
        f"{item['title']}\n"
        f"Author: {item['author']}\n"
        f"Series: {item.get('series') or '-'}\n"
        f"Type: {item['file_type']}\n"
        f"Status: {item['status']}\n"
        f"Visibility: {item['visibility']}"
    )
    await callback.message.edit_text(text, reply_markup=_book_keyboard(item).as_markup())
    await callback.answer("Visibility updated")


@dp.message(F.document)
async def document_handler(message: Message):
    doc = message.document
    if not doc:
        return

    suffix = os.path.splitext(doc.file_name or "")[1].lower()
    if suffix not in {".epub", ".fb2", ".pdf"}:
        await message.answer("Unsupported file type.")
        return

    if not settings.bot_api_token:
        await message.answer("BOT_API_TOKEN not configured.")
        return

    tf = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        await bot.download(doc, destination=tf)
        tf.close()

        with open(tf.name, "rb") as fobj:
            files = {"file": (doc.file_name or f"book{suffix}", fobj, "application/octet-stream")}
            resp = await _backend_request(
                "POST",
                "/api/v1/books/upload",
                message.from_user.id,
                files=files,
            )

        if resp.status_code >= 400:
            await message.answer(f"Upload failed: {resp.text}")
            return

        result = resp.json()
        await message.answer(f"Book handled: {result['message']}\nID: {result['book_id']}")
    finally:
        try:
            os.unlink(tf.name)
        except OSError:
            pass


async def main() -> None:
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
