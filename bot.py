import logging
from telegram import Update
from telegram.ext import filters, ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler
from gpt import GPTClient

class Bot:
  def __init__(self, gpt: GPTClient, chat_id: str|None):
    self.__gpt = gpt
    self.__chat_id = chat_id

  def run(self, token: str):
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler('start', self.__start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.__reply))
    app.add_handler(CommandHandler('new', self.__new_conversation))

    app.run_polling()

  async def __start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
      logging.warning(f"Start command received but ignored because it doesn't have a chat")
      return

    if not self.__check_chat(update.effective_chat.id):
      return

    await context.bot.send_message(chat_id=update.effective_chat.id, text="Start by sending me a message!")

    logging.info(f"Start command executed for chat {update.effective_chat.id}")

  async def __reply(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
      logging.warning(f"Reply command received but ignored because it doesn't have a chat")
      return

    if not self.__check_chat(update.effective_chat.id):
      return

    if not update.message or not update.message.text:
      return

    message = await context.bot.send_message(chat_id=update.effective_chat.id, text="Generating response...")

    text = self.__gpt.complete(update.effective_chat.id, update.message.text)

    await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=message.message_id, text=text)

    logging.info(f"Replied chat {update.effective_chat.id} with text '{text}'")

  async def __new_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
      logging.warning(f"New command received but ignored because it doesn't have a chat")
      return

    if not self.__check_chat(update.effective_chat.id):
      return

    self.__gpt.clear(update.effective_chat.id)

    await context.bot.send_message(chat_id=update.effective_chat.id, text="Starting a new conversation.")

    logging.info(f"Started a new conversation for chat {update.effective_chat.id}")

  def __check_chat(self, chat_id: int):
    if self.__chat_id and chat_id != self.__chat_id:
      logging.info(f"Message received for chat {chat_id} but ignored because it's not the configured chat")
      return False

    return True
