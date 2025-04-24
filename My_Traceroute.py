import argparse
import socket
import time
import struct
import select
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import queue
from typing import Optional, Tuple, Dict
import random


class Traceroute:
    def __init__(self):
        try:
            self.options = self._parse_args()
        except SystemExit as e:
            print(f"Caught SystemExit with code: {e.code}")
            print(f"Arguments: {e.args}")
            sys.exit(1)

        # basic control
        self.queries_per_hop = self.options.queries
        # self.queries_per_send = self.options.sim_queries

        self.timeout = self.options.wait / 1000.0  # 转换为秒
        self.min_send_interval = self.options.z

        self.max_hops = self.options.max_hops
        self.first_ttl = self.options.first_hop

        self.flag_no_resolve = self.options.no_resolve



        #multi threading
        self.responses = queue.Queue()
        self.probes_lock = Lock()


        # Ethernet layer options
        self.interface = self.options.interface


        # IP protocol options
        self.ip_protocol =  "6" if self.options.ipv6 else ("4" if self.options.ipv4 else None)
        self.dest_ip = self._resolve_hostname(self.options.host)
        self.ip_protocol = self._decide_ip_protocol()
        self.src_ip = self.options.source
        # 从本机配置的ip地址发出，如果不是，会报错：traceroute: Cannot assign requested address
        self.type_of_service = self.options.tos
        self.flag_df = self.options.dont_fragment
        self.LSRR_list = self.options.gateway


        # TCP/UDP layer options
        self.dest_port = self.options.port
        self.src_port = self.options.sport
        self.protocol = self.options.protocol.lower()


        # advance control
        self.flag_simulate = self.options.simulate
        self.flag_mtu_test = self.options.mtu


        # output control
        self.flag_show_extensions = self.options.extensions
        self.flag_verbose = self.options.verbose


        # initialize socket according to control info
        self.sock= self._create_socket()
        self._config_params()

        self.results = {}
        self.recv_running = False
        self.probes_sent = {}  # 记录已发送的探测包 {(ttl, seq): probe_info}


    @staticmethod
    def _print_warning(text):
        color = "\033[91m"
        reset_color = "\033[0m"
        print(f"{color}{text}{reset_color}")

    def _decide_ip_protocol(self):
        ret = self.ip_protocol if self.ip_protocol else '4' if '.' in self.dest_ip else '6' if ':' in self.dest_ip else None
        if ret is None:
            raise ValueError(f"unable to resolve host:{self.options.host}")
        else:
            return ret

    @staticmethod
    def  _parse_args() -> argparse.Namespace:
        parser = argparse.ArgumentParser(description="Python实现的Traceroute工具")

        parser.add_argument("host",
                            help="target host url or IP address")

        # Ethernet layer params
        parser.add_argument("-i", "--interface", type=int,
                            help="Specify a network interface to operate with(is to be implemented. Throw an error is you use this)")

        # IP layer params
        ip_group = parser.add_mutually_exclusive_group()
        ip_group.add_argument("-4", "--ipv4", action="store_true",
                            help="Force to use IPv4")
        ip_group.add_argument("-6", "--ipv6", action="store_true",
                            help="Force to use IPv6")
        parser.add_argument("-s", "--source",
                            help="Use source src_addr for outgoing packets")
        parser.add_argument("-t", "--tos", type=int, default=0,
                            help="Set the TOS (IPv4 type of service) or TC (IPv6 traffic class) value for packets")
        parser.add_argument("-F", "--dont-fragment", action="store_true",
                            help="Do not fragment packets")
        parser.add_argument("-f", "--first-hop", type=int, default=1,
                            help="set TTL for the first package (default: 1)")
        parser.add_argument("-m", "--max-hops", type=int, default=30,
                            help="Set the max number of hops (max TTL to be reached) (default: 30)")

        # Transport layer params
        protocol_group = parser.add_mutually_exclusive_group()
        protocol_group.add_argument("-P", "--protocol", choices=["icmp", "udp", "tcp"], default="udp",
                            help="Protocol used, valid input:\"icmp\", \"udp\", \"tcp\", \"tcpconn\" (default: udp)")
        protocol_group.add_argument("-I", "--icmp", action="store_const", dest="protocol",const="icmp",
                            help="使用ICMP ECHO (equivalent to -P icmp)")
        protocol_group.add_argument("-T", "--tcp", action="store_const", dest="protocol",const="tcp",
                            help="use TCP SYN (equivalent to -P tcp)")
        parser.add_argument("--sport", type=int,
                            help="Source port, (default: managed by system)")
        parser.add_argument("-p", "--port", type=int,
                            help="Destination port, use with -T/-U (default: 33434)")

        # basic control
        parser.add_argument("-w", "--wait", type=int, default=5000,
                            help="Waiting time for reply(ms) (default: 5000)")
        parser.add_argument("-q", "--queries", type=int, default=3,
                            help="the number of prob packets sent for every hop (default: 3)")
        parser.add_argument("-z", type=int, default=0,
                            help="Minimum interval time between sending probe packets(ms) (default: 0)")
        # parser.add_argument("-N", "--sim-queries", type=int, default=16,
        #                     help="the number of probes to be sent simultaneously (default: 16)")

        # advance control
        parser.add_argument("-n", "--no-resolve", action="store_true",
                            help="Do not resolve IP address to hostname")
        parser.add_argument("-g", "--gateway", action="append",
                            help="Route packets through the specified gateway (maximum 8 for IPv4 and 127 for IPv6) \n 许多现代路由器/防火墙会 丢弃 包含 LSRR 选项的包（出于安全考虑），导致路径不可达，不推荐使用。")
        parser.add_argument("--mtu", action="store_true",
                            help="Discover MTU along the path being traced. Implies`-F -N 1'")
        parser.add_argument("-S", "--simulate", action="store_true",
                            help="Simulation mode, not sending any real data packet")

        # visualization params
        parser.add_argument("-v", "--verbose", action="store_true",
                            help="Detailed output mode")
        parser.add_argument("-e", "--extensions", action="store_true",
                            help="Show ICMP extensions (if present), including MPLS")



        args = parser.parse_args()

        # 检查各个参数是否合法
        if args.interface:
            parser.error("this function is yet to be implemented")
        if args.protocol == "icmp" and (args.port is not None or args.sport is not None):
            parser.error("ICMP协议不能指定端口（请移除 -p/--port 参数）")
        if args.protocol != "icmp" and args.port is None:
            args.port=33434
        if args.mtu:
            if not args.dont_fragment or (args.sim_queries!=1):
                parser.error("--mtu选项需要-F且将-N设置为1，即设置 dont fragment 为true, 且设置同时发送probe数为1，请手动修改")
        if args.tos<0 or args.tos>255:
            parser.error("-t/--tos 的范围是0-255 (0x00-0xFF), 输入范围不合法, 请修改")
        if args.first_hop<1 or args.first_hop > 255:
            parser.error("-f/--first-hop 的范围是1-255 (0x01-0xFF), 输入范围不合法, 请修改")
        if args.max_hops<1 or args.max_hops > 255:
            parser.error("-m/--max-hops 的范围是1-255 (0x01-0xFF), 输入范围不合法, 请修改")
        if args.sport is not None:
            if args.sport<0 or args.sport>65535:
                parser.error("--sport 的范围是0-65535 (0x0001-0xFFFF), 输入范围不合法, 请修改")
        if args.port is not None:
            if args.port<0 or args.port>65535:
                parser.error("-p/--port 的范围是0-65535 (0x0001-0xFFFF), 输入范围不合法, 请修改")
        if args.wait<0:
            parser.error("-w/--wait Waiting time for reply(ms) 不能为负数，请修改")
        if args.queries<0:
            parser.error("-q/--queries number of prob packets sent for every hop 不能为负数，请修改")
        # if args.sim_queries<0:
        #     parser.error("-N/--sim-queries the number of probes to be sent simultaneously 不能为负数，请修改")
        if args.z<0:
            parser.error("-z Minimum interval time between sending probe packets(ms) 不能为负数，请修改")

        return args

    def _get_ip_protocol(self) -> int:
        if self.ip_protocol == "6":
            return socket.AF_INET6
        elif self.ip_protocol == "4":
            return socket.AF_INET
        else:
            return socket.AF_UNSPEC

    def _resolve_hostname(self, host:str) -> str:
        try:
            # 获取所有与主机名关联的地址信息
            ip_protocol = self._get_ip_protocol()
            try:
                addrinfo = socket.getaddrinfo(host, None, ip_protocol)
            except socket.gaierror as e:
                self._print_warning(f"failed to resolve host:{host} to IPv{self.ip_protocol} address. Error info:{e}")
                sys.exit(1)

            if len(addrinfo)==0:
                print(f"Error: Unable to resolve '{host}'")
                sys.exit(1)

            return addrinfo[0][4][0]

        except socket.gaierror as e:
            print(f"Error: Unable to resolve '{host}': {e}")
            sys.exit(1)

    def _config_params(self):
        # set tos
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, self.type_of_service)

        # set df flag
        if self.flag_df:
            if self.ip_protocol == '6':
                if sys.platform=='linux':
                    self.sock.setsockopt(socket.IPPROTO_IPV6, 23, 2)
                elif sys.platform == 'win32':
                    self.sock.setsockopt(socket.IPPROTO_IPV6, 14, 1)
                elif sys.platform == 'darwin':
                    self.sock.setsockopt(socket.IPPROTO_IPV6, 62, 1)

            elif self.ip_protocol == '4':
                if sys.platform == 'linux':
                    self.sock.setsockopt(socket.IPPROTO_IP, 10, 2)
                elif sys.platform == 'win32':
                    self.sock.setsockopt(socket.IPPROTO_IP, 14, 1)
                elif sys.platform == 'darwin':
                    self.sock.setsockopt(socket.IPPROTO_IP, 67, 1)
            else:
                raise ValueError(f"不支持的网络协议:{self.protocol}")

        # set lsrr
        if self.LSRR_list and self.ip_protocol == 4:
            if len(self.LSRR_list) > 8:
                raise  ValueError(f"too many gateways (max=8)")
            init_ptr = 4
            route_data = b''

            try:
                for ip in self.LSRR_list:
                    ip = self._resolve_hostname(ip)
                    route_data += socket.inet_aton(ip)
            except socket.error as e:
                self._print_warning(f"failed to resolve gateway {e}")
                sys.exit(1)

            option = struct.pack('BBBB', 0x83, len(route_data) + 3, init_ptr, 0) + route_data
            try:
                self.sock.setsockopt(socket.SOL_IP, socket.IP_OPTIONS, option)
            except socket.error as e:
                self._print_warning(f"unable to add lsrr option to IPv4 header. Exception info:{e}")
                sys.exit(1)

        elif self.LSRR_list and self.ip_protocol == 6:
            segments = len(self.LSRR_list)
            header = struct.pack('!BBBB', 0, (segments + 1) * 2, 0, segments)
            header += b'\x00' * 4  # reserved

            try:
                for ip in self.LSRR_list:
                    ip = self._resolve_hostname(ip)
                    header += socket.inet_pton(socket.AF_INET6, ip)
            except socket.error as e:
                self._print_warning(f"failed to resolve gateway {e}")
                sys.exit(1)

            try:
                self.sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_RTHDR, header)
            except socket.error as e:
                self._print_warning(f"unable to add lsrr option to IPv6 header. Exception info:{e}")
                sys.exit(1)


    def _create_socket(self)->socket:
        """
        根据attribute创建套接字并绑定到指定源IP和端口
        :return: 配置好的socket对象
        """
        print("is creating sockets")

        if self.protocol == 'tcp' or self.protocol == 'tcpconn':
            trans_protocol = socket.SOCK_RAW
            ip_type = socket.IPPROTO_TCP
        elif self.protocol == 'udp':
            trans_protocol = socket.SOCK_DGRAM
            ip_type = socket.IPPROTO_UDP
        elif self.protocol == 'icmp':
            trans_protocol = socket.SOCK_RAW
            ip_type = socket.IPPROTO_ICMP
        else:
            raise ValueError(f"不支持的传输协议:{self.protocol}")


        if self.ip_protocol == '4':
            ip_protocol = socket.AF_INET
        elif self.ip_protocol == '6':
            ip_protocol = socket.AF_INET6
        else:
            raise ValueError(f"不支持的网络协议:{self.ip_protocol}")

        try:
            sock = socket.socket(ip_protocol, trans_protocol, ip_type)
        except PermissionError as e:
            print(f"PermissionError: {e}")
            sys.exit(1)

        try:
            if self.src_ip:
                sock.bind((self.src_ip if self.src_ip else '', self.src_port))
        except OSError as e:
            print(f"unsupported ip address {e}")
            self._get_local_ips()
            sys.exit(1)

            # 新增：接收套接字初始化验证
        try:
            # 统一接收套接字协议处理
            recv_proto = {
                "icmp": socket.IPPROTO_ICMP,
                "udp": socket.IPPROTO_ICMP,
                "tcp": socket.IPPROTO_TCP
            }[self.protocol]

            # 显式指定地址族
            recv_family = socket.AF_INET if self.ip_protocol == '4' else socket.AF_INET6
            self.recv_sock = socket.socket(
                family=recv_family,
                type=socket.SOCK_RAW,
                proto=recv_proto
            )

            # 统一设置套接字选项
            self.recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.recv_sock.settimeout(self.timeout)
            self.recv_sock.bind(('', 0))  # 通用绑定方式

            print(f"[DEBUG] 接收套接字创建成功 fd={self.recv_sock.fileno()}")

        except Exception as e:
            print(f"无法创建接收套接字: {str(e)}")
            sys.exit(1)
        return sock

    @staticmethod
    def _get_local_ips():
        ips = []
        try:
            hostname = socket.gethostname()
            for info in socket.getaddrinfo(hostname, None):
                if info[0] == socket.AF_INET:
                    ips.append(info[4][0])
        except socket.gaierror as e:
            print(f"Error: Unable to resolve local ip: {e}")
            sys.exit(1)
        print("usable local ip:", end=' ')
        print(list(set(ips)))

    def run(self):
        """带并行探测的执行主函数"""
        print(f"traceroute to {self.options.host} ({self.dest_ip}), "
              f"max hops {self.max_hops}, {self.queries_per_hop} probes per hop")

        # 调试：检查接收套接字状态
        print(f"[DEBUG] Main thread - recv_sock fd: {self.recv_sock.fileno() if hasattr(self, 'recv_sock') else 'NOT CREATED'}")


        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                # 启动接收线程（确保先启动接收线程）
                recv_future = executor.submit(self._receiver_thread)
                print(f"[DEBUG] Receiver future created: {recv_future}")

                # 等待接收线程初始化（最多1秒）
                start_time = time.time()
                while not getattr(self, 'recv_running', False) and (time.time() - start_time) < 1:
                    time.sleep(0.1)

                if not getattr(self, 'recv_running', False):
                    print("[ERROR] Receiver thread failed to start!")
                    return

                try:
                    # 发送探测包
                    send_futures = []
                    for ttl in range(self.first_ttl, self.first_ttl + self.max_hops):
                        for seq in range(1, self.queries_per_hop + 1):
                            future = executor.submit(
                                self._send_and_record_probe,
                                ttl=ttl,
                                seq=seq
                            )
                            send_futures.append(future)
                            time.sleep(self.min_send_interval / 1000)

                        # 实时显示结果
                        self._display_current_hop(ttl)

                    # 等待发送完成
                    for future in as_completed(send_futures):
                        future.result()  # 只是为了捕获异常

                except KeyboardInterrupt:
                    print("\nTrace interrupted by user")
                finally:
                    self.recv_running = False
                    recv_future.result(timeout=2)  # 增加等待时间
        except Exception as e:
            print(f"[CRITICAL] Main thread error: {e}")
        finally:
            self.close()
            self._display_final_results()

    def _receiver_thread(self):
        """持续接收回复的线程"""
        print(f"\n[DEBUG] Receiver thread STARTED (recv_sock fd: {self.recv_sock.fileno()})")  # 调试输出

        self.recv_running = True
        while getattr(self, 'recv_running', True):
            try:
                if not hasattr(self, 'recv_sock') or self.recv_sock.fileno() == -1:
                    print("[ERROR] Receive socket invalid!")
                    break

                ready, _, _ = select.select([self.recv_sock], [], [], 0.1)
                if ready:
                    try:
                        packet, addr = self.recv_sock.recvfrom(1024)
                        print(f"[DEBUG] Received packet from {addr[0]}")  # 调试输出
                        self._process_reply_packet(packet, addr)
                    except socket.timeout:
                        continue
                    except ConnectionResetError:
                        print("[WARNING] Connection reset by peer")
                        continue

            except Exception as e:
                print(f"[ERROR] Receiver thread crashed: {type(e).__name__}: {e}")
                break



    def _send_and_record_probe(self, ttl: int, seq: int):
        """发送单个探测包并记录结果"""
        # print(f"Sender thread started, send seq: {seq}")
        probe_id = random.randint(0, 65535)
        send_time = time.time()

        # 设置TTL
        if self.ip_protocol == '4':
            self.sock.setsockopt(socket.SOL_IP, socket.IP_TTL, ttl)
        else:
            self.sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_UNICAST_HOPS, ttl)

        # 发送探测包
        if self.protocol == "icmp":
            self._send_icmp_probe(probe_id, seq)
        elif self.protocol == "udp":
            self._send_udp_probe(seq)
        elif self.protocol == "tcp":
            self._send_tcp_probe(seq)

        # 记录发送信息用于匹配回复
        probe_info = {
            'send_time': send_time,
            'ttl': ttl,
            'seq': seq,
            'probe_id': probe_id,
            'matched': False
        }
        self.probes_sent[(ttl, seq)] = probe_info

    def _process_reply_packet(self, packet: bytes, addr: tuple):
        """处理接收到的回复包"""
        try:
            src_ip = addr[0]
            extensions = None

            if self.ip_protocol == '4':
                ip_header_len = (packet[0] & 0x0F) * 4
                transport_header = packet[ip_header_len:]

                if self.flag_show_extensions:
                    extensions = self._process_icmp_extensions(transport_header)

                # ICMP协议处理
                if len(transport_header) >= 8:
                    type_, code = struct.unpack("!BB", transport_header[:2])

                    # ICMP回复（对ICMP探测的响应）
                    if type_ == 0 and self.protocol == "icmp":
                        _, _, probe_id, seq = struct.unpack("!HHHH", transport_header[:8])
                        self._match_reply(probe_id, seq, src_ip, extensions)

                    # ICMP错误（对UDP/TCP的响应）
                    elif type_ in (3, 11) and len(transport_header) >= 28:
                        orig_ip_header = transport_header[8:28]
                        orig_dst_ip = socket.inet_ntoa(orig_ip_header[16:20])

                        if orig_dst_ip == self.dest_ip:
                            if self.protocol == "udp":
                                orig_header = transport_header[28:28 + 8]
                                orig_sport, orig_dport = struct.unpack("!HH", orig_header[:4])
                                seq = orig_dport - self.dest_port + 1
                                self._match_reply(None, seq, src_ip, extensions)

                            elif self.protocol == "tcp":
                                orig_header = transport_header[28:28 + 20]
                                orig_sport, orig_dport = struct.unpack("!HH", orig_header[:4])
                                seq = orig_dport - self.dest_port + 1
                                self._match_reply(None, seq, src_ip, extensions)

        except Exception as e:
            if self.flag_verbose:
                print(f"Error processing reply: {e}")

    def _match_reply(self, probe_id: Optional[int], seq: int, src_ip: str, extensions: Dict = None):
        """匹配回复包与发送的探测包"""
        # 通过seq找到对应的TTL（简化实现，实际可能需要更复杂的匹配逻辑）
        with self.probes_lock:
            for (ttl, s), probe in list(self.probes_sent.items()):
                if s == seq and not probe['matched']:
                    rtt = (time.time() - probe['send_time']) * 1000
                    self._record_hop_result(ttl, src_ip, rtt, extensions or {})
                    probe['matched'] = True
                    break

    def _record_hop_result(self, ttl: int, ip: str, rtt: float, extensions: Dict):
        if ttl not in self.results:
            self.results[ttl] = {
                'probes': [],
                'ip': ip,
                'hostname': None if self.flag_no_resolve else self._resolve_ip_to_hostname(ip),
                'extensions': extensions
            }

        self.results[ttl]['probes'].append({
            'ip': ip,
            'rtt': rtt,
            'reached': ip == self.dest_ip
        })

        # 合并扩展信息
        if extensions:
            self.results[ttl]['extensions'] = extensions

    def _resolve_ip_to_hostname(self, ip: str) -> str:
        """IP地址解析为主机名"""
        if self.flag_no_resolve:
            return ip

        try:
            return socket.gethostbyaddr(ip)[0]
        except (socket.herror, socket.gaierror):
            return ip



    def _send_icmp_probe(self, probe_id: int, seq: int):
        """发送ICMP ECHO请求"""
        checksum = 0
        timestamp = int(time.time())
        header = struct.pack("!BBHHH", 8, 0, checksum, probe_id, seq)
        data = struct.pack('!HHI', probe_id, seq, timestamp)
        data += b'\x00' * (64-len(data))

        # 计算校验和
        checksum = self._calculate_checksum(header + data)
        header = struct.pack("!BBHHH", 8, 0, checksum, probe_id, seq)

        self.sock.sendto(header + data, (self.dest_ip, 0))

    def _send_udp_probe(self, seq: int):
        """发送UDP探测包"""
        # print(f"UDP package {seq} sent.")
        port = self.dest_port + seq - 1
        if port > 65535:
            port = (port-49152) % 16384 + 49152
        data = b"PythonTraceroute"
        data += b'\x00' * (64 - len(data))
        self.sock.sendto(data, (self.dest_ip, port))

    def _send_tcp_probe(self, seq):
        """使用原始套接字发送TCP SYN包"""
        if self.ip_protocol == "4":
            packet = self._build_ipv4_header() + self._build_tcp_syn(seq)
        else:
            packet = self._build_ipv6_header() + self._build_tcp_syn(seq)
        self.sock.sendto(packet, (self.dest_ip, self.dest_port))

    def _build_ipv4_header(self):
        """构造IPv4头部"""
        version_ihl = 0x45
        dscp_ecn = self.type_of_service
        total_len = 40  # 20字节IP头 + 20字节TCP头
        identification = random.randint(0, 65535)
        flags_frag = 0x4000 if self.flag_df else 0  # DF标志
        ttl = 64  # 默认TTL，实际发送时会覆盖
        protocol = socket.IPPROTO_TCP
        src_ip = socket.inet_aton(self.src_ip or socket.gethostbyname(socket.gethostname()))
        dst_ip = socket.inet_aton(self.dest_ip)

        header = struct.pack("!BBHHHBBH4s4s",
                             version_ihl, dscp_ecn, total_len,
                             identification, flags_frag,
                             ttl, protocol, 0,  # 校验和先填0
                             src_ip, dst_ip)

        # 计算校验和
        checksum = self._calculate_checksum(header)
        header = header[:10] + struct.pack("H", checksum) + header[12:]
        return header

    def _build_ipv6_header(self, payload_len: int = 40) -> bytes:
        version = 0x6
        traffic_class = self.type_of_service
        flow_label = 0

        # 基础头部 (40字节)
        header = struct.pack("!IHBB16s16s",
                             (version << 28) | (traffic_class << 20) | flow_label,
                             payload_len,
                             socket.IPPROTO_TCP if self.protocol == "tcp" else socket.IPPROTO_UDP,
                             64,  # Hop Limit (会被覆盖)
                             socket.inet_pton(socket.AF_INET6, self.src_ip or "::"),
                             socket.inet_pton(socket.AF_INET6, self.dest_ip)
                             )

        # 添加扩展头
        if self.LSRR_list:
            routing_header = self._build_ipv6_routing_header()
            header += routing_header
            # 更新下一个头部字段
            header = header[:6] + bytes([43]) + header[7:]  # 43是路由头的协议号

        return header

    def _build_ipv6_routing_header(self) -> bytes:
        """构造IPv6路由头(类型0)"""
        segments = len(self.LSRR_list)
        header = struct.pack("!BBBB",
                             0,  # 下一个头部
                             2 * (segments + 1),  # 头长度(以8字节为单位)
                             0,  # 路由类型(0表示LSRR)
                             segments
                             )

        # 添加地址
        for ip in self.LSRR_list:
            header += socket.inet_pton(socket.AF_INET6, self._resolve_hostname(ip))

        # 填充到8字节倍数
        if len(header) % 8 != 0:
            header += b'\x00' * (8 - (len(header) % 8))

        return header

    def _build_tcp_syn(self, seq):
        tcp_header = struct.pack("!HHLLBBHHH",
                                 self.src_port, self.dest_port,
                                 seq, 0,  # 序列号
                                 5 << 4,  # 数据偏移
                                 0x02,  # SYN标志
                                 8192,  # 窗口大小
                                 0, 0  # 校验和和紧急指针
                                 )

        # 伪头部校验和(IPv4)
        if self.ip_protocol == '4':
            pseudo_header = struct.pack("!4s4sBBH",
                                        socket.inet_aton(self.src_ip),
                                        socket.inet_aton(self.dest_ip),
                                        0, socket.IPPROTO_TCP, len(tcp_header))
        else:
            pseudo_header = struct.pack("!16s16sBBH",
                                        socket.inet_pton(socket.AF_INET6, self.src_ip),
                                        socket.inet_pton(socket.AF_INET6, self.dest_ip),
                                        0, socket.IPPROTO_TCP, len(tcp_header))

        # 计算校验和
        checksum = self._calculate_checksum(pseudo_header + tcp_header)
        return tcp_header[:16] + struct.pack("H", checksum) + tcp_header[18:]

    def _wait_for_reply(self, probe_id: int, seq: int) -> Optional[Tuple[str, float]]:
        start_time = time.time()

        while time.time() - start_time < self.timeout:
            ready = select.select([self.recv_sock], [], [], self.timeout)
            if not ready[0]:
                return None  # 超时无响应

            try:
                packet, addr = self.recv_sock.recvfrom(1024)
                recv_time = time.time()
                src_ip = addr[0]

                # IPv4包解析
                if self.ip_protocol == '4':
                    ip_header_len = (packet[0] & 0x0F) * 4
                    icmp_header = packet[ip_header_len:]

                    # ICMP协议回复处理
                    if self.protocol == "icmp":
                        if len(icmp_header) >= 8:
                            type_, code, _, p_id, p_seq = struct.unpack("!BBHHH", icmp_header[:8])
                            if type_ == 0 and code == 0 and p_id == probe_id and p_seq == seq:
                                return src_ip, (recv_time - start_time) * 1000

                    # UDP/TCP的ICMP错误回复处理
                    elif self.protocol in ("udp", "tcp"):
                        if len(icmp_header) >= 28:  # ICMP错误包至少包含原始IP头
                            orig_ip_header = icmp_header[8:28]
                            orig_dst_ip = socket.inet_ntoa(orig_ip_header[16:20])

                            # 验证是发给我们的错误包
                            if orig_dst_ip == self.dest_ip:
                                type_, code = struct.unpack("!BB", icmp_header[:2])

                                # TTL超时
                                if type_ == 11 and code == 0:
                                    return src_ip, (recv_time - start_time) * 1000

                                # 不可达
                                elif type_ == 3 and code in (1, 2, 3, 9, 10, 13):
                                    return src_ip, (recv_time - start_time) * 1000

                # TODO: IPv6处理逻辑待添加完善
                elif self.ip_protocol == '6':
                    # 基本IPv6头部长度
                    ip_header_len = 40
                    transport_header = packet[ip_header_len:]

                    # ICMPv6处理
                    if self.protocol == "icmp" and len(transport_header) >= 8:
                        type_, code = struct.unpack("!BB", transport_header[:2])
                        if type_ == 129:  # ICMPv6 Echo Reply
                            _, _, p_id, p_seq = struct.unpack("!HHHH", transport_header[:8])
                            if p_id == probe_id and p_seq == seq:
                                return src_ip, (recv_time - start_time) * 1000

            except socket.error as e:
                if self.flag_verbose:
                    print(f"Socket error while waiting for reply: {e}")
                continue

        return None



    def _calculate_checksum(self, data:bytes):
        sum = 0
        for i in range(0, len(data), 2):
            if i + 1 >= len(data):
                sum += data[i] << 8
            else:
                sum += (data[i] << 8) + data[i + 1]
        sum = (sum >> 16) + (sum & 0xffff)
        sum += sum >> 16
        return ~sum & 0xffff

    def _process_icmp_extensions(self, packet: bytes) -> Dict:
        extensions = {
            'mpls': [],
            'other': []
        }

        if len(packet) < 8:
            return extensions

        # ICMP头部长度
        icmp_header_len = 8

        if len(packet) > icmp_header_len + 4:
            ext_start = icmp_header_len
            while ext_start + 4 <= len(packet):
                ext_header = packet[ext_start:ext_start + 4]
                ext_type, ext_len = struct.unpack("!BB", ext_header[:2])

                # mpls类型
                if ext_type == 1 and ext_len >= 8:
                    mpls_data = packet[ext_start + 4:ext_start + 4 + ext_len - 4]
                    for i in range(0, len(mpls_data), 4):
                        if i + 4 <= len(mpls_data):
                            label = struct.unpack("!I", mpls_data[i:i + 4])[0]
                            extensions['mpls'].append({
                                'label': label >> 12,
                                'tc': (label >> 9) & 0x7,
                                's': (label >> 8) & 0x1,
                                'ttl': label & 0xFF
                            })

                # 其他类型扩展
                else:
                    extensions['other'].append({
                        'type': ext_type,
                        'length': ext_len,
                        'data': packet[ext_start + 4:ext_start + ext_len]
                    })

                ext_start += ext_len

        return extensions

    def _display_current_hop(self, ttl: int):
        """显示当前跳的实时结果"""
        if ttl not in self.results or not self.results[ttl]['probes']:
            return

        hop = self.results[ttl]
        line = f"{ttl:2d}  "

        # 显示主机名或IP
        if not hop['ip']:
            line += "*" * (self.queries_per_hop * 8 + 15)
            print(line)
            return

        display_name = hop['ip'] if self.flag_no_resolve else hop.get('hostname', hop['ip'])
        line += f"{display_name:<15}  "

        # 显示每个探测的RTT
        for probe in hop['probes']:
            if probe['rtt'] is not None:
                line += f"{probe['rtt']:>7.2f} ms  "
            else:
                line += "    *     "

        print(line)

        # 显示扩展信息（如果启用）
        if self.flag_show_extensions and hop.get('extensions'):
            self._display_extensions(hop['extensions'])

    def _display_extensions(self, extensions: Dict):
        """显示ICMP扩展信息"""
        if extensions['mpls']:
            print("    MPLS Labels:")
            for mpls in extensions['mpls']:
                print(f"      Label={mpls['label']}, TC={mpls['tc']}, "
                      f"S={mpls['s']}, TTL={mpls['ttl']}")

        if extensions['other']:
            print("    Other Extensions:")
            for ext in extensions['other']:
                print(f"      Type={ext['type']}, Length={ext['length']}")

    def _display_final_results(self):
        """显示最终结果汇总"""
        print("\n=== Trace Complete ===")
        print(self.results)
        reached_target = False

        for ttl in sorted(self.results.keys()):
            hop = self.results[ttl]

            # 跳过完全无响应的跳
            if not hop['ip'] and all(p['rtt'] is None for p in hop['probes']):
                continue

            print(f"\nHop {ttl}:")
            print(f"  IP: {hop['ip']}")
            if not self.flag_no_resolve and 'hostname' in hop:
                print(f"  Hostname: {hop['hostname']}")

            # 计算统计信息
            valid_probes = [p for p in hop['probes'] if p['rtt'] is not None]
            if valid_probes:
                avg_rtt = sum(p['rtt'] for p in valid_probes) / len(valid_probes)
                loss_rate = 1 - len(valid_probes) / len(hop['probes'])
                print(f"  Avg RTT: {avg_rtt:.2f} ms")
                print(f"  Loss: {loss_rate:.0%}")

                # 检查是否到达目标
                if any(p['reached'] for p in hop['probes']):
                    print("  *** REACHED TARGET ***")
                    reached_target = True
                    break
            else:
                print("  All probes timed out")

        if not reached_target:
            print("\nWarning: Did not reach target host within max hops")

    def close(self):
        """安全关闭套接字"""
        self.recv_running = False

        # 关闭接收套接字
        if hasattr(self, 'recv_sock'):
            try:
                self.recv_sock.close()
            except:
                pass

        # 关闭发送套接字
        if hasattr(self, 'sock'):
            try:
                self.sock.close()
            except:
                pass


if __name__ == "__main__":
    traceroute = Traceroute()

    try:
        traceroute.run()
    except KeyboardInterrupt:
        print("\n跟踪已中断")
    finally:
        traceroute.close()
