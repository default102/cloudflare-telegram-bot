from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters, Application
from telegram.error import InvalidToken
from telegram import BotCommand
from bot.config import settings
from bot import handlers
import logging
import sys

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def post_init(application: Application):
    """Set up the bot's menu commands."""
    commands = [
        BotCommand("start", "🏠 主菜单 / 刷新"),
        BotCommand("help", "💡 帮助信息"),
        BotCommand("cancel", "❌ 取消当前操作"),
    ]
    await application.bot.set_my_commands(commands)

def main():
    # 1. Print Startup Info
    logger.info("🚀 Starting Cloudflare DNS Bot...")
    logger.info(f"👤 Allowed User ID: {settings.allowed_user_id}")
    
    # Mask tokens for safety in logs
    masked_tg = settings.tg_token[:5] + "..." + settings.tg_token[-5:] if settings.tg_token and len(settings.tg_token) > 10 else "INVALID"
    masked_cf = settings.cf_api_token[:5] + "..." + settings.cf_api_token[-5:] if settings.cf_api_token and len(settings.cf_api_token) > 10 else "INVALID"
    
    logger.info(f"🔑 TG Token: {masked_tg}")
    logger.info(f"☁️ CF Token: {masked_cf}")

    try:
        application = ApplicationBuilder().token(settings.tg_token).post_init(post_init).build()
    except InvalidToken:
        logger.error("❌ Fatal Error: Invalid Telegram Bot Token. Please check your TG_TOKEN environment variable.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Fatal Error initializing bot: {e}")
        sys.exit(1)

    # Edit Conversation
    edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handlers.prompt_edit_content, pattern="^editval_")],
        states={
            handlers.WAITING_FOR_CONTENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.save_content),
                CallbackQueryHandler(handlers.cancel_callback, pattern="^cancel_conv$")
            ]
        },
        fallbacks=[CommandHandler("cancel", handlers.cancel), CallbackQueryHandler(handlers.cancel_callback, pattern="^cancel_conv$")]
    )
    
    # Add Record Conversation
    add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handlers.start_add_record, pattern="^add_")],
        states={
            handlers.WAITING_FOR_RECORD_TYPE: [
                CallbackQueryHandler(handlers.receive_type, pattern="^type_"),
                CallbackQueryHandler(handlers.cancel_callback, pattern="^cancel_conv$")
            ],
            handlers.WAITING_FOR_RECORD_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.receive_name),
                CallbackQueryHandler(handlers.cancel_callback, pattern="^cancel_conv$")
            ],
            handlers.WAITING_FOR_RECORD_CONTENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.receive_content_and_create),
                CallbackQueryHandler(handlers.cancel_callback, pattern="^cancel_conv$")
            ]
        },
        fallbacks=[CommandHandler("cancel", handlers.cancel), CallbackQueryHandler(handlers.cancel_callback, pattern="^cancel_conv$")]
    )

    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("help", handlers.help_command))
    application.add_handler(CallbackQueryHandler(handlers.list_zones, pattern="^list_zones$"))
    
    # Refactored Handlers
    # 1. Clicking a zone -> Show Record Types
    application.add_handler(CallbackQueryHandler(handlers.show_record_types, pattern="^zone_"))
    # 2. Clicking a type -> List records of that type
    application.add_handler(CallbackQueryHandler(handlers.list_records_by_type, pattern="^typeview_"))
    
    application.add_handler(CallbackQueryHandler(handlers.record_details, pattern="^rec_"))
    application.add_handler(CallbackQueryHandler(handlers.toggle_proxy, pattern="^toggleproxy_"))
    application.add_handler(CallbackQueryHandler(handlers.delete_record_confirm, pattern="^del_"))
    application.add_handler(CallbackQueryHandler(handlers.delete_record_execute, pattern="^confirmdel_"))
    
    application.add_handler(edit_conv)
    application.add_handler(add_conv)

    logger.info("✅ Bot is running and polling for updates...")
    
    try:
        application.run_polling()
    except Exception as e:
        logger.error(f"❌ Runtime Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"❌ Unhandled Exception: {e}")
        sys.exit(1)
