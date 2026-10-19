import flet as ft, os, json, random, time, asyncio

try: 
    from database import QUESTIONS_TEXT
except ImportError: 
    QUESTIONS_TEXT = "1;1;Тест;1;Ответ;Разбор отсутствует."

questions_data = []
state = {
    "active_page": None, "current_df": [], "index": 0, "score": 0, "start_time": 0.0,
    "is_favorite_mode": False, "is_review_mode": False, "is_notebook_mode": False,
    "current_section_name": "", "selected_options_indices": [], "answered_current": False,
    "shuffled_options": [], "search_results": [], "is_multiple_choice": False
}

fav_path = nb_path = wr_path = st_path = se_path = ""
settings = {}

SECTION_COLORS = {
    "1": ft.Colors.ORANGE_800, "2": ft.Colors.BLUE_800, "3": ft.Colors.GREEN_800, 
    "4": ft.Colors.TEAL_800, "5": ft.Colors.RED_800, "6": ft.Colors.DEEP_ORANGE_800, 
    "7": ft.Colors.INDIGO_800, "8": ft.Colors.PURPLE_800, "9": ft.Colors.CYAN_800
}
THEME_PALETTES = {
    "classic": {"primary": ft.Colors.ORANGE_700, "bg_btn": ft.Colors.ORANGE_500}, 
    "premium": {"primary": ft.Colors.INDIGO_700, "bg_btn": ft.Colors.INDIGO_500}, 
    "eco": {"primary": ft.Colors.GREEN_700, "bg_btn": ft.Colors.GREEN_500}, 
    "monochrome": {"primary": ft.Colors.BLUE_GREY_700, "bg_btn": ft.Colors.BLUE_GREY_500}
}

def load_json(p, d):
    if p and os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return d

def save_json(p, data):
    if not p: return
    try:
        with open(p, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)
    except: pass
get_cur_color = lambda: THEME_PALETTES.get(settings.get("theme_style", "classic"), THEME_PALETTES["classic"])["primary"]
get_sec_color = lambda s: SECTION_COLORS.get(str(s), get_cur_color()) if settings.get("adaptive_colors", True) else THEME_PALETTES.get(settings.get("theme_style", "classic"), THEME_PALETTES["classic"])["bg_btn"]
get_all_wrong, get_all_notebook = lambda: load_json(wr_path, []), lambda: load_json(nb_path, [])

def add_wrong_q(q):
    w = get_all_wrong()
    if not any(x.get("текст вопроса") == q.get("текст вопроса") for x in w): w.append(q); save_json(wr_path, w)

def remove_wrong_q(txt): save_json(wr_path, [x for x in get_all_wrong() if x.get("текст вопроса", "").strip() != txt.strip()])
def trigger_vibration(success=True):
    if settings.get("sounds", True) and state["active_page"]:
        try: state["active_page"].vibrate(200 if success else 400)
        except: pass

def toggle_fav_or_nb(path_target, is_nb=False):
    if not state["current_df"] or state["index"] >= len(state["current_df"]): return
    q = state["current_df"][state["index"]]; items = load_json(path_target, [])
    idx = next((i for i, x in enumerate(items) if x.get("текст вопроса") == q.get("текст вопроса")), None)
    if idx is not None: items.pop(idx)
    else: items.append(q)
    save_json(path_target, items)
    if state["current_section_name"] in ["FAVORITES", "NOTEBOOK"]:
        state["current_df"].pop(state["index"])
        if not state["current_df"]: show_menu(); return
        if state["index"] >= len(state["current_df"]): state["index"] = len(state["current_df"]) - 1
    load_question()

async def async_load_question():
    await asyncio.sleep(0.5)
    if state["answered_current"] and state["active_page"]:
        if (state["index"] + 1) >= len(state["current_df"]): finish_test(); return
        state["index"] += 1
        state["answered_current"] = False
        load_question()

question_text = ft.Text(size=16, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)
result_text = ft.Text(size=14, weight=ft.FontWeight.W_500, text_align=ft.TextAlign.CENTER)
timer_text = ft.Text("⏱️ Время: 00:00", size=14, weight=ft.FontWeight.W_500)
progress_bar, square_style = ft.ProgressBar(value=0.0, height=8, color=ft.Colors.ORANGE_700), ft.ButtonStyle(border_radius=8)
back_to_menu_btn, confirm_btn = ft.FilledButton("📁 В меню", style=square_style), ft.FilledButton("✅ Подтвердить ответ", visible=False, style=square_style)
fav_btn, notebook_btn, del_nb_btn = ft.IconButton(icon=ft.Icons.STAR_OUTLINED, icon_size=26), ft.IconButton(icon=ft.Icons.BOOKMARK_OUTLINED, icon_size=26), ft.IconButton(icon=ft.Icons.DELETE_OUTLINED, icon_size=26, icon_color=ft.Colors.RED_400)
options_column, search_input, menu_items_column, main_layout = ft.Column(spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH), ft.TextField(label="Поиск...", prefix_icon=ft.Icons.SEARCH, border_radius=8, expand=True), ft.Column(spacing=8, horizontal_alignment=ft.CrossAxisAlignment.STRETCH), ft.Column(horizontal_alignment=ft.CrossAxisAlignment.STRETCH, spacing=10)

