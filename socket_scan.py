import flet as ft
import socket
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

'''EasyScan(Socket)
ScapyやNpcapに依存せず、Pythonの標準ライブラリのみで実装したGUI簡易スキャナーです。
指定されたITアドレスとポート範囲に対してTCP(3wayハンドシェイク)スキャンを行います。
アプリの初期段階の名残として残しています。jsonファイルは本体と共有しています。

PowerShellかターミナルから直接実行してください。

Caution!!
本プログラムは学習目的のために提供しており、ローカルホスト以外の実際のネットワークに対し、
無断でスキャンを実行すると法的な問題やネットワークへの影響を引き起こす可能性があります。
Caution!!
'''


# --- Constants ---
TARGET_IP_DEFAULT = "127.0.0.1" # 安全のためデフォルトはローカルホスト
PORT_RANGE_DEFAULT = "1-1024" 
SOCKET_TIMEOUT = 1 # 動作の確実性を担保するために1秒指定 短くしてもよい
MAX_WORKERS = 200

# --- Scanning statuses ---
SCANNING_STATUS_PREPARING = "準備完了"
SCANNING_STATUS_STARTING = "スキャン開始"
SCANNING_STATUS_SCANNING = "スキャン中"
SCANNING_STATUS_COMPLETED = "スキャン完了"
SCANNING_STATUS_VALUE_ERROR = "不正なポート範囲"
SCANNING_STATUS_PORTS_DONT_EXIST = "スキャン対象ポート無し"

# --- Socket error codes (Windows) ---
ERROR_CODE_CONNECTION_REFUSED = 10061
ERROR_CODE_WOULD_BLOCK = 10035

# --- Port scan display statuses ---
DISPLAY_STATUS_OPEN = "オープン"
DISPLAY_STATUS_CONNECTION_REFUSED = "接続拒否"
DISPLAY_STATUS_TIMEOUT = "タイムアウト"
DISPLAY_STATUS_NO_RESPONSE = "応答なし"
DISPLAY_STATUS_ERROR = "エラー"
DISPLAY_STATUS_HOST_ERROR = "ホスト解決エラー"

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

    open_ports_info = [] # ソート用にオープンポート情報を格納


    # スキャンロジック本体
    def scan_port(target_ip, port):
        sock = None # 初期化
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(SOCKET_TIMEOUT)

            # ポート番号に対応するサービス名を取得
            service_info = PORT_SERVICES.get(str(port))
            port_display = f"{port}"
            
            # デフォルトプロトコルを設定
            current_scan_protocol = "TCP"
            
            # service_infoがNoneでない(辞書である)ことをチェック
            if service_info:
                name = service_info.get("name", "")
                protocol_from_json = service_info.get("protocol")
                protocol_info = protocol_from_json if protocol_from_json else current_scan_protocol
                port_display = f"{port} ({name}, {protocol_info})" if name else f"{port} (不明, {protocol_info})"
            
            result = sock.connect_ex((target_ip, port))

            # ポートがオープンしている場合
            if result == 0:
                msg = f"{port_display}: {DISPLAY_STATUS_OPEN}"
                open_ports_info.append((port, msg))
                return True

            # 接続が拒否された場合
            elif result == ERROR_CODE_CONNECTION_REFUSED:
                results_text.controls.append(ft.Text(f"{port_display}: {DISPLAY_STATUS_CONNECTION_REFUSED}", color="orange"))

            # ブロックされた場合は視認性確保のため表示しない
            elif result != ERROR_CODE_WOULD_BLOCK:
                # 応答自体がない場合
                results_text.controls.append(ft.Text(f"{port_display}: {DISPLAY_STATUS_NO_RESPONSE} (コード: {result})", color="orange"))

        # ホスト名解決エラー
        except socket.gaierror:
            results_text.controls.append(ft.Text(f"{DISPLAY_STATUS_HOST_ERROR}: '{target_ip}' (ポート: {port_display})", color="red"))
            return False

        # タイムアウトした場合
        except socket.timeout:
            results_text.controls.append(ft.Text(f"{port_display}: {DISPLAY_STATUS_TIMEOUT}", color="orange"))

        # その他のエラー
        except Exception as e:
            results_text.controls.append(ft.Text(f"{port_display}: {DISPLAY_STATUS_ERROR} - {e}", color="orange"))

        # ソケットのクローズ
        finally:
            if sock:
                sock.close()

        # スキャン試行完了(オープンとは限らない)
        return True 


    # スキャン開始時の処理
    def start_scan():
        results_text.controls.clear()
        status_text.value = f"{SCANNING_STATUS_SCANNING}"
        scan_button.disabled = True
        open_ports_info.clear()
        page.update() # 開始時に既存情報をクリアして画面更新

        target_ip = target_input.value
        port_range_str = port_range_input.value
        
        # IPアドレスの検証
        try:
            ports_to_scan = parse_port_range(port_range_str)
            print(f"\n--- TCP(socket) スキャン開始: {target_ip} ---")
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
        
        # スレッドプールを使用してスキャンロジックを並列実行
        def scan_worker():
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {executor.submit(scan_port, target_ip, port): port for port in ports_to_scan}

                for future in as_completed(futures): # 完了したスキャン結果を待機
                    future.result() # 結果を取得した状態を保持

            # ポート番号順にソートして結果を表示
            for port, msg in sorted(open_ports_info):
                results_text.controls.append(ft.Text(msg, color="green"))

            status_text.value = f"{SCANNING_STATUS_COMPLETED}"
            scan_button.disabled = False
            # 画面更新してソート後のスキャン結果を表示
            # Fletの仕様に反しているが、処理的にはスレッドセーフ
            page.update()
            
            # ターミナルに出力
            print(f"スキャン完了: {len(open_ports_info)} 個のオープンポートが見つかりました。")
            for item in open_ports_info:
                print(item)
            return open_ports_info
        
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