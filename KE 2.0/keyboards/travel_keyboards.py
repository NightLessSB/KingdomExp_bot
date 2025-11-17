from datetime import datetime
from calendar import monthcalendar
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from locales import get_text # Import translation function
import locale # Import locale module


def get_phone_keyboard(lang_code: str = 'en') -> ReplyKeyboardMarkup:
    """Keyboard for phone number sharing"""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="📱 " + get_text(lang_code, 'share_contact'), request_contact=True))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)


def get_city_keyboard(lang_code: str = 'en') -> ReplyKeyboardMarkup:
    """Keyboard for current city (location sharing)"""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="📍 " + get_text(lang_code, 'share_location'), request_location=True))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)


def get_cities_keyboard(selected_cities: list, other_cities: list, lang_code: str = 'en') -> InlineKeyboardMarkup:
    """Multi-select keyboard for cities to visit"""
    builder = InlineKeyboardBuilder()
    
    cities = ["Мекка", "Медина", "Дубай", "Стамбул", "Шарм-эш-Шейх", "Каир", "Доха", "Джидда"]
    
    for city in cities:
        translated_city = get_text(lang_code, city) # Get translated city name
        if city in selected_cities:
            builder.add(InlineKeyboardButton(text=f"✅ {translated_city}", callback_data=f"city_{city}"))
        else:
            builder.add(InlineKeyboardButton(text=f"⬜️ {translated_city}", callback_data=f"city_{city}"))
    
    builder.adjust(2)
    
    # Add other cities if any
    for city in other_cities:
        builder.add(InlineKeyboardButton(text=f"✅ {city}", callback_data=f"city_{city}"))
    
    builder.row(InlineKeyboardButton(text=get_text(lang_code, 'other_emoji') + " " + get_text(lang_code, 'other_city'), callback_data="city_other"))
    builder.row(InlineKeyboardButton(text=get_text(lang_code, 'done_emoji') + " " + get_text(lang_code, 'done'), callback_data="city_done"))
    
    return builder.as_markup()


def get_days_keyboard(lang_code: str = 'en') -> InlineKeyboardMarkup:
    """Keyboard for selecting number of days"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="3", callback_data="days_3"))
    builder.add(InlineKeyboardButton(text="5", callback_data="days_5"))
    builder.add(InlineKeyboardButton(text="7", callback_data="days_7"))
    builder.add(InlineKeyboardButton(text="10", callback_data="days_10"))
    builder.add(InlineKeyboardButton(text=get_text(lang_code, 'other_emoji') + " " + get_text(lang_code, 'other'), callback_data="days_other"))
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def get_people_keyboard(lang_code: str = 'en') -> InlineKeyboardMarkup:
    """Keyboard for selecting number of people"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="1", callback_data="people_1"))
    builder.add(InlineKeyboardButton(text="2", callback_data="people_2"))
    builder.add(InlineKeyboardButton(text="3", callback_data="people_3"))
    builder.add(InlineKeyboardButton(text="4+", callback_data="people_4plus"))
    builder.adjust(2, 2)
    return builder.as_markup()


