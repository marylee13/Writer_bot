import asyncio
import logging
import random
import json
import os
from datetime import datetime, date, timedelta, time, timezone
from openai import OpenAI
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    LabeledPrice, PreCheckoutQuery, BotCommand, BotCommandScopeChat,
    BotCommandScopeDefault
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    CallbackQueryHandler, MessageHandler, PreCheckoutQueryHandler,
    filters, JobQueue
)

TOKEN = 8322794271:AAHK0l2jgi8JMuzIBfsOMEvvA43Ek18X6ow
PAYMENT_PROVIDER_TOKEN = 390540012:LIVE:92025
ADMIN_USER_ID = 636261142

DATA_FILE = "writers.json"
STATS_FILE = "premium_stats.json"

# ====== OpenAI (optional — falls back to hardcoded responses if key is absent) ======
# the newest OpenAI model is "gpt-5" which was released August 7, 2025.
# do not change this unless explicitly requested by the user
_openai_api_key = os.environ.get("OPENAI_API_KEY")
if _openai_api_key:
    openai_client = OpenAI(api_key=_openai_api_key)
else:
    openai_client = None
    logging.warning("OPENAI_API_KEY is not set — AI features will use hardcoded fallback responses.")

# ====== ПОДПИСКА ======
PREMIUM_PRICE_RUB = 250
PREMIUM_DAYS = 30

PREMIUM_BENEFITS = (
    "☕ <b>Меньше, чем чашка кофе — а пользы на целый месяц</b>\n\n"
    "Всего <b>250 ₽/месяц</b> — и твоя книга пишется быстрее, легче и интереснее.\n\n"
    "Что получишь с Premium:\n\n"
    "✍️ <b>AI-соавтор: «Продолжи текст»</b>\n"
    "Застрял на сцене? Отправь начало — ИИ напишет ~150 слов продолжения в твоём стиле и жанре. "
    "Никакого творческого блока. Никогда.\n\n"
    "🎭 <b>Генератор персонажей</b>\n"
    "Нажми кнопку — получи готовую карточку живого персонажа: имя, внешность, характер, предыстория, "
    "мотивация, сильная сторона и слабость. Всё под твой жанр. "
    "Можно жать сколько угодно раз — каждый раз новый, неожиданный герой.\n\n"
    "💡 <b>3 AI-идеи за раз</b>\n"
    "Каждый раз три уникальные идеи, заточенные под твой жанр — больше вариантов, больше вдохновения.\n\n"
    "🤖 <b>AI-редактор: разбор текста</b>\n"
    "Отправь отрывок — получишь конкретные советы по стилю, темпу и сюжету.\n\n"
    "📅 <b>Еженедельный AI-отчёт</b>\n"
    "Каждое воскресенье — персональный анализ прогресса и мотивирующий совет на неделю.\n\n"
    "🌙 <b>Своё время напоминания</b>\n"
    "Утро, день или вечер — ты сам выбираешь, когда тебя подтолкнуть к работе.\n\n"
    "⭐ <b>Значок Premium в чате авторов</b>\n"
    "Покажи сообществу, что ты серьёзно относишься к своему творчеству.\n\n"
    "─────────────────────\n"
    "6 инструментов профессионального автора.\n"
    "Одна чашка кофе в месяц. Выбор очевиден 😉"
)

# ====== ЧАСОВЫЕ ПОЯСА ======
TIMEZONES = [
    (2,  "UTC+2 · Калининград"),
    (3,  "UTC+3 · Москва, СПб"),
    (4,  "UTC+4 · Самара, Ижевск"),
    (5,  "UTC+5 · Екатеринбург, Уфа"),
    (6,  "UTC+6 · Омск, Астана"),
    (7,  "UTC+7 · Новосибирск, Красноярск"),
    (8,  "UTC+8 · Иркутск, Улан-Удэ"),
    (9,  "UTC+9 · Якутск, Чита"),
    (10, "UTC+10 · Владивосток, Хабаровск"),
    (11, "UTC+11 · Магадан, Сахалин"),
    (12, "UTC+12 · Камчатка, Чукотка"),
]

# ====== ЖАНРЫ ======
GENRES = {
    "fantasy":    "🧙 Фэнтези",
    "sci_fi":     "🚀 Фантастика",
    "detective":  "🔍 Детектив",
    "romance":    "💕 Романтика",
    "historical": "🏰 Исторический",
    "thriller":   "🔪 Триллер",
    "horror":     "👻 Ужасы",
    "ya":         "🌟 Young Adult",
    "other":      "✍️ Другое",
}

FALLBACK_QUOTES = {
    "fantasy":    "Каждый мир начинается с первого слова — напиши его.",
    "sci_fi":     "Будущее существует только в воображении тех, кто его записывает.",
    "detective":  "Разгадка ждёт — но сначала её нужно придумать.",
    "romance":    "Любовь оживает только тогда, когда её описывают.",
    "historical": "История помнит тех, кто её записывает.",
    "thriller":   "Напряжение строится словами — пора добавить их.",
    "horror":     "Страх живёт в деталях — пиши подробнее.",
    "ya":         "Юность — лучшее время для историй, которые меняют мир.",
    "other":      "Пиши плохо — редактировать можно только написанное.",
}

FALLBACK_IDEAS = {
    "fantasy":    "Придворный маг уже двадцать лет симулирует способности — и вот его раскрыли. Не враги, а лучший ученик, который пришёл не с доносом, а с просьбой научить его тому же.",
    "sci_fi":     "Бортовой журнал станции ведут трое сменщиков. Только после года полёта один из них замечает: записи двух других написаны одним почерком.",
    "detective":  "Следователь закрывает дело — самоубийство, всё сходится. Через неделю ему звонит мертвец. Не с угрозой, а с благодарностью.",
    "romance":    "Они расстались пять лет назад без скандала — просто разошлись. Теперь оба на свадьбе общего друга, и никто из них не привёл пару.",
    "historical": "Горничная в богатом доме умеет читать — этого никто не знает. Каждую ночь она читает письма хозяина и постепенно понимает, что он готовит что-то, что изменит жизнь её семьи.",
    "thriller":   "Женщина замечает, что сосед каждое утро уходит в 7:14 и возвращается в 19:30 — уже три года. Однажды он возвращается в полдень, и она понимает, что смотрела слишком внимательно.",
    "horror":     "Ребёнок перестал бояться темноты после переезда в новый дом. Родители рады. Только соседка, узнав об этом, срочно уехала, ничего не объяснив.",
    "ya":         "Новенькая в классе сразу знает клички всех одноклассников — те, что придумали сами про себя, не вслух. Это никого не смешит.",
    "other":      "Двое на похоронах не знакомы, но оба плачут по-настоящему. В конце один подходит к другому и говорит: «Я не знал его. А вы?»",
}

FALLBACK_TIPS = {
    "fantasy":    "Магия работает убедительно только тогда, когда у неё есть цена. Читатель верит не в саму систему магии, а в то, чего она стоит герою — усилий, здоровья, потери чего-то важного. Придумай, что твой герой отдаёт каждый раз, когда использует свою силу.",
    "sci_fi":     "Технология сама по себе не делает историю научной фантастикой — её делает вопрос «что это меняет в людях?». Возьми любое устройство или открытие в твоём мире и спроси: как оно меняет отношения, власть, одиночество? Туда и копай.",
    "detective":  "Лучшие детективные истории — не про «кто это сделал», а про «почему люди скрывают правду». Каждый свидетель в твоей сцене что-то утаивает — не обязательно о преступлении, но о себе. Это делает допрос живым.",
    "romance":    "Напряжение в романтике держится не на том, что герои не могут быть вместе, а на том, что они боятся. Попробуй написать сцену, где оба хотят одного и того же — но каждый убеждён, что второй не хочет. Это работает лучше любых внешних препятствий.",
    "historical": "Самая распространённая ошибка в историческом романе — современные реакции в старой одежде. Прежде чем писать сцену, спроси: а что бы этот человек в это время считал само собой разумеющимся? Это и есть настоящая эпоха.",
    "thriller":   "Саспенс — это не тайна, а ожидание. Читатель должен знать, что опасность существует, раньше героя. Попробуй дать читателю информацию, которой у героя ещё нет — и смотри, как напряжение само собой нарастает.",
    "horror":     "Страх работает через обыденность, а не через монстров. Самое жуткое — когда знакомое начинает вести себя неправильно: привычный звук, чужой взгляд из родного лица, слова, которые почти верны. Найди в своей сцене одну такую деталь.",
    "ya":         "Подростковые герои убедительны, когда хотят одного, но нуждаются в другом — и сами этого не понимают. Читатель видит это раньше героя, и именно это создаёт эмпатию. Поставь своему герою цель — и придумай, чего он на самом деле ищет.",
    "other":      "Если сцена не идёт, смени точку зрения — буквально. Перепиши абзац от лица другого человека в той же комнате. Часто оказывается, что история рассказывалась не тем голосом, и это сразу становится очевидным.",
}

# ====== ЧЕЛЛЕНДЖИ ======
CHALLENGES = [
    {"id": "c1",  "title": "⚡ Спринт 25 минут",        "desc": "Поставь таймер на 25 минут и пиши без остановки — не редактируй, просто пиши.",       "target": 300},
    {"id": "c2",  "title": "🎭 Новый персонаж",          "desc": "Придумай второстепенного героя: внешность, одна странная привычка и тайна.",            "target": 150},
    {"id": "c3",  "title": "🔄 Смени точку зрения",      "desc": "Перепиши уже написанную сцену от лица другого персонажа.",                              "target": 200},
    {"id": "c4",  "title": "🌍 Опиши место",             "desc": "Напиши описание локации так, чтобы читатель почувствовал запах и температуру.",         "target": 150},
    {"id": "c5",  "title": "💬 Только диалог",           "desc": "Сцена без описаний — только речь. Пусть слова говорят сами за себя.",                  "target": 200},
    {"id": "c6",  "title": "🏃 Быстрый старт",           "desc": "Начни новую главу прямо сейчас. Первые 200 слов — самое трудное.",                     "target": 200},
    {"id": "c7",  "title": "🕵️ Говорящие детали",        "desc": "Опиши три предмета в комнате так, чтобы каждый раскрывал характер хозяина.",           "target": 150},
    {"id": "c8",  "title": "❤️ Внутренний монолог",      "desc": "Напиши, о чём думает герой в один из ключевых моментов истории.",                      "target": 200},
    {"id": "c9",  "title": "🌙 Ночная атмосфера",        "desc": "Сцена, которая происходит ночью — поймай особое настроение и тишину.",                 "target": 250},
    {"id": "c10", "title": "⏰ Поворот сюжета",          "desc": "Добавь неожиданный твист в конце уже написанной сцены или напиши новую с поворотом.",  "target": 200},
    {"id": "c11", "title": "✍️ Без редактирования",      "desc": "Пиши 15 минут, не исправляя ни слова. Поток сознания — это тоже письмо.",              "target": 200},
    {"id": "c12", "title": "🎬 Кинематографичная сцена", "desc": "Только действия и речь — никаких мыслей персонажа. Как в кино.",                       "target": 250},
    {"id": "c13", "title": "💥 Конфликт в диалоге",      "desc": "Напиши сцену, где два персонажа спорят — но на самом деле говорят о разном.",          "target": 200},
    {"id": "c14", "title": "🌅 Первая строка",           "desc": "Придумай и запиши 5 вариантов первой строки для новой главы или рассказа.",             "target": 100},
]

MARATHONS = [
    {"id": "habit21",  "name": "🌱 Привычка за 21 день",    "days": 21, "daily_goal": 200,  "desc": "21 день по 200 слов — научись писать каждый день"},
    {"id": "sprint7",  "name": "🏃 Недельный спринт",       "days": 7,  "daily_goal": 300,  "desc": "7 дней по 300 слов — разгони писательскую мышцу"},
    {"id": "steady14", "name": "📆 Стабильный ритм 14 дней","days": 14, "daily_goal": 500,  "desc": "14 дней по 500 слов — войди в настоящий рабочий ритм"},
    {"id": "nano30",   "name": "📚 NaNoWriMo-стиль 30 дней","days": 30, "daily_goal": 1667, "desc": "30 дней по 1 667 слов — полноценный черновик романа"},
]

# ====== СИСТЕМА УРОВНЕЙ ======
LEVELS = [
    (0,       "🌱 Росток"),
    (1_000,   "✏️ Новичок"),
    (5_000,   "📓 Ученик"),
    (15_000,  "📚 Автор"),
    (30_000,  "🖊️ Писатель"),
    (75_000,  "🏆 Мастер"),
    (150_000, "👑 Романист"),
    (300_000, "🌟 Легенда"),
]

def al_str(n: int) -> str:
    """Авторские листы в скобках. 1 а.л. = 40 000 знаков ≈ 6 000 слов."""
    if n < 300:
        return ""
    al = n / 6000
    return f" ({al:.1f} а.л.)"

def get_level(total_words: int) -> tuple[int, str, int | None]:
    level_index = 0
    for i, (threshold, _) in enumerate(LEVELS):
        if total_words >= threshold:
            level_index = i
    label = LEVELS[level_index][1]
    next_threshold = LEVELS[level_index + 1][0] if level_index + 1 < len(LEVELS) else None
    return level_index, label, next_threshold

# ====== ЗАГРУЗКА ДАННЫХ ======
def load():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

