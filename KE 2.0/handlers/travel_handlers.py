import asyncio
import re
import csv
import json # Import json for easier data handling
import os
import html
from datetime import datetime
from uuid import uuid4
from typing import List
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from states.travel_form import TravelForm
from keyboards.travel_keyboards import (
    get_phone_keyboard,
    get_city_keyboard,
    get_cities_keyboard,
    get_days_keyboard,
    get_people_keyboard,
    get_translator_keyboard,
    get_language_keyboard,
    get_review_keyboard,
    get_edit_keyboard,
    get_calendar_keyboard,
    get_date_confirmation_keyboard,
    get_language_selection_keyboard,
    get_referral_keyboard # Import the new keyboard
)
from locales import get_text # Import translation function
from config import ADMIN_CHAT_IDS

router = Router()

# Type guard helpers for aiogram types
def ensure_callback_message(callback: CallbackQuery) -> Message:
    """Type guard to ensure callback.message is not None"""
    assert callback.message is not None, "Callback message should not be None in handlers"
    return callback.message

def ensure_callback_data(callback: CallbackQuery) -> str:
    """Type guard to ensure callback.data is not None"""
    assert callback.data is not None, "Callback data should not be None in handlers"
    return callback.data

def ensure_message_from_user(message: Message):
    """Type guard to ensure message.from_user is not None"""
    assert message.from_user is not None, "Message from_user should not be None in handlers"
    return message.from_user

# Ensure data directory exists
os.makedirs("data", exist_ok=True)
CSV_FILE = "data/users.csv"
LANG_CSV_FILE = "data/user_languages.json"
PENDING_REQUESTS_FILE = "data/pending_requests.json"
REQUEST_PAYLOAD_KEYS = [
    'user_id',
    'first_name',
    'full_name',
    'phone',
    'current_city',
    'cities_to_visit',
    'other_cities',
    'days',
    'people',
    'need_translator',
    'translator_language',
    'start_date',
    'referral_source',
    'lang_code'
]
MAX_ADMIN_LIST_ITEMS = 10

# Track active admin panels for auto-refresh
active_admin_panels: dict[int, dict] = {}  # {admin_id: {"chat_id": int, "message_id": int, "bot": Bot, "task": Task}}


def is_admin(user_id: int | None) -> bool:
    """Check whether provided user ID belongs to an admin."""
    return bool(user_id and user_id in ADMIN_CHAT_IDS)


def format_phone_number(phone: str | None) -> str:
    """Ensure phone numbers always include country code prefix."""
    if not phone:
        return ""
    digits = re.sub(r'\D', '', phone)
    if not digits:
        return ""
    return f"+{digits}"


def extract_admin_payload(data: dict) -> dict:
    """Filter FSM data to persist only relevant fields for admin panel."""
    payload = {}
    for key in REQUEST_PAYLOAD_KEYS:
        if key in data:
            payload[key] = data.get(key)
    return payload


