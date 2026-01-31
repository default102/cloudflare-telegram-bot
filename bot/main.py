from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
from bot.config import settings
from bot import handlers
import logging

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def main():
    application = ApplicationBuilder().token(settings.tg_token).build()

    # Edit Conversation
    edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handlers.prompt_edit_content, pattern="^editval_")],
        states={
            handlers.WAITING_FOR_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.save_content)]
        },
        fallbacks=[CommandHandler("cancel", handlers.cancel)]
    )
    
    # Add Record Conversation
    add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handlers.start_add_record, pattern="^add_")],
        states={
            handlers.WAITING_FOR_RECORD_TYPE: [CallbackQueryHandler(handlers.receive_type, pattern="^type_")],
            handlers.WAITING_FOR_RECORD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.receive_name)],
            handlers.WAITING_FOR_RECORD_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.receive_content_and_create)]
        },
        fallbacks=[CommandHandler("cancel", handlers.cancel)]
    )

    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CallbackQueryHandler(handlers.list_zones, pattern="^list_zones$"))
    application.add_handler(CallbackQueryHandler(handlers.list_records, pattern="^zone_"))
    application.add_handler(CallbackQueryHandler(handlers.record_details, pattern="^rec_"))
    application.add_handler(CallbackQueryHandler(handlers.toggle_proxy, pattern="^toggleproxy_"))
    application.add_handler(CallbackQueryHandler(handlers.delete_record_confirm, pattern="^del_"))
    application.add_handler(CallbackQueryHandler(handlers.delete_record_execute, pattern="^confirmdel_"))
    
    application.add_handler(edit_conv)
    application.add_handler(add_conv)

    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
