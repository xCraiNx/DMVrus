import flet as ft, os, json, random, time, threading
questions_data = []  # Глобальный массив базы вопросов

try: from database import QUESTIONS_TEXT
except ImportError: QUESTIONS_TEXT = "Раздел;Номер;Текст вопроса;Ответ;Варианты\n1;1;Тест;1;Ответ"
state = {"active_page": None, "current_df": [], "index": 0, "score": 0, "start_time": 0, "app_running": True, "is_favorite_mode": False, "is_review_mode": False, "is_notebook_mode": False, "is_search_test_mode": False, "current_section_name": "", "selected_options_indices": [], "can_tap_to_next": False, "answered_current": False, "original_options": [], "shuffled_options": [], "search_results": [], "is_multiple_choice": False}
import tempfile
data_dir = os.path.join(tempfile.gettempdir(), ".flet_trainer_cache_v2"); os.makedirs(data_dir, exist_ok=True)
fav_path, nb_path, wr_path = os.path.join(data_dir, "fv.json"), os.path.join(data_dir, "nb.json"), os.path.join(data_dir, "wr.json")
st_path, pr_path, se_path = os.path.join(data_dir, "st.json"), os.path.join(data_dir, "pr.json"), os.path.join(data_dir, "se.json")
SECTION_COLORS = {"1": ft.Colors.ORANGE_800, "2": ft.Colors.BLUE_800, "3": ft.Colors.GREEN_800, "4": ft.Colors.TEAL_800, "5": ft.Colors.RED_800, "6": ft.Colors.DEEP_ORANGE_800, "7": ft.Colors.INDIGO_800, "8": ft.Colors.PURPLE_800, "9": ft.Colors.CYAN_800}
THEME_PALETTES = {"classic": {"primary": ft.Colors.ORANGE_700, "bg_btn": ft.Colors.ORANGE_500}, "premium": {"primary": ft.Colors.INDIGO_700, "bg_btn": ft.Colors.INDIGO_500}, "eco": {"primary": ft.Colors.GREEN_700, "bg_btn": ft.Colors.GREEN_500}, "monochrome": {"primary": ft.Colors.BLUE_GREY_700, "bg_btn": ft.Colors.BLUE_GREY_500}}
def load_json(p, d):
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return d
def save_json(p, data):
    try:
        with open(p, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)
    except: pass
settings = load_json(se_path, {"dark_theme": False, "exam_mode": False, "show_hints": True, "shuffle_options": True, "shuffle_questions": True, "sounds": True, "adaptive_colors": True, "theme_style": "classic"})
def get_cur_color(): return THEME_PALETTES.get(settings.get("theme_style", "classic"), THEME_PALETTES["classic"])["primary"]
def get_sec_color(s): return SECTION_COLORS.get(str(s), get_cur_color()) if settings.get("adaptive_colors", True) else THEME_PALETTES.get(settings.get("theme_style", "classic"), THEME_PALETTES["classic"])["bg_btn"]
def on_setting_toggle(k, v, s_map=None):
    settings[k] = v
    if k == "exam_mode" and v: settings["show_hints"] = False; s_map["show_hints"].value = False if s_map and "show_hints" in s_map else None
    elif k == "show_hints" and v: settings["exam_mode"] = False; s_map["exam_mode"].value = False if s_map and "exam_mode" in s_map else None
    save_json(se_path, settings)
def get_all_wrong(): return load_json(wr_path, [])
def get_all_notebook(): return load_json(nb_path, [])
def add_wrong_q(q):
    w = get_all_wrong()
    if not any(x.get("текст вопроса") == q.get("текст вопроса") for x in w): w.append(q); save_json(wr_path, w)
def remove_wrong_q(txt): save_json(wr_path, [x for x in get_all_wrong() if x.get("текст вопроса", "").strip() != txt.strip()])
def trigger_vibration(success=True):
    if settings.get("sounds", True) and state["active_page"]:
        try: state["active_page"].vibrate(200 if success else 400)
        except: pass
def clear_saved_progress():
    try: os.remove(pr_path)
    except: pass
def save_current_progress():
    if not (state["is_notebook_mode"] or state["is_search_test_mode"]): save_json(pr_path, {"index": state["index"], "score": state["score"], "start_time": state["start_time"], "is_favorite_mode": state["is_favorite_mode"], "is_review_mode": state["is_review_mode"], "current_section_name": state["current_section_name"], "current_df": state["current_df"]})
