# -*- coding: utf-8 -*-
import os
import json
import re
import feedparser
from typing import Dict, Any, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)
from telegram.error import Forbidden, BadRequest

# ----------------------------
# Settings & Environment
# ----------------------------
TOKEN = os.getenv("BOT_TOKEN", "8317257722:AAGu4jMVN4rxLLNKS18xxl8C-k_YwIKdZYk")
OWNER_ID = 6648914734  # الـ User ID الرقمي للمالك

DATA_DIR = "bot_data"
os.makedirs(DATA_DIR, exist_ok=True)

MESSAGES_FILE = os.path.join(DATA_DIR, "messages.json")
CHANNELS_FILE = os.path.join(DATA_DIR, "channels.json")
ADMINS_FILE = os.path.join(DATA_DIR, "admins.json")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
FOLDERS_FILE = os.path.join(DATA_DIR, "folders.json")
YT_CHANNELS_FILE = os.path.join(DATA_DIR, "yt_channels.json")

def load_json(path: str, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default

def save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_messages() -> Dict[str, Any]:
    return load_json(MESSAGES_FILE, {})

def set_messages(d: Dict[str, Any]):
    save_json(MESSAGES_FILE, d)

def get_channels() -> Dict[str, Any]:
    return load_json(CHANNELS_FILE, {})

def set_channels(d: Dict[str, Any]):
    save_json(CHANNELS_FILE, d)

def get_admins() -> Dict[str, Any]:
    admins = load_json(ADMINS_FILE, {})
    admins.setdefault(str(OWNER_ID), {
        "create": True, "add_channels": True, "view_messages": True, "manage_admins": True
    })
    save_json(ADMINS_FILE, admins)
    return admins

def set_admins(d: Dict[str, Any]):
    save_json(ADMINS_FILE, d)

def get_state() -> Dict[str, Any]:
    return load_json(STATE_FILE, {})

def set_state(d: Dict[str, Any]):
    save_json(STATE_FILE, d)

def get_folders() -> Dict[str, Any]:
    return load_json(FOLDERS_FILE, {})

def set_folders(d: Dict[str, Any]):
    save_json(FOLDERS_FILE, d)

def load_yt_channels():
    return load_json(YT_CHANNELS_FILE, {})

def save_yt_channels(data):
    save_json(YT_CHANNELS_FILE, data)

# ----------------------------
# Permissions & Helpers
# ----------------------------
def is_owner(uid: int) -> bool:
    return uid == OWNER_ID or uid in [6648914734]

def has_perm(uid: int, perm: str) -> bool:
    if is_owner(uid):
        return True
    admins = get_admins()
    return bool(admins.get(str(uid), {}).get(perm))

def sanitize_channel_username(text: str) -> Optional[str]:
    if re.fullmatch(r"@[\w_]{5,}", text):
        return text
    if re.fullmatch(r"-100\d{10,}", text):
        return text
    return None

def pagination(page: int, total_pages: int, prefix: str) -> List[List[InlineKeyboardButton]]:
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("« السابق", callback_data=f"{prefix}:page:{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("التالي »", callback_data=f"{prefix}:page:{page+1}"))
    return [nav] if nav else []

# ----------------------------
# /start and /help
# ----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "مرحبا بك في بوت ريسبكت لايف، يرجى العلم بان اوامر البوت لن تعمل معك الا بموافقة من مالك البوت أو المطورين."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ الأوامر المتاحة:\n"
        "• /massage لإنشاء الرسالة\n"
        "• /send للإرسال\n"
        "• /folder لإدارة المجلدات\n"
        "• /add للإضافة\n"
        "• /search لجلب وتصفح فيديوهات اليوتيوب"
    )

# ----------------------------
# Folder management
# ----------------------------
async def folder_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id) and not has_perm(update.effective_user.id, "create"):
        return
    kb = [
        [InlineKeyboardButton("➕ اضافة مجلد جديد", callback_data="folder:add")],
        [InlineKeyboardButton("🗑 حذف مجلد محدد", callback_data="folder:delete")],
        [InlineKeyboardButton("📂 عرض جميع المجلدات", callback_data="folder:list")]
    ]
    await update.message.reply_text("اضغط على الاجراء المناسب:", reply_markup=InlineKeyboardMarkup(kb))

