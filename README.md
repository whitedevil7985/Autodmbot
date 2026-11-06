# AutoDM Join Request Bot

This repository contains the AutoDM Telegram bot project. See the setup instructions and commands below.

## Features
- Sends a configurable private message when a user submits a group join request.
- Stores per-group messages in SQLite.
- Admin-only configuration commands.
- Placeholders: `{first_name}`, `{username}`, `{group}`.

## Commands
- `/setmsg <text>` — set the group's DM message
- `/preview` — preview it
- `/delmsg` — remove it
- `/status` — show status

## Setup
1. Create a bot with @BotFather.
2. Add it to the group as an administrator and grant invite-users/manage-invite-links permission.
3. Set `BOT_TOKEN` from `.env.example` as an environment variable.
4. Run `pip install -r requirements.txt` then `python bot.py`.

For Heroku, configure `BOT_TOKEN` and deploy the worker defined in `Procfile`. SQLite on Heroku's ephemeral filesystem is not durable; use PostgreSQL for production persistence.