def load_pending_requests() -> List[dict]:
    """Load pending admin requests from JSON file."""
    if not os.path.exists(PENDING_REQUESTS_FILE):
        return []
    try:
        with open(PENDING_REQUESTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except (json.JSONDecodeError, OSError):
        return []


def save_pending_requests(requests: List[dict]):
    """Persist pending admin requests to JSON file."""
    with open(PENDING_REQUESTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(requests, f, ensure_ascii=False, indent=2)


def add_pending_request(payload: dict) -> dict:
    """Append a new pending request entry for the admin panel."""
    entry = {
        "id": str(uuid4()),
        "status": "new",
        "created_at": datetime.now().isoformat(),
        "payload": payload
    }
    requests = load_pending_requests()
    requests.insert(0, entry)  # newest first
    save_pending_requests(requests)
    return entry


def get_pending_requests(status: str | None = "new") -> List[dict]:
    """Return pending requests, optionally filtered by status."""
    requests = load_pending_requests()
    if status:
        requests = [req for req in requests if req.get("status") == status]
    return requests


def get_pending_request_by_id(request_id: str) -> dict | None:
    """Fetch a single pending request entry."""
    for entry in load_pending_requests():
        if entry.get("id") == request_id:
            return entry
    return None


def mark_request_processed(request_id: str, admin_id: int) -> bool:
    """Mark a request as processed by a specific admin."""
    requests = load_pending_requests()
    updated = False
    for entry in requests:
        if entry.get("id") == request_id:
            entry["status"] = "processed"
            entry["processed_by"] = admin_id
            entry["processed_at"] = datetime.now().isoformat()
            updated = True
            break
    if updated:
        save_pending_requests(requests)
    return updated


def save_to_csv(data: dict):
    """Save travel request data to CSV"""
    file_exists = os.path.isfile(CSV_FILE)
    
    with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
        fieldnames = [
            'timestamp',
            'full_name',
            'phone',
            'current_city',
            'cities_to_visit',
            'days',
            'people',
            'need_translator',
            'translator_language',
            'start_date',
            'referral_source'
        ] # Removed lang_code and user_id
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        if not file_exists:
            writer.writeheader()
        
        writer.writerow({
            'timestamp': datetime.now().isoformat(),
            'full_name': data.get('full_name', ''),
            'phone': data.get('phone', ''),
            'current_city': data.get('current_city', ''),
            'cities_to_visit': ', '.join(data.get('cities_to_visit', [])),
            'days': data.get('days', ''),
            'people': data.get('people', ''),
            'need_translator': data.get('need_translator', ''),
            'translator_language': data.get('translator_language', ''),
            'start_date': data.get('start_date', ''),
            'referral_source': data.get('referral_source', '')
        })


async def safe_delete_message(bot, chat_id: int, message_id: int):
    """Helper to safely delete a message"""
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass

async def delete_previous_bot_message(state: FSMContext, bot, chat_id: int):
    """Delete previous bot message from state"""
    try:
        data = await state.get_data()
        bot_msg_id = data.get('last_bot_message_id')
        if bot_msg_id:
            await safe_delete_message(bot, chat_id, bot_msg_id)
    except Exception:
        pass

async def update_last_bot_message_id(state: FSMContext, message_id: int):
    """Update the last bot message ID in state"""
    try:
        await state.update_data(last_bot_message_id=message_id)
    except Exception:
        pass


async def get_user_lang_code(state: FSMContext) -> str:
    """Get user's language code from state, defaults to 'en'"""
    data = await state.get_data()
    return data.get('lang_code', 'en')


async def start_phone_collection(message_or_callback, state: FSMContext, lang_code: str):
    """Send welcome message and ask for phone number"""
    from aiogram.types import Message, CallbackQuery
    
    target = message_or_callback.message if isinstance(message_or_callback, CallbackQuery) else message_or_callback
    data = await state.get_data()
    first_name = data.get('first_name')
    
    if not first_name:
        user = message_or_callback.from_user if isinstance(message_or_callback, CallbackQuery) else message_or_callback.from_user
        first_name, full_name = extract_user_names(user)
        await state.update_data(first_name=first_name, full_name=full_name)
    
    await delete_previous_bot_message(state, target.bot, target.chat.id)
    
    welcome_text = get_text(lang_code, 'welcome').format(first_name=first_name)
    await target.answer(welcome_text)
    
    bot_msg = await target.answer(
        get_text(lang_code, 'share_phone'),
        reply_markup=get_phone_keyboard(lang_code)
    )
    await update_last_bot_message_id(state, bot_msg.message_id)
    await state.set_state(TravelForm.phone)


def save_user_language(user_id: int, lang_code: str):
    """Save or update user's language preference to a dedicated JSON file"""
    user_id_str = str(user_id)
    user_languages = {}
    if os.path.exists(LANG_CSV_FILE):
        with open(LANG_CSV_FILE, 'r', encoding='utf-8') as f:
            try:
                user_languages = json.load(f)
            except json.JSONDecodeError:
                user_languages = {}

    user_languages[user_id_str] = lang_code

    with open(LANG_CSV_FILE, 'w', encoding='utf-8') as f:
        json.dump(user_languages, f, indent=4)


def get_user_language(user_id: int) -> str | None:
    """Get user's language preference from a dedicated JSON file"""
    user_id_str = str(user_id)
    if not os.path.exists(LANG_CSV_FILE):
        return None

    with open(LANG_CSV_FILE, 'r', encoding='utf-8') as f:
        try:
            user_languages = json.load(f)
            return user_languages.get(user_id_str)
        except json.JSONDecodeError:
            return None


def get_user_data_from_csv(user_id: int) -> dict:
    """Read user data from CSV based on user_id (excluding language preference)"""
    if not os.path.exists(CSV_FILE):
        return {}

    with open(CSV_FILE, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Compare user_id only if it's present in the row
            if 'user_id' in row and row.get('user_id') == str(user_id):
                return row
    return {}


def extract_user_names(user) -> tuple[str, str]:
    """Build first and full names from Telegram profile"""
    first_name = (user.first_name or user.username or "Traveler").strip()
    last_name = (user.last_name or "").strip()
    full_name = f"{first_name} {last_name}".strip() if last_name else first_name
    return first_name, full_name


def build_user_mention(user_id: int | None, full_name: str | None) -> str:
    """Create HTML mention for a Telegram user."""
    safe_name = html.escape((full_name or "Traveler").strip())
    if user_id:
        return f'<a href="tg://user?id={user_id}">{safe_name}</a>'
    return safe_name


def combine_cities(data: dict) -> list[str]:
    """Merge selected and custom cities into a single list."""
    cities = data.get('cities_to_visit', [])
    other_cities = data.get('other_cities', [])
    combined = []
    if isinstance(cities, list):
        combined.extend(cities)
    elif cities:
        combined.append(cities)
    if isinstance(other_cities, list):
        combined.extend(other_cities)
    elif other_cities:
        combined.append(other_cities)
    return [city for city in combined if city]


def format_admin_summary(data: dict) -> str:
    """Create a compact notification for admins"""
    mention = build_user_mention(data.get('user_id'), data.get('full_name'))
    return f"📥 New request from {mention}"


def truncate_label(text: str, limit: int = 40) -> str:
    """Trim text for inline button labels."""
    value = text.strip()
    return value if len(value) <= limit else value[: limit - 1] + "…"


def build_request_preview_text(entry: dict) -> str:
    """Generate compact preview text for admin list."""
    data = entry.get('payload', {})
    name = (data.get('full_name') or data.get('first_name') or "Unknown").strip()
    
    # Format date from created_at
    created_at = entry.get('created_at')
    date_str = "N/A"
    if created_at:
        try:
            dt = datetime.fromisoformat(created_at)
            # Format as Hour Day Month Year (e.g., "14 15 January 2024")
            date_str = dt.strftime("%H %d %B %Y")
        except (ValueError, AttributeError):
            date_str = "N/A"
    
    return truncate_label(f"{name} • {date_str}")


def format_admin_request_details(entry: dict) -> str:
    """Create detailed HTML message for admin panel."""
    data = entry.get('payload', {})
    user_id = data.get('user_id')
    
    # Extract first name and last name from full_name
    full_name = data.get('full_name') or data.get('first_name') or "Unknown"
    name_parts = full_name.split(maxsplit=1)
    first_name = name_parts[0] if name_parts else "Unknown"
    last_name = name_parts[1] if len(name_parts) > 1 else ""
    
    # Create separate links for first name and last name
    if user_id:
        first_name_link = f'<a href="tg://user?id={user_id}">{html.escape(first_name)}</a>'
        if last_name:
            last_name_link = f'<a href="tg://user?id={user_id}">{html.escape(last_name)}</a>'
            name_display = f"{first_name_link} {last_name_link}"
        else:
            name_display = first_name_link
    else:
        name_display = html.escape(full_name)
    
    phone = html.escape(format_phone_number(data.get('phone')) or "N/A")
    cities_list = combine_cities(data)
    cities = html.escape(", ".join(cities_list)) if cities_list else "N/A"
    translator_language = data.get('translator_language')
    translator_line = ""
    if data.get('need_translator') == "Yes":
        lang_value = html.escape(translator_language) if translator_language else "N/A"
        translator_line = f"\n   ↳ Language: {lang_value}"
    
    created_at = entry.get('created_at')
    processed_info = ""
    if entry.get('status') == "processed":
        processed_info = "\n✅ Already processed"
    
    lines = [
        "📄 Full travel request",
        f"👤 Name: {name_display}",
        f"🆔 User ID: {html.escape(str(user_id)) if user_id else 'N/A'}",
        f"📱 Phone: {phone}",
        f"📍 Current city: {html.escape(data.get('current_city')) if data.get('current_city') else 'N/A'}",
        f"🌍 Destinations: {cities}",
        f"📅 Days: {html.escape(data.get('days')) if data.get('days') else 'N/A'}",
        f"👥 People: {html.escape(data.get('people')) if data.get('people') else 'N/A'}",
        f"🗣️ Translator needed: {html.escape(data.get('need_translator')) if data.get('need_translator') else 'N/A'}{translator_line}",
        f"🗓️ Travel date: {html.escape(data.get('start_date')) if data.get('start_date') else 'N/A'}",
        f"📣 Referral: {html.escape(data.get('referral_source')) if data.get('referral_source') else 'N/A'}",
    ]
    
    if created_at:
        lines.append(f"⏱ Submitted: {html.escape(created_at)}")
    if processed_info:
        lines.append(processed_info)
    
    return "\n".join(lines)


def build_admin_panel_keyboard(requests: List[dict]) -> InlineKeyboardMarkup:
    """Assemble inline keyboard for admin panel view."""
    buttons: list[list[InlineKeyboardButton]] = []
    for entry in requests[:MAX_ADMIN_LIST_ITEMS]:
        entry_id = entry.get('id')
        if not entry_id:
            continue
        buttons.append([
            InlineKeyboardButton(
                text=build_request_preview_text(entry),
                callback_data=f"admin_req_{entry_id}"
            )
        ])
    # Refresh button removed - auto-refresh is implemented instead
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def render_admin_panel(target, *, answer_callback: bool = True, start_auto_refresh: bool = False):
    """Send or update the admin panel overview."""
    requests = get_pending_requests()
    count = len(requests)
    if count:
        instructions = "Tap a user to view full request and mark it as processed."
    else:
        instructions = "No new requests right now. Panel auto-refreshes every 10 seconds."
    text = "\n".join([
        "🛠 <b>Admin panel</b>",
        f"Pending requests: <b>{count}</b>",
        instructions
    ])
    keyboard = build_admin_panel_keyboard(requests)
    
    if isinstance(target, CallbackQuery):
        msg = target.message
        admin_id = target.from_user.id
        await msg.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        if answer_callback:
            await target.answer()
        
        # Update tracked panel for auto-refresh
        if start_auto_refresh and admin_id in active_admin_panels:
            active_admin_panels[admin_id]["message_id"] = msg.message_id
            active_admin_panels[admin_id]["chat_id"] = msg.chat.id
    else:
        msg = await target.answer(text, reply_markup=keyboard, parse_mode="HTML")
        admin_id = target.from_user.id
        
        # Start auto-refresh task for new admin panel
        if start_auto_refresh:
            # Stop existing task if any
            if admin_id in active_admin_panels:
                old_task = active_admin_panels[admin_id].get("task")
                if old_task and not old_task.done():
                    old_task.cancel()
            
            # Store panel info
            active_admin_panels[admin_id] = {
                "chat_id": msg.chat.id,
                "message_id": msg.message_id,
                "bot": target.bot
            }
            
            # Start auto-refresh task
            task = asyncio.create_task(auto_refresh_admin_panel(admin_id, target.bot))
            active_admin_panels[admin_id]["task"] = task


async def auto_refresh_admin_panel(admin_id: int, bot):
    """Background task to auto-refresh admin panel every 10 seconds."""
    try:
        while admin_id in active_admin_panels:
            await asyncio.sleep(10)  # Wait 10 seconds
            
            if admin_id not in active_admin_panels:
                break
                
            panel_info = active_admin_panels[admin_id]
            chat_id = panel_info["chat_id"]
            message_id = panel_info["message_id"]
            
            try:
                # Update the admin panel
                requests = get_pending_requests()
                count = len(requests)
                if count:
                    instructions = "Tap a user to view full request and mark it as processed."
                else:
                    instructions = "No new requests right now. Panel auto-refreshes every 10 seconds."
                text = "\n".join([
                    "🛠 <b>Admin panel</b>",
                    f"Pending requests: <b>{count}</b>",
                    instructions
                ])
                keyboard = build_admin_panel_keyboard(requests)
                
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            except Exception as e:
                # Message might have been deleted or edited, stop auto-refresh
                if admin_id in active_admin_panels:
                    del active_admin_panels[admin_id]
                break
    except asyncio.CancelledError:
        # Task was cancelled, clean up
        if admin_id in active_admin_panels:
            del active_admin_panels[admin_id]
    except Exception as e:
        # Any other error, clean up
        if admin_id in active_admin_panels:
            del active_admin_panels[admin_id]


async def notify_admins(bot, data: dict):
    """Send the new booking summary to all configured admins"""
    if not ADMIN_CHAT_IDS:
        return
    
    message_text = format_admin_summary(data)
    tasks = []
    for admin_id in ADMIN_CHAT_IDS:
        tasks.append(bot.send_message(chat_id=admin_id, text=message_text))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for admin_id, result in zip(ADMIN_CHAT_IDS, results):
        if isinstance(result, Exception):
            print(f"[WARN] Failed to notify admin {admin_id}: {result}")


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Start command - initialize conversation or load user language"""
    await state.clear()
    user_id = message.from_user.id
    
    lang_code = get_user_language(user_id)
    first_name, full_name = extract_user_names(message.from_user)

    state_payload = {
        'user_id': user_id,
        'first_name': first_name,
        'full_name': full_name,
        'change_language_only': False
    }
    if lang_code:
        state_payload['lang_code'] = lang_code
    await state.update_data(**state_payload) # Store user data

    if not lang_code:
        choose_text = get_text('en', 'choose_language')
        prefix = f"{first_name}, " if first_name else ""
        bot_msg = await message.answer(
            f"{prefix}{choose_text}", # Default to English for language selection
            reply_markup=get_language_selection_keyboard('en') # Pass 'en' as default
        )
        await update_last_bot_message_id(state, bot_msg.message_id)
        await state.set_state(TravelForm.lang_code)
    else:
        await start_phone_collection(message, state, lang_code)


@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext):
    """Handle /help command"""
    await delete_previous_bot_message(state, message.bot, message.chat.id)
    user_id = message.from_user.id
    persisted_lang = get_user_language(user_id) or 'en'
    await state.clear()
    await state.update_data(user_id=user_id, lang_code=persisted_lang)
    lang_code = persisted_lang
    await safe_delete_message(message.bot, message.chat.id, message.message_id)
    bot_msg = await message.answer(get_text(lang_code, 'help_message'))
    await update_last_bot_message_id(state, bot_msg.message_id)

@router.message(Command("support"))
async def cmd_support(message: Message, state: FSMContext):
    """Handle /support command"""
    await delete_previous_bot_message(state, message.bot, message.chat.id)
    user_id = message.from_user.id
    persisted_lang = get_user_language(user_id) or 'en'
    await state.clear()
    await state.update_data(user_id=user_id, lang_code=persisted_lang)
    lang_code = persisted_lang
    await safe_delete_message(message.bot, message.chat.id, message.message_id)
    bot_msg = await message.answer(get_text(lang_code, 'support_message'))
    await update_last_bot_message_id(state, bot_msg.message_id)

@router.message(Command("language"))
async def cmd_language(message: Message, state: FSMContext):
    """Handle /language command - allow user to change language"""
    await delete_previous_bot_message(state, message.bot, message.chat.id)
    user_id = message.from_user.id
    persisted_lang = get_user_language(user_id) or 'en'
    await state.clear()
    await state.update_data(user_id=user_id, lang_code=persisted_lang, change_language_only=True)
    lang_code = persisted_lang
    await safe_delete_message(message.bot, message.chat.id, message.message_id)
    bot_msg = await message.answer(
        get_text(lang_code, 'change_language_message'),
        reply_markup=get_language_selection_keyboard(lang_code) # Pass lang_code here
    )
    await update_last_bot_message_id(state, bot_msg.message_id)
    await state.set_state(TravelForm.lang_code) # Reuse lang_code state for changing language


@router.message(Command("admin"))
async def cmd_admin_panel(message: Message):
    """Entry point for admin panel."""
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ You are not allowed to open the admin panel.")
        return
    await render_admin_panel(message, start_auto_refresh=True)


@router.callback_query(F.data == "admin_panel_refresh")
async def admin_panel_refresh(callback: CallbackQuery):
    """Refresh admin panel via inline button (kept for backward compatibility, but auto-refresh is active)."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Not authorized", show_alert=True)
        return
    await render_admin_panel(callback, start_auto_refresh=True)


@router.callback_query(F.data.startswith("admin_req_done_"))
async def admin_mark_request_done(callback: CallbackQuery):
    """Mark a specific request as processed."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Not authorized", show_alert=True)
        return
    request_id = callback.data.replace("admin_req_done_", "", 1)
    updated = mark_request_processed(request_id, callback.from_user.id)
    if updated:
        await callback.answer("Request marked as processed ✅")
    else:
        await callback.answer("Request already handled or missing.", show_alert=True)
    # Stop auto-refresh when navigating back to panel
    admin_id = callback.from_user.id
    if admin_id in active_admin_panels:
        task = active_admin_panels[admin_id].get("task")
        if task and not task.done():
            task.cancel()
        del active_admin_panels[admin_id]
    await render_admin_panel(callback, answer_callback=False, start_auto_refresh=True)


@router.callback_query(F.data.startswith("admin_req_"))
async def admin_view_request(callback: CallbackQuery):
    """Show full request details when admin selects a user."""
    if not is_admin(callback.from_user.id):
        await callback.answer("Not authorized", show_alert=True)
        return
    # Avoid handling the _done variant twice
    if callback.data.startswith("admin_req_done_"):
        return
    request_id = callback.data.replace("admin_req_", "", 1)
    entry = get_pending_request_by_id(request_id)
    if not entry:
        await callback.answer("This request is no longer available.", show_alert=True)
        await render_admin_panel(callback, answer_callback=False, start_auto_refresh=True)
        return
    # Stop auto-refresh when viewing request details
    admin_id = callback.from_user.id
    if admin_id in active_admin_panels:
        task = active_admin_panels[admin_id].get("task")
        if task and not task.done():
            task.cancel()
        del active_admin_panels[admin_id]
    
    detail_text = format_admin_request_details(entry)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Mark processed", callback_data=f"admin_req_done_{request_id}")],
        [InlineKeyboardButton(text="↩️ Back", callback_data="admin_panel_refresh")]
    ])
    await callback.message.edit_text(detail_text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(TravelForm.lang_code, F.data.startswith("lang_select_"))
async def process_language_selection(callback: CallbackQuery, state: FSMContext):
    lang_code_new = callback.data.replace("lang_select_", "")
    user_id = callback.from_user.id # Get user_id from callback
    
    await state.update_data(user_id=user_id, lang_code=lang_code_new)
    save_user_language(user_id, lang_code_new) # Save language preference immediately
    
    data = await state.get_data()
    change_language_only = data.get('change_language_only')
    
    await callback.message.delete()
    
    if change_language_only:
        bot_msg = await callback.message.answer(
            get_text(lang_code_new, 'language_changed').format(language=lang_code_new.upper()),
        )
        await update_last_bot_message_id(state, bot_msg.message_id)
        await state.clear()
    else:
        await state.update_data(change_language_only=False)
        await start_phone_collection(callback, state, lang_code_new)
    
    await callback.answer()


@router.message(TravelForm.phone, F.contact | F.text.regexp(r'[\+]?[1-9][\d]{0,15}'))
async def process_phone(message: Message, state: FSMContext):
    """Process phone number from contact or text input"""
    lang_code = await get_user_lang_code(state) # Get lang_code once
    phone = None

    if message.contact:
        phone = message.contact.phone_number
    elif message.text:
        text = message.text.strip()
        # Simple phone regex (already validated by F.text.regexp)
        phone = text

    formatted_phone = format_phone_number(phone)
    
    if formatted_phone:
        await state.update_data(phone=formatted_phone)
        await safe_delete_message(message.bot, message.chat.id, message.message_id)

        # Delete previous bot message
        data = await state.get_data()
        await safe_delete_message(message.bot, message.chat.id, data.get('last_bot_message_id', 0))

        # Check if we're in edit mode
        if data.get('editing_field') == 'phone':
            await state.update_data(editing_field=None)
            # Remove reply keyboard
            bot_msg = await message.answer(get_text(lang_code, 'phone_updated'), reply_markup=ReplyKeyboardRemove())
            await update_last_bot_message_id(state, bot_msg.message_id)
            await show_review(message, state)
            return

        bot_msg = await message.answer(
            get_text(lang_code, 'share_current_city'),
            reply_markup=get_city_keyboard(lang_code)
        )
        await update_last_bot_message_id(state, bot_msg.message_id)
        await state.set_state(TravelForm.current_city)
    else:
        # This else block might be redundant due to F.contact | F.text.regexp
        # but kept for safety or future regex changes
        bot_msg = await message.answer(get_text(lang_code, 'invalid_phone'))
        await safe_delete_message(message.bot, message.chat.id, message.message_id)
        await delete_previous_bot_message(state, message.bot, message.chat.id)
        await update_last_bot_message_id(state, bot_msg.message_id)
        return


@router.message(TravelForm.current_city, F.location | F.text)
async def process_current_city(message: Message, state: FSMContext):
    """Process current city from location or text input"""
    lang_code = await get_user_lang_code(state) # Get lang_code once
    city = None

    if message.location:
        city = f"Lat: {message.location.latitude}, Lon: {message.location.longitude}"
    elif message.text:
        city = message.text.strip()
        if len(city) < 2:
            bot_msg = await message.answer(get_text(lang_code, 'invalid_city'))
            await safe_delete_message(message.bot, message.chat.id, message.message_id)
            await delete_previous_bot_message(state, message.bot, message.chat.id)
            await update_last_bot_message_id(state, bot_msg.message_id)
            return

    if city:
        await state.update_data(current_city=city)
        await safe_delete_message(message.bot, message.chat.id, message.message_id)

        # Delete previous bot message
        await delete_previous_bot_message(state, message.bot, message.chat.id)

        # Check if we're in edit mode
        data = await state.get_data()
        if data.get('editing_field') == 'current_city':
            await state.update_data(editing_field=None)
            # Remove reply keyboard
            bot_msg = await message.answer(get_text(lang_code, 'city_updated'), reply_markup=ReplyKeyboardRemove())
            await update_last_bot_message_id(state, bot_msg.message_id)
            await show_review(message, state)
            return

        # Initialize cities list
        await state.update_data(cities_to_visit=[], other_cities=[])

        bot_msg = await message.answer(
            get_text(lang_code, 'select_cities'),
            reply_markup=get_cities_keyboard([], [], lang_code)
        )
        await update_last_bot_message_id(state, bot_msg.message_id)
        await state.set_state(TravelForm.cities_to_visit)


@router.callback_query(TravelForm.cities_to_visit, F.data.startswith("city_"))
async def process_city_selection(callback: CallbackQuery, state: FSMContext):
    """Process city selection/deselection"""
    data = await state.get_data()
    selected_cities = data.get('cities_to_visit', [])
    other_cities = data.get('other_cities', [])
    lang_code = await get_user_lang_code(state) # Get lang_code once
    
    city_name = callback.data.replace("city_", "")
    
    if city_name == "done":
        if len(selected_cities) + len(other_cities) == 0:
            await callback.answer(get_text(lang_code, 'select_at_least_one_city'), show_alert=True)
            return
        
        # Check if we're in edit mode
        if data.get('editing_field') == 'cities':
            await state.update_data(editing_field=None)
            await show_review(callback.message, state)
            await callback.answer()
            return
        
        await callback.message.edit_text(
            get_text(lang_code, 'how_many_days'),
            reply_markup=get_days_keyboard(lang_code)
        )
        await state.set_state(TravelForm.days)
        await callback.answer()
        
    elif city_name == "other":
        await callback.message.edit_text(get_text(lang_code, 'type_other_city'))
        await state.set_state(TravelForm.other_city)
        await callback.answer()
        
    else:
        # Toggle city selection
        if city_name in selected_cities:
            selected_cities.remove(city_name)
        elif city_name in other_cities:
            other_cities.remove(city_name)
        else:
            if city_name in ["Мекка", "Медина", "Дубай", "Стамбул", "Шарм-эш-Шейх", "Каир", "Доха", "Джидда"]:
                selected_cities.append(city_name)
            else:
                other_cities.append(city_name)
        
        await state.update_data(cities_to_visit=selected_cities, other_cities=other_cities)
        await callback.message.edit_reply_markup(
            reply_markup=get_cities_keyboard(selected_cities, other_cities, lang_code)
        )
        await callback.answer()


@router.message(TravelForm.other_city)
async def process_other_city(message: Message, state: FSMContext):
    """Process other city input"""
    lang_code = await get_user_lang_code(state) # Get lang_code once
    city = message.text.strip()
    data = await state.get_data()

    if len(city) < 2:
        bot_msg = await message.answer(get_text(lang_code, 'invalid_city'))
        await safe_delete_message(message.bot, message.chat.id, message.message_id)
        await delete_previous_bot_message(state, message.bot, message.chat.id)
        await update_last_bot_message_id(state, bot_msg.message_id)
        return
    
    other_cities = data.get('other_cities', [])
    if city not in other_cities:
        other_cities.append(city)
    
    await state.update_data(other_cities=other_cities)
    await safe_delete_message(message.bot, message.chat.id, message.message_id)
    
    selected_cities = data.get('cities_to_visit', [])
    bot_msg = await message.answer(
        get_text(lang_code, 'select_cities'),
        reply_markup=get_cities_keyboard(selected_cities, other_cities, lang_code)
    )
    await update_last_bot_message_id(state, bot_msg.message_id)
    await state.set_state(TravelForm.cities_to_visit)


@router.callback_query(TravelForm.days, F.data.startswith("days_"))
async def process_days(callback: CallbackQuery, state: FSMContext):
    """Process days selection"""
    days_value = callback.data.replace("days_", "")
    data = await state.get_data()
    lang_code = await get_user_lang_code(state) # Get lang_code once
    
    if days_value == "other":
        await callback.message.edit_text(get_text(lang_code, 'enter_number_of_days'))
        await state.set_state(TravelForm.other_days)
        await callback.answer()
    else:
        await state.update_data(days=days_value)
        
        # Check if we're in edit mode
        if data.get('editing_field') == 'days':
            await state.update_data(editing_field=None)
            await show_review(callback.message, state)
            await callback.answer()
            return
        
        await callback.message.edit_text(
            get_text(lang_code, 'how_many_people'),
            reply_markup=get_people_keyboard(lang_code)
        )
        await state.set_state(TravelForm.people)
        await callback.answer()


@router.message(TravelForm.other_days)
async def process_other_days(message: Message, state: FSMContext):
    """Process other days input"""
    lang_code = await get_user_lang_code(state) # Get lang_code once
    try:
        days = int(message.text.strip())
        if days < 1:
            raise ValueError
        await state.update_data(days=str(days))
        await safe_delete_message(message.bot, message.chat.id, message.message_id)
        
        # Delete previous bot message
        await delete_previous_bot_message(state, message.bot, message.chat.id)
        
        # Check if we're in edit mode
        data = await state.get_data()
        if data.get('editing_field') == 'days':
            await state.update_data(editing_field=None)
            await show_review(message, state)
            return
        
        bot_msg = await message.answer(
            get_text(lang_code, 'how_many_people'),
            reply_markup=get_people_keyboard(lang_code)
        )
        await update_last_bot_message_id(state, bot_msg.message_id)
        await state.set_state(TravelForm.people)
    except:
        bot_msg = await message.answer(get_text(lang_code, 'invalid_number'))
        await safe_delete_message(message.bot, message.chat.id, message.message_id)
        await delete_previous_bot_message(state, message.bot, message.chat.id)
        await update_last_bot_message_id(state, bot_msg.message_id)


@router.callback_query(TravelForm.people, F.data.startswith("people_"))
async def process_people(callback: CallbackQuery, state: FSMContext):
    """Process people selection"""
    people_value = callback.data.replace("people_", "")
    data = await state.get_data()
    lang_code = await get_user_lang_code(state) # Get lang_code once
    
    if people_value == "4plus":
        await callback.message.edit_text(get_text(lang_code, 'enter_number_of_people'))
        await state.set_state(TravelForm.other_people)
        await callback.answer()
    else:
        await state.update_data(people=people_value)
        
        # Check if we're in edit mode
        if data.get('editing_field') == 'people':
            await state.update_data(editing_field=None)
            await show_review(callback.message, state)
            await callback.answer()
            return
        
        await callback.message.edit_text(
            get_text(lang_code, 'need_translator'),
            reply_markup=get_translator_keyboard(lang_code)
        )
        await state.set_state(TravelForm.need_translator)
        await callback.answer()


@router.message(TravelForm.other_people)
async def process_other_people(message: Message, state: FSMContext):
    """Process other people input"""
    lang_code = await get_user_lang_code(state) # Get lang_code once
    try:
        people = int(message.text.strip())
        if people < 5:
            raise ValueError
        await state.update_data(people=str(people))
        await safe_delete_message(message.bot, message.chat.id, message.message_id)
        
        # Delete previous bot message
        await delete_previous_bot_message(state, message.bot, message.chat.id)
        
        # Check if we're in edit mode
        data = await state.get_data()
        if data.get('editing_field') == 'people':
            await state.update_data(editing_field=None)
            await show_review(message, state)
            return
        
        bot_msg = await message.answer(
            get_text(lang_code, 'need_translator'),
            reply_markup=get_translator_keyboard(lang_code)
        )
        await update_last_bot_message_id(state, bot_msg.message_id)
        await state.set_state(TravelForm.need_translator)
    except:
        bot_msg = await message.answer(get_text(lang_code, 'invalid_number_5_or_more'))
        await safe_delete_message(message.bot, message.chat.id, message.message_id)
        await delete_previous_bot_message(state, message.bot, message.chat.id)
        await update_last_bot_message_id(state, bot_msg.message_id)


@router.callback_query(TravelForm.need_translator, F.data.startswith("translator_"))
async def process_translator(callback: CallbackQuery, state: FSMContext):
    """Process translator question"""
    answer = callback.data.replace("translator_", "")
    data = await state.get_data()
    is_editing = data.get('editing_field') == 'translator'
    lang_code = await get_user_lang_code(state) # Get lang_code once
    
    if answer == "yes":
        await state.update_data(need_translator="Yes")
        if is_editing:
            await callback.message.edit_text(
                get_text(lang_code, 'which_language'),
                reply_markup=get_language_keyboard(lang_code)
            )
            await state.set_state(TravelForm.translator_language)
        else:
            await callback.message.edit_text(
                get_text(lang_code, 'which_language'),
                reply_markup=get_language_keyboard(lang_code)
            )
            await state.set_state(TravelForm.translator_language)
    else:
        await state.update_data(need_translator="No", translator_language="")
        if is_editing:
            await state.update_data(editing_field=None)
            await show_review(callback.message, state)
        else:
            await show_start_date_calendar(callback.message, state)
    
    await callback.answer()


@router.callback_query(TravelForm.translator_language, F.data.startswith("lang_"))
async def process_language(callback: CallbackQuery, state: FSMContext):
    """Process language selection"""
    lang = callback.data.replace("lang_", "")
    data = await state.get_data()
    lang_code = await get_user_lang_code(state) # Get lang_code once
    
    if lang == "other":
        await callback.message.edit_text(get_text(lang_code, 'enter_language'))
        await state.set_state(TravelForm.other_language)
        await callback.answer()
    else:
        await state.update_data(translator_language=lang)
        data = await state.get_data()
        if data.get('editing_field') == 'translator':
            await state.update_data(editing_field=None)
            await show_review(callback.message, state)
        else:
            await show_start_date_calendar(callback.message, state)
        await callback.answer()


@router.message(TravelForm.other_language)
async def process_other_language(message: Message, state: FSMContext):
    """Process other language input"""
    lang_code = await get_user_lang_code(state) # Get lang_code once
    language = message.text.strip()
    data = await state.get_data()

    if len(language) < 1:
        bot_msg = await message.answer(get_text(lang_code, 'invalid_language'))
        await safe_delete_message(message.bot, message.chat.id, message.message_id)
        await delete_previous_bot_message(state, message.bot, message.chat.id)
        await update_last_bot_message_id(state, bot_msg.message_id)
        return
    
    await state.update_data(translator_language=language)
    await safe_delete_message(message.bot, message.chat.id, message.message_id)
    
    # Delete previous bot message
    data = await state.get_data()
    await delete_previous_bot_message(state, message.bot, message.chat.id)
    
    if data.get('editing_field') == 'translator':
        await state.update_data(editing_field=None)
        await show_review(message, state)
    else:
        await show_start_date_calendar(message, state)


async def show_start_date_calendar(message_or_callback, state: FSMContext):
    """Show calendar for selecting travel date"""
    from aiogram.types import Message, CallbackQuery
    from datetime import datetime
    
    data = await state.get_data()
    lang_code = await get_user_lang_code(state) # Get lang_code once
    today = datetime.now()
    year = today.year
    month = today.month
    selected_date = data.get('start_date') # Get selected date from state
    
    text = get_text(lang_code, 'select_travel_date')
    
    if isinstance(message_or_callback, CallbackQuery):
        # For callbacks, edit_text doesn't create new message, so we track the existing one
        await message_or_callback.message.edit_text(
            text,
            reply_markup=get_calendar_keyboard(year, month, selected_date=selected_date, lang_code=lang_code),
            parse_mode="Markdown"
        )
        await update_last_bot_message_id(state, message_or_callback.message.message_id)
    else:
        # Delete previous bot message
        await delete_previous_bot_message(state, message_or_callback.bot, message_or_callback.chat.id)
        bot_msg = await message_or_callback.answer(
            text,
            reply_markup=get_calendar_keyboard(year, month, selected_date=selected_date, lang_code=lang_code),
            parse_mode="Markdown"
        )
        await update_last_bot_message_id(state, bot_msg.message_id)
    
    await state.set_state(TravelForm.start_date)


async def show_review(message_or_callback, state: FSMContext):
    """Show review summary - accepts Message or CallbackQuery"""
    from aiogram.types import Message, CallbackQuery
    
    data = await state.get_data()
    lang_code = await get_user_lang_code(state) # Get lang_code once
    
    all_cities = data.get('cities_to_visit', []) + data.get('other_cities', [])
    cities_str = ', '.join(all_cities) if all_cities else get_text(lang_code, 'N/A') # Using get_text for N/A
    
    translator_info = ""
    if data.get('need_translator') == "Yes":
        translator_info = get_text(lang_code, 'translator').format(language=data.get('translator_language', get_text(lang_code, 'N/A')))
    
    # Format dates
    dates_info = ""
    start_date = data.get('start_date', '')
    if start_date:
        dates_info = get_text(lang_code, 'travel_date').format(date=start_date)
    
    summary = get_text(lang_code, 'review_info').format(
        full_name=data.get('full_name', get_text(lang_code, 'N/A')),
        phone=data.get('phone', get_text(lang_code, 'N/A')),
        current_city=data.get('current_city', get_text(lang_code, 'N/A')),
        cities_str=cities_str,
        days=data.get('days', get_text(lang_code, 'N/A')),
        people=data.get('people', get_text(lang_code, 'N/A')),
        need_translator=data.get('need_translator', get_text(lang_code, 'N/A')),
        translator_info=translator_info,
        dates_info=dates_info
    )
    
    if isinstance(message_or_callback, CallbackQuery):
        # For callbacks, edit_text doesn't create new message
        await message_or_callback.message.edit_text(summary, reply_markup=get_review_keyboard(lang_code), parse_mode="Markdown")
        await update_last_bot_message_id(state, message_or_callback.message.message_id)
    else:
        # Delete previous bot message
        await delete_previous_bot_message(state, message_or_callback.bot, message_or_callback.chat.id)
        bot_msg = await message_or_callback.answer(summary, reply_markup=get_review_keyboard(lang_code), parse_mode="Markdown")
        await update_last_bot_message_id(state, bot_msg.message_id)
    
    await state.set_state(TravelForm.review)


async def finalize_submission(message_or_callback, state: FSMContext):
    """Persist data and send final thank-you message"""
    from aiogram.types import Message, CallbackQuery
    
    data = await state.get_data()
    save_to_csv(data)
    lang_code = await get_user_lang_code(state)
    admin_payload = extract_admin_payload(data)
    add_pending_request(admin_payload)
    
    if isinstance(message_or_callback, CallbackQuery):
        bot_instance = message_or_callback.message.bot
    else:
        bot_instance = message_or_callback.bot
    
    await notify_admins(bot_instance, data)
    
    acknowledgement = get_text(lang_code, 'referral_saved')
    thank_you_text = get_text(lang_code, 'thank_you')
    
    if isinstance(message_or_callback, CallbackQuery):
        try:
            await message_or_callback.message.edit_text(acknowledgement)
        except Exception:
            pass
        await message_or_callback.message.answer(thank_you_text)
    else:
        await message_or_callback.answer(acknowledgement)
        await message_or_callback.answer(thank_you_text)
    
    await state.clear()


@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext):
    """Handle /help command"""
    lang_code = await get_user_lang_code(state)
    await safe_delete_message(message.bot, message.chat.id, message.message_id)
    bot_msg = await message.answer(get_text(lang_code, 'help_message'))
    await update_last_bot_message_id(state, bot_msg.message_id)

@router.message(Command("support"))
async def cmd_support(message: Message, state: FSMContext):
    """Handle /support command"""
    lang_code = await get_user_lang_code(state)
    await safe_delete_message(message.bot, message.chat.id, message.message_id)
    bot_msg = await message.answer(get_text(lang_code, 'support_message'))
    await update_last_bot_message_id(state, bot_msg.message_id)

@router.message(Command("language"))
async def cmd_language(message: Message, state: FSMContext):
    """Handle /language command - allow user to change language"""
    lang_code = await get_user_lang_code(state)
    await safe_delete_message(message.bot, message.chat.id, message.message_id)
    bot_msg = await message.answer(
        get_text(lang_code, 'change_language_message'),
        reply_markup=get_language_selection_keyboard(lang_code) # Pass lang_code here
    )
    await update_last_bot_message_id(state, bot_msg.message_id)
    await state.update_data(change_language_only=True)
    await state.set_state(TravelForm.lang_code) # Reuse lang_code state for changing language


@router.callback_query(TravelForm.review, F.data == "review_confirm")
async def process_confirm(callback: CallbackQuery, state: FSMContext):
    """After review confirmation, ask how user found the bot"""
    data = await state.get_data()
    all_cities = data.get('cities_to_visit', []) + data.get('other_cities', [])
    await state.update_data(cities_to_visit=all_cities)
    
    lang_code = await get_user_lang_code(state)
    await callback.message.edit_text(
        get_text(lang_code, 'referral_question'),
        reply_markup=get_referral_keyboard(lang_code)
    )
    await update_last_bot_message_id(state, callback.message.message_id)
    await state.set_state(TravelForm.referral_source)
    await callback.answer()


@router.callback_query(TravelForm.referral_source, F.data.startswith("ref_"))
async def process_referral_source(callback: CallbackQuery, state: FSMContext):
    """Handle referral question buttons"""
    lang_code = await get_user_lang_code(state)
    data_key = callback.data
    
    if data_key == "ref_other":
        await callback.message.edit_text(get_text(lang_code, 'enter_other_referral'))
        await update_last_bot_message_id(state, callback.message.message_id)
        await state.set_state(TravelForm.other_referral)
    elif data_key == "ref_skip":
        await state.update_data(referral_source="Skipped")
        await finalize_submission(callback, state)
    else:
        label_map = {
            "ref_instagram": get_text('en', 'referral_instagram'),
            "ref_youtube": get_text('en', 'referral_youtube'),
            "ref_facebook": get_text('en', 'referral_facebook'),
            "ref_website": get_text('en', 'referral_website'),
            "ref_google": get_text('en', 'referral_google'),
        }
        await state.update_data(referral_source=label_map.get(data_key, data_key))
        await finalize_submission(callback, state)
    
    await callback.answer()


@router.message(TravelForm.other_referral)
async def process_other_referral(message: Message, state: FSMContext):
    """Capture custom referral text"""
    lang_code = await get_user_lang_code(state)
    response = (message.text or "").strip()
    
    if not response:
        bot_msg = await message.answer(get_text(lang_code, 'enter_other_referral'))
        await update_last_bot_message_id(state, bot_msg.message_id)
        return
    
    await state.update_data(referral_source=response)
    await safe_delete_message(message.bot, message.chat.id, message.message_id)
    await finalize_submission(message, state)


# Calendar handlers
@router.callback_query(TravelForm.start_date, F.data.startswith("cal_"))
async def process_date_calendar(callback: CallbackQuery, state: FSMContext):
    """Process calendar interactions"""
    from datetime import datetime
    
    data_str = callback.data
    if data_str == "cal_ignore":
        await callback.answer()
        return
    
    data = await state.get_data()
    selected_date = data.get('start_date')
    lang_code = await get_user_lang_code(state) # Get lang_code once
    
    if data_str.startswith("cal_prev_") or data_str.startswith("cal_next_"):
        # Month navigation
        parts = data_str.split("_")
        year = int(parts[2])
        month = int(parts[3])
        
        if "prev" in data_str:
            month -= 1
            if month < 1:
                month = 12
                year -= 1
        else:
            month += 1
            if month > 12:
                month = 1
                year += 1
        
        await callback.message.edit_reply_markup(
            reply_markup=get_calendar_keyboard(year, month, selected_date=selected_date, lang_code=lang_code)
        )
        await callback.answer()
    
    elif data_str.startswith("cal_day_"):
        # Day selected
        parts = data_str.split("_")
        date_str = parts[2]
        await state.update_data(start_date=date_str)
        
        # Show confirmation
        formatted_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %d, %Y")
        await callback.message.edit_text(
            get_text(lang_code, 'date_selected').format(date=formatted_date),
            reply_markup=get_date_confirmation_keyboard(date_str, lang_code=lang_code),
            parse_mode="Markdown"
        )
        await callback.answer()
    
    elif data_str == "cal_skip":
        # Skip date selection
        await state.update_data(start_date="")
        await show_review(callback.message, state)
        await callback.answer()
    
    elif data_str.startswith("cal_confirm_"):
        # Confirm date
        parts = data_str.split("_")
        date_str = parts[2]
        await state.update_data(start_date=date_str)
        await show_review(callback.message, state)
        await callback.answer()
    
    elif data_str == "cal_change":
        # Change date - show calendar again
        today = datetime.now()
        selected_date = data.get('start_date') # Preserve selected date if available
        await callback.message.edit_text(
            get_text(lang_code, 'select_travel_date'),
            reply_markup=get_calendar_keyboard(today.year, today.month, selected_date=selected_date, lang_code=lang_code),
            parse_mode="Markdown"
        )
        await callback.answer()


@router.callback_query(TravelForm.review, F.data == "review_edit")
async def process_edit_choice(callback: CallbackQuery, state: FSMContext):
    """Show edit options"""
    lang_code = await get_user_lang_code(state) # Get lang_code once
    data = await state.get_data()
    await callback.message.edit_text(
        get_text(lang_code, 'edit_field'),
        reply_markup=get_edit_keyboard(lang_code)
    )
    await callback.answer()


@router.callback_query(TravelForm.review, F.data.startswith("edit_"))
async def process_edit_field(callback: CallbackQuery, state: FSMContext):
    """Process edit field selection"""
    message = ensure_callback_message(callback)
    callback_data = ensure_callback_data(callback)
    
    field = callback_data.replace("edit_", "")
    data = await state.get_data()
    lang_code = await get_user_lang_code(state) # Get lang_code once
    
    # Set edit mode flag
    await state.update_data(editing_field=field)
    
    if field == "phone":
        await message.edit_text(
            get_text(lang_code, 'share_phone'),
            reply_markup=get_phone_keyboard(lang_code)
        )
        await state.set_state(TravelForm.phone)
    elif field == "current_city":
        await message.edit_text(
            get_text(lang_code, 'share_current_city'),
            reply_markup=get_city_keyboard(lang_code)
        )
        await state.set_state(TravelForm.current_city)
    elif field == "cities":
        data = await state.get_data()
        selected_cities = data.get('cities_to_visit', [])
        other_cities = data.get('other_cities', [])
        await message.edit_text(
            get_text(lang_code, 'select_cities'),
            reply_markup=get_cities_keyboard(selected_cities, other_cities, lang_code)
        )
        await state.set_state(TravelForm.cities_to_visit)
    elif field == "days":
        await message.edit_text(
            get_text(lang_code, 'how_many_days'),
            reply_markup=get_days_keyboard(lang_code)
        )
        await state.set_state(TravelForm.days)
    elif field == "people":
        await message.edit_text(
            get_text(lang_code, 'how_many_people'),
            reply_markup=get_people_keyboard(lang_code)
        )
        await state.set_state(TravelForm.people)
    elif field == "translator":
        await message.edit_text(
            get_text(lang_code, 'need_translator'),
            reply_markup=get_translator_keyboard(lang_code)
        )
        await state.set_state(TravelForm.need_translator)
    elif field == "dates":
        await state.update_data(editing_field=None)
        await show_start_date_calendar(message, state)
    
    await callback.answer()


@router.message()
async def handle_unexpected(message: Message, state: FSMContext):
    """Handle unexpected messages - prevent crashes"""
    current_state = await state.get_state()
    lang_code = await get_user_lang_code(state) # Get lang_code once
    if current_state is None:
        await message.answer(get_text(lang_code, 'use_start'))
    else:
        # Try to delete the unexpected message
        await safe_delete_message(message.bot, message.chat.id, message.message_id)
        await message.answer(get_text(lang_code, 'use_buttons'))

