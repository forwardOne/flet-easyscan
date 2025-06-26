import flet as ft

# --- Helper Functions (moved to module level) ---
def parse_port_range(port_range_str: str) -> list[int]:
    ''' ポート範囲文字列をパースしてポート番号のリストを返す '''
    ports = []
    parts = port_range_str.split(',')
    for part in parts:
        part = part.strip()
        if '-' in part:
            start, end = map(int, part.split('-'))
            ports.extend(range(start, end + 1))
        else:
            ports.append(int(part))
    return sorted(list(set(ports)))

def create_result_text_widget(res_item: dict, port_services_data: dict) -> tuple[ft.Text | None, bool, str, str]:
    ''' スキャン結果を成型しFlet Text、オープンフラグ、サービス名、詳細情報を返す
    Returns:
        tuple: (Flet Textウィジェット or None, オープンポートかどうかのbool,
                サービス名文字列, 詳細情報文字列)
    '''
    status = res_item['status']
    is_open_port = False
    
    # 'closed' ステータスのポートは表示しない
    if status == 'closed':
        # サービス名と詳細情報として空文字列を追加
        return None, False, "", ""
    
    # ポート番号とスキャンタイプ
    port_num_str = str(res_item['port'])
    scan_type = res_item.get('type', 'N/A').upper()
    service_name_for_col = ""
    description_for_col = ""
    
    # ポート番号がサービス定義に存在するか
    if port_num_str in port_services_data:
        service_entry = port_services_data.get(port_num_str)
        if isinstance(service_entry, list):
            for item in service_entry:
                # .get()を呼び出す前にitemが辞書であることを確認
                if isinstance(item, dict):
                    protocol_from_json = item.get("protocol", "").upper()
                    # スキャンタイプが一致するか、JSON側でプロトコル指定がないか、TCP/UDP許容の場合
                    if scan_type in protocol_from_json or "TCP/UDP" in protocol_from_json or not protocol_from_json:
                        service_name_for_col = item.get("service_name", "")
                        description_for_col = item.get("description", "")
                        # 一致するプロトコルが見つかった
                        break
        elif isinstance(service_entry, dict):
            protocol_from_json = service_entry.get("protocol", "").upper()
            # スキャンタイプが一致するか、JSON側でプロトコル指定がないか、TCP/UDP許容の場合
            if scan_type in protocol_from_json or "TCP/UDP" in protocol_from_json or not protocol_from_json:
                service_name_for_col = service_entry.get("service_name", "")
                description_for_col = service_entry.get("description", "")
    
    # 表示用テキストの成型
    display_text = f"{res_item['port']}/{res_item.get('type','n/a')} - {status}"
    # 短いサービス名が取得できた場合 表示用テキストの末尾に追加
    if service_name_for_col:
        display_text += f" ({service_name_for_col})"
    
    # ステータスカラー
    color = "orange"
    if status == 'open':
        color = "green"
        is_open_port = True
    elif 'error' in status or 'oserror' in status:
        color = "red"
    return ft.Text(display_text, color=color), is_open_port, service_name_for_col, description_for_col

