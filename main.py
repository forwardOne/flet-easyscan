import flet as ft
from views import EasyScanView, SettingsView

# --- Constants ---
def main(page: ft.Page):
    page.title = "EasyScan"
    page.window.width = 950
    page.window.height = 600
    page.window.resizable = True
    page.window.minimizable = True
    page.window.maximizable = False
    page.window.opacity = 0.95
    page.dark_theme = ft.Theme(color_scheme_seed="blue")
    page.theme_mode = ft.ThemeMode.DARK

    # 各ビューのインスタンスを作成
    scan_view = EasyScanView(page)
    settings_view = SettingsView(page)

    # ビューを切り替えるためのメインコンテナ
    main_container = ft.Container(content=scan_view, expand=True, padding=ft.padding.all(20))

    def nav_change(e):
        selected_index = e.control.selected_index
        if selected_index == 0:
            main_container.content = scan_view
        elif selected_index == 1:
            main_container.content = settings_view
        page.update()

    # サイドバー (NavigationRail)
    rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.NONE,  # ラベルを非表示に
        destinations=[
            ft.NavigationRailDestination(
                icon=ft.Icons.PERM_SCAN_WIFI_OUTLINED,
                selected_icon=ft.Icons.PERM_SCAN_WIFI,
                label="Scan",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.SETTINGS_OUTLINED,
                selected_icon=ft.Icons.SETTINGS,
                label="Settings",
            ),
        ],
        on_change=nav_change,
        # アイコンを中央揃えにするための工夫
        leading=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        group_alignment= -0.1,
    )

    # ページ全体のレイアウト
    page.add(ft.Row([rail, ft.VerticalDivider(width=1), main_container], expand=True))

if __name__ == "__main__":
    ft.app(target=main)