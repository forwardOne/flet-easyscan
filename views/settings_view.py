import flet as ft

class SettingsView(ft.Container):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.content = self.build()

    def build(self):
        return ft.Column(
            [
                ft.Text("Settings", size=30, weight=ft.FontWeight.BOLD),
                ft.Text("This is the settings page. More features will be added here."),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        