async def folder_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q: CallbackQuery = update.callback_query
    await q.answer()
    data = q.data or ""
    folders = get_folders()

    if data == "folder:add":
        await q.edit_message_text("اكتب اسم المجلد الجديد:")
        context.user_data["folder_action"] = "add"
        return

    if data == "folder:delete":
        if not folders:
            await q.edit_message_text("لا توجد مجلدات حالياً.")
            return
        kb = [[InlineKeyboardButton(fname, callback_data=f"folder:remove:{fname}")] for fname in folders.keys()]
        await q.edit_message_text("حدد المجلد للحذف:", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data.startswith("folder:remove:"):
        fname = data.split(":", 2)[2]
        if fname in folders:
            folders.pop(fname, None)
            set_folders(folders)
            await q.edit_message_text(f"🗑 تم حذف المجلد: {fname}")
        else:
            await q.edit_message_text("⚠️ المجلد غير موجود.")
        return

    if data == "folder:list":
        if not folders:
            await q.edit_message_text("📭 لا توجد مجلدات.")
            return
        kb = [[InlineKeyboardButton(fname, callback_data=f"folder:view:{fname}")] for fname in folders.keys()]
        await q.edit_message_text("📂 المجلدات:", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data.startswith("folder:view:"):
        fname = data.split(":", 2)[2]
        if fname not in folders or not folders.get(fname):
            await q.edit_message_text("📭 المجلد فارغ.")
            return
        lines = [f"📂 محتوى {fname}:"]
        for mid, msg in folders[fname].items():
            lines.append(f"- #{mid} — {msg.get('title','(بدون عنوان)')}")
        await q.edit_message_text("\n".join(lines))
        return

async def folder_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("folder_action") != "add":
        return
    fname = (update.message.text or "").strip()
    folders = get_folders()
    if not fname:
        await update.message.reply_text("⚠️ اسم المجلد لا يمكن أن يكون فارغاً.")
    elif fname in folders:
        await update.message.reply_text("⚠️ المجلد موجود مسبقاً.")
    else:
        folders[fname] = {}
        set_folders(folders)
        await update.message.reply_text(f"✅ تم إنشاء المجلد: {fname}")
    context.user_data.pop("folder_action", None)

# ----------------------------
# /massage Conversation
# ----------------------------
MASSAGE_TITLE, MASSAGE_PHOTO, MASSAGE_BT, MASSAGE_URL, MASSAGE_PREVIEW = range(5)

async def massage_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_perm(update.effective_user.id, "create"):
        await update.message.reply_text("❌ لا تملك صلاحية إنشاء الرسائل.")
        return ConversationHandler.END
    context.user_data["new_msg"] = {}
    await update.message.reply_text("📌 اكتب عنوان الرسالة:")
    return MASSAGE_TITLE

async def massage_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("⚠️ العنوان فارغ. أعد الكتابة:")
        return MASSAGE_TITLE
    context.user_data["new_msg"]["title"] = text
    await update.message.reply_text("📷 أرسل الصورة:")
    return MASSAGE_PHOTO

async def massage_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("⚠️ أرسل صورة وليس نصاً.")
        return MASSAGE_PHOTO
    context.user_data["new_msg"]["photo"] = update.message.photo[-1].file_id
    await update.message.reply_text("📝 اكتب نص الزر:")
    return MASSAGE_BT

async def massage_bt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("⚠️ نص الزر فارغ. أعد الكتابة:")
        return MASSAGE_BT
    context.user_data["new_msg"]["button_text"] = text
    await update.message.reply_text("🔗 أرسل رابط الزر (http/https):")
    return MASSAGE_URL

async def massage_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = (update.message.text or "").strip()
    if not re.match(r"^https?://", url):
        await update.message.reply_text("⚠️ الرابط يجب أن يبدأ بـ http أو https:")
        return MASSAGE_URL
    context.user_data["new_msg"]["button_url"] = url
    msg = context.user_data["new_msg"]
    kb = [
        [
            InlineKeyboardButton("⏳ حفظ", callback_data="massage:save"),
            InlineKeyboardButton("📂 لمجلد", callback_data="massage:folder"),
            InlineKeyboardButton("❌ إلغاء", callback_data="massage:cancel"),
        ]
    ]
    await update.message.reply_photo(
        photo=msg["photo"],
        caption=f"*{msg['title']}*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return MASSAGE_PREVIEW

async def massage_preview_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q: CallbackQuery = update.callback_query
    await q.answer()
    data = q.data or ""
    msg = context.user_data.get("new_msg", {})

    if data == "massage:cancel":
        try:
            await q.edit_message_caption("❌ تم الإلغاء.")
        except Exception:
            pass
        context.user_data.pop("new_msg", None)
        return ConversationHandler.END

    if data == "massage:save":
        messages = get_messages()
        numeric_ids = [int(i) for i in messages.keys() if str(i).isdigit()] if messages else []
        new_id = str((max(numeric_ids) if numeric_ids else 0) + 1)
        messages[new_id] = msg
        set_messages(messages)
        try:
            await q.edit_message_caption(f"✅ تم حفظ الرسالة العامة برقم: {new_id}")
        except Exception:
            pass
        context.user_data.pop("new_msg", None)
        return ConversationHandler.END

    if data == "massage:folder":
        folders = get_folders()
        if not folders:
            await q.message.reply_text("📭 لا توجد مجلدات.")
            return MASSAGE_PREVIEW
        kb = [[InlineKeyboardButton(fname, callback_data=f"massage:addto:{fname}")] for fname in folders.keys()]
        await q.message.reply_text("اختر المجلد:", reply_markup=InlineKeyboardMarkup(kb))
        return MASSAGE_PREVIEW

    if data.startswith("massage:addto:"):
        folder = data.split(":", 2)[2]
        folders = get_folders()
        if folder not in folders:
            await q.message.reply_text("⚠️ المجلد غير موجود.")
            return MASSAGE_PREVIEW
        folder_msgs = folders.get(folder, {})
        numeric_ids = [int(i) for i in folder_msgs.keys() if str(i).isdigit()] if folder_msgs else []
        msg_id = str((max(numeric_ids) if numeric_ids else 0) + 1)
        folders[folder][msg_id] = msg
        set_folders(folders)
        try:
            await q.edit_message_caption(f"✅ تم الحفظ داخل المجلد: {folder} (#{msg_id})")
        except Exception:
            pass
        context.user_data.pop("new_msg", None)
        return ConversationHandler.END

# ----------------------------
# Channel Management
# ----------------------------
async def add_channel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not has_perm(uid, "add_channels"):
        await update.message.reply_text("❌ لا تملك صلاحية إضافة القنوات.")
        return
    if not context.args:
        await update.message.reply_text("الصيغة الصحيحة:\n/add @username أو آيدي (-100...)")
        return
    
    # التحقق هل هي إضافة يوتيوب أم قناة إرسال عادية
    if len(context.args) >= 3:
        # يوتيوب: /add اسم channel_id النص
        if not is_owner(uid):
            return await update.message.reply_text("❌ غير مسموح لك")
        try:
            name = context.args[0]
            channel_id = context.args[1]
            text = " ".join(context.args[2:])
            yt_channels = load_yt_channels()
            yt_channels[name] = {"id": channel_id, "text": text}
            save_yt_channels(yt_channels)
            await update.message.reply_text(f"✔ تمت إضافة قناة اليوتيوب: {name}")
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ: {e}")
        return

    # قناة تيليجرام عادية
    ch = sanitize_channel_username(context.args[0])
    if not ch:
        await update.message.reply_text("⚠️ صيغة القناة غير صحيحة.")
        return

    channels = get_channels()
    channels[ch] = {"active": True}
    set_channels(channels)
    try:
        await context.bot.send_message(chat_id=ch, text="✅ تم ربط القناة بنجاح.")
        await update.message.reply_text(f"✅ تم حفظ القناة: {ch}")
    except Exception as e:
        await update.message.reply_text(f"❌ تأكد أن البوت مشرف بالصلاحيات الكافية في القناة. الخطأ: {e}")

async def list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channels = get_channels()
    if not channels:
        await update.message.reply_text("📭 لا توجد قنوات محفوظة.")
        return
    items = list(channels.items())
    page = 0
    page_size = 5
    total_pages = (len(items) + page_size - 1) // page_size
    view = items[page*page_size:(page+1)*page_size]

    lines = [f"📺 القنوات ({len(items)}):"]
    kb = []
    for ch, meta in view:
        status = "مفعّلة ✅" if meta.get("active") else "موقوفة ⛔"
        lines.append(f"- {ch} — {status}")
        kb.append([InlineKeyboardButton("⛔ إيقاف" if meta.get("active") else "✅ تفعيل", callback_data=f"channels:toggle:{ch}")])

    kb += pagination(page, total_pages, "channels")
    await update.message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(kb))

async def channels_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q: CallbackQuery = update.callback_query
    await q.answer()
    data = q.data or ""
    parts = data.split(":", 2)
    if len(parts) < 2:
        return
    action = parts[1]

    if action == "toggle":
        ch = parts[2] if len(parts) >= 3 else ""
        channels = get_channels()
        if ch in channels:
            channels[ch]["active"] = not channels[ch].get("active", True)
            set_channels(channels)
            await q.edit_message_text(f"🔄 حالة القناة {ch}: {'مفعّلة ✅' if channels[ch]['active'] else 'موقوفة ⛔'}")
        else:
            await q.edit_message_text("⚠️ القناة غير موجودة.")
        return

    if action == "page":
        try:
            page = int(parts[2]) if len(parts) >= 3 else 0
        except Exception:
            page = 0
        channels = get_channels()
        items = list(channels.items())
        page_size = 5
        total_pages = (len(items) + page_size - 1) // page_size if items else 1
        view = items[page*page_size:(page+1)*page_size]
        lines = [f"📺 القنوات ({len(items)}): صفحة {page+1}/{total_pages}"]
        kb = []
        for ch, meta in view:
            status = "مفعّلة ✅" if meta.get("active") else "موقوفة ⛔"
            lines.append(f"- {ch} — {status}")
            kb.append([InlineKeyboardButton("⛔ إيقاف" if meta.get("active") else "✅ تفعيل", callback_data=f"channels:toggle:{ch}")])
        kb += pagination(page, total_pages, "channels")
        await q.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(kb))
        return

# ----------------------------
# Sending Messages
# ----------------------------
async def send_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_perm(update.effective_user.id, "view_messages"):
        await update.message.reply_text("❌ لا تملك صلاحية رؤية/إرسال الرسائل.")
        return
    kb = [
        [InlineKeyboardButton("🗂 الرسائل العامة", callback_data="send:source:general")],
        [InlineKeyboardButton("📂 من مجلد", callback_data="send:source:folder")],
    ]
    await update.message.reply_text("اختر مصدر الرسائل:", reply_markup=InlineKeyboardMarkup(kb))

async def render_messages_list(owner, context: ContextTypes.DEFAULT_TYPE, items: List, source_key: str, page: int = 0):
    page_size = 4
    total_pages = (len(items) + page_size - 1) // page_size if items else 1
    view = items[page*page_size:(page+1)*page_size]
    lines = [f"🗂 الرسائل ({len(items)}) — صفحة {page+1}/{total_pages}"]
    kb: List[List[InlineKeyboardButton]] = []

    for msg_id, msg in view:
        lines.append(f"- #{msg_id} — {msg.get('title','(بدون عنوان)')}")
        kb.append([
            InlineKeyboardButton("👁 معاينة", callback_data=f"send:{source_key}:preview:{msg_id}"),
            InlineKeyboardButton("🗑 حذف", callback_data=f"send:{source_key}:delete:{msg_id}"),
        ])
        kb.append([
            InlineKeyboardButton("📤 إرسال لقناة", callback_data=f"send:{source_key}:choosech:{msg_id}"),
            InlineKeyboardButton("📢 للجميع", callback_data=f"send:{source_key}:all:{msg_id}"),
        ])

    kb += pagination(page, total_pages, f"send:{source_key}")
    if hasattr(owner, "data"):
        try:
            await owner.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(kb))
        except BadRequest:
            await owner.message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(kb))
    else:
        await owner.message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(kb))

