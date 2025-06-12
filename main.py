import flet as ft
import json
import threading
import scan_logic # scan_logic.py



# --- Constants ---
TARGET_IP_DEFAULT = "127.0.0.1" # localhost
PORT_RANGE_DEFAULT = "1-450,5357" # safe range for testing

# --- Service Name Mapping ---
SERVICES_FILE_PATH = "services.json" # service name map
PORT_SERVICES = {}

# --- Scanning statuses ---
SCANNING_STATUS_PREPARING = "Ready"
SCANNING_STATUS_SCANNING = "Scanning..."
SCANNING_STATUS_COMPLETED = "Completed"
SCANNING_STATUS_VALUE_ERROR = "Value Error"
SCANNING_STATUS_PORTS_DONT_EXIST = "Ports dont exist"

# --- Validate and Load JSON File ---
def load_port_services(filepath: str) -> dict:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"定義ファイル '{filepath}' が見つかりません。")
        return {}
    except json.JSONDecodeError:
        print(f"定義ファイル '{filepath}' の形式が正しくありません。")
        return {}


# --- Helper Functions (moved to module level) ---
def _parse_port_range(port_range_str: str) -> list[int]:
    ''' ポート範囲文字列をパースしてポート番号のリストを返す '''
    ports = []
    parts = port_range_str.split(',')
    for part in parts:
        if '-' in part:
            start, end = map(int, part.split('-'))
            ports.extend(range(start, end + 1))
        else:
            ports.append(int(part))
    return sorted(list(set(ports)))

def _create_result_text_widget(res_item: dict, port_services_data: dict) -> tuple[ft.Text | None, bool]:
    ''' スキャン結果を成型しFlet Textとオープンかどうかのフラグを返す '''
    status = res_item['status']
    is_open_port = False
    
    # 'closed' ステータスのポートは表示しない
    if status == 'closed':
        return None, False
    
    # ポート番号とスキャンタイプ
    port_num_str = str(res_item['port'])
    scan_type = res_item.get('type', 'N/A').upper()
    service_name_display = ""
    
    # ポート番号がサービス定義に存在するか
    if port_num_str in port_services_data:
        service_info = port_services_data.get(port_num_str)
        # プロトコル名の確認
        if service_info:
            name_from_json = service_info.get("name", "")
            protocol_from_json = service_info.get("protocol", "").upper()
            # スキャンタイプの確認
            if scan_type in protocol_from_json or "TCP/UDP" in protocol_from_json or not protocol_from_json:
                service_name_display = name_from_json
                
    # 表示用テキストの成型
    display_text = f"{res_item['port']}/{res_item.get('type','n/a')} - {status}"
    # サービス名が取得できた場合 表示用テキストの末尾に追加
    if service_name_display:
        display_text += f" ({service_name_display})"
        
    # ステータスカラー
    color = "orange"
    if status == 'open':
        color = "green"
        is_open_port = True
    elif 'error' in status or 'oserror' in status:
        color = "red"
    return ft.Text(display_text, color=color), is_open_port



