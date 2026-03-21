import asyncio
import os
import tempfile

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

from app.config import settings


bot = Bot(token=settings.bot_token)
dp = Dispatcher()


async def ensure_user_token(telegram_id: int) -> str | None:
    if not settings.bot_api_token:
        return None
    return settings.bot_api_token


@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer("Reader System bot ready. Send EPUB/FB2/PDF as document.")


@dp.message(Command("help"))
async def help_handler(message: Message):
    await message.answer("Commands: /start, /help, /library. Upload a document to import.")


@dp.message(Command("library"))
async def library_handler(message: Message):
    token = await ensure_user_token(message.from_user.id)
    if not token:
        await message.answer("BOT_API_TOKEN not configured.")
        return
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            f"{settings.backend_base_url}/api/v1/library?page=1&page_size=20",
            headers={"Authorization": f"Bearer {token}"},
        )
    if resp.status_code >= 400:
        await message.answer("Failed to fetch library")
        return

    items = resp.json().get("items", [])
    if not items:
        await message.answer("Library is empty")
        return
    await message.answer("\n".join(f"- {x['title']} ({x['status']})" for x in items))


@dp.message(F.document)
async def document_handler(message: Message):
    doc = message.document
    if not doc:
        return

    suffix = os.path.splitext(doc.file_name or "")[1].lower()
    if suffix not in {".epub", ".fb2", ".pdf"}:
        await message.answer("Unsupported file type.")
        return

    token = await ensure_user_token(message.from_user.id)
    if not token:
        await message.answer("BOT_API_TOKEN not configured.")
        return

    tf = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        await bot.download(doc, destination=tf)
        tf.close()

        data = {
            "title": os.path.splitext(doc.file_name or "Uploaded book")[0],
            "author": message.from_user.full_name or "Unknown",
            "visibility": "private",
        }
        fobj = open(tf.name, "rb")
        files = {"file": (doc.file_name, fobj, "application/octet-stream")}

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{settings.backend_base_url}/api/v1/books/upload",
                data=data,
                files=files,
                headers={"Authorization": f"Bearer {token}"},
            )
        fobj.close()

        if resp.status_code >= 400:
            await message.answer(f"Upload failed: {resp.text}")
            return

        result = resp.json()
        await message.answer(f"Book handled: {result['message']} (book_id={result['book_id']})")
    finally:
        try:
            os.unlink(tf.name)
        except OSError:
            pass


async def main() -> None:
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
