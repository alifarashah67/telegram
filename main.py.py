import asyncio
import json
from typing import List
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.error import TelegramError

class BroadcastBot:
    def __init__(self, token: str, group_ids: List[str], allowed_users: List[int]):
        self.token = token
        self.GROUP_IDS = group_ids
        self.allowed_users = allowed_users
        self.bot = Bot(token=token)
        self.config_file = 'bot_config.json'
        self.pending_messages = {}  # Store pending messages awaiting confirmation
        self.load_config()

    def load_config(self):
        try:
            with open(self.config_file, 'r') as file:
                config = json.load(file)
                self.GROUP_IDS = config.get('GROUP_IDS', self.GROUP_IDS)
        except FileNotFoundError:
            self.save_config()
    
    def save_config(self):
        config = {'GROUP_IDS': self.GROUP_IDS}
        with open(self.config_file, 'w') as file:
            json.dump(config, file)

    async def send_messages(self, message: str, photo_url: str = None) -> List[tuple]:
        results = []
        for group_id in self.GROUP_IDS:
            try:
                if photo_url:  # اگر عکس وجود دارد
                    await self.bot.send_photo(chat_id=group_id, photo=photo_url, caption=message)
                else:  # فقط پیام متنی
                    await self.bot.send_message(chat_id=group_id, text=message)
                results.append((group_id, True, None))
                await asyncio.sleep(2)
            except TelegramError as e:
                results.append((group_id, False, str(e)))
        return results

    def is_user_allowed(self, user_id: int) -> bool:
        return user_id in self.allowed_users

    async def ask_for_confirmation(self, update: Update, message: str, photo_url: str = None):
        keyboard = [
            [
                InlineKeyboardButton("Confirm & Send ✅", callback_data=f"confirm_{update.message.message_id}"),
                InlineKeyboardButton("Cancel ❌", callback_data=f"cancel_{update.message.message_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        confirmation_text = f"""
📝 Your message to send:

{message}

{f'🖼️ Photo URL: {photo_url}' if photo_url else ''}
⚠️ Are you sure you want to send this message to {len(self.GROUP_IDS)} groups?"""
        
        await update.message.reply_text(confirmation_text, reply_markup=reply_markup)
        self.pending_messages[str(update.message.message_id)] = (message, photo_url)

    async def handle_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        action, message_id = query.data.split('_')
        message_data = self.pending_messages.get(message_id)
        
        if not message_data:
            await query.edit_message_text("❌ This request has expired.")
            return
        
        message, photo_url = message_data
        
        if action == "confirm":
            results = await self.send_messages(message, photo_url)
            success_count = sum(1 for _, success, _ in results if success)
            report = f"Message sending results:\n✅ Success: {success_count}\n❌ Errors: {len(results) - success_count}"
            
            for group_id, success, error in results:
                if not success:
                    report += f"\n❌ Error in group {group_id}: {error}"
            
            await query.edit_message_text(report)
        else:
            await query.edit_message_text("❌ Message sending cancelled.")
        
        del self.pending_messages[message_id]

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        groups_list = "\n".join([f"- {gid}" for gid in self.GROUP_IDS])
        await update.message.reply_text(
            f"Hello! Welcome\n"
            f"Available commands:\n"
            f"/send <Message> [Photo URL] - Send message to all groups\n"
            f"/addgroup <Group-ID> - Add new group\n"
            f"/groups - Show list of active groups\n"
            f"/removegroup <group-id> - Delete group\n\n"
            f"Active groups:\n{groups_list or 'No groups have been added yet.'}"
        )

    async def send_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_user_allowed(update.message.from_user.id):
            await update.message.reply_text("❌ You are not allowed to send messages.")
            return

        args = context.args
        if not args:
            await update.message.reply_text("❌ Please provide your message and optionally a photo URL.The correct way:                                      /send Your message here https://example.com/path/to/your/photo.jpg")
            return

        # بررسی وجود عکس
        message = " ".join(args[:-1]) if len(args) > 1 else args[0]
        photo_url = args[-1] if len(args) > 1 and args[-1].startswith("http") else None

        await self.ask_for_confirmation(update, message, photo_url)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_user_allowed(update.message.from_user.id):
            await update.message.reply_text("❌ You are not allowed to send messages.")
            return

        await self.ask_for_confirmation(update, update.message.text)

    async def groups_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_user_allowed(update.message.from_user.id):
            await update.message.reply_text("❌ You are not allowed to view the list of groups.")
            return

        if not self.GROUP_IDS:
            await update.message.reply_text("No groups in the list.")
            return

        groups_list = "\n".join([f"- {gid}" for gid in self.GROUP_IDS])
        await update.message.reply_text(f"List of active groups:\n{groups_list}")

    async def remove_group_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_user_allowed(update.message.from_user.id):
            await update.message.reply_text("❌ You are not allowed to remove groups.")
            return

        if len(context.args) != 1:
            await update.message.reply_text("❌ Please send the group ID. Example: /removegroup -1234567890")
            return

        group_id = context.args[0]
        if group_id in self.GROUP_IDS:
            self.GROUP_IDS.remove(group_id)
            self.save_config()
            await update.message.reply_text(f"✅ Group {group_id} has been successfully removed!")
        else:
            await update.message.reply_text("❌ This group is not in the list.")

    async def add_group_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_user_allowed(update.message.from_user.id):
            await update.message.reply_text("❌ You are not allowed to add groups.")
            return

        if len(context.args) != 1:
            await update.message.reply_text("❌ Please send the group ID. Example: /addgroup -1234567890")
            return

        group_id = context.args[0]
        if not group_id.startswith('-'):
            await update.message.reply_text("❌ The group ID must start with a '-' sign.")
            return

        if group_id in self.GROUP_IDS:
            await update.message.reply_text(f"⚠️ Group {group_id} has already been added.")
            return

        try:
            await self.bot.send_message(chat_id=group_id, text="Test message - This group has been added to the broadcast list.")
            self.GROUP_IDS.append(group_id)
            self.save_config()
            await update.message.reply_text(f"✅ Group {group_id} has been successfully added!")
        except TelegramError as e:
            await update.message.reply_text(f"❌ Error adding group: {str(e)}")

def main():
    BOT_TOKEN = "7944302507:AAH38PgZRPEqPCq6BluIyBfbdSLtNw_ajeY"
    GROUP_IDS = ["-4581627682", "-4050106231", "-4541806770"]
    ALLOWED_USERS = [224921122, 1881464784, 92861319]

    broadcast_bot = BroadcastBot(BOT_TOKEN, GROUP_IDS, ALLOWED_USERS)
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", broadcast_bot.start_command))
    application.add_handler(CommandHandler("send", broadcast_bot.send_command))
    application.add_handler(CommandHandler("addgroup", broadcast_bot.add_group_command))
    application.add_handler(CommandHandler("groups", broadcast_bot.groups_command))
    application.add_handler(CommandHandler("removegroup", broadcast_bot.remove_group_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_bot.handle_message))
    application.add_handler(CallbackQueryHandler(broadcast_bot.handle_confirmation))

    application.run_polling()

if __name__ == "__main__":
    main()
