import flet as ft
import json

TASKS_FILE = "C:\\MyProject\\flet-easyscan\\assets\\tasks.json"

def main(page: ft.Page):
    page.bgcolor = "#1F2227"
    page.padding = 0
    # page.window.frameless = True

    # --- データ管理 ---
    def load_tasks():
        try:
            with open(TASKS_FILE, "r") as f: return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError): return []

    def save_tasks(tasks_data):
        with open(TASKS_FILE, "w") as f: json.dump(tasks_data, f, indent=4)

    tasks = load_tasks()
    state = {
        "selected_index": 0 if tasks else -1,
        "is_editing": False # 編集状態を管理するフラグ
    }
    status_colors = {"IN PROGRESS": "#F7C948", "COMPLETED": "#00FF88", "TODO": "#FF6B6B"}

    # --- UI生成関数 ---
    def on_task_click(e):
        # タスクを切り替えるときは編集状態をリセット
        if state["is_editing"]:
            state["is_editing"] = False
        state["selected_index"] = e.control.data
        update_view()

    def task_card(title: str, subtitle: str, index: int, is_selected: bool, status: str):
        status_indicator = ft.CircleAvatar(bgcolor=status_colors.get(status, "#888888"), radius=5)
        return ft.Container(
            on_click=on_task_click, data=index, padding=ft.padding.symmetric(vertical=15, horizontal=20),
            bgcolor="#2A2D32" if not is_selected else "#3A3F45", border_radius=5,
            content=ft.Row([
                status_indicator,
                ft.Column([
                    ft.Text(title, color="white", size=16),
                    ft.Text(subtitle, color="#888888", size=12),
                ], spacing=5, horizontal_alignment=ft.CrossAxisAlignment.START, expand=True)
            ], spacing=15, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        )

    def create_task_detail_view(index: int):
        if not (0 <= index < len(tasks)):
            return ft.Column([ft.Text("Select a task", size=18, weight="bold", color="white")])

        task = tasks[index]

        def start_editing(e):
            state["is_editing"] = True
            update_view()

        def save_and_exit_editing(e):
            new_description = e.control.value
            tasks[index]["description"] = new_description
            save_tasks(tasks)
            state["is_editing"] = False
            update_view()

        if state["is_editing"]:
            description_content = ft.TextField(
                value=task["description"], multiline=True, border_color="#4D90FE", 
                on_blur=save_and_exit_editing, expand=True, autofocus=True
            )
        else:
            description_content = ft.Row([
                ft.Text(task["description"], color="#CCCCCC", size=12, selectable=True, expand=True),
                ft.IconButton(icon=ft.Icons.EDIT, icon_color="#CCCCCC", on_click=start_editing, tooltip="Edit description")
            ], vertical_alignment=ft.CrossAxisAlignment.START)

        return ft.Column([
            ft.Text(task["title"], size=20, weight="bold", color="white"),
            ft.Row([ft.Container(padding=ft.padding.symmetric(horizontal=6, vertical=2), bgcolor="#4D90FE", border_radius=4, content=ft.Text(tag, size=10, color="white")) for tag in task["tags"]], spacing=5),
            ft.Container(content=description_content, padding=ft.padding.only(top=10)),
            ft.Container(height=20),
            ft.Row([ft.Text(f"Status: {task['status']}", color=status_colors.get(task['status'], "white"))], spacing=10)
        ], spacing=8)

    def create_ai_agent_view():
        chat_history = ft.ListView(
            expand=True, spacing=15,
            controls=[
                ft.Row([ft.CircleAvatar(content=ft.Text("G"), bgcolor="#9C27B0", color="white", radius=16), ft.Container(padding=12, border_radius=10, bgcolor="#2A2D32", content=ft.Text("Hello! I'm Gemini. How can I help you with your cybersecurity tasks today?", color="white", size=14))], spacing=10),
                ft.Row([ft.Container(padding=12, border_radius=10, bgcolor="#3A3F45", content=ft.Text("Can you explain the 'Implement MFA for Admin Access' task in more detail?", color="white", size=14),expand=True)], alignment=ft.MainAxisAlignment.END),
                ft.Row([ft.CircleAvatar(content=ft.Text("G"), bgcolor="#9C27B0", color="white", radius=16), ft.Container(padding=12, border_radius=10, bgcolor="#2A2D32", content=ft.Text("Of course. The **'Implement MFA for Admin Access'** task involves configuring multi-factor authentication for all administrative accounts across production and development environments, ensuring compatibility with existing SSO solutions. It's currently marked as 'IN PROGRESS'.", color="white", size=14) ,expand=True)], spacing=10),
            ]
        )
        input_form = ft.Row([
            ft.TextField(hint_text="Send a message to the agent...", expand=True, border_color="#3A3F45", border_radius=10, color="white", bgcolor="#2A2D32", height=40, content_padding=10),
            ft.IconButton(icon=ft.Icons.SEND_ROUNDED, icon_color="white", bgcolor="#4D90FE")
        ], spacing=10)
        return ft.Column([chat_history, input_form], expand=True, spacing=15)

    # --- UIレイアウト ---
    rail = ft.NavigationRail(
        selected_index=1, label_type=ft.NavigationRailLabelType.NONE, min_width=60, bgcolor="#1A1C20",
        destinations=[
            ft.NavigationRailDestination(icon=ft.Icons.HOME_OUTLINED, selected_icon=ft.Icons.HOME, label="Home"),
            ft.NavigationRailDestination(icon=ft.Icons.VIEW_LIST_OUTLINED, selected_icon=ft.Icons.VIEW_LIST, label="Tasks"),
            ft.NavigationRailDestination(icon=ft.Icons.SETTINGS_OUTLINED, selected_icon=ft.Icons.SETTINGS, label="Settings"),
        ]
    )
    task_detail_view_content = ft.Column()
    task_list_view = ft.Column(spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH, scroll=ft.ScrollMode.AUTO)
    left_panel = ft.Container(
        padding=20, bgcolor="#1F2227", expand=1,
        content=ft.Column([
            ft.Container(content=task_detail_view_content, padding=ft.padding.only(bottom=20), expand=True),
            ft.Text("Task List", color="white", size=18, weight="bold"),
            ft.Container(height=10),
            ft.Container(content=task_list_view, expand=True),
        ], spacing=10)
    )
    right_panel = ft.Container(
        padding=20, bgcolor="#3A3F45", expand=1,
        content=create_ai_agent_view()
    )

    def update_view():
        selected_index = state["selected_index"]
        task_list_view.controls = [task_card(t["title"], t["subtitle"], i, selected_index == i, t["status"]) for i, t in enumerate(tasks)]
        task_detail_view_content.controls = [create_task_detail_view(selected_index)]
        page.update()

    page.add(ft.Row(controls=[rail, left_panel, right_panel], expand=True))
    update_view()

if __name__ == "__main__":
    ft.app(target=main)