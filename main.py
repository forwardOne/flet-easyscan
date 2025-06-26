import flet as ft
from views import EasyScanView

# --- Constants ---
def main(page: ft.Page):
    page.title = "EasyScan"
    page.window.width = 850
    page.window.height = 600
    page.window.resizable = True
    page.window.minimizable = True
    page.window.maximizable = False
    page.window.opacity = 0.95
    page.theme_mode = ft.ThemeMode.DARK

    app = EasyScanView(page) # EasyScanView のインスタンスを作成
    page.add(app)

if __name__ == "__main__":
    ft.app(target=main)