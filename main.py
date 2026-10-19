import asyncio
import json
import os
import random
import re
import time
from pathlib import Path

import flet as ft

from database import QUESTIONS_TEXT


DEFAULT_SETTINGS = {
    "dark_theme": True,
    "exam_mode": False,
    "show_hints": True,
    "shuffle_options": True,
    "shuffle_questions": True,
    "adaptive_colors": True,
    "theme_style": "classic",
    "auto_next": True,
}

THEME_PALETTES = {
    "classic": {"primary": ft.Colors.ORANGE_700, "button": ft.Colors.ORANGE_500},
    "premium": {"primary": ft.Colors.INDIGO_700, "button": ft.Colors.INDIGO_500},
    "eco": {"primary": ft.Colors.GREEN_700, "button": ft.Colors.GREEN_500},
}

SECTION_COLORS = {
    "1": ft.Colors.ORANGE_800,
    "2": ft.Colors.BLUE_800,
    "3": ft.Colors.GREEN_800,
    "4": ft.Colors.TEAL_800,
    "5": ft.Colors.RED_800,
    "6": ft.Colors.DEEP_ORANGE_800,
    "7": ft.Colors.INDIGO_800,
    "8": ft.Colors.PURPLE_800,
    "9": ft.Colors.CYAN_800,
}


def parse_questions(text):
    """Формат строки: раздел;номер;текст;ответ;варианты."""
    questions = []
    seen_numbers = set()

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()

        if not line or line.startswith("Раздел;"):
            continue

        # Разделяем строку на 5 частей (так как у нас 4 символа ';')
        fields = line.split(";", 4)
        if len(fields) != 5:
            raise ValueError(
                f"database.py, строка {line_number}: ожидалось 5 полей, "
                f"получено {len(fields)}"
            )

        section, number, question_text, answer, variants = (
            field.strip() for field in fields
        )

        if not number or not question_text:
            raise ValueError(
                f"database.py, строка {line_number}: пустой номер или текст вопроса"
            )

        if number in seen_numbers:
            raise ValueError(f"database.py: повторяется номер вопроса {number}")
        seen_numbers.add(number)

        options = [option.strip() for option in variants.split("|")]
        if len(options) < 2 or any(not option for option in options):
            raise ValueError(
                f"database.py, вопрос {number}: некорректные варианты ответа"
            )

        answer_numbers = re.findall(r"\d+", answer)
        if not answer_numbers:
            raise ValueError(
                f"database.py, вопрос {number}: отсутствует номер правильного ответа"
            )

        correct = {int(value) - 1 for value in answer_numbers}
        if len(correct) != len(answer_numbers) or any(
            index < 0 or index >= len(options) for index in correct
        ):
            raise ValueError(
                f"database.py, вопрос {number}: ответ {answer!r} "
                f"не соответствует вариантам"
            )

        questions.append(
            {
                "раздел": section,
                "номер": number,
                "текст вопроса": question_text,
                "варианты": options,
                "правильные": correct,
            }
        )

    if not questions:
        raise ValueError("В database.py не найдено ни одного вопроса")

    return questions


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, ValueError, TypeError):
        return default
        