def show_stats_dialog():
    page = state["active_page"]; h = load_json(st_path, [])
    if not h: page.open(ft.AlertDialog(title=ft.Text("📊 Статистика"), content=ft.Text("Нет завершенных тестов."))); return
    c = ft.Column([ft.Text(f"📌 {r['date']} - {r['section']}\n   Результат: {r['score']}/{r['total']} ({(r['score']/r['total']*100) if r['total'] else 0:.1f}%)", size=13) for r in reversed(h[-10:])], spacing=10, scroll=ft.ScrollMode.AUTO, max_height=300)
    page.open(ft.AlertDialog(title=ft.Text("📊 Последние 10 тестов"), content=c))

def show_settings_dialog():
    page, s_map = state["active_page"], {}
    def close_and_refresh(e): page.close(dlg); show_menu()
    def on_ch(k, v):
        settings[k] = v
        if k == "exam_mode" and v: settings["show_hints"] = False; s_map["show_hints"].value = False
        elif k == "show_hints" and v: settings["exam_mode"] = False; s_map["exam_mode"].value = False
        save_json(se_path, settings); page.theme_mode = ft.ThemeMode.DARK if settings["dark_theme"] else ft.ThemeMode.LIGHT; page.update()
    s_map["dark_theme"] = ft.Switch(label="Темная тема", value=settings["dark_theme"], on_change=lambda e: on_ch("dark_theme", e.control.value))
    s_map["exam_mode"] = ft.Switch(label="Режим экзамена", value=settings["exam_mode"], on_change=lambda e: on_ch("exam_mode", e.control.value))
    s_map["show_hints"] = ft.Switch(label="Показывать подсказки", value=settings["show_hints"], on_change=lambda e: on_ch("show_hints", e.control.value))
    s_map["auto_next"] = ft.Switch(label="Автопереход (0.5 сек)", value=settings["auto_next"], on_change=lambda e: on_ch("auto_next", e.control.value))
    dd = ft.Dropdown(label="Палитра", value=settings["theme_style"], options=[ft.dropdown.Option(k, v) for k, v in [("classic", "Оранжевая"), ("premium", "Синяя"), ("eco", "Зеленая")]], on_change=lambda e: [settings.update({"theme_style": e.control.value}), save_json(se_path, settings), close_and_refresh(None)])
    dlg = ft.AlertDialog(title=ft.Text("⚙️ Настройки"), content=ft.Column([s_map["dark_theme"], s_map["exam_mode"], s_map["show_hints"], s_map["auto_next"], ft.Divider(), dd], scroll=ft.ScrollMode.AUTO, max_height=380))
    page.open(dlg)