FEATURE_PROMOS = [
    "Знаешь, что спасает, когда не знаешь, о чём писать? Одна неожиданная идея. Загляни в раздел «💡 Идеи» — там как раз такие.",
    "Кстати, ты знал, что бот помнит каждый твой день письма? Напиши <b>/report 100</b> — и серия продолжится. Маленькие числа тоже считаются.",
    "Есть авторы, которые пишут по 200 слов в день — и за год заканчивают роман. Просто хотел напомнить, что маленький шаг сегодня лучше большого никогда.",
    "Дедлайн — это не страшно, это освобождающе. Попробуй поставить дату в разделе «🎯 Цель» — и посмотри, как начнёт двигаться рукопись.",
    "Один литературный приём может полностью изменить сцену. Загляни в «✍️ Приёмы» — там что-то для твоего жанра. Может, именно то, чего не хватало.",
    "Тут есть авторы, которые пишут каждый день уже несколько недель подряд. Их секрет? Серия дней. Попробуй не прерываться хотя бы неделю — это затягивает.",
    "Если напоминание в 20:00 не попадает в твой ритм — его можно перенести. Просто напиши /reminder и время, которое подходит именно тебе.",
    "В этом чате есть другие авторы — живые люди с рукописями и творческими кризисами. Можно написать им через «💬 Чат авторов». Иногда это помогает больше, чем советы.",
    "Бот знает твой жанр и подбирает идеи и советы под него. Если жанр ещё не выбран — это буквально 10 секунд в разделе «📚 Мой жанр».",
    "Утром в 9:00 и вечером в 21:00 бот присылает что-то вдохновляющее. Если ещё не получал — возможно, часовой пояс сбился. Поправь через /timezone +3",
    "Ты написал больше, чем думаешь. Загляни в «📊 Моя статистика» — там авторские листы, уровень и серия дней. Иногда цифры удивляют.",
    "Когда нет слов — попробуй просто открыть «💡 Идеи» и прочитать. Не обязательно использовать. Просто разогнать мысли.",
    "Писать каждый день необязательно по много. Бот считает любое число — даже 50 слов. Главное, чтобы день не был пустым.",
    "Уровни в боте идут от «Начинающего» до «Легенды». Где ты сейчас — можно посмотреть в статистике. Интересно, кто из чата добрался дальше всех?",
    "Если чувствуешь, что застрял — попробуй написать что-нибудь плохо. Специально. Потом отредактируешь. Но сначала нужен материал.",
]
PROMO_STATE_FILE = "promo_state.json"

def load_promo_state() -> dict:
    if os.path.exists(PROMO_STATE_FILE):
        try:
            with open(PROMO_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"index": 0, "order": list(range(len(FEATURE_PROMOS)))}

