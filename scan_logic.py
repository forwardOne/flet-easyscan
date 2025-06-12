from scapy.all import IP, TCP, UDP, sr1, conf, ICMP
import platform
import socket
import json
from concurrent.futures import ThreadPoolExecutor, as_completed


# --- Constants ---
DEFAULT_TIMEOUT_TCP = 3
MAX_SCAN_WORKERS_TCP = 2
DEFAULT_TIMEOUT_UDP = 5
MAX_SCAN_WORKERS_UDP = 2


# --- Helper for IP Validation ---
def _is_valid_ip(ip_address: str) -> bool:
    """Checks if the string is a valid IPv4 or IPv6 address."""
    try:
        socket.inet_pton(socket.AF_INET, ip_address)
        return True
    except socket.error:
        try:
            socket.inet_pton(socket.AF_INET6, ip_address)
            return True
        except socket.error:
            return False


# --- TCP Helper ---
def _scan_single_tcp_port(target_ip: str, port: int, timeout: int) -> dict:
    """TCP単体スキャン helper 関数
    Args:
        target_ip (str): スキャン対象のIPアドレス
        port (int): スキャンするTCPポート（単体）
        timeout (int): 各パケットの応答を待つタイムアウト（秒）
    Returns:
        (list[dict]) e.g.: [{'port': 80, 'status': 'open'}]
    """
    try:
        # SYNパケット作成
        syn_packet = IP(dst=target_ip)/TCP(dport=port, flags="S")
        resp = sr1(syn_packet, timeout=timeout, verbose=0)


        # 応答なし
        if not resp:
            return {'port': port, 'status': 'filtered'}

        # TCP 応答（TCPレイヤが存在する場合）
        if resp.haslayer(TCP):
            tcp_layer = resp.getlayer(TCP)
            
            # SYN-ACK オープン
            if tcp_layer.flags == "SA": # SYN/ACK
                return {'port': port, 'status': 'open'}
            # RST-ACK クローズ
            elif tcp_layer.flags == "RA": # RST/ACK
                return {'port': port, 'status': 'closed'}
            # その他のTCPフラグ
            else:
                return {'port': port, 'status': 'filtered'}

        # ICMP 応答（フィルタリング）
        elif resp.haslayer(ICMP):
            icmp_layer = resp.getlayer(ICMP)
            
            # ICMP Type3 (Destination Unreachable)
            if icmp_layer.type == 3 and icmp_layer.code in [1, 2, 3, 9, 10, 13]:
                return {'port': port, 'status': 'filtered'}
            # ICMP Type3以外
            else:
                return {'port': port, 'status': 'filtered'}

        # 不明な応答
        else:
            return {'port': port, 'status': 'unknown'}

    # OSErrorを個別に捕捉
    except OSError as oe:
        return {'port': port, 'status': f'oserror: {oe}'}
    # その他エラー
    except Exception as e:
        return {'port': port, 'status': f'error: {e}'}
    finally:
        pass


# --- TCP Submit ---
def tcp_scan(target_ip: str, ports: list[int], timeout: int = DEFAULT_TIMEOUT_TCP):
    """TCPスキャンタスク Thread submit 関数
    Args:
        target_ip (str): スキャン対象のIPアドレス
        ports (list[int]): スキャンするTCPポートのリスト
        timeout (int): 各パケットの応答を待つタイムアウト（秒）
    Returns:
        scan_results (list[dict]) e.g.: [{'port': 80, 'status': 'open'}]
    """
    scan_results = [] # 初期化

    with ThreadPoolExecutor(max_workers=MAX_SCAN_WORKERS_TCP) as executor:
        future_to_port = {
            executor.submit(_scan_single_tcp_port, target_ip, port, timeout): port
            for port in ports
        }
        for future in as_completed(future_to_port):
            try:
                result = future.result()
                if result:
                    scan_results.append(result)

            # エラーハンドリング用 ポート番号とエラーメッセージを記載                
            except Exception as e:
                port_val = future_to_port[future]
                scan_results.append({'port': port_val, 'status': f'executor_error: {e}'})

    return scan_results


