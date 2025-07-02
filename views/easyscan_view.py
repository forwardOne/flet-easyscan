import flet as ft
import threading
from services import scan_logic
from utils import load_port_services, parse_port_range, create_result_text_widget

# --- Constants ---
TARGET_IP_DEFAULT = "127.0.0.1" # localhost
PORT_RANGE_DEFAULT = "1-450,5357" # safe range for testing

# --- Service Name Mapping ---
SERVICES_FILE_PATH = "data/services_name.json"

# --- Scanning statuses ---
SCANNING_STATUS_PREPARING = "Ready"
SCANNING_STATUS_SCANNING = "Scanning..."
SCANNING_STATUS_COMPLETED = "Completed"
SCANNING_STATUS_VALUE_ERROR = "Value Error"
SCANNING_STATUS_PORTS_DONT_EXIST = "Ports dont exist"




class EasyScanView(ft.Container):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.port_services = load_port_services(SERVICES_FILE_PATH)

        # --- Input Area Elements ---
        self.target_input = ft.TextField(label="Target IP/Host", value=f"{TARGET_IP_DEFAULT}", expand=True)

        profile_options = [
            ft.dropdown.Option("Default (TCP & UDP)"),
            ft.dropdown.Option("TCP Only"),
            ft.dropdown.Option("UDP Only"),
        ]
        self.profile_dropdown = ft.Dropdown(
            label="Profile",
            options=profile_options,
            value="Default (TCP & UDP)",
            expand=True
        )

        self.port_range_input = ft.TextField(label="Port Range (e.g. 1-1024)", value=f"{PORT_RANGE_DEFAULT}", expand=True)
        self.scan_button = ft.ElevatedButton(f"Scan", on_click=self.start_scan)
        self.status_text = ft.Text(f"{SCANNING_STATUS_PREPARING}", size=16, color="blue")

        # --- Output Area Elements ---
        self.scan_output_log_area = ft.Column([], expand=True, scroll="always")

        self.ports_hosts_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Host/IP")),
                ft.DataColumn(ft.Text("Port")),
                ft.DataColumn(ft.Text("Protocol")),
                ft.DataColumn(ft.Text("State")),
                ft.DataColumn(ft.Text("Service")),
                ft.DataColumn(ft.Text("Description")),
            ],
            rows=[],
            expand=True,
        )

        self.output_tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(text="Scan Output", content=self.scan_output_log_area),
                ft.Tab(text="Ports/Hosts", content=ft.Column([self.ports_hosts_table], scroll="always", expand=True)),
            ],
            expand=True,
        )
        
        self.content = self.build()
    
    # build メソッドでUIレイアウトを定義
    def build(self):
        # --- Scan Configuration Section ---
        scan_config_content = ft.Column(
            [
                ft.ResponsiveRow(
                    [
                        ft.Container(content=self.target_input, padding=5, col={'xs': 12, 'sm': 6, 'md': 6}),
                        ft.Container(content=self.profile_dropdown, padding=5, col={'xs': 12, 'sm': 6, 'md': 6}),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.ResponsiveRow(
                    [
                        ft.Container(content=self.port_range_input, padding=5, col={'xs': 12, 'sm': 12, 'md': 10}),
                        ft.Container(content=self.scan_button, padding=5, margin=ft.margin.only(top=3), col={'xs': 12, 'sm': 12, 'md': 2})
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            ]
        )

        scan_config_container = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Scan Configuration", style=ft.TextThemeStyle.TITLE_LARGE),
                    scan_config_content,
                ]
            ),
            padding=15,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=ft.border_radius.all(10),
            margin=ft.margin.only(bottom=20)
        )

        # --- Results Section ---
        results_container = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text("Results", style=ft.TextThemeStyle.TITLE_LARGE),
                            ft.Row(
                                [
                                    ft.Text("Status:"),
                                    self.status_text,
                                ],
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    self.output_tabs,
                ],
                expand=True,
            ),
            padding=15,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=ft.border_radius.all(10),
            expand=True,
        )

        return ft.Column(
            [
                ft.Text("Easy Scan", style=ft.TextThemeStyle.HEADLINE_MEDIUM, weight=ft.FontWeight.BOLD),
                scan_config_container,
                results_container,
            ],
            expand=True
        )
    
    # --- Start Scan Method ---
    # スキャン開始ボタンのクリックイベントハンドラ
    def start_scan(self, e):
        self.scan_output_log_area.controls.clear()
        self.ports_hosts_table.rows.clear()
        self.status_text.value = f"{SCANNING_STATUS_SCANNING}"
        self.scan_button.disabled = True

        target_ip = self.target_input.value
        port_range_str = self.port_range_input.value
        selected_profile = self.profile_dropdown.value

        # スキャン情報をOutputエリアの先頭に表示
        scan_info_text = f"--- {selected_profile} Scan started for: {target_ip} on ports: {port_range_str} ---"
        self.scan_output_log_area.controls.append(ft.Text(scan_info_text))
        
        self.page.update()

        # パース呼び出し
        try:
            ports_to_scan = parse_port_range(port_range_str)
            print(f"\n--- {selected_profile} Scan (via scan_logic) started for: {target_ip} on ports: {port_range_str} ---")
        # 不正値の場合は終了
        except ValueError:
            self.scan_output_log_area.controls.append(ft.Text(f"{SCANNING_STATUS_VALUE_ERROR}", color="red"))
            self.scan_button.disabled = False
            self.page.update()
            return
        # 存在しない場合は終了
        if not ports_to_scan:
            self.scan_output_log_area.controls.append(ft.Text(f"{SCANNING_STATUS_PORTS_DONT_EXIST}", color="red"))
            self.scan_button.disabled = False
            self.page.update()
            return
        
        threading.Thread(target=self.scan_worker, args=(target_ip, ports_to_scan), daemon=True).start()
        
    # --- Worker Function ---
    # 実行ワーカースレッド
    def scan_worker(self, target_ip: str, ports_to_scan: list[int]):
        selected_profile = self.profile_dropdown.value
        tcp_ports_to_scan = None
        udp_ports_to_scan = None
        
        # Scan Profile
        if selected_profile == "Default (TCP & UDP)":
            tcp_ports_to_scan = ports_to_scan
            udp_ports_to_scan = ports_to_scan
        elif selected_profile == "TCP Only":
            tcp_ports_to_scan = ports_to_scan
        elif selected_profile == "UDP Only":
            udp_ports_to_scan = ports_to_scan

        scan_results = scan_logic.scan_ports(
            target_ip=target_ip,
            tcp_ports=tcp_ports_to_scan,
            udp_ports=udp_ports_to_scan
        )

        open_ports_count = 0
        # スキャン結果無しの場合
        if not scan_results:
            self.scan_output_log_area.controls.append(ft.Text("スキャン結果がありませんでした。", color="orange"))
        # エラーの場合
        elif any(res.get('status', '').startswith('invalid_ip') for res in scan_results):
            error_message = f"エラー: {scan_results[0]['status']}"
            self.scan_output_log_area.controls.append(ft.Text(error_message, color="red"))
            self.ports_hosts_table.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(target_ip)),
                    ft.DataCell(ft.Text("-")),
                    ft.DataCell(ft.Text("-")),
                    ft.DataCell(ft.Text(error_message, color="red")),
                    ft.DataCell(ft.Text("-")),
                    ft.DataCell(ft.Text("-")),
                ])
            )
        # スキャン結果が存在する場合
        else:
            for res_item in scan_results:
                text_widget, is_open, service_name, description = create_result_text_widget(res_item, self.port_services)
                if text_widget:
                    self.scan_output_log_area.controls.append(text_widget)
                if is_open:
                    open_ports_count += 1
                
                if res_item['status'] != 'closed':
                    self.ports_hosts_table.rows.append(
                        ft.DataRow(cells=[
                            ft.DataCell(ft.Text(target_ip)),
                            ft.DataCell(ft.Text(str(res_item['port']))),
                            ft.DataCell(ft.Text(res_item.get('type', 'N/A').upper())),
                            ft.DataCell(ft.Text(res_item['status'], color=text_widget.color if text_widget else "default")),
                            ft.DataCell(ft.Text(service_name if service_name else "N/A")),
                            ft.DataCell(ft.Text(description if description else "N/A")),
                        ])
                    )
            
            if open_ports_count == 0 and not any(res.get('status', '').startswith('invalid_ip') for res in scan_results):
                self.scan_output_log_area.controls.append(ft.Text("オープンポートは見つかりませんでした。", color="blue"))

        self.status_text.value = f"{SCANNING_STATUS_COMPLETED}"
        self.scan_button.disabled = False
        self.page.update()
