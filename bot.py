import logging
import os
import sqlite3
from contextlib import contextmanager

import psycopg
from telegram import Update
from telegram.constants import ChatType
from telegram.error import TelegramError
from telegram.ext import Application, ChatJoinRequestHandler, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DB_PATH = os.getenv("DATABASE_PATH", "autodm.sqlite3")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
)
logger = logging.getLogger("autodmbot")


def database_url():
    """Normalize Heroku's legacy postgres:// URL and require TLS for hosted DBs."""
    url = DATABASE_URL
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url and "sslmode=" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"
    return url


@contextmanager
def db_connection():
    """Open, commit/rollback, and close one PostgreSQL or local SQLite connection."""
    conn = psycopg.connect(database_url()) if DATABASE_URL else sqlite3.connect(DB_PATH)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def initialize_database():
    with db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS group_settings (
                chat_id BIGINT PRIMARY KEY,
                welcome_text TEXT NOT NULL,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
    logger.info("Database initialized (%s)", "PostgreSQL" if DATABASE_URL else "SQLite")


def get_message(chat_id: int):
    placeholder = "%s" if DATABASE_URL else "?"
    with db_connection() as conn:
        row = conn.execute(
            f"SELECT welcome_text FROM group_settings WHERE chat_id = {placeholder}",
            (chat_id,),
        ).fetchone()
    return row[0] if row else None


def save_message(chat_id: int, welcome_text: str):
    placeholder = "%s" if DATABASE_URL else "?"
    with db_connection() as conn:
        conn.execute(f"""
            INSERT INTO group_settings (chat_id, welcome_text, updated_at)
            VALUES ({placeholder}, {placeholder}, CURRENT_TIMESTAMP)
            ON CONFLICT(chat_id) DO UPDATE SET
                welcome_text = excluded.welcome_text,
                updated_at = CURRENT_TIMESTAMP
        """, (chat_id, welcome_text))


def delete_message(chat_id: int):
    placeholder = "%s" if DATABASE_URL else "?"
    with db_connection() as conn:
        cur = conn.execute(
            f"DELETE FROM group_settings WHERE chat_id = {placeholder}", (chat_id,)
        )
        return cur.rowcount > 0


async def is_group_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat, user = update.effective_chat, update.effective_user
    if not chat or not user or chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return False
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status in ("administrator", "creator")
    except TelegramError:
        logger.exception("Could not verify admin status for chat %s", chat.id)
        return False


async def admin_only(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not await is_group_admin(update, context):
        if update.effective_message:
            await update.effective_message.reply_text(
                "Ye command sirf group admins use kar sakte hain."
            )
        return False
    return True


def render_message(template: str, first_name: str, username: str | None, group: str):
    return (
        template.replace("{first_name}", first_name)
        .replace("{username}", f"@{username}" if username else "")
        .replace("{group}", group)
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "👋 Main AutoDM Join Request Bot hoon. Mujhe group mein admin banao "
        "aur Invite Users permission do. Phir group mein /setmsg se DM message set karo."
    )


async def setmsg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return
    message_text = " ".join(context.args).strip()
    if not message_text:
        await update.effective_message.reply_text(
            "Usage: /setmsg Welcome {first_name}! Aapki request {group} mein mil gayi hai.\n"
            "Placeholders: {first_name}, {username}, {group}"
        )
        return
    save_message(update.effective_chat.id, message_text)
    await update.effective_message.reply_text("✅ Join-request DM message save ho gaya.")


async def preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return
    template = get_message(update.effective_chat.id)
    if not template:
        await update.effective_message.reply_text("Pehle /setmsg se message set karo.")
        return
    sample = render_message(
        template,
        update.effective_user.first_name or "Member",
        update.effective_user.username,
        update.effective_chat.title or "Group",
    )
    await update.effective_message.reply_text("📨 Preview:\n\n" + sample)


async def delmsg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return
    if delete_message(update.effective_chat.id):
        await update.effective_message.reply_text("🗑️ Welcome DM message delete ho gaya.")
    else:
        await update.effective_message.reply_text("Is group ke liye message set nahi tha.")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return
    configured = bool(get_message(update.effective_chat.id))
    database = "PostgreSQL" if DATABASE_URL else "SQLite (local)"
    await update.effective_message.reply_text(
        "⚙️ AutoDM Status\n"
        f"Group: {update.effective_chat.title or update.effective_chat.id}\n"
        f"Welcome DM: {'Set ✅' if configured else 'Not set ❌'}\n"
        f"Database: {database}"
    )


async def on_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    request = update.chat_join_request
    if not request:
        return
    try:
        template = get_message(request.chat.id)
    except Exception:
        logger.exception("Database read failed for chat %s", request.chat.id)
        return
    if not template:
        logger.info("No welcome message configured for chat %s", request.chat.id)
        return

    user = request.from_user
    message = render_message(
        template, user.first_name or "there", user.username, request.chat.title or "the group"
    )
    try:
        await context.bot.send_message(
            chat_id=request.user_chat_id, text=message, disable_web_page_preview=True
        )
        logger.info("Sent join-request DM to user %s for chat %s", user.id, request.chat.id)
    except TelegramError as exc:
        logger.warning("Could not DM requester %s: %s", user.id, exc)


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is required.")
    initialize_database()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setmsg", setmsg))
    app.add_handler(CommandHandler("preview", preview))
    app.add_handler(CommandHandler("delmsg", delmsg))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(ChatJoinRequestHandler(on_join_request))
    logger.info("AutoDM bot starting...")
    app.run_polling(allowed_updates=["message", "chat_join_request"])


if __name__ == "__main__":
    main()
