import argparse
import socket
import time
import struct
import select
import sys
from typing import Optional, List, Tuple, Dict, Union
import random
import platform
import numpy
from numpy.ma.core import append


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
        self.queries_per_send = self.options.sim_queries

        self.timeout = self.options.wait / 1000.0  # 转换为秒
        self.min_send_interval = self.options.z

        self.max_hops = self.options.max_hops
        self.first_ttl = self.options.first_hop


        # Ethernet layer options
        self.interface = self.options.interface


        # IP protocol options
        self.ip_protocol =  "6" if self.options.ipv6 else ("4" if self.options.ipv4 else None)
        self.dest_ip = self._resolve_hostname(self.options.host)
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
        self.flag_no_resolve = self.options.no_resolve
        self.flag_show_extensions = self.options.extensions
        self.flag_verbose = self.options.verbose


        # initialize socket according to control info
        self.sock = self._create_socket()
        self._config_params()

        self.results = {}

        # print(self.__dict__)

    @staticmethod
    def _print_warning(text):
        color = "\033[91m"
        reset_color = "\033[0m"
        print(f"{color}{text}{reset_color}")


    def _parse_args(self) -> argparse.Namespace:
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
        protocol_group.add_argument("-P", "--protocol", choices=["icmp", "udp", "tcp", "tcpconn"], default="udp",
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
        parser.add_argument("-N", "--sim-queries", type=int, default=16,
                            help="the number of probes to be sent simultaneously (default: 16)")
        parser.add_argument("-z", type=int, default=0,
                            help="Minimum interval time between sending probe packets(ms) (default: 0)")

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
        if args.sim_queries<0:
            parser.error("-N/--sim-queries the number of probes to be sent simultaneously 不能为负数，请修改")
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
                self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_OPTIONS, option)
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

        if self.protocol == 'tcp' or self.protocol == 'tcpconn':
            trans_protocol = socket.SOCK_STREAM
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

        return sock

    def _get_local_ips(self):
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
        """执行traceroute"""
        print(f"traceroute到 {self.options.host} ({self.dest_ip}), "
              f"最多 {self.max_hops} 跳, {self.queries_per_hop} 个探测包")

        while self.first_ttl <= self.max_hops:
            hop_result = self._probe_hop()
            self._display_hop(hop_result)

            if hop_result["reached"]:
                break

            self.first_ttl += 1

    def _probe_hop(self) -> Dict:
        """探测指定TTL的一跳"""
        hop_result = {
            "ttl": self.first_ttl,
            "probes": [],
            "reached": False,
            "ip": None,
            "hostname": None
        }

        for seq in range(1, self.queries_per_hop + 1):
            probe_result = self._send_probe(seq)
            hop_result["probes"].append(probe_result)

            if probe_result["ip"] and not hop_result["ip"]:
                hop_result["ip"] = probe_result["ip"]
                try:
                    hop_result["hostname"] = socket.gethostbyaddr(probe_result["ip"])[0]
                except socket.herror:
                    hop_result["hostname"] = probe_result["ip"]

            if probe_result["reached"]:
                hop_result["reached"] = True
                break

        return hop_result

    def _send_probe(self, seq: int) -> Dict:
        """发送单个探测包"""
        probe_id = random.randint(0, 65535)
        send_time = time.time()

        # 设置TTL
        self.send_socket.setsockopt(
            socket.SOL_IP, socket.IP_TTL, self.first_ttl)

        # 根据协议发送不同的探测包
        if self.protocol == "icmp":
            self._send_icmp_probe(probe_id, seq)
        elif self.protocol == "udp":
            self._send_udp_probe(seq)
        elif self.protocol == "tcp":
            self._send_tcp_probe(seq)

        # 等待回复
        reply = self._wait_for_reply(probe_id, seq)

        if reply:
            rtt = (time.time() - send_time) * 1000  # 转换为毫秒
            return {
                "ip": reply[0],
                "rtt": rtt,
                "reached": reply[0] == self.dest_ip
            }
        else:
            return {
                "ip": None,
                "rtt": None,
                "reached": False
            }

    def _send_icmp_probe(self, probe_id: int, seq: int):
        """发送ICMP ECHO请求"""
        checksum = 0
        header = struct.pack("!BBHHH", 8, 0, checksum, probe_id, seq)
        data = b"PythonTraceroute"

        # 计算校验和
        checksum = self._calculate_checksum(header + data)
        header = struct.pack("!BBHHH", 8, 0, checksum, probe_id, seq)

        self.send_socket.sendto(header + data, (self.dest_ip, 0))

    def _send_udp_probe(self, seq: int):
        """发送UDP探测包"""
        port = self.dest_port + seq - 1
        data = b"PythonTraceroute"
        self.send_socket.sendto(data, (self.dest_ip, port))

    def _send_tcp_probe(self, seq: int):
        """发送TCP SYN探测包"""
        port = self.dest_port
        if seq > 1:
            port += seq - 1

        try:
            self.send_socket.connect((self.dest_ip, port))
            self.send_socket.send(b"")
        except socket.error:
            pass

    def _wait_for_reply(self, probe_id: int, seq: int) -> Optional[Tuple[str, int]]:
        """等待回复"""
        start_time = time.time()

        while time.time() - start_time < self.timeout:
            ready = select.select([self.recv_socket], [], [], self.timeout)
            if ready[0]:
                try:
                    packet, addr = self.recv_socket.recvfrom(1024)
                    ip_header = packet[:20]
                    src_ip = socket.inet_ntoa(ip_header[12:16])

                    if self.protocol == "icmp":
                        if self._is_icmp_reply(packet[20:], probe_id, seq):
                            return (src_ip, 0)
                    elif self.protocol == "udp":
                        if self._is_icmp_ttl_exceeded(packet[20:]):
                            return (src_ip, 0)
                        elif self._is_dest_unreachable(packet[20:]):
                            return (src_ip, 0)
                    elif self.protocol == "tcp":
                        if self._is_tcp_syn_ack(packet[20:]):
                            return (src_ip, 0)
                        elif self._is_icmp_ttl_exceeded(packet[20:]):
                            return (src_ip, 0)
                except socket.error:
                    continue

        return None

    def _is_icmp_reply(self, icmp_header: bytes, probe_id: int, seq: int) -> bool:
        """检查是否是ICMP回复"""
        if len(icmp_header) < 8:
            return False

        type_, code, checksum, p_id, p_seq = struct.unpack("!BBHHH", icmp_header[:8])

        return (type_ == 0 and code == 0 and
                p_id == probe_id and p_seq == seq)

    def _is_icmp_ttl_exceeded(self, icmp_header: bytes) -> bool:
        """检查是否是ICMP TTL超时"""
        if len(icmp_header) < 8:
            return False

        type_, code = struct.unpack("!BB", icmp_header[:2])
        return type_ == 11 and code == 0

    def _is_dest_unreachable(self, icmp_header: bytes) -> bool:
        """检查是否是目的不可达"""
        if len(icmp_header) < 8:
            return False

        type_, code = struct.unpack("!BB", icmp_header[:2])
        return type_ == 3

    def _is_tcp_syn_ack(self, tcp_header: bytes) -> bool:
        """检查是否是TCP SYN-ACK回复"""
        if len(tcp_header) < 20:
            return False

        flags = tcp_header[13]
        return (flags & 0x12) == 0x12  # SYN-ACK

    def _calculate_checksum(self, data: bytes) -> int:
        """计算ICMP校验和"""
        if len(data) % 2 != 0:
            data += b'\x00'

        sum_ = 0
        for i in range(0, len(data), 2):
            sum_ += (data[i] << 8) + data[i + 1]

        sum_ = (sum_ >> 16) + (sum_ & 0xffff)
        sum_ += sum_ >> 16
        return ~sum_ & 0xffff

    def _display_hop(self, hop_result: Dict):
        """显示一跳的结果"""
        line = f"{hop_result['ttl']:2d}  "

        if not hop_result["ip"]:
            line += "*" * (self.queries_per_hop * 6 + 10)
            print(line)
            return

        # 显示主机名或IP
        if self.options.no_resolve or not hop_result["hostname"]:
            display_name = hop_result["ip"]
        else:
            display_name = f"{hop_result['hostname']} ({hop_result['ip']})"

        line += f"{display_name}  "

        # 显示每个探测的RTT
        for probe in hop_result["probes"]:
            if probe["rtt"] is not None:
                line += f"{probe['rtt']:.3f} ms  "
            else:
                line += "*  "

        print(line)

    def close(self):
        """关闭套接字"""
        self.send_socket.close()
        self.recv_socket.close()


if __name__ == "__main__":
    traceroute = Traceroute()


    # try:
    #     traceroute.run()
    # except KeyboardInterrupt:
    #     print("\n跟踪已中断")
    # finally:
    #     traceroute.close()