# --- Main Function ---
def main(page: ft.Page):
    # ページ要素
    page.title = "EasyScan"
    page.window.width = 700
    page.window.height = 800
    page.window.maximizable = False
    page.window.opacity = 0.95
    page.theme_mode = ft.ThemeMode.SYSTEM
    
    # Init global PORT_SERVICES
    global PORT_SERVICES
    PORT_SERVICES = load_port_services(SERVICES_FILE_PATH)


    # --- Input Area Elements ---
    target_input = ft.TextField(label="Target IP/Host", value=f"{TARGET_IP_DEFAULT}", expand=True)

    profile_options = [
        ft.dropdown.Option("Default (TCP & UDP)"),
        ft.dropdown.Option("TCP Only"),
        ft.dropdown.Option("UDP Only"),
    ]
    profile_dropdown = ft.Dropdown(
        label="Profile",
        options=profile_options,
        value="Default (TCP & UDP)",
        expand=True
    )

    port_range_input = ft.TextField(label="Port Range (e.g. 1-1024)", value=f"{PORT_RANGE_DEFAULT}", expand=True)
    scan_button = ft.ElevatedButton(f"Scan", on_click=lambda _: start_scan())
    status_text = ft.Text(f"{SCANNING_STATUS_PREPARING}", size=16, color="blue")


    # --- Output Area Elements ---
    scan_output_log_area = ft.Column([], expand=True, scroll="always") # For "Scan Output" tab

    ports_hosts_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Host/IP")),
            ft.DataColumn(ft.Text("Port")),
            ft.DataColumn(ft.Text("Protocol")),
            ft.DataColumn(ft.Text("State")),
            ft.DataColumn(ft.Text("Service/Version")), # Combined for now
        ],
        rows=[],
        expand=True,
    )

    output_tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=[
            ft.Tab(text="Scan Output", content=scan_output_log_area),
            ft.Tab(text="Ports/Hosts", content=ft.Column([ports_hosts_table], scroll="always", expand=True)),
        ],
        expand=True,
    )


    # スキャン開始処理
    def start_scan():
        # 開始時に既存情報をクリアして画面更新
        scan_output_log_area.controls.clear()
        ports_hosts_table.rows.clear()
        status_text.value = f"{SCANNING_STATUS_SCANNING}"
        scan_button.disabled = True
        page.update()

        target_ip = target_input.value
        port_range_str = port_range_input.value
        selected_profile = profile_dropdown.value
        
        # パース呼び出し
        try:
            ports_to_scan = _parse_port_range(port_range_str)
            print(f"\n--- TCP/UDP Scan (via scan_logic) started for: {target_ip} on ports: {port_range_str} ---")
        # 不正値の場合は終了
        except ValueError:
            scan_output_log_area.controls.append(ft.Text(f"{SCANNING_STATUS_PORTS_DONT_EXIST}", color="red"))
            scan_button.disabled = False
            page.update()
            return
        # 存在しない場合は終了
        if not ports_to_scan:
            scan_output_log_area.controls.append(ft.Text(f"{SCANNING_STATUS_PORTS_DONT_EXIST}", color="red"))
            scan_button.disabled = False
            page.update()
            return
        
        # scan_logic.scan_ports を呼び出し
        def scan_worker():
            # プロファイルに基づいてスキャン対象ポートを決定
            tcp_ports_to_scan = None
            udp_ports_to_scan = None

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

            # UI更新のために結果をメインスレッドに渡す必要があるが、
            # 本来Fletでは page.update() をワーカースレッドから直接呼ぶことは非推奨。
            # ここでは、結果表示の更新を行う。

            open_ports_count = 0
            if not scan_results:
                scan_output_log_area.controls.append(ft.Text("スキャン結果がありませんでした。", color="orange"))
            elif any(res.get('status', '').startswith('invalid_ip') for res in scan_results):
                error_message = f"エラー: {scan_results[0]['status']}"
                scan_output_log_area.controls.append(ft.Text(error_message, color="red"))
                ports_hosts_table.rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(target_ip)),
                        ft.DataCell(ft.Text("-")),
                        ft.DataCell(ft.Text("-")),
                        ft.DataCell(ft.Text(error_message, color="red")),
                        ft.DataCell(ft.Text("-")),
                    ])
                )
            else:
                for res_item in scan_results: # scan_logicからの結果は既にソート済み
                    # "Scan Output" Tab
                    text_widget, is_open = _create_result_text_widget(res_item, PORT_SERVICES)
                    if text_widget:
                        scan_output_log_area.controls.append(text_widget)
                    if is_open:
                        open_ports_count += 1
                    
                    # "Ports/Hosts" Tab - 'closed' 以外を表示
                    if res_item['status'] != 'closed':
                        service_name = text_widget.value.split('(')[-1].replace(')','').strip() if text_widget and '(' in text_widget.value else "N/A"
                        if " - " in service_name: # "status (service_name)" から service_name を抽出
                            service_name = service_name.split('(')[-1].replace(')','').strip() if '(' in service_name else service_name.split(" - ")[-1].strip()

                        ports_hosts_table.rows.append(
                            ft.DataRow(cells=[
                                ft.DataCell(ft.Text(target_ip)),
                                ft.DataCell(ft.Text(str(res_item['port']))),
                                ft.DataCell(ft.Text(res_item.get('type', 'N/A').upper())),
                                ft.DataCell(ft.Text(res_item['status'], color=text_widget.color if text_widget else "black")),
                                ft.DataCell(ft.Text(service_name if service_name != res_item['status'] else "N/A")),
                            ])
                        )
                
                # スキャン結果があり (invalid_ipエラーではなく)、オープンポートが一つも見つからなかった場合
                if open_ports_count == 0:
                    scan_output_log_area.controls.append(ft.Text("オープンポートは見つかりませんでした。", color="blue"))

            status_text.value = f"{SCANNING_STATUS_COMPLETED}"
            scan_button.disabled = False
            page.update()
        
        # 非同期で実行
        threading.Thread(target=scan_worker, daemon=True).start()


    # UI要素を画面に追加
    page.add(
        ft.Column(
            [
                ft.ResponsiveRow(
                    [
                        ft.Container(content=target_input, padding=5, col={'xs': 12, 'sm': 6, 'md': 6}),
                        ft.Container(content=profile_dropdown, padding=5, col={'xs': 12, 'sm': 6, 'md': 6}),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.ResponsiveRow(
                    [
                        ft.Container(content=port_range_input, padding=5, col={'xs': 12, 'sm': 12, 'md': 10}),
                        ft.Container(content=scan_button, padding=5, margin=ft.margin.only(top=3), col={'xs': 12, 'sm': 12, 'md': 2})
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Row(
                    [
                        ft.Text("Status:", size=20),
                        ft.Container(content=status_text, margin=ft.margin.only(top=3)),
                    ],
                    alignment=ft.MainAxisAlignment.START
                ),
                output_tabs, # 結果表示エリアをタブに置き換え
            ],
            expand=True
        )
    )

if __name__ == "__main__":
    ft.app(target=main)