def create_menu_card(title, count, on_click, is_sys=False, sec_id="1"):
    bc = get_cur_color() if is_sys else get_sec_color(sec_id); ct = title.upper() 
    return ft.Container(content=ft.Button(content=ft.Row([ft.Text(ct, size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, expand=True), ft.Container(content=ft.Text(str(count), size=11, weight=ft.FontWeight.BOLD, color=bc), bgcolor=ft.Colors.WHITE, padding=ft.Padding(left=8, right=8, top=2, bottom=2), border_radius=10)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), on_click=on_click, style=ft.ButtonStyle(bgcolor=bc, border_radius=8, padding=ft.Padding(left=12, right=12, top=12, bottom=12))))
def filter_search(e):
    v = str(e.control.value).strip().lower()
    if not v: show_menu(); return
    state["search_results"] = [q for q in questions_data if v in str(q.get("текст вопроса", "")).lower()]
    menu_items_column.controls.clear(); menu_items_column.controls.append(create_menu_card("🔍 Найдено совпадений", len(state["search_results"]), lambda e: start_test("SEARCH_RESULT"), True)); state["active_page"].update()

def show_menu():
    if not state["active_page"]: return
    page = state["active_page"]; main_layout.controls.clear(); page.scroll = ft.ScrollMode.AUTO
    state.update({"is_favorite_mode": False, "is_review_mode": False, "is_notebook_mode": False, "current_section_name": "", "current_df": []})
    tc = get_cur_color()
    header = ft.Row([ft.Text("Тренажёр ОТ и ЭБ", size=20, weight=ft.FontWeight.BOLD, expand=True), ft.Row([ft.IconButton(ft.Icons.BAR_CHART, icon_color=tc, on_click=lambda e: show_stats_dialog()), ft.IconButton(ft.Icons.SETTINGS, icon_color=tc, on_click=lambda e: show_settings_dialog())], spacing=0)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    sections = {}
    for q in questions_data:
        full_sec_name = str(q.get("раздел", "1")).strip()
        sections[full_sec_name] = sections.get(full_sec_name, []) + [q]
    menu_items_column.controls.clear()
    r1 = ft.Row([ft.Container(create_menu_card("🟥 Ошибки", len(get_all_wrong()), lambda e: start_test("REVIEW"), True), expand=True), ft.Container(create_menu_card("🟦 Конспект", len(get_all_notebook()), lambda e: start_test("NOTEBOOK"), True), expand=True)], spacing=8)
    r2 = ft.Row([ft.Container(create_menu_card("🟪 20 вопросов", 20, lambda e: start_test("RANDOM_20"), True), expand=True), ft.Container(create_menu_card("🟨 Избранные", len(load_json(fav_path, [])), lambda e: start_test("FAVORITES"), True), expand=True)], spacing=8)
    menu_items_column.controls.extend([r1, r2, ft.Container(height=5)])
    for s in sorted(sections.keys(), key=lambda x: int(x.split(".")[0]) if "." in x and x.split(".")[0].isdigit() else 999):
        ql = sections[s]
        if ql: 
            clean_sec_id = s.split(".")[0].strip() if "." in s else "1"
            menu_items_column.controls.append(create_menu_card(ql[0].get("раздел", s), len(ql), lambda e, sec=s: start_test(sec), sec_id=clean_sec_id))
    search_input.on_change = filter_search
    main_layout.controls.extend([header, ft.Row([search_input]), ft.Divider(height=5, color=ft.Colors.TRANSPARENT), menu_items_column])
    page.update()

def start_test(sec_name):
    state.update({"index": 0, "score": 0, "start_time": time.time(), "is_favorite_mode": sec_name == "FAVORITES", "is_review_mode": sec_name == "REVIEW", "is_notebook_mode": sec_name == "NOTEBOOK", "current_section_name": sec_name})
    if sec_name == "REVIEW": state["current_df"] = get_all_wrong()
    elif sec_name == "NOTEBOOK": state["current_df"] = get_all_notebook()
    elif sec_name == "FAVORITES": state["current_df"] = load_json(fav_path, [])
    elif sec_name == "SEARCH_RESULT": state["current_df"] = state["search_results"]
    elif sec_name == "RANDOM_20": state["current_df"] = random.sample(questions_data, min(20, len(questions_data)))
    else: state["current_df"] = [q for q in questions_data if str(q.get("раздел", "1")).strip() == str(sec_name).strip()]
    if not state["current_df"]: state["active_page"].open(ft.AlertDialog(title=ft.Text("📭 Пусто"), content=ft.Text("Нет вопросов."))); return
    if settings.get("shuffle_questions", True) and sec_name not in ["REVIEW", "NOTEBOOK", "FAVORITES", "SEARCH_RESULT", "RANDOM_20"]: random.shuffle(state["current_df"])
    setup_test_screen(); load_question()

def load_question():
    if state["index"] >= len(state["current_df"]): finish_test(); return
    q = state["current_df"][state["index"]]; state.update({"answered_current": False, "selected_options_indices": []})
    result_text.value, confirm_btn.visible = "", False; progress_bar.value = state["index"] / len(state["current_df"])
    raw_sec = q.get("раздел", "1")
    sec_color_id = raw_sec.split(".")[0].strip() if "." in raw_sec else "1"
    progress_bar.color = get_sec_color(sec_color_id)
    question_text.value = f"{q.get('текст вопроса', '')}"
    is_f = any(x.get("текст вопроса") == q.get("текст вопроса") for x in load_json(fav_path, []))
    fav_btn.icon, fav_btn.icon_color = (ft.Icons.STAR, ft.Colors.AMBER_500) if is_f else (ft.Icons.STAR_OUTLINED, ft.Colors.WHITE if settings.get("dark_theme", True) else ft.Colors.BLACK)
    is_n = any(x.get("текст вопроса") == q.get("текст вопроса") for x in get_all_notebook())
    notebook_btn.icon, notebook_btn.icon_color = (ft.Icons.BOOKMARK, ft.Colors.BLUE_500) if is_n else (ft.Icons.BOOKMARK_OUTLINED, ft.Colors.WHITE if settings.get("dark_theme", True) else ft.Colors.BLACK)
    ro, ct = [x.strip() for x in q.get("варианты", "").split("|") if x.strip()], q.get("ответ", "").strip()
    state["is_multiple_choice"] = (ct.startswith("[") and ct.endswith("]")) or ("," in ct)
    correct_indices = [x.strip() for x in ct.replace("[", "").replace("]", "").split(",") if x.strip()]
    state["shuffled_options"] = []
    for ri, o in enumerate(ro): state["shuffled_options"].append({"text": o, "is_correct": (o in correct_indices) or (str(ri + 1) in correct_indices)})
    if settings.get("shuffle_options", True): random.shuffle(state["shuffled_options"])
    options_column.controls.clear()
    for i, opt in enumerate(state["shuffled_options"]):
        options_column.controls.append(ft.Container(content=ft.Text(opt["text"], size=14, color=ft.Colors.WHITE if settings.get("dark_theme", True) else ft.Colors.BLACK), padding=ft.Padding(left=12, right=12, top=12, bottom=12), border=ft.border.all(1, ft.Colors.GREY_700 if settings.get("dark_theme", True) else ft.Colors.GREY_400), border_radius=10, bgcolor=ft.Colors.GREY_900 if settings.get("dark_theme", True) else ft.Colors.GREY_100, on_click=lambda e, idx=i: select_option(idx)))
    state["active_page"].update()
def select_option(idx):
    if state["answered_current"]: return
    if state["is_multiple_choice"]:
        if idx in state["selected_options_indices"]: state["selected_options_indices"].remove(idx)
        else: state["selected_options_indices"].append(idx)
        confirm_btn.visible = len(state["selected_options_indices"]) > 0
        for i, c in enumerate(options_column.controls): c.bgcolor = (ft.Colors.ORANGE_900 if settings.get("dark_theme", True) else ft.Colors.ORANGE_100) if i in state["selected_options_indices"] else (ft.Colors.GREY_900 if settings.get("dark_theme", True) else ft.Colors.GREY_100)
        state["active_page"].update()
    else: 
        state["selected_options_indices"] = [idx]
        state["answered_current"] = True
        check_answer()

def check_answer():
    state["answered_current"] = True; confirm_btn.visible = False; q = state["current_df"][state["index"]]; is_all = True
    if state["is_multiple_choice"]:
        if not state["selected_options_indices"]: is_all = False
        else:
            for i, o in enumerate(state["shuffled_options"]):
                if o["is_correct"] != (i in state["selected_options_indices"]): is_all = False
    else:
        if not state["selected_options_indices"]: is_all = False
        else:
            sel_idx = state["selected_options_indices"][0]
            is_all = state["shuffled_options"][sel_idx]["is_correct"]
            
    trigger_vibration(success=is_all)
    for i, c in enumerate(options_column.controls):
        o = state["shuffled_options"][i]; is_s = i in state["selected_options_indices"]
        if o["is_correct"] and is_s: c.bgcolor = ft.Colors.GREEN_900 if settings.get("dark_theme", True) else ft.Colors.GREEN_100
        elif o["is_correct"] and not is_s: c.bgcolor = ft.Colors.BLUE_900 if settings.get("dark_theme", True) else ft.Colors.BLUE_100
        elif not o["is_correct"] and is_s: c.bgcolor = ft.Colors.RED_900 if settings.get("dark_theme", True) else ft.Colors.RED_100
    if is_all: state["score"] += 1; remove_wrong_q(q.get("текст вопроса", "")); result_text.value = "🎉 Правильно!"; result_text.color = ft.Colors.GREEN_400 if settings.get("dark_theme", True) else ft.Colors.GREEN_600
    else: add_wrong_q(q); result_text.value = f"💡 Подсказка:\n• {q.get('подсказка', 'Разбор отсутствует.')}"; result_text.color = ft.Colors.RED_400 if settings.get("dark_theme", True) else ft.Colors.RED_600
    state["active_page"].update()
    if is_all and settings.get("auto_next", True) and not settings.get("exam_mode", False): state["active_page"].run_task(async_load_question)
    else:
        btn_text = "➡️ Следующий вопрос" if (state["index"] + 1) < len(state["current_df"]) else "🏁 Завершить тест"
        confirm_btn.text, confirm_btn.visible = btn_text, True; confirm_btn.on_click = lambda e: next_question(); state["active_page"].update()

def next_question(): state["index"] += 1; load_question()
def setup_test_screen():
    page = state["active_page"]; main_layout.controls.clear(); page.scroll = ft.ScrollMode.AUTO
    mr = ft.Row([ft.Text(f"Вопрос {state['index'] + 1} из {len(state['current_df'])}", size=14, weight=ft.FontWeight.BOLD), ft.Row([fav_btn, notebook_btn, del_nb_btn] if state["current_section_name"] in ["FAVORITES", "NOTEBOOK"] else [fav_btn, notebook_btn], spacing=0)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    main_layout.controls.extend([ft.Row([back_to_menu_btn, timer_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), progress_bar, mr, question_text, ft.Row([ft.Container(content=result_text, padding=ft.Padding(top=5, bottom=5))], alignment=ft.MainAxisAlignment.CENTER), options_column, confirm_btn]); page.update()

def finish_test():
    page = state["active_page"]; main_layout.controls.clear(); total = len(state["current_df"]); m, s = divmod(int(time.time() - state["start_time"]), 60)
    h = load_json(st_path, []); h.append({"date": time.strftime("%d.%m.%Y %H:%M"), "section": state["current_section_name"], "score": state["score"], "total": total}); save_json(st_path, h)
    main_layout.controls.append(ft.Column([ft.Text("🎉 Тестирование завершено!", size=20, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER), ft.Text(f"Результат: {state['score']} из {total} ({(state['score']/total*100) if total else 0:.1f}%)", size=16, text_align=ft.TextAlign.CENTER), ft.Text(f"⏱️ Время: {m:02d}:{s:02d}", size=14, text_align=ft.TextAlign.CENTER), ft.Container(height=10), ft.FilledButton("📁 В главное меню", on_click=lambda e: show_menu(), style=square_style)], cross_axis_alignment=ft.CrossAxisAlignment.CENTER, spacing=15)); page.update()

def main(page: ft.Page):
    global questions_data, fav_path, nb_path, wr_path, st_path, se_path, settings
    state["active_page"] = page  
    
    data_dir = page.environment.get("FLET_APP_STORAGE_DATA_DIR", "")
    if not data_dir:
        import tempfile
        data_dir = tempfile.gettempdir()
        
    os.makedirs(data_dir, exist_ok=True)
    
    fav_path = os.path.join(data_dir, "fv.json")
    nb_path = os.path.join(data_dir, "nb.json")
    wr_path = os.path.join(data_dir, "wr.json")
    st_path = os.path.join(data_dir, "st.json")
    se_path = os.path.join(data_dir, "se.json")
    
    settings = load_json(se_path, {"dark_theme": True, "exam_mode": False, "show_hints": True, "shuffle_options": True, "shuffle_questions": True, "sounds": True, "adaptive_colors": True, "theme_style": "classic", "auto_next": True})
    
    page.theme_mode = ft.ThemeMode.DARK if settings.get("dark_theme", True) else ft.ThemeMode.LIGHT  
    page.controls.clear()
    page.add(ft.SafeArea(content=main_layout))
    
    fav_btn.on_click, notebook_btn.on_click, del_nb_btn.on_click = lambda e: toggle_fav_or_nb(fav_path), lambda e: toggle_fav_or_nb(nb_path), lambda e: toggle_fav_or_nb(nb_path)
    back_to_menu_btn.on_click = lambda e: show_menu()
    
    if not questions_data:
        local_text = QUESTIONS_TEXT
        try:
            if os.path.exists("database.py"):
                with open("database.py", "r", encoding="utf-8") as db_file:
                    content = db_file.read()
                    if "QUESTIONS_TEXT =" in content:
                        local_text = content.split("QUESTIONS_TEXT =")[-1].strip().strip('"').strip("'")
        except:
            pass
            
        local_data = []
        for line in local_text.strip().replace("\r", "").split("\n"):
            if not line.strip() or line.startswith("Раздел;"): continue  
            p = line.split(";")
            if len(p) >= 5:
                local_data.append({
                    "раздел": p[0].strip(), "номер": p[1].strip(), "text вопроса": p[2].strip(),
                    "ответ": p[3].strip(), "варианты": p[4].strip(),
                    "подсказка": p[5].strip() if len(p) > 5 else "Разбор отсутствует."
                })
        questions_data = local_data if local_data else [{"раздел": "1. Тест", "номер": "1", "текст вопроса": "Тест", "ответ": "1", "варианты": "Ответ|Вариант 2", "подсказка": "Разбор"}]
        
    show_menu()

if __name__ == "__main__":
    ft.run(main)
