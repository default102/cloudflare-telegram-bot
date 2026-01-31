from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from bot.config import settings
from bot.cf_api import cf
from loguru import logger
import math
from collections import Counter

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
            await update.effective_message.reply_text("⛔ 未授权访问")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

@restricted
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🌐 列出域名", callback_data="list_zones")]]
    await update.message.reply_text("👋 欢迎使用 Cloudflare DNS 机器人！\n点击下方按钮开始管理。", reply_markup=InlineKeyboardMarkup(keyboard))

@restricted
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "💡 **帮助信息**\n\n"
        "此机器人用于管理 Cloudflare DNS 记录。\n\n"
        "🕹 **常用操作**:\n"
        "- /start: 打开主菜单\n"
        "- /cancel: 取消当前的添加/编辑操作\n"
        "- **列表域名**: 查看账号下的所有域名\n"
        "- **点击记录**: 编辑 IP/CNAME，切换代理或删除\n\n"
        "🔒 仅限授权用户使用。"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def list_zones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("正在获取域名列表...")
    
    try:
        zones = await cf.get_zones()
        keyboard = []
        
        # Status Icon Mapping
        status_icons = {
            'active': '✅',
            'pending': '⏳',
            'initializing': '🔄',
            'moved': '⏩',
            'deleted': '❌',
            'deactivated': '🚫'
        }

        for zone in zones:
            icon = status_icons.get(zone.status, '🌐')
            keyboard.append([InlineKeyboardButton(f"{icon} {zone.name}", callback_data=f"zone_{zone.id}")])
        
        keyboard.append([InlineKeyboardButton("🔄 刷新列表", callback_data="list_zones")])
        await query.edit_message_text("📂 **选择要管理的域名**：\n(✅ 正常 | ⏳ 待验证 | 🚫以此类推)", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error listing zones: {e}")
        await query.edit_message_text(f"❌ 获取域名列表失败：{str(e)}")

# --- Level 1: List Record Types ---
async def show_record_types(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("正在获取记录统计...")
    
    # Handle entry from list_zones or back button
    if query.data.startswith("zone_"):
        zone_id = query.data.split("_")[1]
        context.user_data['current_zone_id'] = zone_id
    else:
        zone_id = context.user_data.get('current_zone_id')

    if not zone_id:
        await query.edit_message_text("❌ 会话已过期，请重新列出域名")
        return

    try:
        # Get zone details for name
        zone_info = await cf.get_zone_details(zone_id)
        
        # Fetch all records to count types
        records = await cf.get_dns_records(zone_id)
        
        # Count types
        type_counts = Counter([r.type for r in records])
        
        # Predefined common types + any others found
        common_types = ['A', 'CNAME', 'TXT', 'AAAA', 'MX', 'NS']
        # Merge discovered types
        all_types = sorted(list(set(common_types + list(type_counts.keys()))))
        
        keyboard = []
        row = []
        for t in all_types:
            count = type_counts.get(t, 0)
            # Only show types that have records, OR the common ones even if 0 (optional, let's show all common)
            # To keep it clean, maybe only show types with count > 0 OR strictly the common set.
            # User request: "A, AAAA, CNAME etc classification"
            
            # Let's show buttons for types that exist + common ones.
            # Button format: "A (5)" or "AAAA (0)"
            btn_text = f"{t} ({count})"
            row.append(InlineKeyboardButton(btn_text, callback_data=f"typeview_{t}"))
            
            if len(row) == 2: # 2 buttons per row
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
            
        # Add "Add Record" and "Back"
        keyboard.append([
            InlineKeyboardButton("➕ 添加记录", callback_data=f"add_{zone_id}"),
            InlineKeyboardButton("🔙 返回域名列表", callback_data="list_zones")
        ])
        
        await query.edit_message_text(
            f"📂 域名: `{zone_info.name}`\n👇 **请选择 DNS 记录类型**：", 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error listing types: {e}")
        await query.edit_message_text(f"❌ 获取失败：{str(e)}")

# --- Level 2: List Records by Type ---
async def list_records_by_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # callback: typeview_A
    record_type = query.data.split("_")[1]
    zone_id = context.user_data.get('current_zone_id')
    
    if not zone_id:
        await query.edit_message_text("❌ 会话已过期，请重新列出域名")
        return
    
    try:
        # Fetch zone details for simplification
        zone_info = await cf.get_zone_details(zone_id)
        zone_name = zone_info.name
        
        # Fetch records filtered by type
        records = await cf.get_dns_records(zone_id, type=record_type)
        
        keyboard = []
        for r in records:
            # Icons: ☁️ (Cloud/Proxy) vs 🔘 (Button/DNS Only)
            status_icon = "☁️" if r.proxied else "🔘"
            
            # Full Name (requested by user)
            display_name = r.name
            
            # Truncate if extremely long (Telegram button limit is generous but finite)
            # Typically 40 chars is safe for UI
            if len(display_name) > 40: 
                display_name = display_name[:38] + ".."
            
            # Layout: [Status] Name
            btn_text = f"{status_icon} {display_name}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"rec_{r.id}")])
        
        # Navigation
        keyboard.append([
            InlineKeyboardButton("🔙 返回分类", callback_data=f"zone_{zone_id}"), # Go back to type list
            InlineKeyboardButton("🔙 返回域名列表", callback_data="list_zones")
        ])
        
        await query.edit_message_text(
            f"📂 域名: `{zone_name}`\n📑 **{record_type} 记录列表** (共 {len(records)} 条)：", 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error listing records by type: {e}")
        await query.edit_message_text(f"❌ 获取记录失败：{str(e)}")

async def record_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    record_id = query.data.split("_")[1]
    zone_id = context.user_data.get('current_zone_id')

    if not zone_id:
        await query.edit_message_text("❌ 会话已过期，请重新列出域名")
        return
    
    try:
        r = await cf.get_dns_record_details(zone_id, record_id)
        proxied_status = "✅ 开启 (CDN 加速)" if r.proxied else "🚫 关闭 (仅 DNS)"
        
        details = (
            f"📝 **记录详情**\n"
            f"────────────────\n"
            f"🔹 **类型**: `{r.type}`\n"
            f"🏷 **名称**: `{r.name}`\n"
            f"🎯 **内容**: `{r.content}`\n"
            f"🐢 **TTL**: `{r.ttl if r.ttl != 1 else 'Auto'}`\n"
            f"☁️ **代理**: {proxied_status}\n"
            f"────────────────"
        )
        
        # Back button logic: Try to go back to the same type list if possible
        # For simplicity, we go back to the type list of this record's type
        
        keyboard = [
            [InlineKeyboardButton("✏️ 编辑内容", callback_data=f"editval_{record_id}"),
             InlineKeyboardButton("🔄 切换代理", callback_data=f"toggleproxy_{record_id}_{str(r.proxied).lower()}")],
            [InlineKeyboardButton("🗑️ 删除记录", callback_data=f"del_{record_id}")],
            [InlineKeyboardButton("🔙 返回列表", callback_data=f"typeview_{r.type}")] 
        ]
        
        await query.edit_message_text(details, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error fetching record details: {e}")
        await query.edit_message_text(f"❌ 错误：{str(e)}")

# --- Edit Flow ---
async def prompt_edit_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    record_id = query.data.split("_")[1]
    zone_id = context.user_data.get('current_zone_id')
    
    context.user_data['edit_zone_id'] = zone_id
    context.user_data['edit_record_id'] = record_id
    
    keyboard = [[InlineKeyboardButton("❌ 取消编辑", callback_data="cancel_conv")]]
    await query.message.reply_text(
        "👉 **请输入新的记录内容** (IP 或主机名)：\n\n您可以直接发送文字，或点击下方按钮取消。", 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return WAITING_FOR_CONTENT

async def save_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_content = update.message.text.strip()
    zone_id = context.user_data['edit_zone_id']
    record_id = context.user_data['edit_record_id']
    
    try:
        existing = await cf.get_dns_record_details(zone_id, record_id)
        update_data = {
            'type': existing.type,
            'name': existing.name,
            'content': new_content,
            'ttl': existing.ttl,
            'proxied': existing.proxied
        }
        await cf.update_dns_record(zone_id, record_id, update_data)
        await update.message.reply_text("✅ **记录更新成功！**", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ 更新失败：{str(e)}")
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /cancel command"""
    await update.message.reply_text("❌ 操作已取消")
    return ConversationHandler.END

async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles 'Cancel' button click during conversation"""
    query = update.callback_query
    await query.answer("已取消操作")
    await query.edit_message_text("❌ 操作已取消")
    return ConversationHandler.END

# --- Toggle Proxy ---
async def toggle_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split("_")
    record_id = parts[1]
    current_state = parts[2]
    zone_id = context.user_data.get('current_zone_id')

    current_proxied = current_state == 'true'
    new_proxied = not current_proxied

    try:
        existing = await cf.get_dns_record_details(zone_id, record_id)
        update_data = {
            'type': existing.type,
            'name': existing.name,
            'content': existing.content,
            'ttl': existing.ttl,
            'proxied': new_proxied
        }
        await cf.update_dns_record(zone_id, record_id, update_data)
        await query.answer(f"代理状态已更改为: {new_proxied}")
        await record_details(update, context)
    except Exception as e:
        await query.answer(f"操作失败：{str(e)}", show_alert=True)

# --- Delete Flow ---
async def delete_record_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    record_id = query.data.split("_")[1]
    
    keyboard = [
        [InlineKeyboardButton("⚠️ 确认删除", callback_data=f"confirmdel_{record_id}")],
        [InlineKeyboardButton("🔙 取消 (返回详情)", callback_data=f"rec_{record_id}")]
    ]
    
    warning_text = (
        "⚠️ **安全警告**\n"
        "────────────────\n"
        "您正在尝试 **删除** 此 DNS 解析记录。\n"
        "此操作不可撤销，可能会导致您的网站或服务无法访问。\n\n"
        "**确定要继续吗？**"
    )
    
    await query.edit_message_text(warning_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def delete_record_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    record_id = query.data.split("_")[1]
    zone_id = context.user_data.get('current_zone_id')
    
    try:
        # We need the record details to know which type list to go back to, 
        # but the record will be deleted.
        # So we default to going back to the MAIN category list (zone_id).
        await cf.delete_dns_record(zone_id, record_id)
        await query.answer("✅ 记录已成功删除", show_alert=True)
        
        # Return to Category List (show_record_types)
        # We need to simulate the "zone_{id}" data pattern or call the function directly
        # Re-using show_record_types requires context.user_data['current_zone_id'] which is set
        query.data = f"zone_{zone_id}" 
        await show_record_types(update, context)
        
    except Exception as e:
        await query.answer(f"❌ 删除失败：{str(e)}", show_alert=True)

# --- Add Record Flow ---
async def start_add_record(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['add_zone_id'] = query.data.split("_")[1]
    
    keyboard = [
        [InlineKeyboardButton("A", callback_data="type_A"), InlineKeyboardButton("CNAME", callback_data="type_CNAME")],
        [InlineKeyboardButton("TXT", callback_data="type_TXT"), InlineKeyboardButton("AAAA", callback_data="type_AAAA")],
        [InlineKeyboardButton("❌ 取消", callback_data="cancel_conv")]
    ]
    await query.edit_message_text("🆕 **选择要添加的记录类型**：", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return WAITING_FOR_RECORD_TYPE

async def receive_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    record_type = query.data.split("_")[1]
    context.user_data['add_record_type'] = record_type
    
    keyboard = [[InlineKeyboardButton("❌ 取消", callback_data="cancel_conv")]]
    await query.edit_message_text(
        f"已选择类型：`{record_type}`\n\n👉 请输入 **记录名称** (例如 `sub` 或 `@` 代表根域名)：", 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return WAITING_FOR_RECORD_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    context.user_data['add_record_name'] = name
    
    keyboard = [[InlineKeyboardButton("❌ 取消", callback_data="cancel_conv")]]
    await update.message.reply_text(
        f"名称已设置为 `{name}`。\n\n👉 请输入 **解析内容** (IP 或主机名)：", 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return WAITING_FOR_RECORD_CONTENT

async def receive_content_and_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    content = update.message.text.strip()
    zone_id = context.user_data['add_zone_id']
    
    data = {
        'type': context.user_data['add_record_type'],
        'name': context.user_data['add_record_name'],
        'content': content,
        'proxied': False
    }
    
    try:
        await cf.create_dns_record(zone_id, data)
        await update.message.reply_text("✅ **DNS 记录创建成功！**", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ 创建失败：{str(e)}")
        
    return ConversationHandler.END