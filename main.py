import flet as ft
from views import EasyScanView

# --- Constants ---
def main(page: ft.Page):
    page.title = "Easy Low-layer scan"
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

    # メインコンテナ
    main_container = ft.Container(content=scan_view, expand=True, padding=ft.padding.all(20))

    # ページ全体のレイアウト
    page.add(main_container)

if __name__ == "__main__":
    ft.app(target=main)