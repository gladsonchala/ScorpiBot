import time
from collections import deque
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from utils import ScorpiAPI
from text_processor import TextManager
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Define your triggers here
TRIGGER_KEYWORDS = ["princess", "selene", "how are you", "joke", "fun", "guys", "jema"]

class PrincessSeleneBot:
    def __init__(self, token):
        self.application = ApplicationBuilder().token(token).build()
        self.last_update_id = None  # To keep track of the last processed update
        self.text_manager = TextManager()  # Initialize TextManager
        self.user_histories = {}  # Store message history for each user

        # Command Handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))

        # Message Handlers
        self.application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, self.group_message_handler))
        self.application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, self.private_message_handler))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        start_message = (
            "Hey there, cutie! I'm Princess Selene, your flirty, fun, and oh-so-cute chat buddy. 😘😂"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=start_message)
        logger.info(f"Sent start message to {update.effective_chat.id}")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_message = (
            "Here's what I can do:\n"
            "- Chat with you in a fun and flirty way.\n"
            "- Engage in playful and warm conversations with you!\n"
            "Just mention me in a group or chat with me privately to see my magic! ✨"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=help_message)
        logger.info(f"Sent help message to {update.effective_chat.id}")

    def store_message_history(self, user_id, message):
        """Store user messages and limit to 1000 characters and 1 hour."""
        current_time = time.time()
        if user_id not in self.user_histories:
            self.user_histories[user_id] = deque()
        
        # Add new message to the queue with the current timestamp
        self.user_histories[user_id].append((message, current_time))
        
        # Remove messages older than 1 hour
        while self.user_histories[user_id] and current_time - self.user_histories[user_id][0][1] > 3600:
            self.user_histories[user_id].popleft()

        # Remove old messages if the total character count exceeds 1000
        total_characters = sum(len(msg[0]) for msg in self.user_histories[user_id])
        while total_characters > 1000:
            removed_message = self.user_histories[user_id].popleft()
            total_characters -= len(removed_message[0])

    async def process_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, chat_type: str):
        if self.last_update_id and update.update_id <= self.last_update_id:
            return  # Skip processing if the message is older than the last processed one

        if not update.message:
            return  # Skip updates that are not messages

        user_message = update.message.text
        user_name = update.message.from_user.first_name
        user_username = update.message.from_user.username
        user_id = update.message.from_user.id
        message_id = update.message.message_id
        logger.debug(f"Received message from {user_name} (@{user_username}): {user_message} in {chat_type}")

        # Store the message in history
        self.store_message_history(user_id, user_message)

        try:
            # Prepare full chat history for translation
            full_history = ' '.join(msg[0] for msg in self.user_histories[user_id])
            
            # Translate both the chat history and recent message to English
            translated_history, history_lang_code = self.text_manager.detect_and_translate_to_english(full_history)
            translated_message, _ = self.text_manager.detect_and_translate_to_english(user_message)

            logger.debug(f"Translated history: {translated_history}")
            logger.debug(f"Translated recent message: {translated_message}")

            # If it's a reply, get the name, ID, and username of the person who replied to the bot
            if update.message.reply_to_message:
                replied_user_name = update.message.reply_to_message.from_user.first_name
                replied_user_username = update.message.reply_to_message.from_user.username
                replied_user_id = update.message.reply_to_message.from_user.id
                # Concatenate user info with the message
                translated_message = f"{translated_message} (Reply from {replied_user_name} (@{replied_user_username}), ID: {replied_user_id})"
                logger.debug(f"Modified message with replied user info: {translated_message}")

            # Prepare final message with user details
            final_message = f"User {user_name} (@{user_username}, ID: {user_id}): {translated_message}"

            # Make the API call with the translated history and message
            api_response = ScorpiAPI.get_response(f"Our Last Chat(used for to remember): {translated_history}\n\nMy new Message: {final_message}")
            logger.debug(f"API response data: {api_response}")

            # Translate the response back to the original language
            reply_text = self.text_manager.translate_from_english(api_response, history_lang_code)
            logger.debug(f"Translated API response to original language ({history_lang_code}): {reply_text}")

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=reply_text,
                reply_to_message_id=message_id  # Reply to the original message
            )
            logger.info(f"Sent response to {update.effective_chat.id} in reply to message {message_id}")
        except Exception as e:
            logger.error(f"Error in process_message: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Oops! Something went wrong. 😅",
                reply_to_message_id=message_id
            )

        self.last_update_id = update.update_id  # Update the last processed update ID

    async def group_message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_message = update.message.text.lower()
        bot_username = context.bot.username

        # Check if the message contains any trigger keywords, mentions the bot, or is a reply to the bot
        if any(keyword in user_message for keyword in TRIGGER_KEYWORDS) or \
           f"@{bot_username}" in user_message or \
           (update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id):
            await self.process_message(update, context, "group")

    async def private_message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.process_message(update, context, "private")

    def run(self):
        logger.info("Starting Princess Selene...")
        self.application.run_polling()
