def percent(current, target):
    if target <= 0:
        return 0
    return min(round((current / target) * 100), 100)


ACHIEVEMENTS = [
    {"icon": "🌱", "title": "Перший крок", "description": "Проведи свій перший урок.", "current_key": "total_lessons", "target": 1},
    {"icon": "🎈", "title": "Хороший старт", "description": "Відвідай 3 уроки.", "current_key": "total_lessons", "target": 3},
    {"icon": "📘", "title": "Учень", "description": "Відвідай 5 уроків.", "current_key": "total_lessons", "target": 5},
    {"icon": "📚", "title": "Активний учень", "description": "Відвідай 10 уроків.", "current_key": "total_lessons", "target": 10},
    {"icon": "🎓", "title": "Досвідчений", "description": "Відвідай 20 уроків.", "current_key": "total_lessons", "target": 20},
    {"icon": "🏆", "title": "Профі", "description": "Відвідай 50 уроків.", "current_key": "total_lessons", "target": 50},
    {"icon": "👑", "title": "Легенда", "description": "Відвідай 100 уроків.", "current_key": "total_lessons", "target": 100},

    {"icon": "🔥", "title": "Вогник", "description": "3 уроки за останні 7 днів.", "current_key": "lessons_last_7_days", "target": 3},
    {"icon": "🎵", "title": "В ритмі", "description": "5 уроків за останні 7 днів.", "current_key": "lessons_last_7_days", "target": 5},
    {"icon": "💥", "title": "Сильний темп", "description": "7 уроків за останні 14 днів.", "current_key": "lessons_last_14_days", "target": 7},
    {"icon": "⚡", "title": "Швидкий ритм", "description": "10 уроків за останні 30 днів.", "current_key": "lessons_last_30_days", "target": 10},
    {"icon": "🚀", "title": "На максимумі", "description": "15 уроків за останні 30 днів.", "current_key": "lessons_last_30_days", "target": 15},

    {"icon": "🍀", "title": "Перше ДЗ", "description": "Здай перше домашнє завдання.", "current_key": "submitted_homeworks", "target": 1},
    {"icon": "✅", "title": "Відповідальний", "description": "Здай 5 домашніх завдань.", "current_key": "submitted_homeworks", "target": 5},
    {"icon": "📦", "title": "Все закрито", "description": "Здай 15 домашніх завдань.", "current_key": "submitted_homeworks", "target": 15},
    {"icon": "🧠", "title": "Наполегливий", "description": "Здай 30 домашніх завдань.", "current_key": "submitted_homeworks", "target": 30},
    {"icon": "🎉", "title": "Святкуємо прогрес", "description": "Здай 50 домашніх завдань.", "current_key": "submitted_homeworks", "target": 50},

    {"icon": "🎯", "title": "Вчасно", "description": "Здай 5 ДЗ без прострочень.", "current_key": "on_time_homeworks", "target": 5},
    {"icon": "📌", "title": "Організованість", "description": "Здай 10 ДЗ без прострочень.", "current_key": "on_time_homeworks", "target": 10},
    {"icon": "💫", "title": "Натхнення", "description": "Здай 20 ДЗ без прострочень.", "current_key": "on_time_homeworks", "target": 20},
    {"icon": "🔒", "title": "Без боргів", "description": "Не мати прострочених ДЗ.", "current_key": "no_late_homeworks", "target": 1},

    {"icon": "💡", "title": "Ідея!", "description": "Отримай перше перевірене ДЗ.", "current_key": "checked_homeworks", "target": 1},
    {"icon": "⭐", "title": "Перевірений результат", "description": "Отримай 5 перевірених робіт.", "current_key": "checked_homeworks", "target": 5},
    {"icon": "🧩", "title": "Уважність", "description": "Отримай 10 перевірених робіт.", "current_key": "checked_homeworks", "target": 10},
    {"icon": "🌟", "title": "Високий рівень", "description": "Отримай 15 перевірених робіт.", "current_key": "checked_homeworks", "target": 15},
    {"icon": "💎", "title": "Якісна робота", "description": "Отримай 30 перевірених робіт.", "current_key": "checked_homeworks", "target": 30},

    {"icon": "⚡", "title": "Швидкий старт", "description": "Здай 3 ДЗ у день отримання.", "current_key": "same_day_homeworks", "target": 3},
    {"icon": "🚄", "title": "Без затримок", "description": "Здай 10 ДЗ у день отримання.", "current_key": "same_day_homeworks", "target": 10},

    {"icon": "🪴", "title": "Перші результати", "description": "Здай 3 домашні завдання.","current_key": "submitted_homeworks", "target": 3},
    {"icon": "🧭", "title": "На правильному шляху", "description": "Здай 10 домашніх завдань.","current_key": "submitted_homeworks", "target": 10},
    {"icon": "📈", "title": "Гарний прогрес", "description": "Здай 20 домашніх завдань.","current_key": "submitted_homeworks", "target": 20},

    {"icon": "📊", "title": "Сильний результат", "description": "Здай 35 домашніх завдань.","current_key": "submitted_homeworks", "target": 35},
    {"icon": "🌠", "title": "Великий прогрес", "description": "Здай 50 домашніх завдань.","current_key": "submitted_homeworks", "target": 50},
    {"icon": "🏅", "title": "Майстер домашніх", "description": "Здай 100 домашніх завдань.","current_key": "submitted_homeworks", "target": 100},

    {"icon": "🕯️", "title": "Спокійний темп", "description": "2 активні тижні.", "current_key": "active_weeks", "target": 2},
    {"icon": "📍", "title": "Тут і зараз", "description": "3 активні тижні.", "current_key": "active_weeks", "target": 3},
    {"icon": "💚", "title": "Постійність", "description": "4 активні тижні.", "current_key": "active_weeks", "target": 4},
    {"icon": "🌿", "title": "Звичка навчатись", "description": "8 активних тижнів.", "current_key": "active_weeks", "target": 8},

    {"icon": "🌙", "title": "Нічна сова", "description": "Здай ДЗ після 22:00.", "current_key": "night_homeworks", "target": 1},
    {"icon": "🦉", "title": "Нічний режим", "description": "3 нічні здачі.", "current_key": "night_homeworks", "target": 3},
    {"icon": "🌅", "title": "Ранній старт", "description": "Здай ДЗ до 8:00.", "current_key": "morning_homeworks", "target": 1},
    {"icon": "☀️", "title": "Ранкова продуктивність", "description": "5 ранніх здач.", "current_key": "morning_homeworks", "target": 5},

    {"icon": "🦁", "title": "Сміливець", "description": "Здай прострочене ДЗ.", "current_key": "late_submissions", "target": 1},
    {"icon": "🛤️", "title": "Не зупиняйся", "description": "Відвідай 40 уроків.", "current_key": "total_lessons", "target": 40},
    {"icon": "📖", "title": "Любов до навчання", "description": "Відвідай 60 уроків.", "current_key": "total_lessons", "target": 60},
    {"icon": "🏔️", "title": "Великий шлях", "description": "Відвідай 75 уроків.", "current_key": "total_lessons", "target": 75},
    {"icon": "🌌", "title": "Космічний рівень", "description": "Відвідай 150 уроків.", "current_key": "total_lessons", "target": 150},

]


def build_achievements(stats):
    achievements = []

    for item in ACHIEVEMENTS:
        current = stats.get(item["current_key"], 0)
        target = item["target"]

        achievement = {
            **item,
            "current": current,
            "progress": percent(current, target),
            "is_done": current >= target,
        }

        achievements.append(achievement)

    return achievements