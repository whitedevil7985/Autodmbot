# AutoDM Join Request Bot

Telegram bot that sends a configurable private welcome message when someone submits a join request to a group or supergroup.

## Features
- Handles Telegram `chat_join_request` updates.
- Sends the message using Telegram's temporary `user_chat_id` permission.
- Stores a separate welcome message for each group.
- Uses **PostgreSQL** when `DATABASE_URL` is configured; falls back to local SQLite for development.
- Restricts configuration commands to group admins.
- Supports placeholders: `{first_name}`, `{username}`, `{group}`.

## Commands
Use these in the target group:
- `/setmsg <text>` — set or replace the group's DM message
- `/preview` — preview the configured message
- `/delmsg` — delete the configured message
- `/status` — show configuration and database status

Example:
`/setmsg Hi {first_name}! Your request to join {group} has been received.`

## Local setup
1. Create a bot with @BotFather.
2. Add it to your group as an administrator and grant invite-users/manage-invite-links permission.
3. Install dependencies: `pip install -r requirements.txt`
4. Set `BOT_TOKEN`.
5. Optionally set `DATABASE_URL` to a PostgreSQL connection URL.
6. Run: `python bot.py`

Without `DATABASE_URL`, the bot uses a local SQLite file named `autodm.sqlite3`.

## Heroku deployment
1. Create a Heroku app and connect this GitHub repository, branch `main`.
2. Add the **Heroku Postgres** add-on from the app's Resources or Add-ons page. Heroku will provision `DATABASE_URL` automatically.
3. In Settings → Config Vars, set `BOT_TOKEN` to your BotFather token. Do not manually paste or commit database credentials.
4. Deploy the `main` branch.
5. In Resources, enable exactly one `worker` dyno. Do not run multiple polling workers with the same bot token.

The Procfile starts `python bot.py` as a worker. Heroku Postgres persists group settings across dyno restarts and replacements. If you previously used SQLite, its settings are not migrated automatically; run `/setmsg` again for each group after switching to PostgreSQL.

## Telegram notes and security
Telegram allows the bot to contact a join requester using `user_chat_id` for a limited period (up to five minutes), subject to Bot API restrictions. If Telegram rejects the DM, the error is logged and the join request is left unchanged. The bot does not approve or decline requests.

Messages are sent as plain text. Keep `BOT_TOKEN` and database credentials private; never commit real secrets.
