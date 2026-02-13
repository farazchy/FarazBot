# 🤖 FarazBot

FarazBot is a custom Discord moderation and management bot designed to keep communities safe, organized, and professional.

Built with `discord.py 2.x`, FarazBot includes automated moderation tools, welcome messages, approval-based punishments, and server management features.

---

## 🚀 Features

✅ Welcome new members automatically  
✅ Auto-delete banned words  
✅ Detect links or severe triggers  
✅ Request server owner approval before kick/ban  
✅ Private mod-log approval system  
✅ Owner-only management commands  

---

## 🛡 Moderation System

When a severe trigger (e.g. suspicious link or defined phrase) is detected:

1. The message is removed.
2. An approval request is sent to the `mod-log` channel.
3. The server owner can:
   - ✅ Approve → Kick/Ban user
   - ❌ Decline → No action taken

This ensures control stays with the server owner.

---

## ⚙️ Environment Variables

FarazBot uses environment variables for security.

Set these in your hosting platform (Render, Railway, etc.):

| Variable | Description |
|----------|------------|
| `DISCORD_TOKEN` | Your bot token from Discord Developer Portal |
| `WELCOME_CHANNEL_ID` | Channel ID where welcome messages are sent |
| `MOD_LOG_CHANNEL_ID` | Channel ID for approval requests |
| `ACTION_ON_APPROVAL` | `kick` or `ban` |

---

## 📦 Installation (Local)

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python bot.py