async def send_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q: CallbackQuery = update.callback_query
    await q.answer()
    data = q.data or ""

    if data.startswith("send:source:"):
        src = data.split(":", 2)[2]
        if src == "general":
            messages = get_messages()
            if not messages:
                await q.edit_message_text("📭 لا توجد رسائل عامة.")
                return
            await render_messages_list(q, context, list(messages.items()), "general", page=0)
            return
        if src == "folder":
            folders = get_folders()
            if not folders:
                await q.edit_message_text("📭 لا توجد مجلدات.")
                return
            kb = [[InlineKeyboardButton(fname, callback_data=f"send:choosefolder:{fname}")] for fname in folders.keys()]
            await q.edit_message_text("اختر مجلد:", reply_markup=InlineKeyboardMarkup(kb))
            return

    if data.startswith("send:choosefolder:"):
        folder = data.split(":", 2)[2]
        folders = get_folders()
        if folder not in folders or not folders[folder]:
            await q.edit_message_text("📭 هذا المجلد فارغ.")
            return
        state = get_state()
        state[f"current_folder:{q.from_user.id}"] = folder
        set_state(state)
        await render_messages_list(q, context, list(folders[folder].items()), "folder", page=0)
        return

    if data.startswith("send:") and ":page:" in data:
        parts = data.split(":")
        if len(parts) >= 4 and parts[2] == "page":
            source_key = parts[1]
            try:
                page = int(parts[3])
            except Exception:
                page = 0
            if source_key == "general":
                messages = get_messages()
                await render_messages_list(q, context, list(messages.items()), "general", page)
                return
            else:
                state = get_state()
                folder = state.get(f"current_folder:{q.from_user.id}")
                folders = get_folders()
                if not folder or folder not in folders:
                    await q.edit_message_text("⚠️ المجلد غير محدد.")
                    return
                await render_messages_list(q, context, list(folders[folder].items()), "folder", page)
                return

    parts = data.split(":")
    if len(parts) >= 4 and parts[0] == "send":
        source_key = parts[1]
        action = parts[2]
        msg_id = parts[3]

        if source_key == "general":
            messages = get_messages()
            msg = messages.get(msg_id)
        else:
            state = get_state()
            folder = state.get(f"current_folder:{q.from_user.id}")
            folders = get_folders()
            msg = folders.get(folder, {}).get(msg_id)

        if not msg:
            await q.edit_message_text("⚠️ الرسالة غير موجودة.")
            return

        if action == "preview":
            kb = [[InlineKeyboardButton(msg["button_text"], url=msg["button_url"])]]
            try:
                await q.message.reply_photo(photo=msg["photo"], caption=f"*{msg['title']}*", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))
                await q.edit_message_text(f"✅ تمت المعاينة للرسالة #{msg_id}.")
            except Exception:
                pass
            return

        if action == "delete":
            if source_key == "general":
                messages = get_messages()
                messages.pop(msg_id, None)
                set_messages(messages)
                await q.edit_message_text(f"🗑 تم حذف الرسالة العامة #{msg_id}.")
                await render_messages_list(q, context, list(messages.items()), "general", page=0)
            else:
                state = get_state()
                folder = state.get(f"current_folder:{q.from_user.id}")
                folders = get_folders()
                if folder in folders:
                    folders[folder].pop(msg_id, None)
                    set_folders(folders)
                await q.edit_message_text(f"🗑 تم حذف الرسالة #{msg_id} من مجلد {folder}.")
                await render_messages_list(q, context, list(folders.get(folder, {}).items()), "folder", page=0)
            return

        if action == "choosech":
            channels = get_channels()
            active = [ch for ch, meta in channels.items() if meta.get("active")]
            if not active:
                await q.edit_message_text("⚠️ لا توجد قنوات مفعّلة.")
                return
            kb_full = [[InlineKeyboardButton(ch, callback_data=f"send:{source_key}:to:{msg_id}:{ch}")] for ch in active]
            await q.edit_message_text(f"اختر قناة لإرسال الرسالة #{msg_id}:", reply_markup=InlineKeyboardMarkup(kb_full))
            return

        if action == "all":
            channels = get_channels()
            active = [ch for ch, meta in channels.items() if meta.get("active")]
            if not active:
                await q.edit_message_text("⚠️ لا توجد قنوات مفعّلة.")
                return
            kb = [[InlineKeyboardButton(msg["button_text"], url=msg["button_url"])]]
            ok, fail = 0, 0
            for ch in active:
                try:
                    await context.bot.send_photo(chat_id=ch, photo=msg["photo"], caption=f"*{msg['title']}*", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))
                    ok += 1
                except Exception:
                    fail += 1
            await q.edit_message_text(f"📢 أُرسلت الرسالة #{msg_id} — نجاح: {ok} | فشل: {fail}")
            return

        if action == "to":
            ch = ":".join(parts[4:]) if len(parts) >= 5 else ""
            kb = [[InlineKeyboardButton(msg["button_text"], url=msg["button_url"])]]
            try:
                await context.bot.send_photo(chat_id=ch, photo=msg["photo"], caption=f"*{msg['title']}*", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))
                await q.edit_message_text(f"📤 تم إرسال الرسالة #{msg_id} إلى {ch}.")
            except Exception as e:
                await q.edit_message_text(f"❌ فشل الإرسال إلى {ch}: {e}")
            return

