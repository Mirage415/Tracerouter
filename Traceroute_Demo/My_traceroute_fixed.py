
import argparse
import socket
import time
import struct
import select
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Optional, List
import random
import os
import platform


class Traceroute:
    def __init__(self):

        # Initialize state variables
        self.results = {}
        self.probes_sent = {}
        self.recv_running = False
        self.lock = Lock()
        self.recv_sock = None
        self.sock = None
        try:
            self.options = self._parse_args()
        except SystemExit as e:
            print(f"Caught SystemExit with code: {e.code}")
            print(f"Arguments: {e.args}")
            sys.exit(1)


    def init(self):
        # Initialize basic parameters
        self._init_basic_parameters()

        # Initialize network parameters
        self._init_network_parameters()

        # Initialize output parameters
        self._init_output_parameters()

        # Initialize sockets
        self._init_sockets()

        # print(self.__dict__)

    def _init_basic_parameters(self):
        self.queries_per_hop = self.options.queries
        self.timeout = self.options.wait / 1000.0
        self.min_send_interval = self.options.z / 1000.0
        self.max_hops = self.options.max_hops
        self.first_ttl = self.options.first_hop
        self.flag_no_resolve = self.options.no_resolve
        self.flag_simulate = self.options.simulate
        self.flag_mtu_test = self.options.mtu
        self.flag_show_extensions = self.options.extensions
        self.flag_verbose = self.options.verbose

    def _init_network_parameters(self):
        # IP protocol selection
        self.ip_protocol = "6" if self.options.ipv6 else "4" if self.options.ipv4 else None
        self.ip_protocol = '4'# 尚未支持ipv6，因此仅设定为ipv4
        self.dest_ip = self._resolve_hostname(self.options.host)
        self.ip_protocol = self._decide_ip_protocol()  # 若未指定ip协议，则根据DNS返回的ipv地址类型设定ip协议

        # Source IP handling
        self.src_ip = self.options.source
        if not self.src_ip:
            self.src_ip = self._get_default_source_ip()

        # Other IP options
        self.type_of_service = self.options.tos
        self.flag_df = self.options.dont_fragment
        self.LSRR_list = self.options.gateway

        # Transport layer options
        self.dest_port = self.options.port or 33434
        self.src_port = self.options.sport or random.randint(32768, 61000)
        self.protocol = self.options.protocol.lower()
        self.packet_size = self.options.packet_size

    def _init_output_parameters(self):

        self.probe_sequence = self.options.probe_sequence
        self.series_count = self.options.series_count
        self.series_interval = self.options.series_interval / 1000.0

    def _get_default_source_ip(self) -> str:
        try:
            if self.ip_protocol == '4':
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect((self.dest_ip, 80))
                return s.getsockname()[0]
            else:
                s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
                s.connect((self.dest_ip, 80))
                return s.getsockname()[0]
        except Exception:
            return ''

    @staticmethod
    def _print_warning(text: str):
        color = "\033[91m"
        reset_color = "\033[0m"
        print(f"{color}{text}{reset_color}")

    def _decide_ip_protocol(self) -> str:
        if self.ip_protocol:
            return self.ip_protocol
        try:
            if '.' in self.dest_ip:
                return '4'
            elif ':' in self.dest_ip:
                return '6'
            else:
                raise ValueError(f"Unable to determine IP version for {self.dest_ip}")
        except Exception as e:
            raise ValueError(f"Unable to resolve host {self.options.host}: {e}")

    @staticmethod
    def _parse_args() -> argparse.Namespace:
        parser = argparse.ArgumentParser(description="Advanced Python Traceroute Implementation")

        # Target specification
        target_group = parser.add_mutually_exclusive_group(required=False)
        target_group.add_argument("host", nargs='?', help="Target hostname or IP address")
        target_group.add_argument("-i", "--input-file", help="File containing list of target hosts (one per line)")

        # IP layer options
        ip_group = parser.add_mutually_exclusive_group()
        ip_group.add_argument("-4", "--ipv4", action="store_true", help="Force IPv4")
        ip_group.add_argument("-6", "--ipv6", action="store_true", help="Force IPv6")

        parser.add_argument("-s", "--source", help="Source address for outgoing packets")
        parser.add_argument("-t", "--tos", type=int, default=0,
                            help="Type of Service (IPv4) or Traffic Class (IPv6) value (0-255)")
        parser.add_argument("-F", "--dont-fragment", action="store_true",
                            help="Set Don't Fragment flag in packet")
        parser.add_argument("-f", "--first-hop", type=int, default=1,
                            help="Set initial TTL value (1-255)")
        parser.add_argument("-m", "--max-hops", type=int, default=30,
                            help="Maximum number of hops to probe (1-255)")
        parser.add_argument("-g", "--gateway", action="append",
                            help="Route packets through specified gateway (LSRR option)")

        # Transport layer options
        protocol_group = parser.add_mutually_exclusive_group()
        protocol_group.add_argument("-P", "--protocol", choices=["icmp", "udp", "tcp"], default="udp",
                                    help="Protocol to use for probes")
        protocol_group.add_argument("-I", "--icmp", action="store_const", dest="protocol", const="icmp",
                                    help="Use ICMP echo requests (equivalent to -P icmp)")
        protocol_group.add_argument("-T", "--tcp", action="store_const", dest="protocol", const="tcp",
                                    help="Use TCP SYN packets (equivalent to -P tcp)")

        parser.add_argument("--sport", type=int, help="Source port number")
        parser.add_argument("-p", "--port", type=int, help="Destination port number")
        parser.add_argument("--probe-sequence", nargs='+', default=["udp", "tcp", "icmp"],
                            help="Sequence of probe protocols to use per hop")
        parser.add_argument("--packet-size", type=int, default=64,
                            help="Size of probe packets in bytes")

        # Timing and probing options
        parser.add_argument("-w", "--wait", type=int, default=5000,
                            help="Wait time for response in milliseconds")
        parser.add_argument("-q", "--queries", type=int, default=1,
                            help="Number of probes that every series will sent for any protocol contains.")
        parser.add_argument("-z", type=int, default=0,
                            help="Minimum interval between probes in milliseconds")
        parser.add_argument("--series-count", type=int, default=1,
                            help="Number of probe series per hop")
        parser.add_argument("--series-interval", type=int, default=100,
                            help="Interval between probe series in milliseconds")

        # Output options
        parser.add_argument("-n", "--no-resolve", action="store_true",
                            help="Do not resolve IP addresses to hostnames")
        parser.add_argument("-v", "--verbose", action="store_true",
                            help="Verbose output")
        parser.add_argument("-e", "--extensions", action="store_true",
                            help="Show ICMP extensions")
        parser.add_argument("-S", "--simulate", action="store_true",
                            help="Simulation mode (don't actually send packets)")
        parser.add_argument("--mtu", action="store_true",
                            help="Discover MTU along path (implies -F -N 1)")

        args = parser.parse_args()

        # Post-processing and validation
        if args.mtu:
            args.dont_fragment = True

        # Validate numeric ranges
        for param in [(args.tos, 0, 255, "TOS"),
                      (args.first_hop, 1, 255, "First hop TTL"),
                      (args.max_hops, 1, 255, "Max hops"),
                      (args.port, 1, 65535, "Port") if args.port else (None, None, None, None),
                      (args.sport, 1, 65535, "Source port") if args.sport else (None, None, None, None),
                      (args.wait, 0, None, "Wait time"),
                      (args.queries, 1, None, "Queries per hop"),
                      (args.z, 0, None, "Probe interval")]:
            if param[0] is not None and (param[0] < param[1] or (param[2] is not None and param[0] > param[2])):
                parser.error(f"{param[3]} must be between {param[1]} and {param[2]} (got {param[0]})")

        if args.protocol == "icmp" and (args.port or args.sport):
            parser.error("ICMP protocol cannot specify port numbers")

        return args

    def _init_sockets(self):
        try:
            self.sock = self._create_send_socket()
            self.recv_sock = self._create_recv_socket()
            self._config_socket_options()
        except Exception as e:
            self._print_warning(f"Failed to initialize sockets: {str(e)}")
            sys.exit(1)

    def _create_send_socket(self) -> socket.socket:
        if self.protocol == 'tcp':
            trans_protocol = socket.SOCK_STREAM
            ip_proto = socket.IPPROTO_TCP
        elif self.protocol == 'udp':
            trans_protocol = socket.SOCK_DGRAM
            ip_proto = socket.IPPROTO_UDP
        elif self.protocol == 'icmp':
            trans_protocol = socket.SOCK_RAW
            ip_proto = socket.IPPROTO_ICMP
        else:
            raise ValueError(f"Unsupported protocol: {self.protocol}")

        family = socket.AF_INET6 if self.ip_protocol == '6' else socket.AF_INET

        try:
            sock = socket.socket(family, trans_protocol, ip_proto)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Bind to source IP if specified
            if self.src_ip:
                sock.bind((self.src_ip, self.src_port))

            return sock
        except PermissionError as e:
            self._print_warning(f"Permission denied: {e}. Try running as root.")
            sys.exit(1)
        except Exception as e:
            self._print_warning(f"Failed to create send socket: {e}")
            sys.exit(1)

    def _create_recv_socket(self) -> socket.socket:
        try:
            family = socket.AF_INET6 if self.ip_protocol == '6' else socket.AF_INET

            if self.protocol == 'icmp':
                proto = socket.IPPROTO_ICMP
            elif self.protocol == 'udp':
                proto = socket.IPPROTO_ICMP  # For UDP we get ICMP responses
            else:  # TCP
                proto = socket.IPPROTO_TCP

            sock = socket.socket(family, socket.SOCK_RAW, proto)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            sock.settimeout(self.timeout)
            sock.bind(('', 0))

            # On Linux, we need to enable receiving the TTL/hop limit
            if platform.system() == 'Linux':
                sock.setsockopt(socket.SOL_IP, 12, 1) # IP_RECVTTL
                if self.ip_protocol == '6':
                    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_RECVHOPLIMIT, 1)

            return sock
        except Exception as e:
            self._print_warning(f"Failed to create receive socket: {e}")
            sys.exit(1)

    def _config_socket_options(self):
        # Set TOS/DSCP
        if self.type_of_service:
            if self.ip_protocol == '4':
                self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, self.type_of_service)
            else:
                self.sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_TCLASS, self.type_of_service)

        # Set Don't Fragment flag
        if self.flag_df:
            if self.ip_protocol == '4':
                if platform.system() == 'Linux':
                    self.sock.setsockopt(socket.IPPROTO_IP, 10, 2)  # IP_MTU_DISCOVER
                elif platform.system() == 'Windows':
                    self.sock.setsockopt(socket.IPPROTO_IP, 14, 1)  # IP_DONTFRAGMENT
                else:  # macOS/BSD
                    self.sock.setsockopt(socket.IPPROTO_IP, 67, 1)  # IP_DONTFRAG
            else:  # IPv6
                if platform.system() == 'Linux':
                    self.sock.setsockopt(socket.IPPROTO_IPV6, 10, 2) # IPV6_MTU_DISCOVER
                elif platform.system() == 'Windows':
                    self.sock.setsockopt(socket.IPPROTO_IPV6, 14, 1) # IPV6_DONTFRAG
                else:  # macOS/BSD
                    self.sock.setsockopt(socket.IPPROTO_IPV6, 62, 1)  # IPV6_DONTFRAG

        # Configure Loose Source Routing if specified
        if self.LSRR_list:
            self._config_source_routing()

    def _config_source_routing(self):
        if self.ip_protocol == '4':
            if len(self.LSRR_list) > 8:
                raise ValueError("Too many gateways for IPv4 LSRR (max 8)")

            init_ptr = 4
            route_data = b''

            for ip in self.LSRR_list:
                try:
                    route_data += socket.inet_aton(self._resolve_hostname(ip))
                except socket.error as e:
                    self._print_warning(f"Failed to resolve gateway {ip}: {e}")
                    sys.exit(1)

            option = struct.pack('BBBB', 0x83, len(route_data) + 3, init_ptr, 0) + route_data

            try:
                self.sock.setsockopt(socket.SOL_IP, socket.IP_OPTIONS, option)
            except socket.error as e:
                self._print_warning(f"Failed to set LSRR option: {e}")
                sys.exit(1)

        else:  # IPv6
            segments = len(self.LSRR_list)
            header = struct.pack('!BBBB', 0, (segments + 1) * 2, 0, segments)
            header += b'\x00' * 4  # Reserved

            for ip in self.LSRR_list:
                try:
                    header += socket.inet_pton(socket.AF_INET6, self._resolve_hostname(ip))
                except socket.error as e:
                    self._print_warning(f"Failed to resolve gateway {ip}: {e}")
                    sys.exit(1)

            try:
                self.sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_RTHDR, header)
            except socket.error as e:
                self._print_warning(f"Failed to set IPv6 routing header: {e}")
                sys.exit(1)

    def _resolve_hostname(self, host: str) -> str:
        print(host)
        try:
            family = socket.AF_INET6 if self.ip_protocol == '6' else socket.AF_INET
            addrinfo = socket.getaddrinfo(host, None, family)
            return addrinfo[0][4][0]
        except socket.gaierror as e:
            self._print_warning(f"Failed to resolve {host}: {e}")
            sys.exit(1)


    def _get_target_list(self) -> List[str]:
        if self.options.input_file:
            with open(self.options.input_file) as f:
                return [line.strip() for line in f if line.strip()]
        return [self.options.host]

    def run(self):
        self.init()
        print(f"Traceroute to {self.options.host} ({self.dest_ip}), "
              f"max hops {self.max_hops}, {self.queries_per_hop} probes per hop")

        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                # Start receiver thread first
                recv_future = executor.submit(self._receiver_thread)

                # Wait for receiver to initialize
                start_time = time.time()
                while not self.recv_running and (time.time() - start_time) < 1:
                    time.sleep(0.1)

                if not self.recv_running:
                    raise RuntimeError("Receiver thread failed to start")

                try:
                    # Send probes for each TTL

                    for ttl in range(self.first_ttl, self.first_ttl + self.max_hops):
                        self._probe_hop(ttl)

                        # Check if we've reached the target
                        if self._check_target_reached(ttl):
                            break

                except KeyboardInterrupt:
                    print("\nTrace interrupted by user")
                finally:
                    self.recv_running = False
                    recv_future.result(timeout=2)

        except Exception as e:
            self._print_warning(f"Traceroute failed: {e}")
        finally:
            self.close()
            self._display_final_results()
            return self.results

    def _probe_hop(self, ttl: int):
        for series in range(self.series_count):
            for proto in self.probe_sequence:
                for seq in range(1, self.queries_per_hop + 1):
                    if self._send_probe(ttl, series, proto, seq):
                        time.sleep(self.min_send_interval)

            time.sleep(self.series_interval)

        # Display results for this hop
        self._display_current_hop(ttl)

    def _send_probe(self, ttl: int, series: int, proto: str, seq: int) -> bool:
        if self.flag_simulate:
            return True

        probe_id = f"{ttl}-{series}-{proto}-{seq}"
        send_time = time.time()

        # Set TTL
        if self.ip_protocol == '4':
            self.sock.setsockopt(socket.SOL_IP, socket.IP_TTL, ttl)
        else:
            self.sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_UNICAST_HOPS, ttl)

        # Send based on protocol
        try:
            if proto == "udp":
                self._send_udp_probe(seq)
            elif proto == "tcp":
                self._send_tcp_probe(seq)
            elif proto == "icmp":
                self._send_icmp_probe(seq)
        except Exception as e:
            if self.flag_verbose:
                self._print_warning(f"Failed to send {proto} probe: {e}")
            return False

        # Record probe info
        with self.lock:
            self.probes_sent[probe_id] = {
                'send_time': send_time,
                'ttl': ttl,
                'series': series,
                'proto': proto,
                'seq': seq,
                'matched': False
            }

        return True

    def _send_udp_probe(self, seq: int):
        port = self.dest_port + seq - 1
        if port > 65535:
            port = (port - 49152) % 16384 + 49152  # Wrap around to dynamic ports

        data = b"P" * self.packet_size
        self.sock.sendto(data, (self.dest_ip, port))

    def _send_tcp_probe(self, seq: int):
        if self.ip_protocol == '4':
            packet = self._build_ipv4_header() + self._build_tcp_header(seq)
        else:
            packet = self._build_ipv6_header() + self._build_tcp_header(seq)

        self.sock.sendto(packet, (self.dest_ip, self.dest_port))

    def _send_icmp_probe(self, seq: int):
        ident = random.randint(0, 65535)
        checksum = 0
        header = struct.pack("!BBHHH", 8, 0, checksum, ident, seq)
        data = b"P" * (self.packet_size - len(header))

        # Calculate checksum
        checksum = self._calculate_checksum(header + data)
        header = struct.pack("!BBHHH", 8, 0, checksum, ident, seq)

        self.sock.sendto(header + data, (self.dest_ip, 0))

    def _build_ipv4_header(self) -> bytes:
        version_ihl = 0x45  # IPv4, 5 word header
        dscp_ecn = self.type_of_service
        total_len = 40  # 20 byte IP header + 20 byte TCP header
        ident = random.randint(0, 65535)
        flags_frag = 0x4000 if self.flag_df else 0  # DF flag
        ttl = 64  # Will be overwritten
        proto = socket.IPPROTO_TCP
        src_ip = socket.inet_aton(self.src_ip)
        dst_ip = socket.inet_aton(self.dest_ip)

        header = struct.pack("!BBHHHBBH4s4s",
                             version_ihl, dscp_ecn, total_len,
                             ident, flags_frag,
                             ttl, proto, 0,  # Checksum initially 0
                             src_ip, dst_ip)

        # Checksum
        checksum = self._calculate_checksum(header)
        return header[:10] + struct.pack("H", checksum) + header[12:]

    def _build_ipv6_header(self, payload_len: int = 40) -> bytes:
        version = 0x6
        traffic_class = self.type_of_service
        flow_label = 0

        header = struct.pack("!IHBB16s16s",
                             (version << 28) | (traffic_class << 20) | flow_label,
                             payload_len,
                             socket.IPPROTO_TCP if self.protocol == "tcp" else socket.IPPROTO_UDP,
                             64,  # Hop limit (will be overwritten)
                             socket.inet_pton(socket.AF_INET6, self.src_ip),
                             socket.inet_pton(socket.AF_INET6, self.dest_ip))

        # Add extension headers if needed
        if self.LSRR_list:
            routing_header = self._build_ipv6_routing_header()
            header += routing_header
            # Update next header field
            header = header[:6] + bytes([43]) + header[7:]  # 43 is routing header

        return header

    def _build_ipv6_routing_header(self) -> bytes:
        segments = len(self.LSRR_list)
        header = struct.pack("!BBBB",
                             0,  # Next header
                             2 * (segments + 1),  # Header length in 8-byte units
                             0,  # Routing type (0 for LSRR)
                             segments)

        # Add addresses
        for ip in self.LSRR_list:
            header += socket.inet_pton(socket.AF_INET6, self._resolve_hostname(ip))

        # Pad to 8-byte multiple
        if len(header) % 8 != 0:
            header += b'\x00' * (8 - (len(header) % 8))

        return header

    def _build_tcp_header(self, seq: int) -> bytes:
        tcp_header = struct.pack("!HHLLBBHHH",
                                 self.src_port, self.dest_port,
                                 seq, 0,  # Sequence number, ACK number
                                 5 << 4,  # offset
                                 0x02,  # flag
                                 8192,  # Window size
                                 0, 0)  # Checksum and urgent pointer

        # Calculate checksum with pseudo-header
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

        checksum = self._calculate_checksum(pseudo_header + tcp_header)
        return tcp_header[:16] + struct.pack("H", checksum) + tcp_header[18:]

    def _receiver_thread(self):
        self.recv_running = True
        cnt = 0

        while self.recv_running:
            try:
                ready, _, _ = select.select([self.recv_sock], [], [], 0.1)
                if ready:
                    try:
                        packet, addr = self.recv_sock.recvfrom(1024)
                        self._process_reply_packet(packet, addr)
                    except socket.timeout:
                        continue
                    except ConnectionResetError:
                        if self.flag_verbose:
                            self._print_warning("Connection reset by peer")
                        continue
            except Exception as e:
                if self.flag_verbose:
                    self._print_warning(f"Receiver error: {e}")
                break

    def _process_reply_packet(self, packet: bytes, addr: tuple):
        try:
            src_ip = addr[0]
            extensions = {}

            if self.ip_protocol == '4':
                self._process_ipv4_reply(packet, src_ip, extensions)
            else:
                self._process_ipv6_reply(packet, src_ip, extensions)
        except Exception as e:
            if self.flag_verbose:
                self._print_warning(f"Error processing reply: {e}")

    def _process_ipv4_reply(self, packet: bytes, src_ip: str, extensions: dict):
        ip_header_len = (packet[0] & 0x0F) * 4
        transport_header = packet[ip_header_len:]

        if self.flag_show_extensions:
            extensions.update(self._process_icmp_extensions(transport_header))

        # ICMP protocol handling
        if len(transport_header) >= 8:
            type_, code = struct.unpack("!BB", transport_header[:2])

            # ICMP Echo Reply (response to our ICMP probe)
            if type_ == 0 and self.protocol == "icmp":
                _, _, probe_id, seq = struct.unpack("!HHHH", transport_header[:8])
                self._match_reply(probe_id, seq, src_ip, extensions)

            # ICMP errors (response to UDP/TCP)
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

    def _process_ipv6_reply(self, packet: bytes, src_ip: str, extensions: dict):
        """Process IPv6 reply packet"""
        # Basic IPv6 header is 40 bytes
        transport_header = packet[40:]

        if self.flag_show_extensions:
            extensions.update(self._process_icmp_extensions(transport_header))

        # ICMPv6 handling
        if len(transport_header) >= 8:
            type_, code = struct.unpack("!BB", transport_header[:2])

            # ICMPv6 Echo Reply
            if type_ == 129 and self.protocol == "icmp":
                _, _, probe_id, seq = struct.unpack("!HHHH", transport_header[:8])
                self._match_reply(probe_id, seq, src_ip, extensions)

            # ICMPv6 errors (Time Exceeded, Destination Unreachable)
            elif type_ in (3, 11) and len(transport_header) >= 48:
                # IPv6 header is 40 bytes, we need to look at the original packet
                orig_transport = transport_header[48:]

                if self.protocol == "udp" and len(orig_transport) >= 8:
                    orig_sport, orig_dport = struct.unpack("!HH", orig_transport[:4])
                    seq = orig_dport - self.dest_port + 1
                    self._match_reply(None, seq, src_ip, extensions)

                elif self.protocol == "tcp" and len(orig_transport) >= 20:
                    orig_sport, orig_dport = struct.unpack("!HH", orig_transport[:4])
                    seq = orig_dport - self.dest_port + 1
                    self._match_reply(None, seq, src_ip, extensions)

    def _match_reply(self, probe_id: Optional[int], seq: int, src_ip: str, extensions: dict):
        with self.lock:
            # Try to find matching probe
            for probe_key, probe in list(self.probes_sent.items()):
                if (probe['seq'] == seq and
                        (probe_id is None or ('probe_id' in probe and probe['probe_id'] == probe_id)) and
                        not probe['matched']):
                    rtt = (time.time() - probe['send_time']) * 1000
                    reached = src_ip == self.dest_ip

                    self._record_hop_result(
                        probe['ttl'],
                        probe['series'],
                        probe['proto'],
                        {
                            'ip': src_ip,
                            'rtt': rtt,
                            'reached': reached,
                            'extensions': extensions
                        }
                    )

                    probe['matched'] = True
                    break

    def _record_hop_result(self, ttl: int, series: int, proto: str, result: dict):
        if ttl not in self.results:
            self.results[ttl] = {
                'udp': {'probes': [], 'stats': {}},
                'tcp': {'probes': [], 'stats': {}},
                'icmp': {'probes': [], 'stats': {}},
                'extensions': {}
            }

        # Record the probe result
        self.results[ttl][proto]['probes'].append({
            'rtt': result['rtt'],
            'from': result['ip'],
            'reached': result['reached']
        })

        # Update extensions if present
        if result.get('extensions'):
            self.results[ttl]['extensions'].update(result['extensions'])

        # Update statistics
        self._update_hop_stats(ttl, proto)

    def _update_hop_stats(self, ttl: int, proto: str):
        probes = self.results[ttl][proto]['probes']
        valid_rtts = [p['rtt'] for p in probes if p['rtt'] is not None]

        stats = {
            'count': len(probes),
            'responses': len(valid_rtts),
            'loss': (len(probes) - len(valid_rtts)) / len(probes) if probes else 0.0
        }

        if valid_rtts:
            stats.update({
                'min': min(valid_rtts),
                'max': max(valid_rtts),
                'avg': sum(valid_rtts) / len(valid_rtts)
            })

        self.results[ttl][proto]['stats'] = stats

    def _check_target_reached(self, ttl: int) -> bool:
        """Check if we've reached the target"""
        if ttl not in self.results:
            return False

        for proto in ['udp', 'tcp', 'icmp']:
            for probe in self.results[ttl][proto]['probes']:
                if probe.get('reached', False):
                    return True

        return False

    def _display_current_hop(self, ttl: int):
        """Display results for current hop"""
        if ttl not in self.results:
            print(f"{ttl:2d}  *")
            return

        hop = self.results[ttl]
        line = f"{ttl:2d}  "

        responding_ip = None
        for proto in ['udp', 'tcp', 'icmp']:
            for probe in hop[proto]['probes']:
                if probe['from']:
                    responding_ip = probe['from']
                    break
            if responding_ip:
                break

        if not responding_ip:
            line += "*" * (self.queries_per_hop * 8 + 15)
            print(line)
            return

        hostname = responding_ip
        if not self.flag_no_resolve:
            try:
                hostname = socket.gethostbyaddr(responding_ip)[0]
            except (socket.herror, socket.gaierror):
                pass

        line += f"{hostname:<15}  "

        for proto in self.probe_sequence:
            probes = hop[proto]['probes']
            if len(probes) >= self.queries_per_hop:  # Only display if we sent probes
                for probe in probes[:self.queries_per_hop]:  # Only display configured number
                    if probe['rtt'] is not None:
                        line += f"{probe['rtt']:>7.2f} ms  "
                    else:
                        line += "    *     "

        print(line)

        if self.flag_show_extensions and hop.get('extensions'):
            self._display_extensions(hop['extensions'])

    def _display_extensions(self, extensions: dict):
        if extensions.get('mpls'):
            print("    MPLS Labels:")
            for mpls in extensions['mpls']:
                print(f"      Label={mpls['label']}, TC={mpls['tc']}, "
                      f"S={mpls['s']}, TTL={mpls['ttl']}")

        if extensions.get('other'):
            print("    Other Extensions:")
            for ext in extensions['other']:
                print(f"      Type={ext['type']}, Length={ext['length']}")

    def _display_final_results(self):
        print("\n=== Traceroute Results ===")
        reached_target = False

        for ttl in sorted(self.results.keys()):
            hop = self.results[ttl]

            # Skip hops with no responses at all
            if all(len(hop[proto]['probes']) == 0 for proto in ['udp', 'tcp', 'icmp']):
                continue

            print(f"\nHop {ttl}:")

            # Display IP and hostname
            ips = set()
            for proto in ['udp', 'tcp', 'icmp']:
                for probe in hop[proto]['probes']:
                    if probe['from']:
                        ips.add(probe['from'])

            for ip in ips:
                hostname = ip
                if not self.flag_no_resolve:
                    try:
                        hostname = socket.gethostbyaddr(ip)[0]
                    except (socket.herror, socket.gaierror):
                        pass
                print(f"  IP: {ip} ({hostname})")

                # Check if we reached target
                if ip == self.dest_ip:
                    reached_target = True

            # Display statistics per protocol
            for proto in self.probe_sequence:
                stats = hop[proto]['stats']
                if not stats:
                    continue
                if stats:
                    if stats['count'] > 0:
                        print(f"  {proto.upper()} Stats: "
                            f"Sent={stats['count']}, "
                            f"Responses={stats['responses']}, "
                            f"Loss={stats['loss']:.0%}")

                        if stats['responses'] > 0:
                            print(f"    RTT: Min={stats['min']:.2f}ms, "
                                f"Avg={stats['avg']:.2f}ms, "
                                f"Max={stats['max']:.2f}ms")

            # Display extensions if present
            if self.flag_show_extensions and hop.get('extensions'):
                self._display_extensions(hop['extensions'])

        if not reached_target:
            print("\nWarning: Did not reach target host within max hops")

        # Add metadata to results
        self.results['metadata'] = {
            'target': self.dest_ip,
            'protocol': self.protocol,
            'ip_version': self.ip_protocol,
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
            'reached_target': reached_target
        }


    @staticmethod
    def _calculate_checksum(data: bytes) -> int:
        if len(data) % 2 != 0:
            data += b'\x00'  # Pad to even length

        total = 0
        for i in range(0, len(data), 2):
            word = (data[i] << 8) + data[i + 1]
            total += word
            total = (total & 0xffff) + (total >> 16)

        return ~total & 0xffff

    @staticmethod
    def _process_icmp_extensions(packet: bytes) -> dict:
        extensions = {
            'mpls': [],
            'other': []
        }

        if len(packet) < 8:
            return extensions

        ext_start = 8

        while ext_start + 4 <= len(packet):
            ext_type, ext_len = struct.unpack("!BB", packet[ext_start:ext_start + 2])

            # MPLS extension (type 1)
            if ext_type == 1 and ext_len >= 8:
                mpls_data = packet[ext_start + 4:ext_start + ext_len]
                for i in range(0, len(mpls_data), 4):
                    if i + 4 <= len(mpls_data):
                        label = struct.unpack("!I", mpls_data[i:i + 4])[0]
                        extensions['mpls'].append({
                            'label': label >> 12,
                            'tc': (label >> 9) & 0x7,
                            's': (label >> 8) & 0x1,
                            'ttl': label & 0xFF
                        })

            # Other extensions
            elif ext_len >= 4:
                extensions['other'].append({
                    'type': ext_type,
                    'length': ext_len,
                    'data': packet[ext_start + 4:ext_start + ext_len]
                })

            ext_start += ext_len

        return extensions

    def close(self):
        self.recv_running = False

        if hasattr(self, 'sock') and self.sock:
            try:
                self.sock.close()
            except:
                pass

        if hasattr(self, 'recv_sock') and self.recv_sock:
            try:
                self.recv_sock.close()
            except:
                pass


if __name__ == "__main__":
    try:
        traceroute = Traceroute()
        traceroute.run()

    except KeyboardInterrupt:
        print("\nTraceroute interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        if 'traceroute' in locals():
            traceroute.close()