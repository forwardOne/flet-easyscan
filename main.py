import flet as ft
import json
import threading
import scan_logic # scan_logic.py


# --- Constants ---
TARGET_IP_DEFAULT = "127.0.0.1" # 安全のためデフォルトはローカルホスト
PORT_RANGE_DEFAULT = "1-1024" 

# --- Scanning statuses ---
SCANNING_STATUS_PREPARING = "準備完了"
SCANNING_STATUS_STARTING = "スキャン開始"
SCANNING_STATUS_SCANNING = "スキャン中"
SCANNING_STATUS_COMPLETED = "スキャン完了"
SCANNING_STATUS_VALUE_ERROR = "不正なポート範囲"
SCANNING_STATUS_PORTS_DONT_EXIST = "スキャン対象ポート無し"

# --- Service Name Mapping ---
SERVICES_FILE_PATH = "services.json"
PORT_SERVICES = {}

def load_port_services(filepath: str) -> dict:
    # JSONファイル検証 エラーハンドリング手法としてGeminiからの提案
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f) # 問題なければJSON読み込み
    except FileNotFoundError:
        print(f"定義ファイル '{filepath}' が見つかりません。")
        return {}
    except json.JSONDecodeError:
        print(f"定義ファイル '{filepath}' の形式が正しくありません。")
        return {}


# --- Main Function ---
def main(page: ft.Page):
    # ページ要素
    page.title = "EasyScan(Socket)"
    page.window.width = 600
    page.window.height = 500
    page.window.maximizable = False
    page.window.opacity = 0.95
    page.theme_mode = ft.ThemeMode.SYSTEM
    
    # グローバル変数のPORT_SERVICESを初期化
    global PORT_SERVICES
    PORT_SERVICES = load_port_services(SERVICES_FILE_PATH)

    # UI要素
    target_input = ft.TextField(label="ターゲットIP/ホスト", value=f"{TARGET_IP_DEFAULT}", expand=True)
    port_range_input = ft.TextField(label="ポート範囲 (e.g. 1-1024)", value=f"{PORT_RANGE_DEFAULT}", expand=True)
    scan_button = ft.ElevatedButton(f"{SCANNING_STATUS_STARTING}", on_click=lambda _: start_scan())
    status_text = ft.Text(f"{SCANNING_STATUS_PREPARING}", size=16, color="blue")
    results_text = ft.Column([], expand=True, scroll="always")
    
    # ポート範囲指定の確認
    def parse_port_range(port_range_str):
        ports = []
        parts = port_range_str.split(',')
        for part in parts:
            if '-' in part:
                start, end = map(int, part.split('-'))
                ports.extend(range(start, end + 1))
            else:
                ports.append(int(part))
        return sorted(list(set(ports)))

    # open_ports_info は scan_logic からの結果を直接処理するため不要


    # スキャン開始時の処理
    def start_scan():
        results_text.controls.clear()
        status_text.value = f"{SCANNING_STATUS_SCANNING}"
        scan_button.disabled = True
        page.update() # 開始時に既存情報をクリアして画面更新

        target_ip = target_input.value
        port_range_str = port_range_input.value
        
        try:
            # ポート範囲のパース (これはUIからの入力なので引き続き必要)
            ports_to_scan = parse_port_range(port_range_str)
            print(f"\n--- Scan (via scan_logic) started for: {target_ip} ---")
        except ValueError:
            results_text.controls.append(ft.Text(f"{SCANNING_STATUS_VALUE_ERROR}", color="red"))
            scan_button.disabled = False
            page.update()
            return # 不正値の場合は終了
        
        if not ports_to_scan:
            results_text.controls.append(ft.Text(f"{SCANNING_STATUS_PORTS_DONT_EXIST}", color="red"))
            scan_button.disabled = False
            page.update()
            return # 存在しない場合は終了
        
        # scan_logic を使用してスキャンを実行するワーカースレッド
        def scan_worker():
            # scan_logic.scan_ports を呼び出し
            # 今回はTCPスキャンのみを実行
            scan_results = scan_logic.scan_ports(
                target_ip=target_ip,
                tcp_ports=ports_to_scan,
                udp_ports=None # UDPは次回以降
                # tcp_timeout は scan_logic のデフォルト値を使用
            )

            # UI更新のために結果をメインスレッドに渡す必要があるが、
            # Fletでは page.update() をワーカースレッドから直接呼ぶことは非推奨。
            # ただし、小規模な更新や、ユーザーがpage.update()のタイミングを制御できる場合は許容されることも。
            # ここでは、結果表示の更新を行う。
            # results_text.controls.clear() # スキャン開始時にクリア済み

            open_ports_count = 0
            if not scan_results:
                results_text.controls.append(ft.Text("スキャン結果がありませんでした。", color="orange"))
            elif any(res.get('status', '').startswith('invalid_ip') for res in scan_results):
                results_text.controls.append(ft.Text(f"エラー: {scan_results[0]['status']}", color="red"))
            else:
                for res in scan_results: # scan_logicからの結果は既にソート済み
                    port_num_str = str(res['port'])
                    scan_type = res.get('type', 'N/A').upper()
                    status = res['status']

                    service_name_display = ""
                    if port_num_str in PORT_SERVICES:
                        service_info = PORT_SERVICES.get(port_num_str)
                        if service_info:
                            name_from_json = service_info.get("name", "")
                            protocol_from_json = service_info.get("protocol", "").upper()
                            if scan_type in protocol_from_json or "TCP/UDP" in protocol_from_json or not protocol_from_json:
                                service_name_display = name_from_json

                    display_text = f"{res['port']}/{res.get('type','n/a')} - {status}"
                    if service_name_display:
                        display_text += f" ({service_name_display})"

                    color = "orange" # Default color
                    if status == 'open':
                        color = "green"
                        open_ports_count += 1
                    elif 'error' in status or 'oserror' in status:
                        color = "red"
                    elif status == 'closed': # closed は表示しないか、控えめに
                        continue # 表示しない場合
                        # color = ft.colors.with_opacity(0.5, "grey") # 控えめに表示する場合
                    
                    results_text.controls.append(ft.Text(display_text, color=color))

                if open_ports_count == 0 and not any(r['status'] == 'open' for r in scan_results if not r.get('status','').startswith('invalid_ip')):
                    results_text.controls.append(ft.Text("オープンポートは見つかりませんでした。", color="blue"))

            status_text.value = f"{SCANNING_STATUS_COMPLETED}"
            scan_button.disabled = False
            page.update()
        
        # スキャンを非同期で実行
        threading.Thread(target=scan_worker, daemon=True).start()

    # UI要素を画面に追加
    page.add(
        ft.Column(
            [
                ft.ResponsiveRow(
                    [
                        ft.Container(content=target_input, col={'xs': 12, 'sm': 12, 'md': 12}),
                        ft.Container(content=port_range_input, col={'xs': 12, 'sm': 12, 'md': 12}),
                        ft.Container(content=scan_button, col={'xs': 12, 'sm': 12, 'md': 12}),
                    ],
                ),
                ft.Row([ft.Text("Status:", size=20), status_text]),
                ft.Container(
                    content=results_text,
                    alignment=ft.alignment.center,
                    expand=True,
                    padding=10,
                )
            ],
            expand=True
        )
    )

if __name__ == "__main__":
    ft.app(target=main)