# --- UDP Helper ---
def _scan_single_udp_port(target_ip: str, port: int, timeout: int) -> dict:
    """UDP単体スキャン helper 関数
    Args:
        target_ip (str): スキャン対象のIPアドレス
        port (int): スキャンするUDPポート（単体）
        timeout (int): 各パケットの応答を待つタイムアウト（秒）
    Returns:
        (list[dict]) e.g.: [{'port': 80, 'status': 'open'}]
    """ 
    try:
        # UDPパケット作成 宛先ポート指定
        udp_packet = IP(dst=target_ip)/UDP(dport=port)
        resp = sr1(udp_packet, timeout=timeout, verbose=0)
        
        # 応答なし
        if not resp:
            # UDPの場合、応答がないことは 'open|filtered' と解釈されることが多い
            return {'port': port, 'status': 'open|filtered'}

        # UDP 応答
        if resp.haslayer(UDP):
            return {'port': port, 'status': 'open'}
        # ICMP Port Unreachable (Type 3, Code 3) はポートがクローズされていることを示す
        elif resp.haslayer(ICMP) and resp.getlayer(ICMP).type == 3 and resp.getlayer(ICMP).code == 3:
            return {'port': port, 'status': 'closed'}
        # その他のICMPエラー (e.g., Type 3, Code 1, 2, 9, 10, 13) はフィルタリングされている可能性
        elif resp.haslayer(ICMP) and resp.getlayer(ICMP).type == 3 and resp.getlayer(ICMP).code in [1, 2, 9, 10, 13]:
            return {'port': port, 'status': 'filtered'}
        # 不明な応答
        else:
            return {'port': port, 'status': 'unknown'}

    # OSErrorを個別に捕捉
    except OSError as oe:
        return {'port': port, 'status': f'oserror: {oe}'}
    # その他のエラー
    except Exception as e:
        return {'port': port, 'status': f'error: {e}'}
    finally:
        pass


# --- UDP Submit ---
def udp_scan(target_ip: str, ports: list[int], timeout: int = DEFAULT_TIMEOUT_UDP):
    """UDPスキャンタスク Thread submit 関数
    Args:
        target_ip (str): スキャン対象のIPアドレス
        ports (list[int]): スキャンするUDPポートのリスト
        timeout (int): 各パケットの応答を待つタイムアウト（秒）
    Returns:
        scan_results (list[dict]) e.g.: [{'port': 53, 'status': 'open'}]
    """
    scan_results = [] # Initialize scan_results

    with ThreadPoolExecutor(max_workers=MAX_SCAN_WORKERS_UDP) as executor:
        future_to_port = {
            executor.submit(_scan_single_udp_port, target_ip, port, timeout): port
            for port in ports
        }
        for future in as_completed(future_to_port):
            try:
                result = future.result()
                if result:
                    scan_results.append(result)

            # エラーハンドリング用 ポート番号とエラーメッセージを記載                
            except Exception as e:
                port_val = future_to_port[future]
                scan_results.append({'port': port_val, 'status': f'executor_error: {e}'})

    return scan_results


# --- TCP/UDP Function Call ---
def scan_ports(
    target_ip: str,
    tcp_ports: list[int] = None,
    udp_ports: list[int] = None,
    tcp_timeout: int = DEFAULT_TIMEOUT_TCP,
    udp_timeout: int = DEFAULT_TIMEOUT_UDP) -> list[dict]:

    """TCP/UDP 統合スキャン呼び出し関数 結果をマージ
    Args:
        target_ip (str): スキャン対象のIPアドレス。
        tcp_ports (list[int], optional): TCPポートのリスト Noneの場合実行しない
        udp_ports (list[int], optional): UDPポートのリスト Noneの場合実行しない
        timeout (int): 各パケットの応答を待つタイムアウト（秒）
    Returns:
        all_results (list[dict]): 全結果をマージし、ポート番号でソートしたリスト
    """
    all_results = []

    # --- Scapy Configuration for Windows ---
    if platform.system() == "Windows":
        conf.use_npcap = True
        conf.use_pcap = True
    else:
        print("Using default Scapy settings.\n(e.g., run with sudo on Linux)")

    # --- IP Validation ---
    if not _is_valid_ip(target_ip):
        print(f"Error: Invalid target IP address provided: {target_ip}")
        # 不正なIPの場合は、エラー情報を含む結果を返すか例外を発生させることも検討。
        return [{'port': 0, 'status': f'invalid_ip: {target_ip}', 'type': 'n/a'}]

    # TCPスキャン呼び出し
    if tcp_ports:
        tcp_res = tcp_scan(target_ip, tcp_ports, tcp_timeout)
        for res in tcp_res:
            res['type'] = 'tcp'
            all_results.append(res)

    # UDPスキャン呼び出し
    if udp_ports:
        udp_res = udp_scan(target_ip, udp_ports, udp_timeout)
        for res in udp_res:
            res['type'] = 'udp'
            all_results.append(res)

    # ポート番号でソート
    all_results.sort(key=lambda x: x['port'])
    return all_results