# ----------------------------
# Admins Management
# ----------------------------
async def admin_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not has_perm(uid, "manage_admins"):
        await update.message.reply_text("❌ لا تملك صلاحية إدارة الأدمن.")
        return
    if not context.args:
        await update.message.reply_text("اكتب المعرف الرقمي: /admin 123456789")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("⚠️ يجب إدخال رقم صحيح.")
        return

    admins = get_admins()
    admins.setdefault(str(target_id), {
        "create": True, "add_channels": True, "view_messages": True, "manage_admins": False
    })
    set_admins(admins)
    await update.message.reply_text(f"✅ تم إضافة {target_id} كأدمن.")

async def admins_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not has_perm(uid, "manage_admins"):
        await update.message.reply_text("❌ لا تملك صلاحية إدارة الأدمن.")
        return
    admins = get_admins()
    items = list(admins.items())
    lines = ["👥 قائمة الأدمن:"]
    kb = []
    for auid, perms in items:
        owner_tag = " (المالك)" if int(auid) == OWNER_ID else ""
        lines.append(f"- {auid}{owner_tag}: {perms}")
        kb.append([
            InlineKeyboardButton("إنشاء ✅" if perms.get("create") else "إنشاء ⛔", callback_data=f"admins:toggle:{auid}:create"),
            InlineKeyboardButton("قنوات ✅" if perms.get("add_channels") else "قنوات ⛔", callback_data=f"admins:toggle:{auid}:add_channels"),
        ])
        kb.append([
            InlineKeyboardButton("رؤية ✅" if perms.get("view_messages") else "رؤية ⛔", callback_data=f"admins:toggle:{auid}:view_messages"),
            InlineKeyboardButton("إدارة ✅" if perms.get("manage_admins") else "إدارة ⛔", callback_data=f"admins:toggle:{auid}:manage_admins"),
        ])
        if int(auid) != OWNER_ID:
            kb.append([InlineKeyboardButton("🗑 إزالة الأدمن", callback_data=f"admins:remove:{auid}")])
        kb.append([InlineKeyboardButton("— — —", callback_data="noop")])
    await update.message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(kb))