def toggle_favorite(e):
    q = state["current_df"][state["index"]]; f = load_json(fav_path, [])
    idx = next((i for i, x in enumerate(f) if x.get("текст вопроса") == q.get("текст вопроса")), None)
    if idx is not None: f.pop(idx)
    else: f.append(q)
    save_json(fav_path, f); load_question()
def toggle_notebook(e):
    q = state["current_df"][state["index"]]; n = get_all_notebook()
    idx = next((i for i, x in enumerate(n) if x.get("текст вопроса") == q.get("текст вопроса")), None)
    if idx is not None: n.pop(idx)
    else: n.append(q)
    save_json(nb_path, n); load_question()
def delete_current_from_notebook(e): q = state["current_df"][state["index"]]; save_json(nb_path, [x for x in get_all_notebook() if x.get("текст вопроса", "").strip() != q.get("текст вопроса", "").strip()]); state["current_df"].pop(state["index"]); load_question()
question_text, result_text, timer_text = ft.Text(size=18, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER), ft.Text(size=16, weight=ft.FontWeight.W_500, text_align=ft.TextAlign.CENTER), ft.Text("⏱️ Время: 00:00", size=14, weight=ft.FontWeight.W_500)
progress_bar, square_style = ft.ProgressBar(value=0.0, height=8, color=ft.Colors.ORANGE_700), ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
back_to_menu_btn, confirm_btn = ft.FilledButton("📁 В меню", style=square_style), ft.FilledButton("✅ Подтвердить ответ", visible=False, style=square_style)
fav_btn, notebook_btn, del_nb_btn = ft.IconButton(icon=ft.Icons.STAR_OUTLINED, icon_size=26), ft.IconButton(icon=ft.Icons.BOOKMARK_OUTLINED, icon_size=26), ft.IconButton(icon=ft.Icons.DELETE_OUTLINED, icon_size=26, icon_color=ft.Colors.RED_400)
options_column, search_input, menu_items_column = ft.Column(spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH), ft.TextField(label="Поиск...", prefix_icon=ft.Icons.SEARCH, border_radius=8, expand=True), ft.Column(spacing=8, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
def show_stats_dialog():
    page = state["active_page"]; h = load_json(st_path, [])
    if not h: page.open(ft.AlertDialog(title=ft.Text("📊 Статистика"), content=ft.Text("Нет завершенных тестов."))); return
    c = ft.Column([ft.Text(f"📌 {r['date']} - {r['section']}\n   Результат: {r['score']}/{r['total']} ({ (r['score']/r['total']*100) if r['total'] else 0 :.1f}%)", size=13) for r in reversed(h[-10:])], spacing=10, scroll=ft.ScrollMode.AUTO, max_height=300)
    page.open(ft.AlertDialog(title=ft.Text("📊 Последние 10 тестов"), content=c))
def show_settings_dialog():
    page = state["active_page"]; s_map = {}
    def on_ch(k, e, k_ref=None):
        on_setting_toggle(k, e.control.value, s_map)
        if k_ref and k_ref in s_map: s_map[k_ref].value = settings[k_ref]; s_map[k_ref].update()
        if k == "dark_theme": page.theme_mode = ft.ThemeMode.DARK if e.control.value else ft.ThemeMode.LIGHT; page.update()
    s_map["dark_theme"] = ft.Switch(label="Темная тема", value=settings.get("dark_theme"), on_change=lambda e: on_ch("dark_theme", e))
    s_map["exam_mode"] = ft.Switch(label="Режим экзамена", value=settings.get("exam_mode"), on_change=lambda e: on_ch("exam_mode", e, "show_hints"))
    s_map["show_hints"] = ft.Switch(label="Показывать подсказки", value=settings.get("show_hints"), on_change=lambda e: on_ch("show_hints", e, "exam_mode"))
    s_map["shuffle_questions"] = ft.Switch(label="Перемешивать билеты", value=settings.get("shuffle_questions"), on_change=lambda e: on_ch("shuffle_questions", e))
    s_map["shuffle_options"] = ft.Switch(label="Перемешивать ответы", value=settings.get("shuffle_options"), on_change=lambda e: on_ch("shuffle_options", e))
    s_map["sounds"] = ft.Switch(label="Виброотклик", value=settings.get("sounds"), on_change=lambda e: on_ch("sounds", e))
    s_map["adaptive_colors"] = ft.Switch(label="Адаптивные цвета", value=settings.get("adaptive_colors", True), on_change=lambda e: [on_ch("adaptive_colors", e), show_menu()])
    dd = ft.Dropdown(label="Палитра", value=settings.get("theme_style", "classic"), options=[ft.dropdown.Option("classic", "Оранжевая"), ft.dropdown.Option("premium", "Синяя"), ft.dropdown.Option("eco", "Зеленая"), ft.dropdown.Option("monochrome", "Серая")], on_change=lambda e: [settings.update({"theme_style": e.control.value}), save_json(se_path, settings), show_menu()])
    page.open(ft.AlertDialog(title=ft.Text("⚙️ Настройки"), content=ft.Column([s_map["dark_theme"], s_map["exam_mode"], s_map["show_hints"], s_map["shuffle_questions"], s_map["shuffle_options"], s_map["sounds"], s_map["adaptive_colors"], ft.Divider(), dd], spacing=10, scroll=ft.ScrollMode.AUTO, max_height=380)))
def create_menu_card(title, count, on_click, is_sys=False, sec_id="1"):
    bc = get_cur_color() if is_sys else get_sec_color(sec_id); tl = title.lower()
    ct = "ПРОТИВОПОЖАРНЫЙ РЕЖИМ" if "противопожарного" in tl else ("ПЕРВАЯ ПОМОЩЬ" if "первой" in tl else ("ОХРАНА ТРУДА В ЭУ" if "охране труда" in tl else ("ПТЭ ЭЛЕКТРОУСТАНОВОК" if "технической эксплуатации" in tl else ("ПРАВИЛА УСТРОЙСТВА ЭУ" if "устройства электроустановок" in tl else ("ПРАВИЛА ПЕРЕКЛЮЧЕНИЙ" if "переключений" in tl else ("РАБОТА С ПЕРСОНАЛОМ" if "персоналом" in tl else title.upper()))))))
    return ft.Container(content=ft.ElevatedButton(content=ft.Row([ft.Text(ct, size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, expand=True), ft.Container(content=ft.Text(str(count), size=12, weight=ft.FontWeight.BOLD, color=bc), bgcolor=ft.Colors.WHITE, padding=ft.padding.symmetric(horizontal=8, vertical=2), border_radius=10)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), on_click=on_click, style=ft.ButtonStyle(bgcolor=bc, shape=ft.RoundedRectangleBorder(radius=8), padding=ft.padding.all(15))), margin=ft.margin.only(bottom=2))
def filter_search(e):
    v = str(e.control.value).strip().lower()
    if not v: show_menu(); return
    state["search_results"] = [q for q in questions_data if v in str(q.get("текст вопроса", "")).lower()]
    menu_items_column.controls.clear(); menu_items_column.controls.append(create_menu_card("🔍 Найдено совпадений", len(state["search_results"]), lambda e: start_test("SEARCH_RESULT"), True)); state["active_page"].update()
def show_menu():
    if not state["active_page"]: return
    page = state["active_page"]; page.controls.clear(); page.scroll = ft.ScrollMode.AUTO; state.update({"is_favorite_mode": False, "is_review_mode": False, "is_notebook_mode": False, "is_search_test_mode": False, "current_section_name": "", "current_df": []})
    tc = get_cur_color(); header = ft.Row([ft.Text("Тренажёр ОТ и ЭБ", size=24, weight=ft.FontWeight.BOLD, expand=True), ft.Row([ft.IconButton(icon=ft.Icons.BAR_CHART, icon_color=tc, on_click=lambda e: show_stats_dialog()), ft.IconButton(icon=ft.Icons.SETTINGS, icon_color=tc, on_click=lambda e: show_settings_dialog()), ft.IconButton(icon=ft.Icons.REFRESH, icon_color=tc, on_click=lambda e: [clear_saved_progress(), show_menu()])], spacing=0)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    sections = {}
    for q in questions_data:
        raw_sec = str(q.get("раздел", "1")).strip(); sec_id = raw_sec.split(".")[0].strip() if "." in raw_sec else "1"
        sections[sec_id] = sections.get(sec_id, []) + [q]
    menu_items_column.controls.clear()
    r1 = ft.Row([ft.Container(create_menu_card("🟥 Ошибки", len(get_all_wrong()), lambda e: start_test("REVIEW"), True), expand=True), ft.Container(create_menu_card("🟦 Конспект", len(get_all_notebook()), lambda e: start_test("NOTEBOOK"), True), expand=True)], spacing=8)
    r2 = ft.Row([ft.Container(create_menu_card("🟪 20 вопросов", 20, lambda e: start_test("RANDOM_20"), True), expand=True), ft.Container(create_menu_card("🟨 Избранные", len(load_json(fav_path, [])), lambda e: start_test("FAVORITES"), True), expand=True)], spacing=8)
    menu_items_column.controls.extend([r1, r2, ft.Container(height=10)])
    for s in sorted(sections.keys(), key=lambda x: int(x) if x.isdigit() else 999):
        ql = sections[s]; sec_title = ql[0].get("раздел", f"Раздел {s}") if ql else f"Раздел {s}"
        menu_items_column.controls.append(create_menu_card(sec_title, len(ql), lambda e, sec=s: start_test(sec), sec_id=s))
    search_input.on_change = filter_search; page.add(header, ft.Row([search_input]), ft.Divider(height=5, color=ft.Colors.TRANSPARENT), menu_items_column); page.update()
def start_test(sec_name):
    state.update({"index": 0, "score": 0, "start_time": time.time(), "is_favorite_mode": sec_name=="FAVORITES", "is_review_mode": sec_name=="REVIEW", "is_notebook_mode": sec_name=="NOTEBOOK", "is_search_test_mode": sec_name=="SEARCH_RESULT", "current_section_name": sec_name, "app_running": True})
    if sec_name == "REVIEW": state["current_df"] = get_all_wrong()
    elif sec_name == "NOTEBOOK": state["current_df"] = get_all_notebook()
    elif sec_name == "FAVORITES": state["current_df"] = load_json(fav_path, [])
    elif sec_name == "SEARCH_RESULT": state["current_df"] = state["search_results"]
    elif sec_name == "RANDOM_20": state["current_df"] = random.sample(questions_data, min(20, len(questions_data)))
    else: state["current_df"] = [q for q in questions_data if str(q.get("раздел", "1")).strip() == str(sec_name).strip()]
    if not state["current_df"]: state["active_page"].open(ft.AlertDialog(title=ft.Text("📭 Пусто"), content=ft.Text("Нет вопросов."))); return
    if settings.get("shuffle_questions") and sec_name not in ["REVIEW", "NOTEBOOK", "FAVORITES", "SEARCH_RESULT", "RANDOM_20"]: random.shuffle(state["current_df"])
    setup_test_screen(); load_question()
def load_question():
    if state["index"] >= len(state["current_df"]): finish_test(); return
    q = state["current_df"][state["index"]]; state.update({"answered_current": False, "can_tap_to_next": False, "selected_options_indices": []}); save_current_progress()
    result_text.value = ""; confirm_btn.visible = False; progress_bar.value = state["index"] / len(state["current_df"]); progress_bar.color = get_sec_color(q.get("раздел", "1"))
    question_text.value = f"{q.get('текст вопроса', '')}"
    is_f = any(x.get("текст вопроса") == q.get("текст вопроса") for x in load_json(fav_path, []))
    fav_btn.icon, fav_btn.icon_color = (ft.Icons.STAR, ft.Colors.AMBER_500) if is_f else (ft.Icons.STAR_OUTLINED, ft.Colors.WHITE if settings.get("dark_theme") else ft.Colors.BLACK)
    is_n = any(x.get("текст вопроса") == q.get("текст вопроса") for x in get_all_notebook())
    notebook_btn.icon, notebook_btn.icon_color = (ft.Icons.BOOKMARK, ft.Colors.BLUE_500) if is_n else (ft.Icons.BOOKMARK_OUTLINED, ft.Colors.WHITE if settings.get("dark_theme") else ft.Colors.BLACK)
    ro = [x.strip() for x in q.get("варианты", "").split("|") if x.strip()]; ct = q.get("ответ", "").strip()
    state["is_multiple_choice"] = ct.startswith("[") and ct.endswith("]")
    cl = [x.strip() for x in ct[1:-1].split(",") if x.strip()] if state["is_multiple_choice"] else [ct]
    state["original_options"] = [{"text": o, "is_correct": o in cl} for o in ro]; state["shuffled_options"] = list(state["original_options"])
    if settings.get("shuffle_options"): random.shuffle(state["shuffled_options"])
    options_column.controls.clear()
    for i, opt in enumerate(state["shuffled_options"]): options_column.controls.append(ft.Container(content=ft.Text(opt["text"], size=15, color=ft.Colors.BLACK if not settings.get("dark_theme") else ft.Colors.WHITE), padding=ft.padding.all(14), border=ft.border.all(1, ft.Colors.GREY_400 if not settings.get("dark_theme") else ft.Colors.GREY_700), border_radius=10, bgcolor=ft.Colors.GREY_100 if not settings.get("dark_theme") else ft.Colors.GREY_900, on_click=lambda e, idx=i: select_option(idx)))
    state["active_page"].update()
def select_option(idx):
    if state["answered_current"]: return
    if state["is_multiple_choice"]:
        if idx in state["selected_options_indices"]: state["selected_options_indices"].remove(idx)
        else: state["selected_options_indices"].append(idx)
        confirm_btn.visible = len(state["selected_options_indices"]) > 0
        for i, c in enumerate(options_column.controls): c.bgcolor = (ft.Colors.ORANGE_100 if i in state["selected_options_indices"] else ft.Colors.GREY_100) if not settings.get("dark_theme") else (ft.Colors.ORANGE_900 if i in state["selected_options_indices"] else ft.Colors.GREY_900)
        state["active_page"].update()
    else: state["selected_options_indices"] = [idx]; check_answer()
def check_answer():
    if state["answered_current"]: return
    state["answered_current"] = True; confirm_btn.visible = False; q = state["current_df"][state["index"]]; is_all = True
    if state["is_multiple_choice"]:
        for i, o in enumerate(state["shuffled_options"]):
            if o["is_correct"] != (i in state["selected_options_indices"]): is_all = False
    else:
        if not state["selected_options_indices"]: is_all = False
        else:
            sel = state["selected_options_indices"][0]
            is_all = state["shuffled_options"][sel]["is_correct"] if sel < len(state["shuffled_options"]) else False
    trigger_vibration(success=is_all)
    for i, c in enumerate(options_column.controls):
        o = state["shuffled_options"][i]; is_s = i in state["selected_options_indices"]
        if o["is_correct"]: c.bgcolor = ft.Colors.GREEN_100 if not settings.get("dark_theme") else ft.Colors.GREEN_900
        elif is_s: c.bgcolor = ft.Colors.RED_100 if not settings.get("dark_theme") else ft.Colors.RED_900
    if is_all: state["score"] += 1; remove_wrong_q(q.get("текст вопроса", "")); result_text.value = "🎉 Правильно!"; result_text.color = ft.Colors.GREEN_600
    else: add_wrong_q(q); result_text.value = f"💡 Подсказка:\n• {q.get('подсказка', 'Разбор отсутствует.')}"; result_text.color = ft.Colors.RED_600
    if settings.get("exam_mode", False): state["index"] += 1; load_question()
    else:
        state["can_tap_to_next"] = True; state["active_page"].update()
        if is_all:
            def aut():
                time.sleep(0.5)
                if state["can_tap_to_next"] and state["answered_current"]: state["index"] += 1; load_question()
            threading.Thread(target=aut, daemon=True).start()
def setup_test_screen():
    page = state["active_page"]; page.controls.clear(); page.scroll = ft.ScrollMode.AUTO; mr = ft.Row([ft.Text(f"Вопрос {state['index'] + 1} из {len(state['current_df'])}", size=16, weight=ft.FontWeight.BOLD), ft.Row([fav_btn, notebook_btn, del_nb_btn] if state["is_notebook_mode"] else [fav_btn, notebook_btn], spacing=0)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)
    page.add(ft.GestureDetector(content=ft.Column([ft.Row([back_to_menu_btn, timer_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), progress_bar, mr, question_text, ft.Row([ft.Container(content=result_text, padding=ft.padding.only(top=5, bottom=5))], alignment=ft.MainAxisAlignment.CENTER), options_column, confirm_btn], horizontal_alignment=ft.CrossAxisAlignment.STRETCH, spacing=15), on_tap=lambda e: load_question() if state["can_tap_to_next"] and not state.update({"index": state["index"]+1}) else None))
def finish_test():
    page = state["active_page"]; page.controls.clear(); state["app_running"] = False; total = len(state["current_df"]); m, s = divmod(int(time.time() - state["start_time"]), 60)
    h = load_json(st_path, []); h.append({"date": time.strftime("%d.%m.%Y %H:%M"), "section": state["current_section_name"], "score": state["score"], "total": total}); save_json(st_path, h); clear_saved_progress()
    page.add(ft.Column([ft.Text("🎉 Тестирование завершено!", size=22, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER), ft.Text(f"Результат: {state['score']} из {total} ({ (state['score']/total*100) if total else 0 :.1f}%)", size=18, text_align=ft.TextAlign.CENTER), ft.Text(f"⏱️ Затраченное время: {m:02d}:{s:02d}", size=15, text_align=ft.TextAlign.CENTER), ft.Container(height=10), ft.FilledButton("📁 В главное меню", on_click=lambda e: show_menu(), style=square_style)], cross_axis_alignment=ft.CrossAxisAlignment.CENTER, spacing=15))
def main(page: ft.Page):
    state["active_page"] = page; page.safe_area = False; main_layout = ft.Column(horizontal_alignment=ft.CrossAxisAlignment.STRETCH, spacing=10)
    page.add = lambda *controls: [main_layout.controls.extend(controls), page.update()]; page.controls.clear(); page.controls.append(ft.SafeArea(content=main_layout)); page.update()
    try:
        global settings, questions_data; page.theme_mode = ft.ThemeMode.DARK; search_input.on_change = filter_search
        
        # Индикатор загрузки базы при первом холодном запуске
        page.add(ft.Container(content=ft.Column([ft.ProgressRing(color=ft.Colors.ORANGE_700), ft.Text("Загрузка базы вопросов...", size=16, weight=ft.FontWeight.W_500)], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER), expand=True))
        
        def async_parser():
            global questions_data; local_data = []
            for line in QUESTIONS_TEXT.strip().replace("\r", "").split("\n"):
                if not line.strip() or line.startswith("Раздел;"): continue
                p = line.split(";")
                if len(p) >= 5:
                    raw_sec = p[0].strip(); clean_sec = raw_sec.split(".")[0].strip() if "." in raw_sec else "1"
                    local_data.append({"раздел": clean_sec, "номер": p[1].strip(), "текст вопроса": p[2].strip(), "ответ": p[3].strip(), "варианты": p[4].strip(), "подсказка": p[5].strip() if len(p) > 5 else "Разбор отсутствует."})
            questions_data = local_data if local_data else [{"раздел": "1", "номер": "1", "текст вопроса": "Тест", "ответ": "Ответ", "варианты": "Ответ|Вариант 2", "подсказка": "Разбор отсутствует."}]
            
            # Рендерим меню только после того, как все 731 строка считаны в память
            page.run_task(lambda: show_menu())
            
        back_to_menu_btn.on_click = lambda e: [clear_saved_progress(), show_menu()]
        fav_btn.on_click, notebook_btn.on_click, del_nb_btn.on_click, confirm_btn.on_click = toggle_favorite, toggle_notebook, delete_current_from_notebook, check_answer
        
        threading.Thread(target=async_parser, daemon=True).start()
    except Exception as e:
        import traceback; page.controls.clear(); page.controls.append(ft.SafeArea(content=ft.Column([ft.Text("🚨 СБОЙ:", size=20, weight=ft.FontWeight.BOLD), ft.Container(content=ft.Text(traceback.format_exc(), size=12), bgcolor=ft.Colors.GREY_900, padding=10, expand=True)], scroll=ft.ScrollMode.AUTO))); page.update(); return
    def timer_loop():
        while state["app_running"]:
            time.sleep(1)
            if state["start_time"] > 0 and state["active_page"]:
                m, s = divmod(int(time.time() - state["start_time"]), 60)
                try: timer_text.value = f"⏱️ Время: {m:02d}:{s:02d}"; page.update()
                except: pass
    threading.Thread(target=timer_loop, daemon=True).start()

    while state["app_running"]:
        time.sleep(1)