def save_json(path, data):
    """Запись через временный файл, чтобы снизить риск повреждения JSON."""
    temporary_path = path.with_name(path.name + ".tmp")
    with open(temporary_path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
    os.replace(temporary_path, path)


def main(page: ft.Page):
    questions = parse_questions(QUESTIONS_TEXT)
    by_number = {question["номер"]: question for question in questions}

    # В Android Flet предоставляет каталог данных приложения через эту переменную.
    # Для запуска на компьютере используется отдельный каталог в домашней папке.
    # Проверяем переменные окружения Flet для Android
    data_directory = os.environ.get("FLET_APP_STORAGE_DATA_DIR")
    if not data_directory:
        environment = getattr(page, "environment", None)
        if isinstance(environment, dict):
            data_directory = environment.get("FLET_APP_STORAGE_DATA_DIR")

    if data_directory:
        # Если Flet передал правильный путь для Android
        storage = Path(data_directory)
    else:
        # Резервный механизм определения ОС
        import platform
        if platform.system() == "Linux" and Path("/data/data").exists():
            # Если мы на Android (среда Linux с каталогом приложений), но Flet не передал путь,
            # используем стандартную временную директорию кэша приложения, где точно есть права
            import tempfile
            storage = Path(tempfile.gettempdir()) / "flet_trainer_app"
        else:
            # Для Windows, macOS и обычного Linux на ПК
            storage = Path.home() / ".flet_trainer_app"

    # Создаем папку, теперь с правильными правами доступа
    storage.mkdir(parents=True, exist_ok=True)


    paths = {
        "favorites": storage / "fv.json",
        "notebook": storage / "nb.json",
        "wrong": storage / "wr.json",
        "statistics": storage / "st.json",
        "settings": storage / "se.json",
    }

    stored_settings = load_json(paths["settings"], {})
    settings = DEFAULT_SETTINGS | (
        stored_settings if isinstance(stored_settings, dict) else {}
    )

    state = {
        "current": [],
        "index": 0,
        "score": 0,
        "section": "",
        "selected": set(),
        "displayed_options": [],
        "answered": False,
        "testing": False,
        "started": 0.0,
        "session": 0,
        "search_results": [],
    }

    page.theme_mode = (
        ft.ThemeMode.DARK if settings["dark_theme"] else ft.ThemeMode.LIGHT
    )

    main_layout = ft.Column(
        spacing=10,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )
    menu_items = ft.Column(
        spacing=8,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )
    options_column = ft.Column(
        spacing=10,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    search_input = ft.TextField(
        label="Поиск по тексту вопроса",
        prefix_icon=ft.Icons.SEARCH,
        expand=True,
    )
    question_text = ft.Text(
        size=16,
        weight=ft.FontWeight.BOLD,
        text_align=ft.TextAlign.CENTER,
    )
    counter_text = ft.Text(size=14, weight=ft.FontWeight.BOLD)
    result_text = ft.Text(
        size=14,
        text_align=ft.TextAlign.CENTER,
    )
    timer_text = ft.Text("⏱️ Время: 00:00", size=14)
    progress_bar = ft.ProgressBar(value=0, height=8)

    back_button = ft.FilledButton(
        "📁 В меню",
        on_click=lambda e: show_menu(),
    )
    confirm_button = ft.FilledButton(
        "✅ Подтвердить ответ",
        visible=False,
    )
    favorite_button = ft.IconButton(icon=ft.Icons.STAR_OUTLINED)
    notebook_button = ft.IconButton(icon=ft.Icons.BOOKMARK_OUTLINED)

    def theme_color():
        palette = THEME_PALETTES.get(
            settings["theme_style"], THEME_PALETTES["classic"]
        )
        return palette["primary"]

    def section_color(section):
        palette = THEME_PALETTES.get(
            settings["theme_style"], THEME_PALETTES["classic"]
        )
        if not settings["adaptive_colors"]:
            return palette["button"]
        section_id = section.split(".", 1)[0].strip()
        return SECTION_COLORS.get(section_id, palette["button"])

    def saved_numbers(kind):
        """Читает и новый формат [номера], и старые списки словарей."""
        data = load_json(paths[kind], [])
        if not isinstance(data, list):
            return []

        result = []
        for item in data:
            number = (
                str(item.get("номер", ""))
                if isinstance(item, dict)
                else str(item)
            )
            if number in by_number and number not in result:
                result.append(number)
        return result

    def set_saved_numbers(kind, numbers):
        save_json(paths[kind], numbers)

    def current_question():
        return state["current"][state["index"]]

    def update_bookmark_icons():
        number = current_question()["номер"]
        is_favorite = number in saved_numbers("favorites")
        is_notebook = number in saved_numbers("notebook")

        favorite_button.icon = (
            ft.Icons.STAR if is_favorite else ft.Icons.STAR_OUTLINED
        )
        favorite_button.icon_color = (
            ft.Colors.AMBER_500 if is_favorite else theme_color()
        )
        notebook_button.icon = (
            ft.Icons.BOOKMARK if is_notebook else ft.Icons.BOOKMARK_OUTLINED
        )
        notebook_button.icon_color = (
            ft.Colors.BLUE_500 if is_notebook else theme_color()
        )

    def toggle_saved(kind):
        if not state["testing"]:
            return

        number = current_question()["номер"]
        numbers = saved_numbers(kind)

        if number in numbers:
            numbers.remove(number)
        else:
            numbers.append(number)

        set_saved_numbers(kind, numbers)
        # Не вызываем load_question(): иначе можно повторно ответить
        # на уже засчитанный вопрос.
        update_bookmark_icons()
        page.update()

    favorite_button.on_click = lambda e: toggle_saved("favorites")
    notebook_button.on_click = lambda e: toggle_saved("notebook")

    def menu_card(title, count, callback, color):
        return ft.FilledButton(
            content=ft.Row(
                [
                    ft.Text(
                        title,
                        size=11,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE,
                        expand=True,
                    ),
                    ft.Text(
                        str(count),
                        size=11,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            on_click=callback,
            style=ft.ButtonStyle(
                bgcolor=color,
                padding=ft.Padding(
                    left=12, right=12, top=12, bottom=12
                ),
            ),
        )

    def show_statistics():
        history = load_json(paths["statistics"], [])
        if not isinstance(history, list) or not history:
            page.open(
                ft.AlertDialog(
                    title=ft.Text("📊 Статистика"),
                    content=ft.Text("Нет завершённых тестов."),
                )
            )
            return

        entries = []
        for record in reversed(history[-10:]):
            total = record.get("total", 0)
            score = record.get("score", 0)
            percent = score / total * 100 if total else 0
            entries.append(
                ft.Text(
                    f"{record.get('date', '')} — "
                    f"{record.get('section', '')}\n"
                    f"{score}/{total} ({percent:.1f}%)",
                    size=13,
                )
            )

        page.open(
            ft.AlertDialog(
                title=ft.Text("📊 Последние 10 тестов"),
                content=ft.Container(
                    height=300,
                    content=ft.Column(
                        entries,
                        spacing=10,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                ),
            )
        )

    def show_settings():
        switches = {}

        def change_setting(key, value):
            settings[key] = value

            if key == "exam_mode" and value:
                settings["show_hints"] = False
                switches["show_hints"].value = False
            elif key == "show_hints" and value:
                settings["exam_mode"] = False
                switches["exam_mode"].value = False

            save_json(paths["settings"], settings)
            page.theme_mode = (
                ft.ThemeMode.DARK
                if settings["dark_theme"]
                else ft.ThemeMode.LIGHT
            )
            page.update()

        for key, label in [
            ("dark_theme", "Тёмная тема"),
            ("exam_mode", "Режим экзамена: не показывать ответ"),
            ("show_hints", "Показывать подсказки при ошибке"),
            ("auto_next", "Автопереход после правильного ответа"),
            ("shuffle_questions", "Перемешивать вопросы раздела"),
            ("shuffle_options", "Перемешивать варианты ответа"),
            ("adaptive_colors", "Цвета разделов"),
        ]:
            switches[key] = ft.Switch(
                label=label,
                value=settings[key],
                on_change=lambda e, setting_key=key: change_setting(
                    setting_key, e.control.value
                ),
            )

        def change_palette(e):
            change_setting("theme_style", e.control.value)
            page.close(dialog)
            show_menu()

        palette = ft.Dropdown(
            label="Палитра",
            value=settings["theme_style"],
            options=[
                ft.dropdown.Option("classic", "Оранжевая"),
                ft.dropdown.Option("premium", "Синяя"),
                ft.dropdown.Option("eco", "Зелёная"),
            ],
            on_change=change_palette,
        )

        dialog = ft.AlertDialog(
            title=ft.Text("⚙️ Настройки"),
            content=ft.Container(
                height=380,
                content=ft.Column(
                    [*switches.values(), palette],
                    scroll=ft.ScrollMode.AUTO,
                ),
            ),
        )
        page.open(dialog)

    def show_menu():
        state["session"] += 1
        state["testing"] = False
        state["current"] = []
        main_layout.controls.clear()
        menu_items.controls.clear()
        search_input.value = ""

        sections = {}
        for question in questions:
            sections.setdefault(question["раздел"], []).append(question)

        color = theme_color()
        header = ft.Row(
            [
                ft.Text(
                    "Тренажёр ОТ и ЭБ",
                    size=20,
                    weight=ft.FontWeight.BOLD,
                    expand=True,
                ),
                ft.IconButton(
                    icon=ft.Icons.BAR_CHART,
                    icon_color=color,
                    on_click=lambda e: show_statistics(),
                ),
                ft.IconButton(
                    icon=ft.Icons.SETTINGS,
                    icon_color=color,
                    on_click=lambda e: show_settings(),
                ),
            ]
        )

        menu_items.controls.extend(
            [
                ft.Row(
                    [
                        ft.Container(
                            content=menu_card(
                                "🟥 Ошибки",
                                len(saved_numbers("wrong")),
                                lambda e: start_test("REVIEW"),
                                color,
                            ),
                            expand=True,
                        ),
                        ft.Container(
                            content=menu_card(
                                "🟦 Конспект",
                                len(saved_numbers("notebook")),
                                lambda e: start_test("NOTEBOOK"),
                                color,
                            ),
                            expand=True,
                        ),
                    ],
                    spacing=8,
                ),
                ft.Row(
                    [
                        ft.Container(
                            content=menu_card(
                                "🟪 20 вопросов",
                                min(20, len(questions)),
                                lambda e: start_test("RANDOM_20"),
                                color,
                            ),
                            expand=True,
                        ),
                        ft.Container(
                            content=menu_card(
                                "🟨 Избранные",
                                len(saved_numbers("favorites")),
                                lambda e: start_test("FAVORITES"),
                                color,
                            ),
                            expand=True,
                        ),
                    ],
                    spacing=8,
                ),
            ]
        )

        def section_order(section):
            prefix = section.split(".", 1)[0].strip()
            return int(prefix) if prefix.isdigit() else 999

        for section in sorted(sections, key=section_order):
            menu_items.controls.append(
                menu_card(
                    section,
                    len(sections[section]),
                    lambda e, selected=section: start_test(selected),
                    section_color(section),
                )
            )

        main_layout.controls.extend(
            [
                header,
                ft.Row([search_input]),
                menu_items,
            ]
        )
        page.update()

    def on_search(e):
        query = (e.control.value or "").strip().lower()
        if not query:
            show_menu()
            return

        state["search_results"] = [
            question
            for question in questions
            if query in question["текст вопроса"].lower()
        ]
        menu_items.controls.clear()
        menu_items.controls.append(
            menu_card(
                "🔍 Найдено совпадений",
                len(state["search_results"]),
                lambda event: start_test("SEARCH_RESULT"),
                theme_color(),
            )
        )
        page.update()

    search_input.on_change = on_search

    async def update_timer(session):
        while state["testing"] and state["session"] == session:
            elapsed = int(time.time() - state["started"])
            minutes, seconds = divmod(elapsed, 60)
            timer_text.value = f"⏱️ Время: {minutes:02d}:{seconds:02d}"
            page.update()
            await asyncio.sleep(1)

    async def auto_advance(session, question_index):
        await asyncio.sleep(0.5)
        if (
            state["testing"]
            and state["session"] == session
            and state["index"] == question_index
            and state["answered"]
        ):
            next_question()

    def start_test(section):
        if section == "REVIEW":
            selected_questions = [
                by_number[number] for number in saved_numbers("wrong")
            ]
        elif section == "NOTEBOOK":
            selected_questions = [
                by_number[number] for number in saved_numbers("notebook")
            ]
        elif section == "FAVORITES":
            selected_questions = [
                by_number[number] for number in saved_numbers("favorites")
            ]
        elif section == "SEARCH_RESULT":
            selected_questions = list(state["search_results"])
        elif section == "RANDOM_20":
            selected_questions = random.sample(
                questions, min(20, len(questions))
            )
        else:
            selected_questions = [
                question
                for question in questions
                if question["раздел"] == section
            ]
            if settings["shuffle_questions"]:
                random.shuffle(selected_questions)

        if not selected_questions:
            page.open(
                ft.AlertDialog(
                    title=ft.Text("📭 Пусто"),
                    content=ft.Text("Нет вопросов для этого режима."),
                )
            )
            return

        state["session"] += 1
        state["current"] = selected_questions
        state["index"] = 0
        state["score"] = 0
        state["section"] = section
        state["started"] = time.time()
        state["testing"] = True

        main_layout.controls.clear()
        main_layout.controls.extend(
            [
                ft.Row(
                    [back_button, timer_text],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                progress_bar,
                ft.Row(
                    [
                        ft.Container(content=counter_text, expand=True),
                        favorite_button,
                        notebook_button,
                    ]
                ),
                question_text,
                result_text,
                options_column,
                confirm_button,
            ]
        )

        page.run_task(update_timer, state["session"])
        load_question()

    def load_question():
        if state["index"] >= len(state["current"]):
            finish_test()
            return

        question = current_question()
        state["answered"] = False
        state["selected"] = set()

        displayed = [
            {
                "text": text,
                "correct": index in question["правильные"],
            }
            for index, text in enumerate(question["варианты"])
        ]
        if settings["shuffle_options"]:
            random.shuffle(displayed)
        state["displayed_options"] = displayed

        total = len(state["current"])
        counter_text.value = f"Вопрос {state['index'] + 1} из {total}"
        question_text.value = question["текст вопроса"]
        progress_bar.value = state["index"] / total
        progress_bar.color = section_color(question["раздел"])

        result_text.value = ""
        confirm_button.visible = False
        confirm_button.text = "✅ Подтвердить ответ"
        confirm_button.on_click = lambda e: check_answer()

        update_bookmark_icons()
        options_column.controls.clear()

        for index, option in enumerate(displayed):
            options_column.controls.append(
                ft.Container(
                    content=ft.Text(option["text"], size=14),
                    padding=ft.Padding(
                        left=12, right=12, top=12, bottom=12
                    ),
                    border=ft.border.all(1, ft.Colors.GREY_600),
                    border_radius=10,
                    on_click=lambda e, selected=index: select_option(selected),
                )
            )

        page.update()

    def select_option(index):
        if not state["testing"] or state["answered"]:
            return

        question = current_question()
        is_multiple = len(question["правильные"]) > 1

        if is_multiple:
            if index in state["selected"]:
                state["selected"].remove(index)
            else:
                state["selected"].add(index)
        else:
            state["selected"] = {index}

        for option_index, control in enumerate(options_column.controls):
            control.bgcolor = (
                ft.Colors.ORANGE_900
                if option_index in state["selected"] and settings["dark_theme"]
                else ft.Colors.ORANGE_100
                if option_index in state["selected"]
                else None
            )

        if is_multiple or settings["exam_mode"]:
            confirm_button.visible = bool(state["selected"])
            page.update()
        else:
            check_answer()

    def check_answer():
        if not state["testing"] or state["answered"] or not state["selected"]:
            return

        state["answered"] = True
        question = current_question()
        selected = state["selected"]
        displayed = state["displayed_options"]

        is_correct = all(
            option["correct"] == (index in selected)
            for index, option in enumerate(displayed)
        )

        wrong_numbers = saved_numbers("wrong")
        number = question["номер"]

        if is_correct:
            state["score"] += 1
            if number in wrong_numbers:
                wrong_numbers.remove(number)
                set_saved_numbers("wrong", wrong_numbers)
        elif number not in wrong_numbers:
            wrong_numbers.append(number)
            set_saved_numbers("wrong", wrong_numbers)

        if settings["exam_mode"]:
            result_text.value = "Ответ принят."
        else:
            for index, control in enumerate(options_column.controls):
                option = displayed[index]

                if option["correct"] and index in selected:
                    control.bgcolor = ft.Colors.GREEN_900
                elif option["correct"]:
                    control.bgcolor = ft.Colors.BLUE_900
                elif index in selected:
                    control.bgcolor = ft.Colors.RED_900

            if is_correct:
                result_text.value = "🎉 Правильно!"
            elif settings["show_hints"]:
                correct_texts = [
                    option["text"]
                    for option in displayed
                    if option["correct"]
                ]
                result_text.value = (
                    "Неверно. Правильный ответ:\n"
                    + "\n".join(f"• {text}" for text in correct_texts)
                )
            else:
                result_text.value = "Неверно."

        if (
            is_correct
            and settings["auto_next"]
            and not settings["exam_mode"]
        ):
            confirm_button.visible = False
            page.update()
            page.run_task(
                auto_advance, state["session"], state["index"]
            )
            return

        confirm_button.text = (
            "➡️ Следующий вопрос"
            if state["index"] + 1 < len(state["current"])
            else "🏁 Завершить тест"
        )
        confirm_button.on_click = lambda e: next_question()
        confirm_button.visible = True
        page.update()

    def next_question():
        if not state["testing"] or not state["answered"]:
            return
        state["index"] += 1
        load_question()

    def finish_test():
        if not state["testing"]:
            return

        state["testing"] = False
        state["session"] += 1

        total = len(state["current"])
        score = state["score"]
        elapsed = int(time.time() - state["started"])
        minutes, seconds = divmod(elapsed, 60)

        history = load_json(paths["statistics"], [])
        if not isinstance(history, list):
            history = []

        history.append(
            {
                "date": time.strftime("%d.%m.%Y %H:%M"),
                "section": state["section"],
                "score": score,
                "total": total,
            }
        )
        save_json(paths["statistics"], history)

        main_layout.controls.clear()
        main_layout.controls.append(
            ft.Column(
                [
                    ft.Text(
                        "🎉 Тестирование завершено!",
                        size=20,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Text(
                        f"Результат: {score} из {total} "
                        f"({score / total * 100:.1f}%)"
                    ),
                    ft.Text(f"⏱️ Время: {minutes:02d}:{seconds:02d}"),
                    ft.FilledButton(
                        "📁 В главное меню",
                        on_click=lambda e: show_menu(),
                    ),
                ],
                spacing=15,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
        page.update()

    page.scroll = ft.ScrollMode.AUTO
    page.add(ft.SafeArea(content=main_layout))
    show_menu()


if __name__ == "__main__":
    ft.run(main)