async def admins_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q: CallbackQuery = update.callback_query
    await q.answer()
    data = q.data or ""
    parts = data.split(":")
    if len(parts) < 2:
        return
    action = parts[1]

    if action == "toggle" and len(parts) >= 4:
        auid, perm = parts[2], parts[3]
        admins = get_admins()
        if auid not in admins:
            return
        if int(auid) == OWNER_ID and perm == "manage_admins":
            return
        admins[auid][perm] = not admins[auid].get(perm, False)
        set_admins(admins)
        await q.edit_message_text("🔄 تم تعديل الصلاحيات.")
        return

    if action == "remove" and len(parts) >= 3:
        auid = parts[2]
        if int(auid) == OWNER_ID:
            return
        admins = get_admins()
        admins.pop(auid, None)
        set_admins(admins)
        await q.edit_message_text(f"🗑 تم إزالة {auid}.")
        return

# ----------------------------
# YouTube Feature Integration
# ----------------------------
def get_latest_video(channel_id):
    try:
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        feed = feedparser.parse(url)
        if not feed.entries:
            return None, None, None
        entry = feed.entries[0]
        video_id = entry.yt_videoid
        title = entry.title
        video_url = entry.link
        thumbnail = None
        if "media_thumbnail" in entry:
            thumbnail = entry.media_thumbnail[0]["url"]
        elif "media_content" in entry:
            thumbnail = entry.media_content[0]["url"]
        else:
            thumbnail = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
        return title, video_url, thumbnail
    except Exception:
        return None, None, None

