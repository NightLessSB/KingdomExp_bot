from aiogram.fsm.state import State, StatesGroup


class TravelForm(StatesGroup):
    phone = State()
    current_city = State()
    cities_to_visit = State()
    other_city = State()
    days = State()
    other_days = State()
    people = State()
    other_people = State()
    need_translator = State()
    translator_language = State()
    other_language = State()
    start_date = State()
    review = State()
    lang_code = State()
    referral_source = State()
    other_referral = State()

