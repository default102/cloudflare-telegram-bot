from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from bot.config import settings
from bot.cf_api import cf
from loguru import logger

# States for ConversationHandler
WAITING_FOR_CONTENT = 1
WAITING_FOR_RECORD_TYPE = 2
WAITING_FOR_RECORD_NAME = 3
WAITING_FOR_RECORD_CONTENT = 4

# Helper to check auth
def restricted(func):
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id != settings.allowed_user_id:
            await update.effective_message.reply_text("⛔ 未授权访问。")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

@restricted
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🌐 列出域名", callback_data="list_zones")]]
    await update.message.reply_text("👋 欢迎使用 Cloudflare DNS 机器人！", reply_markup=InlineKeyboardMarkup(keyboard))

async def list_zones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("正在获取域名列表...")
    
    try:
        zones = await cf.get_zones()
        keyboard = []
        for zone in zones:
            keyboard.append([InlineKeyboardButton(f"📂 {zone['name']}", callback_data=f"zone_{zone['id']}")])
        
        keyboard.append([InlineKeyboardButton("🔄 刷新", callback_data="list_zones")])
        await query.edit_message_text("请选择要管理的域名：", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Error listing zones: {e}")
        await query.edit_message_text(f"❌ 获取域名列表失败：{str(e)}")

async def list_records(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    zone_id = query.data.split("_")[1]
    # Save zone_id to context for "Add Record" flow
    context.user_data['current_zone_id'] = zone_id

    try:
        records = await cf.get_dns_records(zone_id)
        keyboard = []
        for r in records:
            # icon based on proxy status
            proxy_icon = "☁️" if r['proxied'] else "🛡️"
            btn_text = f"{r['type']} | {r['name']} | {proxy_icon}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"rec_{zone_id}_{r['id']}")])
        
        # Navigation
        keyboard.append([
            InlineKeyboardButton("➕ 添加记录", callback_data=f"add_{zone_id}"),
            InlineKeyboardButton("🔙 返回域名列表", callback_data="list_zones")
        ])
        
        await query.edit_message_text(f"域名的 DNS 记录：", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Error listing records: {e}")
        await query.edit_message_text(f"❌ 获取记录失败：{str(e)}")

async def record_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    _, zone_id, record_id = query.data.split("_")
    
    try:
        r = await cf.get_dns_record_details(zone_id, record_id)
        
        details = (
            f"**类型:** {r['type']}\n"
            f"**名称:** `{r['name']}`\n"
            f"**内容:** `{r['content']}`\n"
            f"**TTL:** {r['ttl']}\n"
            f"**代理:** {'是' if r['proxied'] else '否'}"
        )
        
        keyboard = [
            [InlineKeyboardButton("✏️ 编辑内容", callback_data=f"editval_{zone_id}_{record_id}")],
            [InlineKeyboardButton("🔄 切换代理状态", callback_data=f"toggleproxy_{zone_id}_{record_id}_{str(r['proxied']).lower()}")],
            [InlineKeyboardButton("🗑️ 删除", callback_data=f"del_{zone_id}_{record_id}")],
            [InlineKeyboardButton("🔙 返回", callback_data=f"zone_{zone_id}")]
        ]
        
        await query.edit_message_text(details, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error fetching record details: {e}")
        await query.edit_message_text(f"❌ 错误：{str(e)}")

# --- Edit Flow ---
async def prompt_edit_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, zone_id, record_id = query.data.split("_")
    
    context.user_data['edit_zone_id'] = zone_id
    context.user_data['edit_record_id'] = record_id
    
    await query.message.reply_text("👉 请输入新的内容 (IP 或主机名)：")
    return WAITING_FOR_CONTENT

async def save_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_content = update.message.text.strip()
    zone_id = context.user_data['edit_zone_id']
    record_id = context.user_data['edit_record_id']
    
    try:
        # We need to fetch the existing record to keep other fields (Name, Type) same
        # Cloudflare PUT requires all fields usually, or PATCH
        # Let's fetch first
        existing = await cf.get_dns_record_details(zone_id, record_id)
        
        update_data = {
            'type': existing['type'],
            'name': existing['name'],
            'content': new_content,
            'ttl': existing['ttl'],
            'proxied': existing['proxied']
        }
        
        await cf.update_dns_record(zone_id, record_id, update_data)
        await update.message.reply_text("✅ 记录更新成功！")
    except Exception as e:
        await update.message.reply_text(f"❌ 更新失败：{str(e)}")
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ 操作已取消。")
    return ConversationHandler.END

# --- Toggle Proxy ---
async def toggle_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, zone_id, record_id, current_state = query.data.split("_")
    current_proxied = current_state == 'true'
    new_proxied = not current_proxied

    try:
        existing = await cf.get_dns_record_details(zone_id, record_id)
        update_data = {
            'type': existing['type'],
            'name': existing['name'],
            'content': existing['content'],
            'ttl': existing['ttl'],
            'proxied': new_proxied
        }
        await cf.update_dns_record(zone_id, record_id, update_data)
        await query.answer(f"代理状态已更改为: {new_proxied}")
        
        # Refresh view
        await record_details(update, context)
        
    except Exception as e:
        await query.answer(f"操作失败：{str(e)}", show_alert=True)

# --- Delete Flow ---
async def delete_record_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, zone_id, record_id = query.data.split("_")
    
    keyboard = [
        [InlineKeyboardButton("✅ 确认删除", callback_data=f"confirmdel_{zone_id}_{record_id}")],
        [InlineKeyboardButton("❌ 取消", callback_data=f"rec_{zone_id}_{record_id}")]
    ]
    await query.edit_message_text("⚠️ 您确定要删除此记录吗？", reply_markup=InlineKeyboardMarkup(keyboard))

async def delete_record_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, zone_id, record_id = query.data.split("_")
    
    try:
        await cf.delete_dns_record(zone_id, record_id)
        await query.answer("记录已删除")
        # Go back to list
        query.data = f"zone_{zone_id}"
        await list_records(update, context)
    except Exception as e:
        await query.answer(f"删除失败：{str(e)}", show_alert=True)

# --- Add Record Flow ---
async def start_add_record(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['add_zone_id'] = query.data.split("_")[1]
    
    keyboard = [
        [InlineKeyboardButton("A", callback_data="type_A"), InlineKeyboardButton("CNAME", callback_data="type_CNAME")],
        [InlineKeyboardButton("TXT", callback_data="type_TXT"), InlineKeyboardButton("AAAA", callback_data="type_AAAA")]
    ]
    await query.edit_message_text("选择记录类型：", reply_markup=InlineKeyboardMarkup(keyboard))
    return WAITING_FOR_RECORD_TYPE

async def receive_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    record_type = query.data.split("_")[1]
    context.user_data['add_record_type'] = record_type
    
    await query.edit_message_text(f"""已选择类型：{record_type}
现在请输入 **名称** (例如 `sub` 或 `@` 代表根域名)：
""", parse_mode="Markdown")
    return WAITING_FOR_RECORD_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    context.user_data['add_record_name'] = name
    await update.message.reply_text(f"""名称已设置为 `{name}`。
现在请输入 **内容** (IP 或主机名)：
""", parse_mode="Markdown")
    return WAITING_FOR_RECORD_CONTENT

async def receive_content_and_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    content = update.message.text.strip()
    zone_id = context.user_data['add_zone_id']
    
    data = {
        'type': context.user_data['add_record_type'],
        'name': context.user_data['add_record_name'],
        'content': content,
        'proxied': False # Default to false for safety
    }
    
    try:
        await cf.create_dns_record(zone_id, data)
        await update.message.reply_text("✅ 记录创建成功！")
    except Exception as e:
        await update.message.reply_text(f"❌ 创建失败：{str(e)}")
        
    return ConversationHandler.END