async def yt_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return await update.message.reply_text("❌ غير مسموح لك")
    channels = load_yt_channels()
    if not channels:
        return await update.message.reply_text("❌ لا توجد قنوات يوتيوب مضافة. استخدم /add لإضافة قناة مع آيدي القناة والنص.")
    keyboard = [[InlineKeyboardButton(name, callback_data=f"ytshow|{name}")] for name in channels]
    await update.message.reply_text("اختر قناة يوتيوب:", reply_markup=InlineKeyboardMarkup(keyboard))

async def yt_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    
    if not ("|" in data and (data.startswith("ytshow") or data.startswith("ytsend") or data.startswith("ytsendto"))):
        return

    parts = data.split("|")
    action = parts[0]
    name = parts[1]
    channels = load_yt_channels()
    info = channels.get(name)

    if not info and action != "ytsendto":
        return await query.message.reply_text("❌ القناة غير موجودة")

    if action == "ytshow":
        title, url, thumb = get_latest_video(info["id"])
        if not title:
            return await query.message.reply_text("❌ لا يوجد فيديو جديد")
        text = info["text"]
        caption = f"🎬 *{title}*\n\n{text}"
        keyboard = [
            [InlineKeyboardButton("▶️ مشاهدة", url=url)],
            [InlineKeyboardButton("📤 إرسال إلى قناة", callback_data=f"ytsend|{name}")]
        ]
        context.user_data["last_video"] = {
            "title": title, "url": url, "thumb": thumb, "text": text
        }
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=thumb,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif action == "ytsend":
        video = context.user_data.get("last_video")
        if not video:
            return await query.message.reply_text("❌ لا يوجد فيديو محفوظ")
        send_keyboard = [[InlineKeyboardButton(ch, callback_data=f"ytsendto|{ch}")] for ch in channels]
        await query.message.reply_text("اختر القناة للإرسال:", reply_markup=InlineKeyboardMarkup(send_keyboard))

    elif action == "ytsendto":
        video = context.user_data.get("last_video")
        if not video:
            return await query.message.reply_text("❌ لا يوجد فيديو محفوظ")
        target_channel = name
        caption = f"🎬 *{video['title']}*\n\n{video['text']}"
        try:
            await context.bot.send_photo(
                chat_id=target_channel,
                photo=video["thumb"],
                caption=caption,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⤶ الـدخـول للـمـقـطـع ⤷", url=video["url"])]
                ])
            )
            await query.message.reply_text("✔ تم الإرسال بنجاح")
        except Exception as e:
            await query.message.reply_text(f"❌ فشل الإرسال:\n{e}")