def save_promo_state(state: dict):
    try:
        with open(PROMO_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
    except Exception as e:
        logging.warning(f"Failed to save promo state: {e}")

_promo_state = load_promo_state()
# Если порядок ещё не перемешан или не совпадает по длине — инициализируем заново
if len(_promo_state.get("order", [])) != len(FEATURE_PROMOS):
    import random as _random
    order = list(range(len(FEATURE_PROMOS)))
    _random.shuffle(order)
    _promo_state = {"index": 0, "order": order}
    save_promo_state(_promo_state)

users = load()
awaiting_chat_message = set()
awaiting_chat_reply = set()       # приватный ответ
awaiting_chat_reply_pub = set()   # публичный ответ
pending_reply_to: dict = {}       # uid -> target_uid
awaiting_analyze_text = set()
awaiting_continue_text = set()
awaiting_daily_goal = set()
awaiting_book_deadline = set()
awaiting_book_pace = set()
pending_book_pace: dict = {}  # uid -> "day" | "week" | "month"
awaiting_dev_question = set()
awaiting_dev_reply = set()        # ожидаем текст ответа от администратора
pending_dev_reply: dict = {}      # admin_uid -> target_user_id

# ====== СТАТИСТИКА КЛИКОВ ======
def load_stats():
    if not os.path.exists(STATS_FILE):
        return {"premium_info_clicks": 0, "premium_buy_clicks": 0, "unique_interested": []}
    with open(STATS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_stats(data):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

click_stats = load_stats()

# ====== ПОЛЬЗОВАТЕЛЬ ======
def get_user(user_id, name):
    uid = str(user_id)
    if uid not in users:
        users[uid] = {
            "name": name,
            "goal": 500,
            "words_today": 0,
            "total_words": 0,
            "streak": 0,
            "last_day": "",
            "genre": "other",
            "chat_enabled": True,
            "premium_until": "",
            "reminder_hour": 20,
            "reminder_minute": 0,
            "weekly_words": [],
        }
    u = users[uid]
    for key, default in [
        ("genre", "other"), ("chat_enabled", True),
        ("premium_until", ""), ("reminder_hour", 20),
        ("reminder_minute", 0), ("weekly_words", []),
        ("tz_offset", 3), ("last_morning_tip", ""), ("last_evening_tip", ""),
        ("deadline_date", ""), ("deadline_goal", 0), ("last_deadline_check", ""),
        ("deadline_pace_words", 0), ("deadline_pace_period", ""),
        ("active_marathon", {}), ("challenges_done", 0),
        ("last_promo_idx", -1), ("last_promo_ts", 0),
        ("onboarded", False),
    ]:
        if key not in u:
            u[key] = default
    # Пользователь с выбранным жанром или написанными словами считается прошедшим настройку
    if not u["onboarded"] and (u.get("genre", "other") != "other" or u.get("total_words", 0) > 0 or u.get("last_day", "") != ""):
        u["onboarded"] = True
    return u

def is_premium(user: dict) -> bool:
    if not user.get("premium_until"):
        return False
    try:
        return date.fromisoformat(user["premium_until"]) >= date.today()
    except ValueError:
        return False

def premium_badge(user: dict) -> str:
    return "⭐ " if is_premium(user) else ""

# ====== AI генерация ======
def _generate_ideas_sync(genre_key: str, count: int = 1):
    if openai_client is None:
        raise RuntimeError("OpenAI client is not configured")
    genre_name = GENRES.get(genre_key, "")
    prompt = (
        f"Ты — опытный романист, который любит делиться идеями с друзьями-писателями. "
        f"Твой друг пишет в жанре «{genre_name}» и застрял — подкинь ему {count} живых идеи. "
        f"\n\nКаждая идея должна:\n"
        f"- быть про конкретного человека в конкретной ситуации, а не абстрактную концепцию\n"
        f"- содержать понятный человеческий конфликт или эмоцию (ревность, вина, страх потери, желание, стыд)\n"
        f"- быть достаточно конкретной, чтобы сразу представить сцену\n"
        f"- звучать как идея, которую мог бы подсказать умный друг, а не как задание из учебника\n"
        f"\nНЕ начинай идеи с «Что если» — сразу описывай ситуацию или персонажа. "
        f"Избегай заезженных клише жанра. Каждая идея — 2–3 живых предложения. "
        f"Пронумеруй. Только русский язык, разговорный стиль, никакого канцелярита."
    )
    response = openai_client.chat.completions.create(
        model="gpt-5",
        messages=[{"role": "user", "content": prompt}]
    )
    content = response.choices[0].message.content
    return content.strip() if content else None

async def generate_ideas(genre_key: str = "other", count: int = 1):
    try:
        result = await asyncio.to_thread(_generate_ideas_sync, genre_key, count)
        if result:
            return result
    except Exception as e:
        logging.warning(f"OpenAI idea generation failed: {e}")
    ideas = [FALLBACK_IDEAS.get(genre_key, FALLBACK_IDEAS["other"])]
    return "\n".join(f"{i+1}. {idea}" for i, idea in enumerate(ideas))

def _generate_quote_sync(genre_key: str, words_today: int, streak: int):
    if openai_client is None:
        raise RuntimeError("OpenAI client is not configured")
    genre_name = GENRES.get(genre_key, "")
    response = openai_client.chat.completions.create(
        model="gpt-5",
        messages=[{"role": "user", "content": (
            f"Ты помогаешь автору, пишущему в жанре «{genre_name}». "
            f"Сегодня он написал {words_today} слов, его серия — {streak} дней подряд. "
            f"Напиши одно короткое мотивирующее высказывание с учётом жанра и прогресса. "
            f"Ответь одним предложением на русском языке."
        )}]
    )
    content = response.choices[0].message.content
    return content.strip() if content else None

async def generate_quote(genre_key: str, words_today: int, streak: int):
    try:
        result = await asyncio.to_thread(_generate_quote_sync, genre_key, words_today, streak)
        if result:
            return result
    except Exception as e:
        logging.warning(f"OpenAI quote generation failed: {e}")
    return FALLBACK_QUOTES.get(genre_key, FALLBACK_QUOTES["other"])

def _generate_tip_sync(genre_key: str):
    if openai_client is None:
        raise RuntimeError("OpenAI client is not configured")
    genre_name = GENRES.get(genre_key, "")
    response = openai_client.chat.completions.create(
        model="gpt-5",
        messages=[{"role": "user", "content": (
            f"Ты — опытный редактор и писатель, который ведёт мастер-классы. "
            f"Дай один конкретный писательский совет для автора, работающего в жанре «{genre_name}». "
            f"\nСовет должен быть про то, КАК писать лучше: техники, приёмы, крючки, ритм, "
            f"структура сцен, работа с диалогом, темп, точка зрения, атмосфера — "
            f"что угодно из писательского ремесла, адаптированное под этот жанр. "
            f"\nПравила:\n"
            f"- говори как умный друг-редактор, не как учебник\n"
            f"- объясни приём и сразу покажи, как его применить прямо сейчас\n"
            f"- конкретно, живо, без воды и общих слов вроде «пиши от души»\n"
            f"- 3–5 предложений\n"
            f"- никаких вступлений вроде «Вот совет:» — сразу по делу\n"
            f"Только русский язык."
        )}]
    )
    content = response.choices[0].message.content
    return content.strip() if content else None

async def generate_tip(genre_key: str):
    try:
        result = await asyncio.to_thread(_generate_tip_sync, genre_key)
        if result:
            return result
    except Exception as e:
        logging.warning(f"OpenAI tip generation failed: {e}")
    return FALLBACK_TIPS.get(genre_key, FALLBACK_TIPS["other"])

def _analyze_text_sync(genre_key: str, text: str):
    if openai_client is None:
        raise RuntimeError("OpenAI client is not configured")
    genre_name = GENRES.get(genre_key, "")
    response = openai_client.chat.completions.create(
        model="gpt-5",
        messages=[{"role": "user", "content": (
            f"Ты редактор, помогающий автору в жанре «{genre_name}». "
            f"Проанализируй следующий отрывок и дай краткие советы по стилю, темпу и сюжету (3–5 пунктов). "
            f"Будь конкретен и доброжелателен. Ответь на русском языке.\n\nОтрывок:\n{text}"
        )}]
    )
    content = response.choices[0].message.content
    return content.strip() if content else None

async def analyze_text(genre_key: str, text: str):
    try:
        result = await asyncio.to_thread(_analyze_text_sync, genre_key, text)
        if result:
            return result
    except Exception as e:
        logging.warning(f"OpenAI text analysis failed: {e}")
    return "Не удалось выполнить анализ. Попробуй позже."

def _continue_text_sync(genre_key: str, name: str, text: str):
    if openai_client is None:
        raise RuntimeError("OpenAI client is not configured")
    genre_name = GENRES.get(genre_key, "")
    response = openai_client.chat.completions.create(
        model="gpt-5",
        messages=[{"role": "user", "content": (
            f"Ты соавтор, помогающий писателю {name} в жанре «{genre_name}». "
            f"Автор прислал начало сцены. Продолжи текст органично: сохрани стиль, голос и темп автора. "
            f"Напиши примерно 120–150 слов продолжения на русском языке. "
            f"Не повторяй уже написанное, просто продолжай с того места, где автор остановился. "
            f"Дай только текст продолжения, без пояснений.\n\nТекст автора:\n{text}"
        )}]
    )
    content = response.choices[0].message.content
    return content.strip() if content else None

async def continue_text(genre_key: str, name: str, text: str):
    try:
        result = await asyncio.to_thread(_continue_text_sync, genre_key, name, text)
        if result:
            return result
    except Exception as e:
        logging.warning(f"OpenAI text continuation failed: {e}")
    return "Не удалось написать продолжение. Попробуй позже."

def _generate_character_sync(genre_key: str):
    if openai_client is None:
        raise RuntimeError("OpenAI client is not configured")
    genre_name = GENRES.get(genre_key, "")
    response = openai_client.chat.completions.create(
        model="gpt-5",
        messages=[{"role": "user", "content": (
            f"Создай детального, живого персонажа для произведения в жанре «{genre_name}». "
            f"Оформи карточку персонажа строго в следующем формате на русском языке:\n\n"
            f"🧑 Имя: [имя и фамилия, уместные для жанра]\n"
            f"🎂 Возраст: [возраст]\n"
            f"👁 Внешность: [2–3 запоминающиеся детали]\n"
            f"🧠 Характер: [3–4 черты, включая противоречие]\n"
            f"📖 Предыстория: [2–3 предложения — что сформировало персонажа]\n"
            f"🎯 Мотивация: [чего хочет и почему]\n"
            f"⚡ Сильная сторона: [одна ключевая сила]\n"
            f"💔 Слабость: [уязвимость или внутренний конфликт]\n"
            f"🗣 Речевая привычка: [одна особенность речи или жест]\n\n"
            f"Персонаж должен быть неожиданным, не банальным. Только карточка, без вступлений."
        )}]
    )
    content = response.choices[0].message.content
    return content.strip() if content else None

async def generate_character(genre_key: str):
    try:
        result = await asyncio.to_thread(_generate_character_sync, genre_key)
        if result:
            return result
    except Exception as e:
        logging.warning(f"OpenAI character generation failed: {e}")
    return "Не удалось создать персонажа. Попробуй позже."

def _weekly_report_sync(name: str, genre_key: str, total_words: int, streak: int, words_this_week: int):
    if openai_client is None:
        raise RuntimeError("OpenAI client is not configured")
    genre_name = GENRES.get(genre_key, "")
    response = openai_client.chat.completions.create(
        model="gpt-5",
        messages=[{"role": "user", "content": (
            f"Ты наставник писателя. Автор {name} пишет в жанре «{genre_name}». "
            f"За эту неделю написано {words_this_week} слов, всего {total_words} слов, серия {streak} дней. "
            f"Напиши короткий вдохновляющий еженедельный отчёт с анализом прогресса и советом на следующую неделю. "
            f"Ответь на русском языке, 3–4 предложения."
        )}]
    )
    content = response.choices[0].message.content
    return content.strip() if content else None

# ====== КЛАВИАТУРЫ ======
def main_menu_keyboard(user: dict):
    premium = is_premium(user)
    keyboard = [
        [InlineKeyboardButton("🎯 Установить цель", callback_data="goal")],
        [InlineKeyboardButton("📝 Отчет о словах", callback_data="report")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("💡 Идея дня", callback_data="idea"),
         InlineKeyboardButton("✍️ Приёмы", callback_data="prompt")],
        [InlineKeyboardButton("📚 Мой жанр", callback_data="genre_menu"),
         InlineKeyboardButton("💬 Чат авторов", callback_data="chat_menu")],
        [InlineKeyboardButton("🏃 Челленджи и марафоны", callback_data="challenge_menu")],
        [InlineKeyboardButton("💀 Жёсткий дедлайн", callback_data="deadline_menu"),
         InlineKeyboardButton("🌍 Часовой пояс", callback_data="tz_menu")],
    ]
    if premium:
        keyboard.append([
            InlineKeyboardButton("🤖 Разбор текста", callback_data="analyze"),
            InlineKeyboardButton("✍️ Продолжи текст", callback_data="continue_text_btn"),
        ])
        keyboard.append([
            InlineKeyboardButton("🎭 Создать персонажа", callback_data="gen_character_btn"),
        ])
    else:
        keyboard.append([InlineKeyboardButton("☕ Premium — как чашка кофе!", callback_data="premium_info")])
    keyboard.append([InlineKeyboardButton("✉️ Вопрос разработчику", callback_data="ask_dev")])
    return InlineKeyboardMarkup(keyboard)

def timezone_keyboard():
    keyboard = []
    for i in range(0, len(TIMEZONES), 2):
        row = [InlineKeyboardButton(TIMEZONES[i][1], callback_data=f"settz_{TIMEZONES[i][0]}")]
        if i + 1 < len(TIMEZONES):
            row.append(InlineKeyboardButton(TIMEZONES[i+1][1], callback_data=f"settz_{TIMEZONES[i+1][0]}"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("« Назад", callback_data="back_menu")])
    return InlineKeyboardMarkup(keyboard)

def challenge_main_keyboard(has_marathon: bool):
    kb = [
        [InlineKeyboardButton("🎯 Челлендж дня", callback_data="challenge_daily")],
        [InlineKeyboardButton("🏅 Список марафонов", callback_data="marathon_menu")],
    ]
    if has_marathon:
        kb.append([InlineKeyboardButton("📊 Мой марафон", callback_data="marathon_status")])
    kb.append([InlineKeyboardButton("« Назад", callback_data="back_menu")])
    return InlineKeyboardMarkup(kb)

def marathon_list_keyboard():
    rows = []
    for i, m in enumerate(MARATHONS):
        rows.append([InlineKeyboardButton(f"{m['name']} ({m['daily_goal']} сл/день)", callback_data=f"marathon_join_{i}")])
    rows.append([InlineKeyboardButton("« Назад", callback_data="challenge_menu")])
    return InlineKeyboardMarkup(rows)

def genre_keyboard():
    keyboard = []
    items = list(GENRES.items())
    for i in range(0, len(items), 2):
        row = [InlineKeyboardButton(items[i][1], callback_data=f"setgenre_{items[i][0]}")]
        if i + 1 < len(items):
            row.append(InlineKeyboardButton(items[i + 1][1], callback_data=f"setgenre_{items[i + 1][0]}"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("« Назад", callback_data="back_menu")])
    return InlineKeyboardMarkup(keyboard)

def chat_menu_keyboard(chat_enabled: bool):
    toggle_label = "🔕 Отключить сообщения" if chat_enabled else "🔔 Включить сообщения"
    keyboard = [
        [InlineKeyboardButton("✍️ Написать в чат", callback_data="chat_write")],
        [InlineKeyboardButton(toggle_label, callback_data="chat_toggle")],
        [InlineKeyboardButton("« Назад", callback_data="back_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)

def premium_keyboard():
    keyboard = [
        [InlineKeyboardButton("☕ Оформить за 250 ₽/месяц", callback_data="premium_buy")],
        [InlineKeyboardButton("« Назад в меню", callback_data="back_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)

# ====== РАССЫЛКА В ЧАТ ======
async def broadcast_chat_message(
    bot, sender_id: int, sender_name: str, genre_key: str,
    text: str = "", premium: bool = False,
    photo_id: str = None, document_id: str = None, doc_name: str = ""
):
    genre_label = GENRES.get(genre_key, "✍️ Другое")
    badge = "⭐ " if premium else ""
    header = f"💬 Чат авторов\n{badge}{sender_name} [{genre_label}]:"
    reply_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("↩️ Ответить", callback_data=f"chat_reply_{sender_id}")
    ]])
    sent = 0
    for user_id_str, user in users.items():
        if int(user_id_str) == sender_id:
            continue
        if not user.get("chat_enabled", True):
            continue
        try:
            if photo_id:
                caption = f"{header}\n\n{text}" if text else header
                await bot.send_photo(chat_id=int(user_id_str), photo=photo_id,
                                     caption=caption, reply_markup=reply_kb)
            elif document_id:
                caption = f"{header}\n\n{text}" if text else header
                await bot.send_document(chat_id=int(user_id_str), document=document_id,
                                        caption=caption, reply_markup=reply_kb)
            else:
                await bot.send_message(chat_id=int(user_id_str),
                                       text=f"{header}\n\n{text}", reply_markup=reply_kb)
            sent += 1
        except Exception as e:
            logging.warning(f"Could not send chat to {user_id_str}: {e}")
    return sent

# ====== КОМАНДЫ ======
def onboard_genre_keyboard():
    """Клавиатура выбора жанра для онбординга (ob_ префикс)."""
    items = list(GENRES.items())
    keyboard = []
    for i in range(0, len(items), 2):
        row = [InlineKeyboardButton(items[i][1], callback_data=f"ob_genre_{items[i][0]}")]
        if i + 1 < len(items):
            row.append(InlineKeyboardButton(items[i + 1][1], callback_data=f"ob_genre_{items[i + 1][0]}"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("Пропустить →", callback_data="ob_goal_step")])
    return InlineKeyboardMarkup(keyboard)

def onboard_goal_keyboard():
    """Клавиатура быстрого выбора дневной нормы."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("300 слов", callback_data="ob_goal_300"),
            InlineKeyboardButton("500 слов", callback_data="ob_goal_500"),
        ],
        [
            InlineKeyboardButton("1 000 слов", callback_data="ob_goal_1000"),
            InlineKeyboardButton("2 000 слов", callback_data="ob_goal_2000"),
        ],
        [InlineKeyboardButton("✏️ Своё число", callback_data="ob_goal_custom")],
        [InlineKeyboardButton("Пропустить →", callback_data="ob_done")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id, update.effective_user.first_name)
    # Новый — только если ни разу не проходил настройку и ничего не писал
    is_new = (
        not user.get("onboarded", False)
        and user.get("total_words", 0) == 0
        and user.get("last_day", "") == ""
        and user.get("genre", "other") == "other"
    )
    save(users)

    if is_new:
        welcome_text = (
            f"Привет, {user['name']}! 👋\n\n"
            "Я — <b>«Пиши или умри»</b>, твой личный помощник автора.\n\n"
            "Вот что я умею:\n"
            "✍️ Считаю слова и веду статистику\n"
            "💡 Генерирую идеи и советы по твоему жанру\n"
            "🔥 Держу серию дней и повышаю уровень\n"
            "📖 Слежу за дедлайном книги\n"
            "⏰ Напоминаю писать в удобное время\n\n"
            "Давай настроим тебя за минуту — это 2 простых шага!"
        )
        gif_path = "welcome.gif"
        if os.path.exists(gif_path):
            with open(gif_path, "rb") as gif:
                await update.message.reply_animation(
                    animation=gif,
                    caption=welcome_text,
                    parse_mode="HTML",
                )
        else:
            await update.message.reply_text(welcome_text, parse_mode="HTML")

        await update.message.reply_text(
            "📚 <b>Шаг 1 из 2 — Выбери жанр</b>\n\n"
            "В каком жанре пишешь? Бот подберёт идеи, советы и мотивацию именно под твой стиль:",
            parse_mode="HTML",
            reply_markup=onboard_genre_keyboard()
        )
    else:
        welcome_text = (
            f"С возвращением, {user['name']}! 👋\n"
            "Открывай документ — твоя история ждёт.\n\n"
            "💬 <b>Чат авторов</b> включён — ты видишь сообщения других авторов. "
            "Отключить можно в меню «💬 Чат авторов»."
        )
        gif_path = "welcome.gif"
        if os.path.exists(gif_path):
            with open(gif_path, "rb") as gif:
                await update.message.reply_animation(
                    animation=gif,
                    caption=welcome_text,
                    parse_mode="HTML",
                    reply_markup=main_menu_keyboard(user)
                )
        else:
            await update.message.reply_text(
                welcome_text,
                parse_mode="HTML",
                reply_markup=main_menu_keyboard(user)
            )

async def goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id, update.effective_user.first_name)
    try:
        g = int(context.args[0])
        user["goal"] = g
        save(users)
        await update.message.reply_text(f"Новая цель установлена: {g} слов")
    except (IndexError, ValueError):
        await update.message.reply_text("Использование: /goal <число>")

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id, update.effective_user.first_name)
    try:
        words = int(context.args[0])
        today = str(date.today())
        old_level_idx, _, _ = get_level(user["total_words"])
        if user["last_day"] != today:
            user["words_today"] = 0
            user["streak"] += 1
        user["last_day"] = today
        user["words_today"] += words
        user["total_words"] += words
        # track weekly words
        weekly = user.get("weekly_words", [])
        weekly.append({"date": today, "words": words})
        user["weekly_words"] = weekly[-70:]
        save(users)
        genre_key = user.get("genre", "other")
        quote = await generate_quote(genre_key, user["words_today"], user["streak"])
        new_level_idx, new_level_label, next_threshold = get_level(user["total_words"])
        prem = "⭐ Premium активна\n" if is_premium(user) else ""
        progress_bar = ""
        if next_threshold:
            filled = int((user["total_words"] / next_threshold) * 10)
            progress_bar = f"\nПрогресс до следующего уровня: [{'█' * filled}{'░' * (10 - filled)}]"
        level_up_msg = ""
        if new_level_idx > old_level_idx:
            level_up_msg = f"\n\n🎉 <b>НОВЫЙ УРОВЕНЬ: {new_level_label}!</b>\nТы достиг нового рубежа — продолжай писать!"
        # Дедлайн: прогресс
        deadline_msg = ""
        dl_date = user.get("deadline_date", "")
        dl_goal = user.get("deadline_goal", 0)
        if dl_date:
            try:
                days_left = (date.fromisoformat(dl_date) - date.today()).days
                if dl_goal:
                    words_left = max(0, dl_goal - user["total_words"])
                    if days_left > 0 and words_left > 0:
                        pace = words_left // days_left
                        deadline_msg = f"\n\n💀 <b>Дедлайн</b>: {dl_date}\nОсталось: {words_left} слов за {days_left} д. (~{pace}/день)"
                    elif words_left == 0:
                        deadline_msg = "\n\n🏆 <b>Цель дедлайна достигнута!</b> Ты сделал это!"
                else:
                    if days_left >= 0:
                        deadline_msg = f"\n\n📖 <b>Книга</b>: {days_left} дн. до дедлайна ({dl_date})"
            except ValueError:
                pass
        await update.message.reply_text(
            f"{prem}"
            f"Сегодня написано: {user['words_today']} слов{al_str(user['words_today'])}\n"
            f"Всего: {user['total_words']} слов{al_str(user['total_words'])}\n"
            f"Серия дней: {user['streak']}\n"
            f"Уровень: {new_level_label}{progress_bar}\n\n"
            f"💬 {quote}"
            f"{level_up_msg}{deadline_msg}",
            parse_mode="HTML"
        )
    except (IndexError, ValueError):
        await update.message.reply_text("Использование: /report <число>")

async def reminder_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id, update.effective_user.first_name)
    if not is_premium(user):
        await update.message.reply_text(
            "⭐ Настройка времени напоминания — это Premium-функция.\n"
            "Оформи подписку в главном меню."
        )
        return
    try:
        parts = context.args[0].split(":")
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError
        user["reminder_hour"] = h
        user["reminder_minute"] = m
        save(users)
        await update.message.reply_text(f"🌙 Время напоминания установлено: {h:02d}:{m:02d}")
    except (IndexError, ValueError, AttributeError):
        await update.message.reply_text("Использование: /reminder ЧЧ:ММ  (например: /reminder 09:00)")

async def deadline_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id, update.effective_user.first_name)
    if context.args and context.args[0].lower() == "off":
        user["deadline_date"] = ""
        user["deadline_goal"] = 0
        user["last_deadline_check"] = ""
        save(users)
        await update.message.reply_text("✅ Дедлайн отменён.")
        return
    try:
        dl_date_str = context.args[0]
        dl_goal = int(context.args[1])
        deadline_date = date.fromisoformat(dl_date_str)
        if deadline_date <= date.today():
            await update.message.reply_text("❌ Дата дедлайна должна быть в будущем.")
            return
        if dl_goal <= 0:
            await update.message.reply_text("❌ Цель должна быть больше нуля слов.")
            return
        days_left = (deadline_date - date.today()).days
        words_left = max(0, dl_goal - user["total_words"])
        pace = words_left // max(1, days_left)
        user["deadline_date"] = dl_date_str
        user["deadline_goal"] = dl_goal
        user["last_deadline_check"] = ""
        save(users)
        await update.message.reply_text(
            f"💀 <b>Жёсткий дедлайн установлен!</b>\n\n"
            f"Цель: <b>{dl_goal} слов{al_str(dl_goal)}</b> к <b>{dl_date_str}</b>\n"
            f"Дней: {days_left}\n"
            f"Нужно писать: ~<b>{pace} слов/день</b>\n\n"
            f"Я буду следить. Не подведи себя.",
            parse_mode="HTML"
        )
    except (IndexError, ValueError, TypeError):
        await update.message.reply_text(
            "Использование: /deadline ГГГГ-ММ-ДД СЛОВА\n"
            "Пример: /deadline 2026-05-01 50000\n\n"
            "Чтобы отменить: /deadline off"
        )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    awaiting_chat_message.discard(uid)
    awaiting_analyze_text.discard(uid)
    awaiting_continue_text.discard(uid)
    awaiting_daily_goal.discard(uid)
    awaiting_book_deadline.discard(uid)
    awaiting_book_pace.discard(uid)
    pending_book_pace.pop(uid, None)
    awaiting_dev_question.discard(uid)
    awaiting_chat_reply.discard(uid)
    awaiting_chat_reply_pub.discard(uid)
    pending_reply_to.pop(uid, None)
    user = get_user(uid, update.effective_user.first_name)
    await update.message.reply_text("Отменено.", reply_markup=main_menu_keyboard(user))

RU_MONTHS = {
    "января":1,"февраля":2,"марта":3,"апреля":4,"мая":5,"июня":6,
    "июля":7,"августа":8,"сентября":9,"октября":10,"ноября":11,"декабря":12,
    "янв":1,"фев":2,"мар":3,"апр":4,"май":5,"июн":6,
    "июл":7,"авг":8,"сен":9,"окт":10,"ноя":11,"дек":12,
}

def parse_deadline_input(text: str):
    """Парсит строку вида 'ДД.ММ.ГГГГ СЛОВА' или '1 июня 2026 80000'.
    Возвращает (date_iso, words) или (None, None)."""
    import re
    text = text.strip()
    words_count = None
    date_obj = None

    # Вытащим число слов (последнее число в строке)
    nums = re.findall(r'\d+', text)
    if not nums:
        return None, None

    # Попытка 1: ДД.ММ.ГГГГ СЛОВА или ГГГГ-ММ-ДД СЛОВА
    m = re.match(r'(\d{1,2})[./](\d{1,2})[./](\d{4})\s+(\d+)', text)
    if m:
        d, mo, y, w = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        try:
            date_obj = date(y, mo, d)
            words_count = w
        except ValueError:
            pass

    if not date_obj:
        m = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d+)', text)
        if m:
            y, mo, d, w = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
            try:
                date_obj = date(y, mo, d)
                words_count = w
            except ValueError:
                pass

    # Попытка 2: "1 июня 2026 80000"
    if not date_obj:
        m = re.match(r'(\d{1,2})\s+([а-яё]+)\s+(\d{4})\s+(\d+)', text, re.IGNORECASE)
        if m:
            d, mon_str, y, w = int(m.group(1)), m.group(2).lower(), int(m.group(3)), int(m.group(4))
            mo = RU_MONTHS.get(mon_str)
            if mo:
                try:
                    date_obj = date(y, mo, d)
                    words_count = w
                except ValueError:
                    pass

    if date_obj and words_count and date_obj > date.today():
        return date_obj.isoformat(), words_count
    return None, None


def parse_date_only(text: str):
    """Парсит строку с только датой: 'ДД.ММ.ГГГГ', 'ГГГГ-ММ-ДД', '1 июня 2026'.
    Возвращает date_iso или None."""
    import re
    text = text.strip()
    date_obj = None

    # ДД.ММ.ГГГГ или ДД/ММ/ГГГГ
    m = re.match(r'^(\d{1,2})[./](\d{1,2})[./](\d{4})$', text)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            date_obj = date(y, mo, d)
        except ValueError:
            pass

    # ГГГГ-ММ-ДД
    if not date_obj:
        m = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', text)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            try:
                date_obj = date(y, mo, d)
            except ValueError:
                pass

    # "1 июня 2026"
    if not date_obj:
        m = re.match(r'^(\d{1,2})\s+([а-яё]+)\s+(\d{4})$', text, re.IGNORECASE)
        if m:
            d, mon_str, y = int(m.group(1)), m.group(2).lower(), int(m.group(3))
            mo = RU_MONTHS.get(mon_str)
            if mo:
                try:
                    date_obj = date(y, mo, d)
                except ValueError:
                    pass

    if date_obj and date_obj > date.today():
        return date_obj.isoformat()
    return None

async def adminstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if ADMIN_USER_ID and uid != ADMIN_USER_ID:
        return
    total_users = len(users)
    active_today = sum(
        1 for u in users.values()
        if u.get("last_day") == str(date.today())
    )
    premium_active = sum(1 for u in users.values() if is_premium(u))
    info_clicks = click_stats.get("premium_info_clicks", 0)
    buy_clicks = click_stats.get("premium_buy_clicks", 0)
    unique_interested = len(click_stats.get("unique_interested", []))
    potential_revenue = unique_interested * PREMIUM_PRICE_RUB
    total_payments = click_stats.get("total_payments", 0)
    total_revenue = click_stats.get("total_revenue_rub", 0)
    paid_users_count = len(click_stats.get("paid_users", []))
    conversion = (
        f"{paid_users_count / unique_interested * 100:.1f}%"
        if unique_interested > 0 else "—"
    )
    # Показываем, какое письмо отправится следующим
    order = _promo_state.get("order", list(range(len(FEATURE_PROMOS))))
    idx = _promo_state.get("index", 0)
    next_msg_index = order[idx % len(order)]
    next_msg_preview = FEATURE_PROMOS[next_msg_index][:80] + "…"
    await update.message.reply_text(
        f"📊 <b>Статистика бота</b>\n\n"
        f"👤 Всего пользователей: <b>{total_users}</b>\n"
        f"✍️ Активны сегодня: <b>{active_today}</b>\n"
        f"⭐ Premium подписок активно: <b>{premium_active}</b>\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"💰 <b>Продажи</b>\n\n"
        f"🧾 Всего оплат: <b>{total_payments}</b>\n"
        f"👥 Уникальных плательщиков: <b>{paid_users_count}</b>\n"
        f"💵 Выручка: <b>{total_revenue} ₽</b>\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"🎯 <b>Воронка</b>\n\n"
        f"👁 Открыли страницу Premium: <b>{info_clicks}</b> раз\n"
        f"🛒 Нажали «Оформить»: <b>{buy_clicks}</b> раз\n"
        f"🙋 Уникальных заинтересованных: <b>{unique_interested}</b> чел.\n"
        f"✅ Конверсия в оплату: <b>{conversion}</b>\n\n"
        f"📈 Потенциал (все заинтересованные): <b>{potential_revenue} ₽/мес</b>\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"💌 <b>Следующее письмо</b> (#{next_msg_index + 1}/15):\n"
        f"<i>{next_msg_preview}</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("💌 Отправить письмо сейчас", callback_data="admin_send_promo")
        ]])
    )

async def testpromo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if ADMIN_USER_ID and uid != ADMIN_USER_ID:
        return
    msg_index, msg = _advance_promo_state()
    sent = await _send_promo(context.bot, msg_index, msg)
    await update.message.reply_text(
        f"✅ Письмо #{msg_index + 1}/15 отправлено {sent} пользователям:\n\n"
        f"<i>{msg[:200]}{'…' if len(msg) > 200 else ''}</i>",
        parse_mode="HTML"
    )

# ====== КНОПКИ ======
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    user = get_user(uid, query.from_user.first_name)
    genre_key = user.get("genre", "other")
    premium = is_premium(user)

    if query.data == "goal":
        dl_date = user.get("deadline_date", "")
        dl_goal = user.get("deadline_goal", 0)
        book_line = "📖 Книга: не задана"
        if dl_date:
            try:
                days_left = (date.fromisoformat(dl_date) - date.today()).days
                if days_left >= 0:
                    if dl_goal:
                        book_line = f"📖 Книга: {dl_goal} слов{al_str(dl_goal)} до {dl_date} ({days_left} дн.)"
                    else:
                        book_line = f"📖 Книга: закончить до {dl_date} ({days_left} дн.)"
                else:
                    book_line = f"📖 Книга: дедлайн {dl_date} истёк"
            except ValueError:
                pass
        await query.message.reply_text(
            f"🎯 <b>Твои цели</b>\n\n"
            f"📅 Дневная норма: <b>{user.get('goal', 500)} слов</b>\n"
            f"{book_line}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📅 Изменить дневную норму", callback_data="set_daily_goal")],
                [InlineKeyboardButton("📖 Закончить книгу до...", callback_data="set_book_deadline")],
                [InlineKeyboardButton("« Меню", callback_data="back_menu")],
            ])
        )

    elif query.data.startswith("ob_genre_"):
        chosen = query.data.replace("ob_genre_", "")
        if chosen in GENRES:
            user["genre"] = chosen
            user["onboarded"] = True
            save(users)
        genre_label = GENRES.get(chosen, "")
        await query.message.reply_text(
            f"{'✅ Жанр: ' + genre_label + chr(10) + chr(10) if genre_label else ''}"
            f"🎯 <b>Шаг 2 из 2 — Дневная норма</b>\n\n"
            f"Сколько слов в день ты планируешь писать?\n\n"
            f"<i>Подсказка: новички — 200–500 слов (1–2 стр.), "
            f"опытные авторы — 1 000–2 000, марафонцы — от 2 000.</i>",
            parse_mode="HTML",
            reply_markup=onboard_goal_keyboard()
        )

    elif query.data == "ob_goal_step":
        await query.message.reply_text(
            "🎯 <b>Шаг 2 из 2 — Дневная норма</b>\n\n"
            "Сколько слов в день ты планируешь писать?\n\n"
            "<i>Подсказка: новички — 200–500 слов (1–2 стр.), "
            "опытные авторы — 1 000–2 000, марафонцы — от 2 000.</i>",
            parse_mode="HTML",
            reply_markup=onboard_goal_keyboard()
        )

    elif query.data in ("ob_goal_300", "ob_goal_500", "ob_goal_1000", "ob_goal_2000"):
        goal_val = int(query.data.split("_")[-1])
        user["goal"] = goal_val
        user["onboarded"] = True
        save(users)
        await query.message.reply_text(
            f"🎉 <b>Всё готово!</b>\n\n"
            f"Жанр: {GENRES.get(user.get('genre', 'other'), '✍️ Другое')}\n"
            f"Дневная норма: <b>{goal_val} слов</b>\n\n"
            f"Теперь ты знаешь свои инструменты:\n"
            f"📝 <b>/report 500</b> — записать слова за день\n"
            f"💡 <b>Идеи</b> — AI придумает тему для следующей сцены\n"
            f"🎯 <b>Цель</b> — поставить дедлайн книги\n"
            f"⏰ Напоминания приходят в 20:00 (можно изменить)\n\n"
            f"Удачи, {user['name']}! Первые слова — самые важные. ✍️",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(user)
        )

    elif query.data == "ob_goal_custom":
        awaiting_daily_goal.add(uid)
        await query.message.reply_text(
            "✏️ Введи своё число слов в день:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Пропустить →", callback_data="ob_done")]])
        )

    elif query.data == "ob_done":
        awaiting_daily_goal.discard(uid)
        user["onboarded"] = True
        save(users)
        await query.message.reply_text(
            f"🎉 <b>Готово! Добро пожаловать!</b>\n\n"
            f"Жанр: {GENRES.get(user.get('genre', 'other'), '✍️ Другое')}\n"
            f"Дневная норма: <b>{user.get('goal', 500)} слов</b>\n\n"
            f"Как работает бот:\n"
            f"📝 <b>/report 500</b> — записать слова за день\n"
            f"💡 <b>Идеи</b> — AI придумает тему для следующей сцены\n"
            f"🎯 <b>Цель</b> — поставить дедлайн книги\n"
            f"⏰ Напоминания приходят каждый день в 20:00\n\n"
            f"Удачи, {user['name']}! ✍️",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(user)
        )

    elif query.data == "set_daily_goal":
        awaiting_daily_goal.add(uid)
        await query.message.reply_text(
            "📅 Сколько слов в день хочешь писать?\n\nПросто введи число:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Отмена", callback_data="goal")]])
        )

    elif query.data == "set_book_deadline":
        awaiting_book_deadline.add(uid)
        dl_date = user.get("deadline_date", "")
        cancel_row = []
        if dl_date:
            cancel_row = [InlineKeyboardButton("❌ Убрать дедлайн", callback_data="deadline_cancel")]
        await query.message.reply_text(
            "📖 <b>Закончить книгу до...</b>\n\n"
            "Введи дату — когда хочешь закончить книгу:\n\n"
            "<code>01.06.2026</code>\n"
            "<code>1 июня 2026</code>\n"
            "<code>2026-06-01</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                ([cancel_row] if cancel_row else []) +
                [[InlineKeyboardButton("Отмена", callback_data="goal")]]
            )
        )

    elif query.data == "report":
        await query.message.reply_text("Напиши команду /report <число> чтобы добавить написанные слова.")

    elif query.data == "stats":
        genre_label = GENRES.get(genre_key, "не выбран")
        prem_str = f"⭐ Premium до {user['premium_until']}\n" if premium else ""
        level_idx, level_label, next_threshold = get_level(user["total_words"])
        if next_threshold:
            filled = int((user["total_words"] / next_threshold) * 10)
            progress_bar = f"\n[{'█' * filled}{'░' * (10 - filled)}] до следующего уровня"
        else:
            progress_bar = "\n[██████████] Максимальный уровень!"
        dl_date = user.get("deadline_date", "")
        dl_goal = user.get("deadline_goal", 0)
        deadline_str = ""
        if dl_date:
            try:
                days_left = (date.fromisoformat(dl_date) - date.today()).days
                if dl_goal:
                    words_left = max(0, dl_goal - user["total_words"])
                    pct = min(100, int(user["total_words"] / dl_goal * 100))
                    if days_left >= 0 and words_left > 0:
                        pace = words_left // max(1, days_left)
                        deadline_str = (
                            f"\n\n💀 <b>Жёсткий дедлайн</b>\n"
                            f"Цель: {dl_goal} слов{al_str(dl_goal)} к {dl_date}\n"
                            f"Прогресс: {pct}% ({user['total_words']}{al_str(user['total_words'])}/{dl_goal})\n"
                            f"Осталось: {words_left} слов за {days_left} дн. (~{pace}/день)"
                        )
                    elif words_left == 0:
                        deadline_str = f"\n\n🏆 <b>Дедлайн выполнен!</b> {dl_goal} слов{al_str(dl_goal)} к {dl_date} — СДЕЛАНО!"
                    else:
                        deadline_str = f"\n\n💀 <b>Дедлайн просрочен</b> ({dl_date}). Устанавливай новый!"
                else:
                    if days_left >= 0:
                        deadline_str = f"\n\n📖 <b>Дедлайн книги:</b> {dl_date} (осталось {days_left} дн.)"
                    else:
                        deadline_str = f"\n\n📖 <b>Дедлайн книги</b> {dl_date} — истёк. Устанавливай новый!"
            except ValueError:
                pass
        await query.message.reply_text(
            f"📊 <b>Статистика</b>\n"
            f"{prem_str}"
            f"Жанр: {genre_label}\n"
            f"Сегодня: {user['words_today']} слов{al_str(user['words_today'])}\n"
            f"Всего: {user['total_words']} слов{al_str(user['total_words'])}\n"
            f"Серия дней: {user['streak']}\n\n"
            f"🏅 Уровень: <b>{level_label}</b>{progress_bar}"
            f"{deadline_str}",
            parse_mode="HTML"
        )

    elif query.data == "idea":
        count = 3 if premium else 1
        label = "3 AI-идеи" if premium else "AI-идея"
        await query.message.reply_text(f"⏳ Генерирую {label}...")
        ideas_text = await generate_ideas(genre_key, count)
        await query.message.reply_text(f"💡 {'Идеи дня' if premium else 'Идея дня'}:\n\n{ideas_text}")

    elif query.data == "prompt":
        await query.message.reply_text("⏳ Подбираю приём...")
        tip_text = await generate_tip(genre_key)
        await query.message.reply_text(
            f"✍️ <b>Приём дня</b>\n\n{tip_text}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✍️ Ещё приём", callback_data="prompt"),
                InlineKeyboardButton("« Меню", callback_data="back_menu"),
            ]])
        )

    elif query.data == "deadline_menu":
        dl_date = user.get("deadline_date", "")
        dl_goal = user.get("deadline_goal", 0)
        if dl_date:
            try:
                days_left = (date.fromisoformat(dl_date) - date.today()).days
                if dl_goal:
                    words_left = max(0, dl_goal - user["total_words"])
                    pct = min(100, int(user["total_words"] / dl_goal * 100))
                    status = (
                        f"🔴 <b>Активный дедлайн</b>\n"
                        f"Цель: {dl_goal} слов{al_str(dl_goal)} к {dl_date}\n"
                        f"Написано: {user['total_words']}{al_str(user['total_words'])} из {dl_goal} ({pct}%)\n"
                        f"Дней осталось: {days_left}\n"
                        f"Нужно в день: ~{words_left // max(1, days_left)} слов"
                    )
                else:
                    status = (
                        f"📖 <b>Дедлайн книги</b>\n"
                        f"Закончить до: {dl_date}\n"
                        f"Дней осталось: {days_left}"
                    )
            except ValueError:
                status = "Дедлайн активен."
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отменить дедлайн", callback_data="deadline_cancel")],
                [InlineKeyboardButton("« Назад", callback_data="back_menu")],
            ])
        else:
            status = (
                "💀 <b>Жёсткий дедлайн</b>\n\n"
                "Устанавливаешь себе дату и цель по словам. "
                "Бот ежедневно будет напоминать, сколько нужно писать, "
                "а если ты провалишься — получишь максимально жёсткое сообщение.\n\n"
                "<b>Как поставить:</b>\n"
                "/deadline ГГГГ-ММ-ДД СЛОВА\n\n"
                "<b>Пример:</b>\n"
                "/deadline 2026-05-01 50000\n\n"
                "<i>Это значит: 50 000 слов до 1 мая. Без отмазок.</i>"
            )
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data="back_menu")]])
        await query.message.reply_text(status, parse_mode="HTML", reply_markup=keyboard)

    elif query.data == "deadline_cancel":
        user["deadline_date"] = ""
        user["deadline_goal"] = 0
        user["last_deadline_check"] = ""
        save(users)
        await query.message.reply_text(
            "✅ Дедлайн отменён. Можешь поставить новый в любое время.",
            reply_markup=main_menu_keyboard(user)
        )

    elif query.data in ("book_pace_day", "book_pace_week", "book_pace_month"):
        period_map = {"book_pace_day": "day", "book_pace_week": "week", "book_pace_month": "month"}
        label_map = {"day": "в день", "week": "в неделю", "month": "в месяц"}
        period = period_map[query.data]
        pending_book_pace[uid] = period
        awaiting_book_pace.add(uid)
        await query.message.reply_text(
            f"✍️ Сколько слов ты планируешь писать <b>{label_map[period]}</b>?\n\n"
            f"Просто введи число:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Пропустить", callback_data="book_pace_skip")
            ]])
        )

    elif query.data == "book_pace_skip":
        awaiting_book_pace.discard(uid)
        pending_book_pace.pop(uid, None)
        await query.message.reply_text(
            "👍 Хорошо, темп не задан. Бот напомнит о дедлайне книги по мере приближения даты.",
            reply_markup=main_menu_keyboard(user)
        )

    elif query.data == "genre_menu":
        genre_label = GENRES.get(genre_key, "не выбран")
        await query.message.reply_text(
            f"Текущий жанр: {genre_label}\n\nВыбери жанр своего произведения:",
            reply_markup=genre_keyboard()
        )

    elif query.data.startswith("setgenre_"):
        chosen = query.data.replace("setgenre_", "")
        if chosen in GENRES:
            user["genre"] = chosen
            user["onboarded"] = True
            save(users)
            await query.message.reply_text(
                f"Жанр установлен: {GENRES[chosen]} ✅\n"
                f"Теперь идеи и мотивация будут подобраны специально для тебя!",
                reply_markup=main_menu_keyboard(user)
            )

    elif query.data == "chat_menu":
        active_count = sum(1 for u in users.values() if u.get("chat_enabled", True))
        await query.message.reply_text(
            f"💬 Чат авторов\n\n"
            f"Здесь можно написать сообщение всем авторам, использующим бота.\n"
            f"Сейчас в чате: {active_count} участников.\n\n"
            f"Твои сообщения видят все, кто включил чат.",
            reply_markup=chat_menu_keyboard(user.get("chat_enabled", True))
        )

    elif query.data == "chat_write":
        awaiting_chat_message.add(uid)
        await query.message.reply_text(
            "✍️ <b>Написать в чат авторов</b>\n\n"
            "Отправь текст, фото или файл — всё это увидят другие авторы.\n"
            "К фото и файлу можно добавить подпись.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Отмена", callback_data="chat_menu")
            ]])
        )

    elif query.data.startswith("chat_reply_priv_"):
        try:
            target_uid = int(query.data.replace("chat_reply_priv_", ""))
        except ValueError:
            return
        target_user = users.get(str(target_uid))
        target_name = target_user["name"] if target_user else "автор"
        awaiting_chat_reply.add(uid)
        pending_reply_to[uid] = target_uid
        await query.message.reply_text(
            f"🔒 Приватный ответ → <b>{target_name}</b>\n\n"
            "Напиши своё сообщение — его увидит только этот автор:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Отмена", callback_data="chat_menu")
            ]])
        )

    elif query.data.startswith("chat_reply_pub_"):
        try:
            target_uid = int(query.data.replace("chat_reply_pub_", ""))
        except ValueError:
            return
        target_user = users.get(str(target_uid))
        target_name = target_user["name"] if target_user else "автор"
        awaiting_chat_reply_pub.add(uid)
        pending_reply_to[uid] = target_uid
        await query.message.reply_text(
            f"💬 Публичный ответ → <b>{target_name}</b>\n\n"
            "Напиши своё сообщение — его увидят все участники чата:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Отмена", callback_data="chat_menu")
            ]])
        )

    elif query.data.startswith("chat_reply_"):
        try:
            target_uid = int(query.data.replace("chat_reply_", ""))
        except ValueError:
            return
        target_user = users.get(str(target_uid))
        target_name = target_user["name"] if target_user else "автор"
        await query.message.reply_text(
            f"↩️ Ответить <b>{target_name}</b>. Выбери формат:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔒 Приватно", callback_data=f"chat_reply_priv_{target_uid}"),
                    InlineKeyboardButton("💬 Публично", callback_data=f"chat_reply_pub_{target_uid}"),
                ],
                [InlineKeyboardButton("Отмена", callback_data="chat_menu")],
            ])
        )

    elif query.data == "chat_toggle":
        user["chat_enabled"] = not user.get("chat_enabled", True)
        save(users)
        status = "включены 🔔" if user["chat_enabled"] else "отключены 🔕"
        await query.message.reply_text(f"Сообщения чата {status}.", reply_markup=main_menu_keyboard(user))

    elif query.data == "analyze":
        if not premium:
            await query.message.reply_text("⭐ Это Premium-функция. Оформи подписку в главном меню.")
            return
        awaiting_analyze_text.add(uid)
        await query.message.reply_text(
            "🤖 Отправь отрывок своего текста (до 2000 символов).\n"
            "Или /cancel чтобы отменить."
        )

    elif query.data == "continue_text_btn":
        if not premium:
            await query.message.reply_text("⭐ Это Premium-функция. Оформи подписку в главном меню.")
            return
        awaiting_continue_text.add(uid)
        await query.message.reply_text(
            "✍️ Отправь начало сцены или абзац, который хочешь продолжить.\n\n"
            "ИИ напишет ~150 слов в твоём стиле и жанре.\n"
            "Или /cancel чтобы отменить."
        )

    elif query.data == "gen_character_btn":
        if not premium:
            await query.message.reply_text("⭐ Это Premium-функция. Оформи подписку в главном меню.")
            return
        await query.message.reply_text("🎭 Создаю персонажа для твоего жанра...")
        result = await generate_character(user.get("genre", "other"))
        await query.message.reply_text(
            f"🎭 <b>Новый персонаж:</b>\n\n{result}\n\n"
            f"<i>Нажми кнопку ещё раз, чтобы создать другого персонажа.</i>",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(user)
        )

    elif query.data == "premium_info":
        # Трекинг клика на "узнать о подписке"
        click_stats["premium_info_clicks"] = click_stats.get("premium_info_clicks", 0) + 1
        if str(uid) not in click_stats.get("unique_interested", []):
            click_stats.setdefault("unique_interested", []).append(str(uid))
        save_stats(click_stats)
        await query.message.reply_text(
            PREMIUM_BENEFITS,
            parse_mode="HTML",
            reply_markup=premium_keyboard()
        )

    elif query.data == "premium_buy":
        # Трекинг клика на "оформить подписку"
        click_stats["premium_buy_clicks"] = click_stats.get("premium_buy_clicks", 0) + 1
        if str(uid) not in click_stats.get("unique_interested", []):
            click_stats.setdefault("unique_interested", []).append(str(uid))
        save_stats(click_stats)
        if not PAYMENT_PROVIDER_TOKEN:
            await query.message.reply_text(
                "🚀 Отлично, что ты заинтересован!\n\n"
                "Оплата Premium откроется совсем скоро — мы уже готовим систему.\n\n"
                "Следи за обновлениями 👀"
            )
            return
        await context.bot.send_invoice(
            chat_id=uid,
            title="⭐ Premium — Пиши или умри",
            description=(
                "Подписка на 30 дней. Что входит: "
                "✍️ AI-соавтор (продолжение текста) · "
                "🎭 Генератор персонажей · "
                "💡 3 AI-идеи за раз · "
                "🤖 Разбор текста · "
                "📅 Еженедельный AI-отчёт · "
                "🌙 Своё время напоминания · "
                "⭐ Premium-значок в чате"
            ),
            payload="premium_30days",
            provider_token=PAYMENT_PROVIDER_TOKEN,
            currency="RUB",
            prices=[LabeledPrice("Premium подписка — 30 дней", PREMIUM_PRICE_RUB * 100)],
            start_parameter="premium",
            need_email=True,
            send_email_to_provider=True,
            protect_content=False,
        )

    elif query.data == "challenge_menu":
        am = user.get("active_marathon", {})
        await query.message.reply_text(
            "🏃 <b>Челленджи и марафоны</b>\n\n"
            "<b>Челлендж дня</b> — небольшое ежедневное задание, которое освежает голову и разгоняет перо. "
            "Меняется каждый день.\n\n"
            "<b>Марафон</b> — многодневный вызов с нормой слов в день. "
            "Бот проверяет прогресс и сообщает об успехах и провалах.\n\n"
            + (f"Активный марафон: <b>{am.get('name','')}</b> — день {am.get('completed_days',0)}/{am.get('days',0)}"
               if am else "У тебя сейчас нет активного марафона."),
            parse_mode="HTML",
            reply_markup=challenge_main_keyboard(bool(am))
        )

    elif query.data == "challenge_daily":
        day_idx = date.today().toordinal() % len(CHALLENGES)
        ch = CHALLENGES[day_idx]
        done = user.get("challenges_done", 0)
        await query.message.reply_text(
            f"🎯 <b>Челлендж дня</b>\n\n"
            f"<b>{ch['title']}</b>\n\n"
            f"{ch['desc']}\n\n"
            f"📝 Целевой объём: ~{ch['target']} слов\n"
            f"Выполнено челленджей всего: {done}\n\n"
            f"<i>Напиши /report &lt;число&gt;, когда сделаешь — слова зачтутся в общий счёт!</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Принять вызов!", callback_data="challenge_accept")],
                [InlineKeyboardButton("« Назад", callback_data="challenge_menu")],
            ])
        )

    elif query.data == "challenge_accept":
        user["challenges_done"] = user.get("challenges_done", 0) + 1
        save(users)
        day_idx = date.today().toordinal() % len(CHALLENGES)
        ch = CHALLENGES[day_idx]
        await query.message.reply_text(
            f"🔥 Вызов принят! <b>{ch['title']}</b>\n\n"
            f"Пиши — и не забудь зафиксировать слова через /report.\n"
            f"Принято челленджей: {user['challenges_done']}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Меню", callback_data="back_menu")]])
        )

    elif query.data == "marathon_menu":
        await query.message.reply_text(
            "🏅 <b>Выбери марафон</b>\n\n"
            + "\n\n".join(f"<b>{m['name']}</b>\n{m['desc']}" for m in MARATHONS),
            parse_mode="HTML",
            reply_markup=marathon_list_keyboard()
        )

    elif query.data.startswith("marathon_join_"):
        idx = int(query.data.split("_")[-1])
        m = MARATHONS[idx]
        existing = user.get("active_marathon", {})
        if existing:
            await query.message.reply_text(
                f"⚠️ У тебя уже идёт марафон <b>{existing.get('name','')}</b>.\n\n"
                f"Сначала заверши или отмени его через «📊 Мой марафон».",
                parse_mode="HTML",
                reply_markup=challenge_main_keyboard(True)
            )
        else:
            user["active_marathon"] = {
                "id": m["id"], "name": m["name"],
                "daily_goal": m["daily_goal"], "days": m["days"],
                "start_date": date.today().isoformat(),
                "completed_days": 0, "last_check_date": "",
            }
            save(users)
            await query.message.reply_text(
                f"🚀 <b>Марафон начат!</b>\n\n"
                f"<b>{m['name']}</b>\n{m['desc']}\n\n"
                f"Норма: <b>{m['daily_goal']} слов в день</b> × {m['days']} дней\n"
                f"Каждый день, когда норма выполнена, бот засчитывает день.\n\n"
                f"Старт: сегодня. Удачи!",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Меню", callback_data="back_menu")]])
            )

    elif query.data == "marathon_status":
        am = user.get("active_marathon", {})
        if not am:
            await query.message.reply_text(
                "У тебя нет активного марафона. Запишись через «🏅 Список марафонов».",
                reply_markup=challenge_main_keyboard(False)
            )
        else:
            pct = int(am.get("completed_days", 0) / max(1, am["days"]) * 100)
            filled = int(pct / 10)
            days_gone = (date.today() - date.fromisoformat(am["start_date"])).days + 1
            days_left = am["days"] - am.get("completed_days", 0)
            await query.message.reply_text(
                f"📊 <b>{am['name']}</b>\n\n"
                f"Прогресс: {am.get('completed_days',0)}/{am['days']} дней\n"
                f"[{'█' * filled}{'░' * (10-filled)}] {pct}%\n"
                f"Норма: {am['daily_goal']} слов/день\n"
                f"Идёт день {days_gone}, осталось зачесть: {days_left} дн.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Покинуть марафон", callback_data="marathon_leave")],
                    [InlineKeyboardButton("« Назад", callback_data="challenge_menu")],
                ])
            )

    elif query.data == "marathon_leave":
        user["active_marathon"] = {}
        save(users)
        await query.message.reply_text(
            "Марафон отменён. В следующий раз — до конца!",
            reply_markup=challenge_main_keyboard(False)
        )

    elif query.data == "tz_menu":
        current_offset = user.get("tz_offset", 3)
        tz_label = next((label for off, label in TIMEZONES if off == current_offset), f"UTC+{current_offset}")
        await query.message.reply_text(
            f"🌍 <b>Выбери свой часовой пояс</b>\n\n"
            f"Сейчас выбран: <b>{tz_label}</b>\n\n"
            f"Все напоминания и советы будут приходить в твоё местное время.",
            parse_mode="HTML",
            reply_markup=timezone_keyboard()
        )

    elif query.data.startswith("settz_"):
        offset = int(query.data.split("_")[1])
        user["tz_offset"] = offset
        save(users)
        tz_label = next((label for off, label in TIMEZONES if off == offset), f"UTC+{offset}")
        await query.message.reply_text(
            f"✅ Часовой пояс установлен: <b>{tz_label}</b>\n\n"
            f"Утренний совет будет приходить в 09:00, вечерний — в 21:00 по твоему времени.",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(user)
        )

    elif query.data == "ask_dev":
        if not ADMIN_USER_ID:
            await query.message.reply_text(
                "Функция временно недоступна.",
                reply_markup=main_menu_keyboard(user)
            )
        else:
            awaiting_dev_question.add(uid)
            await query.message.reply_text(
                "✉️ <b>Вопрос разработчику</b>\n\n"
                "Напиши свой вопрос, пожелание или сообщение об ошибке — "
                "я прочитаю лично и отвечу в этом же чате.\n\n"
                "<i>Просто отправь текст ниже:</i>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Отмена", callback_data="back_menu")
                ]])
            )

    elif query.data.startswith("dev_reply_"):
        if uid != ADMIN_USER_ID:
            await query.answer("Нет доступа.", show_alert=True)
            return
        try:
            target_uid = int(query.data.replace("dev_reply_", ""))
        except ValueError:
            await query.answer("Ошибка ID.", show_alert=True)
            return
        target_user = users.get(str(target_uid))
        target_name = target_user["name"] if target_user else f"ID {target_uid}"
        awaiting_dev_reply.add(uid)
        pending_dev_reply[uid] = target_uid
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"↩️ <b>Ответ для {target_name}</b>\n\nНапиши ответ — он придёт пользователю от имени бота:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Отмена", callback_data="back_menu")
            ]])
        )

    elif query.data == "admin_send_promo":
        if uid != ADMIN_USER_ID:
            await query.answer("Нет доступа.", show_alert=True)
            return
        msg_index, msg = _advance_promo_state()
        sent = await _send_promo(context.bot, msg_index, msg)
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"✅ Письмо #{msg_index + 1}/15 отправлено {sent} пользователям.\n\n"
            f"<i>{msg[:200]}{'…' if len(msg) > 200 else ''}</i>",
            parse_mode="HTML"
        )

    elif query.data == "back_menu":
        awaiting_daily_goal.discard(uid)
        awaiting_book_deadline.discard(uid)
        awaiting_book_pace.discard(uid)
        pending_book_pace.pop(uid, None)
        awaiting_chat_message.discard(uid)
        awaiting_chat_reply.discard(uid)
        awaiting_chat_reply_pub.discard(uid)
        pending_reply_to.pop(uid, None)
        awaiting_analyze_text.discard(uid)
        awaiting_continue_text.discard(uid)
        awaiting_dev_question.discard(uid)
        awaiting_dev_reply.discard(uid)
        pending_dev_reply.pop(uid, None)
        await query.message.reply_text("Главное меню:", reply_markup=main_menu_keyboard(user))

# ====== ПЛАТЕЖИ ======
async def precheckout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query: PreCheckoutQuery = update.pre_checkout_query
    if query.invoice_payload == "premium_30days":
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Неизвестный платёж")

async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid, update.effective_user.first_name)
    payment = update.message.successful_payment
    amount_rub = payment.total_amount // 100

    current_until = user.get("premium_until", "")
    try:
        base = max(date.fromisoformat(current_until), date.today())
    except ValueError:
        base = date.today()
    new_until = base + timedelta(days=PREMIUM_DAYS)
    user["premium_until"] = new_until.isoformat()
    save(users)

    # Трекинг продажи
    click_stats["total_payments"] = click_stats.get("total_payments", 0) + 1
    click_stats["total_revenue_rub"] = click_stats.get("total_revenue_rub", 0) + amount_rub
    if str(uid) not in click_stats.get("paid_users", []):
        click_stats.setdefault("paid_users", []).append(str(uid))
    save_stats(click_stats)

    # Уведомление пользователю
    await update.message.reply_text(
        f"🎉 <b>Добро пожаловать в Premium!</b>\n\n"
        f"Подписка активна до <b>{new_until.strftime('%d.%m.%Y')}</b>.\n\n"
        f"Теперь тебе доступно:\n"
        f"✍️ AI-соавтор — продолжение текста\n"
        f"🎭 Генератор персонажей\n"
        f"💡 3 идеи за раз\n"
        f"🤖 Разбор текста\n"
        f"📅 Еженедельный AI-отчёт\n"
        f"🌙 Своё время напоминания (/reminder ЧЧ:ММ)\n"
        f"⭐ Premium-значок в чате\n\n"
        f"Пиши — твоя история ждёт! 🚀",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(user)
    )

    # Уведомление администратору
    if ADMIN_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_USER_ID,
                text=(
                    f"💰 <b>Новая оплата!</b>\n\n"
                    f"👤 {user['name']} (ID: {uid})\n"
                    f"📖 Жанр: {GENRES.get(user.get('genre', 'other'), '—')}\n"
                    f"💵 Сумма: {amount_rub} ₽\n"
                    f"📅 Premium до: {new_until.strftime('%d.%m.%Y')}\n\n"
                    f"📊 Всего оплат: {click_stats.get('total_payments', 1)}\n"
                    f"💰 Общая выручка: {click_stats.get('total_revenue_rub', amount_rub)} ₽"
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            logging.warning(f"Admin payment notification failed: {e}")

# ====== ТЕКСТОВЫЕ СООБЩЕНИЯ ======
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid, update.effective_user.first_name)
    text = update.message.text.strip()

    if uid in awaiting_daily_goal:
        awaiting_daily_goal.discard(uid)
        try:
            g = int(text.strip())
            if g <= 0:
                raise ValueError
            user["goal"] = g
            user["onboarded"] = True
            save(users)
            await update.message.reply_text(
                f"✅ Дневная норма обновлена: <b>{g} слов в день</b>",
                parse_mode="HTML",
                reply_markup=main_menu_keyboard(user)
            )
        except ValueError:
            await update.message.reply_text(
                "Нужно ввести число больше нуля. Попробуй ещё раз — нажми «🎯 Установить цель».",
                reply_markup=main_menu_keyboard(user)
            )
        return

    if uid in awaiting_book_deadline:
        awaiting_book_deadline.discard(uid)
        dl_iso = parse_date_only(text)
        if dl_iso:
            user["deadline_date"] = dl_iso
            user["deadline_goal"] = 0
            user["last_deadline_check"] = ""
            save(users)
            try:
                days_left = (date.fromisoformat(dl_iso) - date.today()).days
            except Exception:
                days_left = 0
            await update.message.reply_text(
                f"📖 <b>Дедлайн установлен: {dl_iso}</b> (осталось {days_left} дн.)\n\n"
                f"Как часто ты планируешь писать? Выбери период — бот будет напоминать отправить отчёт:",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("в день", callback_data="book_pace_day"),
                        InlineKeyboardButton("в неделю", callback_data="book_pace_week"),
                        InlineKeyboardButton("в месяц", callback_data="book_pace_month"),
                    ],
                    [InlineKeyboardButton("Пропустить", callback_data="book_pace_skip")],
                ])
            )
        else:
            await update.message.reply_text(
                "Не получилось распознать дату. Попробуй в таком формате:\n\n"
                "<code>01.06.2026</code>\n"
                "<code>1 июня 2026</code>\n"
                "<code>2026-06-01</code>\n\n"
                "Дата должна быть в будущем.",
                parse_mode="HTML",
                reply_markup=main_menu_keyboard(user)
            )
        return

    if uid in awaiting_book_pace:
        awaiting_book_pace.discard(uid)
        period = pending_book_pace.pop(uid, "day")
        try:
            n = int(text.strip())
            if n <= 0:
                raise ValueError
            if period == "week":
                daily = max(1, round(n / 7))
                period_label = f"{n} слов в неделю (~{daily}/день)"
            elif period == "month":
                daily = max(1, round(n / 30))
                period_label = f"{n} слов в месяц (~{daily}/день)"
            else:
                daily = n
                period_label = f"{n} слов в день"
            user["goal"] = daily
            user["deadline_pace_words"] = n
            user["deadline_pace_period"] = period
            save(users)
            await update.message.reply_text(
                f"✅ <b>Темп записан: {period_label}</b>\n\n"
                f"Дневная норма обновлена до <b>{daily} слов</b>.\n"
                f"Бот будет напоминать тебе отправлять отчёт каждый день. 💪",
                parse_mode="HTML",
                reply_markup=main_menu_keyboard(user)
            )
        except ValueError:
            await update.message.reply_text(
                "Введи число больше нуля. Например: <code>500</code>",
                parse_mode="HTML",
                reply_markup=main_menu_keyboard(user)
            )
        return

    if uid in awaiting_analyze_text:
        awaiting_analyze_text.discard(uid)
        if len(text) > 2000:
            text = text[:2000]
        await update.message.reply_text("🤖 Анализирую текст...")
        result = await analyze_text(user.get("genre", "other"), text)
        await update.message.reply_text(f"📝 Разбор текста:\n\n{result}", reply_markup=main_menu_keyboard(user))
        return

    if uid in awaiting_continue_text:
        awaiting_continue_text.discard(uid)
        if len(text) > 2000:
            text = text[:2000]
        await update.message.reply_text("✍️ Пишу продолжение...")
        result = await continue_text(user.get("genre", "other"), user["name"], text)
        await update.message.reply_text(
            f"📖 <b>Продолжение:</b>\n\n{result}",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(user)
        )
        return

    if uid in awaiting_dev_reply:
        awaiting_dev_reply.discard(uid)
        target_uid = pending_dev_reply.pop(uid, None)
        if not target_uid or not text:
            await update.message.reply_text("Отменено.", reply_markup=main_menu_keyboard(user))
            return
        target_user = users.get(str(target_uid))
        target_name = target_user["name"] if target_user else f"ID {target_uid}"
        try:
            await context.bot.send_message(
                chat_id=target_uid,
                text=f"✉️ <b>Ответ разработчика</b>\n\n{text}",
                parse_mode="HTML"
            )
            await update.message.reply_text(
                f"✅ Ответ отправлен пользователю {target_name}.",
                reply_markup=main_menu_keyboard(user)
            )
        except Exception as e:
            logging.warning(f"Dev reply send failed: {e}")
            await update.message.reply_text(
                f"Не удалось отправить пользователю {target_name} (ID: {target_uid}).\nОшибка: {e}",
                reply_markup=main_menu_keyboard(user)
            )
        return

    if uid in awaiting_dev_question:
        awaiting_dev_question.discard(uid)
        if not text:
            await update.message.reply_text("Вопрос не может быть пустым.", reply_markup=main_menu_keyboard(user))
            return
        genre_label = GENRES.get(user.get("genre", "other"), "не выбран")
        prem_label = "⭐ Premium" if is_premium(user) else "Free"
        admin_msg = (
            f"✉️ <b>Вопрос разработчику</b>\n\n"
            f"От: {user['name']} (ID: {uid})\n"
            f"Жанр: {genre_label} | {prem_label}\n"
            f"Слов всего: {user.get('total_words', 0)}\n\n"
            f"<b>Сообщение:</b>\n{text}"
        )
        # Если пользователь сам является администратором — показываем прямо в чате
        if uid == ADMIN_USER_ID:
            await update.message.reply_text(
                f"👤 <i>Ты отправил вопрос от своего имени (тест режима):</i>\n\n{admin_msg}",
                parse_mode="HTML",
                reply_markup=main_menu_keyboard(user)
            )
            return
        try:
            await context.bot.send_message(
                chat_id=ADMIN_USER_ID,
                text=admin_msg,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("↩️ Ответить", callback_data=f"dev_reply_{uid}")
                ]])
            )
            await update.message.reply_text(
                "✅ Вопрос отправлен! Разработчик прочитает и ответит тебе в этом чате.",
                reply_markup=main_menu_keyboard(user)
            )
        except Exception as e:
            logging.warning(f"Dev question forward failed: {e}")
            await update.message.reply_text(
                "Не удалось отправить. Попробуй позже.",
                reply_markup=main_menu_keyboard(user)
            )
        return

    if uid in awaiting_chat_reply:
        awaiting_chat_reply.discard(uid)
        target_uid = pending_reply_to.pop(uid, None)
        if not target_uid or not text:
            await update.message.reply_text("Отменено.", reply_markup=main_menu_keyboard(user))
            return
        target_user = users.get(str(target_uid))
        target_name = target_user["name"] if target_user else "автор"
        genre_label = GENRES.get(user.get("genre", "other"), "✍️ Другое")
        badge = "⭐ " if is_premium(user) else ""
        try:
            await context.bot.send_message(
                chat_id=target_uid,
                text=(
                    f"🔒 <b>Личный ответ от {badge}{user['name']} [{genre_label}]</b>\n\n"
                    f"{text}"
                ),
                parse_mode="HTML"
            )
            await update.message.reply_text(
                f"✅ Приватный ответ отправлен {target_name}!",
                reply_markup=main_menu_keyboard(user)
            )
        except Exception as e:
            logging.warning(f"Chat reply failed: {e}")
            await update.message.reply_text(
                "Не удалось доставить ответ — возможно, автор заблокировал бот.",
                reply_markup=main_menu_keyboard(user)
            )
        return

    if uid in awaiting_chat_reply_pub:
        awaiting_chat_reply_pub.discard(uid)
        target_uid = pending_reply_to.pop(uid, None)
        if not target_uid or not text:
            await update.message.reply_text("Отменено.", reply_markup=main_menu_keyboard(user))
            return
        target_user = users.get(str(target_uid))
        target_name = target_user["name"] if target_user else "автор"
        genre_label = GENRES.get(user.get("genre", "other"), "✍️ Другое")
        badge = "⭐ " if is_premium(user) else ""
        reply_kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("↩️ Ответить", callback_data=f"chat_reply_{uid}")
        ]])
        broadcast_msg = (
            f"💬 Чат авторов\n"
            f"{badge}{user['name']} [{genre_label}] → <b>{target_name}</b>:\n\n"
            f"{text}"
        )
        sent = 0
        for user_id_str, u in users.items():
            recv_uid = int(user_id_str)
            if recv_uid == uid:
                continue
            if not u.get("chat_enabled", True):
                continue
            # Адресату — чуть другой заголовок
            if recv_uid == target_uid:
                msg_for_target = (
                    f"💬 Чат авторов\n"
                    f"{badge}{user['name']} [{genre_label}] отвечает тебе:\n\n"
                    f"{text}"
                )
                try:
                    await context.bot.send_message(chat_id=recv_uid,
                                                   text=msg_for_target,
                                                   parse_mode="HTML",
                                                   reply_markup=reply_kb)
                    sent += 1
                except Exception as e:
                    logging.warning(f"Chat pub reply to target failed: {e}")
            else:
                try:
                    await context.bot.send_message(chat_id=recv_uid,
                                                   text=broadcast_msg,
                                                   parse_mode="HTML",
                                                   reply_markup=reply_kb)
                    sent += 1
                except Exception as e:
                    logging.warning(f"Chat pub reply broadcast failed: {e}")
        await update.message.reply_text(
            f"✅ Публичный ответ отправлен {sent} авторам!",
            reply_markup=main_menu_keyboard(user)
        )
        return

    if uid in awaiting_chat_message:
        awaiting_chat_message.discard(uid)
        if not text:
            await update.message.reply_text("Сообщение не может быть пустым.")
            return
        sent = await broadcast_chat_message(
            context.bot, uid,
            user["name"], user.get("genre", "other"),
            text, is_premium(user)
        )
        await update.message.reply_text(
            f"✅ Сообщение отправлено {sent} авторам!",
            reply_markup=main_menu_keyboard(user)
        )
        return

# ====== ФОТО И ФАЙЛЫ В ЧАТ ======
async def handle_chat_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid, update.effective_user.first_name)
    if uid not in awaiting_chat_message:
        return
    awaiting_chat_message.discard(uid)
    photo = update.message.photo[-1]  # наибольшее разрешение
    caption = update.message.caption or ""
    sent = await broadcast_chat_message(
        context.bot, uid,
        user["name"], user.get("genre", "other"),
        text=caption, premium=is_premium(user),
        photo_id=photo.file_id
    )
    await update.message.reply_text(
        f"✅ Фото отправлено {sent} авторам!",
        reply_markup=main_menu_keyboard(user)
    )

async def handle_chat_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid, update.effective_user.first_name)
    if uid not in awaiting_chat_message:
        return
    awaiting_chat_message.discard(uid)
    doc = update.message.document
    caption = update.message.caption or ""
    sent = await broadcast_chat_message(
        context.bot, uid,
        user["name"], user.get("genre", "other"),
        text=caption, premium=is_premium(user),
        document_id=doc.file_id, doc_name=doc.file_name or ""
    )
    await update.message.reply_text(
        f"✅ Файл «{doc.file_name or 'документ'}» отправлен {sent} авторам!",
        reply_markup=main_menu_keyboard(user)
    )

# ====== ЕЖЕНЕДЕЛЬНЫЙ ОТЧЁТ (Premium) ======
async def weekly_report_job(context: ContextTypes.DEFAULT_TYPE):
    today = date.today()
    week_ago = (today - timedelta(days=7)).isoformat()
    for user_id_str, user in users.items():
        if not is_premium(user):
            continue
        weekly = user.get("weekly_words", [])
        words_this_week = sum(
            e["words"] for e in weekly if e.get("date", "") >= week_ago
        )
        try:
            report_text = await asyncio.to_thread(
                _weekly_report_sync,
                user["name"], user.get("genre", "other"),
                user["total_words"], user["streak"], words_this_week
            )
            if not report_text:
                report_text = f"За неделю написано {words_this_week} слов. Отличная работа, продолжай!"
            await context.bot.send_message(
                chat_id=int(user_id_str),
                text=f"📅 Еженедельный отчёт:\n\n{report_text}"
            )
        except Exception as e:
            logging.warning(f"Weekly report failed for {user_id_str}: {e}")

# ====== УТРЕННИЕ И ВЕЧЕРНИЕ СОВЕТЫ ======
def _motivation_tip_sync(genre_key: str, period: str):
    if openai_client is None:
        raise RuntimeError("OpenAI client is not configured")
    genre_name = GENRES.get(genre_key, "")
    if period == "morning":
        prompt = (
            f"Ты вдохновляющий наставник для писателей. Автор пишет в жанре «{genre_name}». "
            f"Напиши короткий утренний совет (3–4 предложения) — как настроиться на работу, "
            f"разогреть воображение и войти в поток. Совет должен быть конкретным и применимым прямо сейчас. "
            f"Ответь на русском языке, без приветствий и подписей."
        )
    else:
        prompt = (
            f"Ты вдохновляющий наставник для писателей. Автор пишет в жанре «{genre_name}». "
            f"Напиши короткий вечерний совет (3–4 предложения) — как подвести итог дня, "
            f"сохранить мысли для завтра и завершить работу с удовлетворением. "
            f"Ответь на русском языке, без приветствий и подписей."
        )
    response = openai_client.chat.completions.create(
        model="gpt-5",
        messages=[{"role": "user", "content": prompt}]
    )
    content = response.choices[0].message.content
    return content.strip() if content else None

async def motivation_job(context: ContextTypes.DEFAULT_TYPE):
    if not users:
        return
    utc_now = datetime.now(tz=timezone.utc)
    today = utc_now.date().isoformat()
    tips_cache = {}

    for user_id_str, user in list(users.items()):
        tz_off = user.get("tz_offset", 3)
        local_now = utc_now + timedelta(hours=tz_off)
        local_hour = local_now.hour
        genre_key = user.get("genre", "other")

        if local_hour == 9 and user.get("last_morning_tip", "") != today:
            period = "morning"
            cache_key = f"morning_{genre_key}"
            prefix = f"🌅 <b>Доброе утро, {user['name']}!</b>"
            fallback = "Начни день с нескольких слов — даже пять минут письма лучше, чем ничего. Твоя история ждёт тебя!"
            tip_field = "last_morning_tip"
        elif local_hour == 21 and user.get("last_evening_tip", "") != today:
            period = "evening"
            cache_key = f"evening_{genre_key}"
            prefix = f"🌙 <b>Добрый вечер, {user['name']}!</b>"
            fallback = "Запиши хотя бы одну мысль о своей истории перед сном — утром она станет отправной точкой для нового текста."
            tip_field = "last_evening_tip"
        else:
            continue

        if cache_key not in tips_cache:
            try:
                tip = await asyncio.to_thread(_motivation_tip_sync, genre_key, period)
                tips_cache[cache_key] = tip or fallback
            except Exception as e:
                logging.warning(f"Motivation tip generation failed: {e}")
                tips_cache[cache_key] = fallback

        try:
            await context.bot.send_message(
                chat_id=int(user_id_str),
                text=f"{prefix}\n\n{tips_cache[cache_key]}",
                parse_mode="HTML"
            )
            user[tip_field] = today
            save(users)
        except Exception as e:
            logging.warning(f"Motivation send failed for {user_id_str}: {e}")

# ====== ЕЖЕДНЕВНЫЕ НАПОМИНАНИЯ ======
async def daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    default_hour, default_minute = 20, 0
    utc_now = datetime.now(tz=timezone.utc)
    for user_id_str, user in list(users.items()):
        tz_off = user.get("tz_offset", 3)
        local_now = utc_now + timedelta(hours=tz_off)
        local_today = (utc_now + timedelta(hours=tz_off)).date().isoformat()
        h = user.get("reminder_hour", default_hour)
        m = user.get("reminder_minute", default_minute)

        # ====== ПРОВЕРКА ПРОВАЛА ДЕДЛАЙНА (в полночь по локальному времени) ======
        dl_date = user.get("deadline_date", "")
        dl_goal = user.get("deadline_goal", 0)
        last_dl_check = user.get("last_deadline_check", "")
        if dl_date and dl_goal and local_now.hour == 0 and last_dl_check != local_today:
            try:
                dl_d = date.fromisoformat(dl_date)
                local_date_obj = date.fromisoformat(local_today)
                if local_date_obj > dl_d and user["total_words"] < dl_goal:
                    user["last_deadline_check"] = local_today
                    save(users)
                    words_short = dl_goal - user["total_words"]
                    brutal_messages = [
                        f"💀 ДЕДЛАЙН ПРОВАЛЕН, {user['name']}.\n\nТы обещал {dl_goal} слов к {dl_date}. Написал {user['total_words']}. Не хватило {words_short} слов.\n\nНе хватило времени? Вдохновения? Сил? Книга не интересовалась твоими отговорками — она просто не написана. Ставь новый дедлайн. И на этот раз — без компромиссов.",
                        f"💀 {user['name']}, ты не справился.\n\n{dl_goal} слов к {dl_date}. Написано: {user['total_words']}. Дефицит: {words_short} слов.\n\nЭти слова никто за тебя не напишет. Никогда. Ставь новый дедлайн — и хватит себя жалеть: /deadline",
                        f"💀 {user['name']}. Дедлайн прошёл. Книга — нет.\n\nНужно было {dl_goal} слов. Есть {user['total_words']}. Не хватает {words_short}.\n\nКаждый день без слов — это день, который твоя книга уже не вернёт. Новый дедлайн: /deadline",
                        f"💀 Провал зафиксирован, {user['name']}.\n\n{dl_goal} слов к {dl_date}. Реальность: {user['total_words']}. Разрыв: {words_short} слов.\n\nТы знал об этом дедлайне. Ты выбрал не писать. Хватит выбирать не писать. /deadline",
                        f"💀 {user['name']}, срок вышел.\n\nОбещание: {dl_goal} слов. Выполнение: {user['total_words']}. Осталось за бортом: {words_short} слов.\n\nПустой документ — это не творческий кризис. Это выбор. Сделай другой: /deadline",
                        f"💀 Время истекло, {user['name']}.\n\nДо финиша не хватило {words_short} слов. {user['total_words']} из {dl_goal}.\n\nТвои персонажи застряли на полуслове. Читатели — в пустоте. Верни их — ставь новый дедлайн: /deadline",
                        f"💀 {user['name']}, дедлайн мёртв. Книга — тоже.\n\nБыло нужно {dl_goal}. Написано {user['total_words']}. Пропасть: {words_short} слов.\n\nНе «почти», не «скоро», не «работаю над этим» — просто не сделано. /deadline",
                        f"💀 Дедлайн {dl_date} наступил, {user['name']}. И ушёл.\n\n{words_short} слов так и остались ненаписанными. {user['total_words']} из {dl_goal}.\n\nКаждая великая книга когда-то была просто следующим словом. Напиши его. /deadline",
                        f"💀 {user['name']}, {dl_date} наступило.\n\nТвой счёт: {user['total_words']} слов из {dl_goal}. Промах: {words_short} слов.\n\nОправдания уже придуманы — это точно. Но книга от них не появится. Только слова. /deadline",
                        f"💀 {user['name']}. {dl_goal} слов. {dl_date}. Не выполнено.\n\nНаписано {user['total_words']}. До финала не дошёл {words_short} слов.\n\nЭта история заслуживает быть написанной. Ты заслуживаешь её закончить. Без отступлений: /deadline",
                        f"💀 Отчёт по дедлайну, {user['name']}.\n\nПлан: {dl_goal} слов к {dl_date}. Факт: {user['total_words']}. Недостача: {words_short} слов.\n\nЕсли бы каждая отговорка была словом — книга была бы написана трижды. Пора писать по-настоящему: /deadline",
                        f"💀 {user['name']}, {dl_date} позади.\n\nТы написал {user['total_words']} из {dl_goal}. Финал оказался на {words_short} слов дальше, чем ты добрался.\n\nЭти слова ждут тебя до сих пор. Иди к ним: /deadline",
                        f"💀 Дедлайн не ждал, {user['name']}.\n\n{dl_goal} слов к {dl_date} — договор нарушен. Написано {user['total_words']}. Долг: {words_short} слов.\n\nТы сам поставил эту планку. Только ты можешь её взять. Снова: /deadline",
                        f"💀 {user['name']}. Срок истёк.\n\n{user['total_words']} слов из {dl_goal}. Не хватило {words_short}.\n\nЭто была твоя история. Она всё ещё может стать настоящей. Но только если ты напишешь её до конца: /deadline",
                        f"💀 Провал, {user['name']}. Конкретный.\n\nЦелился в {dl_goal} слов к {dl_date}. Попал в {user['total_words']}. Промах: {words_short} слов.\n\nПромахи — это данные, не приговор. Скорректируй прицел: /deadline",
                        f"💀 {user['name']}, дедлайн не перенесли.\n\n{dl_goal} слов к {dl_date}. Написано {user['total_words']}. Осталось {words_short} — и они никуда не делись.\n\nОни ждут тебя на следующей сессии. Не заставляй их ждать долго: /deadline",
                        f"💀 {user['name']}, книга не закончена.\n\n{dl_goal} слов — цель. {user['total_words']} слов — реальность. {words_short} слов — пустота.\n\nПустота не исчезнет сама. Заполни её: /deadline",
                        f"💀 {user['name']}. {dl_date} наступило.\n\n{user['total_words']} из {dl_goal}. До финала {words_short} слов, которых нет.\n\nВсе великие романы написаны людьми, которые не сдались. Ты ещё не сдался. Ставь дедлайн: /deadline",
                        f"💀 Итог по {dl_date}, {user['name']}.\n\nОбещал {dl_goal}. Написал {user['total_words']}. Разрыв {words_short} слов.\n\nРазрыв — не стена. Это маршрут. Пора идти: /deadline",
                        f"💀 {user['name']}, дедлайн закрыт.\n\n{dl_goal} слов к {dl_date} — не выполнено. Финал отстоит на {words_short} слов от того, где ты остановился.\n\nОстановился — не значит упал. Значит, пора снова двигаться: /deadline",
                    ]
                    try:
                        await context.bot.send_message(
                            chat_id=int(user_id_str),
                            text=random.choice(brutal_messages),
                        )
                    except Exception as e:
                        logging.warning(f"Deadline fail message error for {user_id_str}: {e}")
                    continue
            except ValueError:
                pass

        # ====== ПРОВЕРКА МАРАФОНА (в полночь по локальному времени) ======
        am = user.get("active_marathon", {})
        if am and local_now.hour == 0 and am.get("last_check_date", "") != local_today:
            yesterday = (date.fromisoformat(local_today) - timedelta(days=1)).isoformat()
            yesterday_words = sum(
                e["words"] for e in user.get("weekly_words", []) if e.get("date") == yesterday
            )
            am["last_check_date"] = local_today
            if yesterday_words >= am["daily_goal"]:
                am["completed_days"] = am.get("completed_days", 0) + 1
                user["active_marathon"] = am
                save(users)
                if am["completed_days"] >= am["days"]:
                    user["active_marathon"] = {}
                    save(users)
                    try:
                        await context.bot.send_message(
                            chat_id=int(user_id_str),
                            text=f"🏆 <b>МАРАФОН ЗАВЕРШЁН!</b>\n\n"
                                 f"Ты прошёл весь марафон <b>{am['name']}</b> до конца!\n"
                                 f"{am['days']} дней, {am['daily_goal']} слов в день. Это серьёзно. Гордись собой!",
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logging.warning(f"Marathon finish message error for {user_id_str}: {e}")
                else:
                    try:
                        await context.bot.send_message(
                            chat_id=int(user_id_str),
                            text=f"✅ <b>День марафона засчитан!</b>\n"
                                 f"{am['name']}: {am['completed_days']}/{am['days']} дней\n"
                                 f"Так держать — сегодня снова {am['daily_goal']} слов!",
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logging.warning(f"Marathon day ok message error for {user_id_str}: {e}")
            else:
                user["active_marathon"] = am
                save(users)
                try:
                    await context.bot.send_message(
                        chat_id=int(user_id_str),
                        text=f"⚠️ <b>День марафона не засчитан</b>\n"
                             f"{am['name']}: вчера написано {yesterday_words} сл. "
                             f"(нужно {am['daily_goal']})\n"
                             f"Ещё {am['completed_days']}/{am['days']} дней. Сегодня — навёрстывай!",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logging.warning(f"Marathon day miss message error for {user_id_str}: {e}")

        # Обычное напоминание — только в нужное время
        if local_now.hour != h or local_now.minute != m:
            continue

        genre_key = user.get("genre", "other")
        genre_label = GENRES.get(genre_key, "")
        name = user.get("name", "друг")

        # Слова сегодня — только если last_day совпадает с сегодня
        actual_today = user.get("words_today", 0) if user.get("last_day", "") == local_today else 0
        goal = user.get("goal", 500)
        streak = user.get("streak", 0)
        last_day = user.get("last_day", "")
        local_yesterday = (date.fromisoformat(local_today) - timedelta(days=1)).isoformat()
        words_left_goal = max(0, goal - actual_today)

        # ── Персонализированный хук ────────────────────────────
        if actual_today >= goal:
            hook = random.choice([
                f"✅ {name}, норма выполнена — {actual_today} слов! Можешь остановиться. Или добавить ещё немного?",
                f"✅ {actual_today} слов уже есть. Цель закрыта. Хочешь написать ещё — или заслуженный отдых?",
            ])
        elif actual_today > 0 and words_left_goal <= 150:
            hook = random.choice([
                f"✍️ {name}, до нормы — всего {words_left_goal} слов. Это буквально пять минут. Закроешь сегодня?",
                f"✍️ Осталось {words_left_goal} слов до цели. Ты почти у финиша — дотяни!",
            ])
        elif actual_today > 0:
            hook = random.choice([
                f"✍️ Хорошее начало: {actual_today} слов написано. До нормы ещё {words_left_goal}. Продолжишь?",
                f"✍️ {actual_today} слов — уже неплохо, {name}. Осталось {words_left_goal}. Не останавливайся!",
            ])
        elif last_day == local_yesterday:
            if streak >= 7:
                hook = random.choice([
                    f"🔥 {streak} дней подряд — не прерывай сегодня. Открывай документ.",
                    f"🔥 Серия {streak} дней на кону. Напиши сегодня — не дай ей погаснуть.",
                ])
            else:
                hook = random.choice([
                    f"✍️ Вчера ты писал. Сегодня тоже пора — открывай документ, {name}.",
                    f"✍️ День {streak + 1} подряд, если напишешь сегодня. Пора!",
                ])
        elif last_day and last_day < local_yesterday:
            try:
                days_since = (date.fromisoformat(local_today) - date.fromisoformat(last_day)).days
            except ValueError:
                days_since = 2
            if days_since == 1:
                hook = random.choice([
                    f"⚠️ {name}, вчера ты не писал. Сегодня тоже пропустишь?",
                    f"⚠️ Один пропущенный день легко превращается в два. Напиши сегодня — пока не поздно.",
                ])
            elif days_since <= 4:
                hook = random.choice([
                    f"⚠️ {days_since} дня без письма, {name}. Твоя история ещё ждёт тебя.",
                    f"⚠️ Ты не писал {days_since} дня. Вернись — даже 50 слов лучше нуля.",
                ])
            else:
                hook = random.choice([
                    f"💬 {days_since} дней без слова. Писатели не ждут настроения — они пишут несмотря на него.",
                    f"💬 Прошло {days_since} дней, {name}. Твои персонажи застыли на месте и ждут тебя.",
                ])
        else:
            hook = random.choice([
                f"✍️ Привет, {name}! Сегодня хороший день, чтобы написать несколько слов.",
                f"✍️ {name}, открывай документ — первые слова всегда самые трудные, остальное пойдёт само.",
            ])

        # ── Дополнительные подсказки ────────────────────────────
        deadline_hint = ""
        if dl_date:
            try:
                days_left = (date.fromisoformat(dl_date) - date.fromisoformat(local_today)).days
                if dl_goal:
                    words_left_dl = max(0, dl_goal - user["total_words"])
                    if days_left >= 0 and words_left_dl > 0:
                        pace = words_left_dl // max(1, days_left)
                        deadline_hint = f"\n\n💀 До дедлайна {days_left} дн. Нужно ~{pace} слов/день."
                else:
                    if 0 <= days_left <= 14:
                        deadline_hint = f"\n\n📖 До дедлайна книги {days_left} дн. Пиши каждый день!"
                    elif days_left > 14:
                        deadline_hint = f"\n\n📖 Дедлайн книги: {dl_date} ({days_left} дн.)."
            except ValueError:
                pass

        marathon_hint = ""
        am = user.get("active_marathon", {})
        if am:
            marathon_hint = f"\n\n🏃 Марафон «{am.get('name','')}»: день {am.get('completed_days',0)+1}/{am.get('days',0)}. Норма: {am.get('daily_goal',0)} сл."

        genre_hint = f" Жанр: {genre_label}." if genre_key != "other" else ""

        try:
            await context.bot.send_message(
                chat_id=int(user_id_str),
                text=f"{hook}{genre_hint}{deadline_hint}{marathon_hint}"
            )
        except Exception as e:
            logging.warning(f"Reminder failed for {user_id_str}: {e}")

# ====== ПРОМО ФУНКЦИЙ В ЧАТ (каждые 3 часа) ======
def _advance_promo_state() -> tuple[int, str]:
    """Берёт следующее промо из очереди, обновляет и сохраняет состояние.
    Возвращает (msg_index, text)."""
    import random as _random
    global _promo_state
    order = _promo_state.get("order", list(range(len(FEATURE_PROMOS))))
    idx = _promo_state.get("index", 0)
    msg_index = order[idx % len(order)]
    msg = FEATURE_PROMOS[msg_index]
    next_idx = idx + 1
    if next_idx >= len(FEATURE_PROMOS):
        new_order = list(range(len(FEATURE_PROMOS)))
        _random.shuffle(new_order)
        if new_order[0] == msg_index and len(new_order) > 1:
            new_order[0], new_order[1] = new_order[1], new_order[0]
        _promo_state = {"index": 0, "order": new_order}
    else:
        _promo_state = {"index": next_idx, "order": order}
    save_promo_state(_promo_state)
    return msg_index, msg

async def _send_promo(bot, msg_index: int, msg: str) -> int:
    """Рассылает промо всем пользователям с chat_enabled.
    Пропускает тех, кто уже получил это же сообщение (защита от дублей)."""
    import time as _time
    now_ts = _time.time()
    sent = 0
    for user_id_str, u in list(users.items()):
        if not u.get("chat_enabled", True):
            continue
        # Пропускаем если тот же msg_index уже получен менее 2 часов назад
        if u.get("last_promo_idx") == msg_index:
            last_ts = u.get("last_promo_ts", 0)
            if now_ts - last_ts < 7200:
                continue
        try:
            await bot.send_message(
                chat_id=int(user_id_str),
                text=f"💌 <b>Вам письмо!</b>\n\n{msg}",
                parse_mode="HTML"
            )
            u["last_promo_idx"] = msg_index
            u["last_promo_ts"] = now_ts
            sent += 1
        except Exception as e:
            logging.warning(f"Promo failed for {user_id_str}: {e}")
    save(users)
    return sent

async def feature_promo_job(context: ContextTypes.DEFAULT_TYPE):
    if not users:
        return
    msg_index, msg = _advance_promo_state()
    sent = await _send_promo(context.bot, msg_index, msg)
    logging.info(f"Feature promo sent (msg #{msg_index}) to {sent} users")

# ====== МОНИТОРИНГ ======
async def health_check_job(context: ContextTypes.DEFAULT_TYPE):
    issues = []
    fixed = 0

    try:
        data = load()
        required = [
            ("genre", "other"), ("chat_enabled", True),
            ("premium_until", ""), ("reminder_hour", 20),
            ("reminder_minute", 0), ("weekly_words", []),
            ("tz_offset", 3), ("last_morning_tip", ""), ("last_evening_tip", ""),
            ("deadline_date", ""), ("deadline_goal", 0), ("last_deadline_check", ""),
            ("deadline_pace_words", 0), ("deadline_pace_period", ""),
            ("active_marathon", {}), ("challenges_done", 0),
            ("last_promo_idx", -1), ("last_promo_ts", 0),
            ("onboarded", False),
            ("words_today", 0), ("total_words", 0), ("streak", 0),
            ("last_day", ""), ("goal", 500), ("name", "Автор"),
        ]
        needs_save = False
        for uid, u in data.items():
            for key, default in required:
                if key not in u:
                    u[key] = default
                    fixed += 1
                    needs_save = True
            if not isinstance(u.get("weekly_words"), list):
                u["weekly_words"] = []
                fixed += 1
                needs_save = True
            if not isinstance(u.get("active_marathon"), dict):
                u["active_marathon"] = {}
                fixed += 1
                needs_save = True
        if needs_save:
            save(data)
            users.update(data)
            issues.append(f"Автоисправлено полей: {fixed}")
    except Exception as e:
        issues.append(f"Ошибка чтения/записи данных: {e}")

    try:
        import tempfile, shutil
        tmp = DATA_FILE + ".healthcheck_tmp"
        shutil.copy2(DATA_FILE, tmp)
        os.remove(tmp)
    except Exception as e:
        issues.append(f"Ошибка файловой системы: {e}")

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if issues:
        msg = f"⚠️ Health check {ts}:\n" + "\n".join(f"• {i}" for i in issues)
        logging.warning(msg)
        if ADMIN_USER_ID:
            try:
                await context.bot.send_message(chat_id=ADMIN_USER_ID, text=msg)
            except Exception as e:
                logging.warning(f"Health check admin notify failed: {e}")
    else:
        logging.info(f"✅ Health check OK {ts} | users: {len(data)} | fixed: {fixed}")

# ====== ЗАПУСК ======
async def _set_commands(app):
    user_commands = [
        BotCommand("start",    "📋 Главное меню"),
        BotCommand("report",   "✍️ Добавить слова — /report 500"),
        BotCommand("goal",     "🎯 Установить дневную цель — /goal 500"),
        BotCommand("deadline", "💀 Жёсткий дедлайн — /deadline 2026-05-01 50000"),
        BotCommand("reminder", "⏰ Время напоминания, Premium — /reminder 09:00"),
        BotCommand("cancel",   "❌ Отменить текущее действие"),
    ]
    await app.bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())
    if ADMIN_USER_ID:
        admin_commands = user_commands + [
            BotCommand("adminstats", "📊 Статистика бота (только для админа)"),
            BotCommand("testpromo",  "💌 Отправить следующее письмо всем пользователям"),
        ]
        await app.bot.set_my_commands(
            admin_commands, scope=BotCommandScopeChat(chat_id=ADMIN_USER_ID)
        )

def main():
    logging.basicConfig(level=logging.INFO)

    app = ApplicationBuilder().token(TOKEN).post_init(_set_commands).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("goal", goal))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("reminder", reminder_cmd))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("deadline", deadline_cmd))
    app.add_handler(CommandHandler("adminstats", adminstats))
    app.add_handler(CommandHandler("testpromo", testpromo))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(PreCheckoutQueryHandler(precheckout_handler))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_chat_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_chat_document))

    job_queue: JobQueue = app.job_queue
    # Напоминания каждую минуту — бот сам проверяет у кого пришло время
    job_queue.run_repeating(daily_reminder, interval=60, first=10)
    # Мотивационные советы — каждый час, проверяет локальное время каждого пользователя
    job_queue.run_repeating(motivation_job, interval=3600, first=30)
    # Еженедельный отчёт по воскресеньям 10:00 МСК = 07:00 UTC
    job_queue.run_daily(weekly_report_job, time(hour=7, minute=0, tzinfo=timezone.utc), days=(6,))
    # Health check каждые 6 часов (4 раза в сутки)
    job_queue.run_repeating(health_check_job, interval=21600, first=60)
    # Промо функций бота в чат авторов — каждые 3 часа, ротация по 15 сообщениям
    job_queue.run_repeating(feature_promo_job, interval=10800, first=10800)

    print("Bot started")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
