import flet as ft
import socket
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

def main(page: ft.Page):
    page.title = "EasyScan(Flet)"
    page.window_width = 400
    page.window_height = 400
    page.theme_mode = ft.ThemeMode.DARK

    # UI要素
    target_input = ft.TextField(label="ターゲットIP/ホスト", value="127.0.0.1", expand=True)
    port_range_input = ft.TextField(label="ポート範囲 (例: 1-1024)", value="1-500", expand=True)
    scan_button = ft.ElevatedButton("スキャン開始", on_click=lambda _: start_scan())
    results_text = ft.Column([], expand=True, scroll="always")
    progress_bar = ft.ProgressBar(bar_height=10, expand=True, value=0, visible=False)

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

    open_ports_info = []

    def scan_port(target_ip, port):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((target_ip, port))
            if result == 0:
                try:
                    sock.send(b"\r\n")
                    banner = sock.recv(1024).decode("utf-8", errors="ignore").strip()
                except Exception:
                    banner = ""
                msg = f"ポート {port} がオープンしています。"
                if banner:
                    msg += f" バナー: {banner}"
                open_ports_info.append((port, msg))
                sock.close()
                return True
            elif result == 10061:
                results_text.controls.append(ft.Text(f"ポート {port}: 接続拒否", color="orange"))
            # 10035 は表示しない
            elif result not in [10035]:
                results_text.controls.append(ft.Text(f"ポート {port}: 応答なし (コード: {result})", color="orange"))
            sock.close()
        except socket.gaierror:
            results_text.controls.append(ft.Text(f"エラー: ホスト '{target_ip}' を解決できませんでした。", color="red"))
            return False
        except socket.timeout:
            results_text.controls.append(ft.Text(f"ポート {port}: タイムアウト", color="orange"))
        except Exception as e:
            results_text.controls.append(ft.Text(f"ポート {port}: エラー - {e}", color="orange"))
        return True

    def start_scan():
        results_text.controls.clear()
        results_text.controls.append(ft.Text("スキャンを開始します...\n"))
        progress_bar.value = 0
        progress_bar.visible = True
        scan_button.disabled = True
        open_ports_info.clear()
        page.update()

        target_ip = target_input.value
        port_range_str = port_range_input.value

        try:
            ports_to_scan = parse_port_range(port_range_str)
        except ValueError:
            results_text.controls.append(ft.Text("エラー: 不正なポート範囲です。例: 1-1024 または 80,443", color="red"))
            scan_button.disabled = False
            progress_bar.visible = False
            page.update()
            return

        if not ports_to_scan:
            results_text.controls.append(ft.Text("スキャンするポートがありません。", color="red"))
            scan_button.disabled = False
            progress_bar.visible = False
            page.update()
            return

        total_ports = len(ports_to_scan)
        scanned_count = 0

        def update_progress():
            nonlocal scanned_count
            scanned_count += 1
            progress_bar.value = scanned_count / total_ports
            page.update()

        def scan_worker():
            with ThreadPoolExecutor(max_workers=100) as executor:
                futures = {executor.submit(scan_port, target_ip, port): port for port in ports_to_scan}

                for future in as_completed(futures):
                    if future.result() is not False:
                        update_progress()
                    else:
                        break

            # ポート番号順にソートして結果を表示
            for port, msg in sorted(open_ports_info):
                results_text.controls.append(ft.Text(msg, color="green"))

            results_text.controls.append(ft.Text("\nスキャンが完了しました。", color="blue"))
            scan_button.disabled = False
            progress_bar.visible = False
            page.update()

        threading.Thread(target=scan_worker, daemon=True).start()

    # UI要素を追加
    page.add(
        ft.Column(
            [
                ft.ResponsiveRow(
                    [
                        ft.Container(content=target_input, col={'xs': 12, 'sm': 5, 'md': 5, 'lg': 5}),
                        ft.Container(content=port_range_input, col={'xs': 12, 'sm': 5, 'md': 5, 'lg': 5}),
                        ft.Container(content=scan_button, col={'xs': 12, 'sm': 2, 'md': 2, 'lg': 2}),
                    ],
                ),
                ft.Container(
                    content=progress_bar,
                    height=10,
                    padding=ft.padding.symmetric(vertical=5),
                ),
                ft.Row([ft.Text("Result:", size=20)]),
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