def get_translator_keyboard(lang_code: str = 'en') -> InlineKeyboardMarkup:
    """Keyboard for translator question"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅ " + get_text(lang_code, 'yes'), callback_data="translator_yes"))
    builder.add(InlineKeyboardButton(text="❌ " + get_text(lang_code, 'no'), callback_data="translator_no"))
    builder.adjust(2)
    return builder.as_markup()


def get_language_keyboard(lang_code: str = 'en') -> InlineKeyboardMarkup:
    """Keyboard for selecting translator language"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🇷🇺 RU", callback_data="lang_RU"))
    builder.add(InlineKeyboardButton(text="🇬🇧 EN", callback_data="lang_EN"))
    builder.add(InlineKeyboardButton(text="🇫🇷 FR", callback_data="lang_FR"))
    builder.add(InlineKeyboardButton(text="🇩🇪 DE", callback_data="lang_DE"))
    builder.add(InlineKeyboardButton(text=get_text(lang_code, 'other_emoji') + " " + get_text(lang_code, 'other'), callback_data="lang_other"))
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def get_review_keyboard(lang_code: str = 'en') -> InlineKeyboardMarkup:
    """Keyboard for review confirmation"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅ " + get_text(lang_code, 'confirm'), callback_data="review_confirm"))
    builder.add(InlineKeyboardButton(text="✏️ " + get_text(lang_code, 'edit'), callback_data="review_edit"))
    builder.adjust(1)
    return builder.as_markup()


def get_edit_keyboard(lang_code: str = 'en') -> InlineKeyboardMarkup:
    """Keyboard for selecting field to edit"""
    builder = InlineKeyboardBuilder()
    fields = [
        (get_text(lang_code, 'phone_emoji') + " " + get_text(lang_code, 'phone'), "edit_phone"),
        (get_text(lang_code, 'current_city_emoji') + " " + get_text(lang_code, 'current_city'), "edit_current_city"),
        (get_text(lang_code, 'cities_to_visit_emoji') + " " + get_text(lang_code, 'cities_to_visit'), "edit_cities"),
        (get_text(lang_code, 'days_emoji') + " " + get_text(lang_code, 'days'), "edit_days"),
        (get_text(lang_code, 'people_emoji') + " " + get_text(lang_code, 'people'), "edit_people"),
        (get_text(lang_code, 'translator_emoji') + " " + get_text(lang_code, 'translator_text'), "edit_translator"),
        (get_text(lang_code, 'travel_dates_emoji') + " " + get_text(lang_code, 'travel_dates'), "edit_dates"),
    ]
    for text, callback in fields:
        builder.add(InlineKeyboardButton(text=text, callback_data=callback))
    builder.adjust(2)
    return builder.as_markup()


def get_language_selection_keyboard(current_lang_code: str = 'en') -> InlineKeyboardMarkup:
    """Keyboard for initial language selection or changing language"""
    builder = InlineKeyboardBuilder()
    languages = {
        "ru": "🇷🇺 Русский",
        "en": "🇬🇧 English",
        "de": "🇩🇪 Deutsch"
    }

    for lang_code, lang_name in languages.items():
        text = f"{lang_name} ✅" if lang_code == current_lang_code else lang_name
        builder.add(InlineKeyboardButton(text=text, callback_data=f"lang_select_{lang_code}"))
    builder.adjust(1)
    return builder.as_markup()


def get_calendar_keyboard(year: int, month: int, selected_date: str = None, lang_code: str = 'en') -> InlineKeyboardMarkup:
    """Professional calendar keyboard with month navigation"""
    builder = InlineKeyboardBuilder()
    
    # Set locale for month and weekday names
    locale_map = {
        "en": "en_US.UTF-8",
        "ru": "ru_RU.UTF-8",
        "de": "de_DE.UTF-8"
    }
    current_locale = locale_map.get(lang_code, "en_US.UTF-8")
    try:
        locale.setlocale(locale.LC_ALL, current_locale)
    except locale.Error:
        try:
            locale.setlocale(locale.LC_ALL, lang_code + "_" + lang_code.upper() + ".utf8")
        except locale.Error:
            locale.setlocale(locale.LC_ALL, "C") # Fallback to default C locale

    # Month names (dynamically translated)
    # Weekday headers (dynamically translated)
    weekdays = [datetime(2023, 11, 6).replace(day=d).strftime("%a") for d in range(1, 8)] # Start from Monday
    for day_name in weekdays:
        builder.add(InlineKeyboardButton(text=day_name, callback_data="cal_ignore"))
    builder.adjust(7)
    
    # Get calendar for the month
    today = datetime.now().date()
    calendar_month = monthcalendar(year, month)
    
    # Parse selected date if provided
    selected_dt = None
    if selected_date:
        try:
            selected_dt = datetime.strptime(selected_date, "%Y-%m-%d").date()
        except:
            pass
    
    # Days grid
    for week in calendar_month:
        for day in week:
            if day == 0:
                # Empty cell
                builder.add(InlineKeyboardButton(text=" ", callback_data="cal_ignore"))
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                date_obj = datetime(year, month, day).date()
                
                # Check if date is in the past
                is_past = date_obj < today
                
                # Format button text
                if selected_dt and date_obj == selected_dt:
                    text = f"✅{day}"
                elif date_obj == today:
                    text = f"📍{day}"
                elif is_past:
                    text = f"·{day}"
                else:
                    text = str(day)
                
                # Disable past dates
                if is_past:
                    builder.add(InlineKeyboardButton(text=text, callback_data="cal_ignore"))
                else:
                    builder.add(InlineKeyboardButton(text=text, callback_data=f"cal_day_{date_str}"))
        builder.adjust(7)
    
    # Month/year and navigation (below calendar)
    month_name = datetime(year, month, 1).strftime("%B")
    month_str = f"{month_name} {year}"
    builder.row(
        InlineKeyboardButton(text="◀️", callback_data=f"cal_prev_{year}_{month}"),
        InlineKeyboardButton(text=f"{month_name.capitalize()} {year}", callback_data="cal_ignore"), # Capitalize month name
        InlineKeyboardButton(text="▶️", callback_data=f"cal_next_{year}_{month}")
    )
    
    # Action buttons
    builder.row(InlineKeyboardButton(text="🗓️ " + get_text(lang_code, 'cal_skip'), callback_data="cal_skip")) # Translate "Skip" and add emoji
    
    return builder.as_markup()


def get_date_confirmation_keyboard(date_str: str, lang_code: str = 'en') -> InlineKeyboardMarkup:
    """Keyboard for confirming selected date"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text=get_text(lang_code, 'cal_confirm'), callback_data=f"cal_confirm_{date_str}"))
    builder.add(InlineKeyboardButton(text=get_text(lang_code, 'cal_change'), callback_data="cal_change"))
    builder.adjust(2)
    return builder.as_markup()


def get_referral_keyboard(lang_code: str = 'en') -> InlineKeyboardMarkup:
    """Keyboard asking how the user discovered the bot"""
    builder = InlineKeyboardBuilder()
    options = [
        ("referral_instagram", "ref_instagram"),
        ("referral_youtube", "ref_youtube"),
        ("referral_facebook", "ref_facebook"),
        ("referral_website", "ref_website"),
        ("referral_google", "ref_google"),
    ]
    for text_key, callback in options:
        builder.add(InlineKeyboardButton(text=get_text(lang_code, text_key), callback_data=callback))
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text=get_text(lang_code, 'referral_other'), callback_data="ref_other"))
    builder.row(InlineKeyboardButton(text=get_text(lang_code, 'referral_skip'), callback_data="ref_skip"))
    return builder.as_markup()