# ----------------------------
# Cancel Handler
# ----------------------------
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("❌ تم الإلغاء.")
    context.user_data.pop("new_msg", None)
    context.user_data.pop("folder_action", None)
    return ConversationHandler.END

# ----------------------------
# Conversation Definition
# ----------------------------
massage_conv = ConversationHandler(
    entry_points=[CommandHandler("massage", massage_entry)],
    states={
        MASSAGE_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, massage_title)],
        MASSAGE_PHOTO: [MessageHandler(filters.PHOTO, massage_photo)],
        MASSAGE_BT:    [MessageHandler(filters.TEXT & ~filters.COMMAND, massage_bt)],
        MASSAGE_URL:   [MessageHandler(filters.TEXT & ~filters.COMMAND, massage_url)],
        MASSAGE_PREVIEW: [
            CallbackQueryHandler(massage_preview_actions, pattern=r"^massage:"),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    allow_reentry=True
)

# ----------------------------
# Main App Execution
# ----------------------------
def main():
    app = Application.builder().token(TOKEN).build()

    # Basics
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("cancel", cancel))

    # Massage Conversation
    app.add_handler(massage_conv)

    # Folders
    app.add_handler(CommandHandler("folder", folder_entry))
    app.add_handler(CallbackQueryHandler(folder_actions, pattern=r"^folder:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, folder_text))

    # Channels & Add
    app.add_handler(CommandHandler("add", add_channel_cmd))
    app.add_handler(CommandHandler("channels", list_channels))
    app.add_handler(CallbackQueryHandler(channels_actions, pattern=r"^channels:"))

    # Send Messages
    app.add_handler(CommandHandler("send", send_entry))
    app.add_handler(CallbackQueryHandler(send_actions, pattern=r"^send:"))

    # Admins
    app.add_handler(CommandHandler("admin", admin_add))
    app.add_handler(CommandHandler("admins", admins_list))
    app.add_handler(CallbackQueryHandler(admins_actions, pattern=r"^admins:"))

    # YouTube Feature Handlers
    app.add_handler(CommandHandler("search", yt_search))
    app.add_handler(CallbackQueryHandler(yt_button_handler, pattern=r"^yt"))

    # Noop Handler
    app.add_handler(CallbackQueryHandler(lambda update, context: update.callback_query.answer(), pattern=r"^noop$"))

    print("Bot is starting on Railway...")
    app.run_polling()

if __name__ == "__main__":
    main()