# --- Test ---
if __name__ == "__main__":
    SERVICES_FILE_PATH = "services.json" # services.jsonのパス
    PORT_SERVICES_DATA = {}

    def _load_port_services_for_test(filepath: str) -> dict:
        """テスト用のサービス情報読み込み関数"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"警告: サービス定義ファイル '{filepath}' が見つかりません。サービス名は表示されません。")
            return {}
        except json.JSONDecodeError:
            print(f"警告: サービス定義ファイル '{filepath}' の形式が正しくありません。サービス名は表示されません。")
            return {}

    PORT_SERVICES_DATA = _load_port_services_for_test(SERVICES_FILE_PATH)

    def _parse_ports_for_test(port_str: str) -> list[int]: # この関数は変更なし
        """テスト用の簡易ポート範囲パーサー"""
        ports = set()
        if not port_str:
            return []
        parts = port_str.split(',')
        for part in parts:
            part = part.strip()
            if '-' in part:
                start, end = map(int, part.split('-'))
                ports.update(range(start, end + 1))
            else:
                ports.add(int(part))
        return sorted(list(ports))

    target_ip = "127.0.0.1"
    tcp_port_str = "1-1024" # テスト用TCPポート範囲
    udp_port_str = "53, 67, 68, 69, 123, 137, 138, 161, 162, 500, 514, 520" # テスト用UDPポート範囲

    print("--- Starting")
    test_results = scan_ports(
        target_ip=target_ip,
        tcp_ports=_parse_ports_for_test(tcp_port_str),
        udp_ports=_parse_ports_for_test(udp_port_str)
    )

    print(f"\nScan report for {target_ip}")
    # 表示ヘッダーを調整
    print(f"{'PORT/TYPE':<12} {'STATE':<15} SERVICE")

    displayed_ports = 0
    closed_ports_count = 0
    interesting_statuses = ['open', 'open|filtered', 'filtered', 'unknown'] # エラーは常に表示

    for res in test_results:
        port_num_str = str(res['port'])
        # スキャンタイプの取得
        scan_type_for_service_lookup = res['type'].upper()
        status = res['status']

        service_name_display = ""
        if port_num_str in PORT_SERVICES_DATA:
            service_info = PORT_SERVICES_DATA[port_num_str]
            name_from_json = service_info.get("name", "")
            protocol_from_json = service_info.get("protocol", "").upper() # "TCP", "UDP", "TCP/UDP"
            # スキャンタイプが一致するか、JSON側でプロトコル指定がない場合
            if scan_type_for_service_lookup in protocol_from_json or not protocol_from_json:
                service_name_display = name_from_json

        port_type_display = f"{res['port']}/{res['type']}"

        if status in interesting_statuses or 'error' in status or 'oserror' in status:
            print(f"{port_type_display:<12} {status:<15} {service_name_display}")
            displayed_ports += 1
        elif status == 'closed':
            closed_ports_count += 1

    if closed_ports_count > 0:
        print(f"Not shown: {closed_ports_count} closed ports.")
    if displayed_ports == 0 and closed_ports_count == 0 and not any('invalid_ip' in res['status'] for res in test_results) :
        print("No open, filtered, or unknown ports found.")

    print("--- Done")
