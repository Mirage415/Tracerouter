import socket
import struct
import time
DEST_PORT = 33434

class Traceroute:
    def __init__(self, destination, max_hops = 30, timeout = 2):
        '''
        destination:目标主机（ip）
        max_hops: max_TTL
        timeout: 等待ICMP回复的最大时间/秒
        '''
        self._destination = destination
        self._maxttl = max_hops
        self._timeout = timeout 
        self._results = [] # 保存每一跳的结果
    
    def perform_traceroute(self):
        # 先获取目的地址的IP
        try:
            dest = socket.gethostbyname(self._destination)
        except socket.gaierror: #getaddrinfo()的缩写，尝试访问一个无效地址（DNS阻塞或错误，非法Ip或port）
            print(f'Unable to resolve host: {self._destination}')
            return
        # print("traceroute to {} ({}), {} hops max".format(self._destination, dest, self._maxttl))
        print(f'traceroute to {self._destination}({dest}, {self._maxttl} hops max)')

        for ttl in range(1, self._maxttl):
            # 记录这一hop发送时间
            send_time = time.time()
            self.send_packet(ttl, dest)
            response = self.receive_packet(ttl, send_time)
            self._results.append(response)

            # print(f'TTL: {response['TTL']:3}')
            print(f"TTL: {response['ttl']:3}  {response.get('addr', '*'):<15}  {response.get('rtt','')}")

        # for ttl in range(1, self._maxttl + 1):
        #     self.send_packet(ttl)
            if response['type'] == 'destination_reached':
                break
        
    def send_packet(self, ttl, dest):
        '''
        使用UDP探测报文，并设置ttl
        '''
        usock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        # 设置ttl
        # struct.pack(format, v1, v2)返回一个bytes对象
        usock.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, struct.pack('I', ttl)) #把ttl pack成int
        usock.sendto(b'', (dest, DEST_PORT)) #发一个空包到目标端口
        usock.close()

    def receive_packet(self, ttl, send_time):
        '''
        创建一个原始socket接收icmp回复，根据icmp类型判断本跳的结果
        并计算RTT
        '''
        # create a primal socket, to receive ICMP reply
        rsock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP) #ipporoto_icmp：只接收icmp信息
        rsock.settimeout(self._timeout)#设置接收数据的超时时间，超过就退出等待
        # 下面尝试接受icmp包
        try:
            '''
            接收数据，接收到之后记录接收到的时刻，记为rcv_time，并用接收时间剪去发送时间得到RTT，times1000变成毫秒
            '''
            packet, addr = rsock.recv(512)
            rcv_time = time.time()
            rttnotms = rcv_time - send_time
            rtt = rttnotms * 1000
            '''
            将数据包的前20个字节视为IP header（IP最小长度），使用struct.unpack和指定格式把IP头部分解。头部的第0个index
            包含版本和header长度，其中低4位iph[0]&0x0F表示IP header的长度，为4bytes，所以诚意4得到IP header的bytes数
            '''
            # ip header
            ipHeader = packet[:20]
            iph = struct.unpack('!BBHHHBBH4s4s', ipHeader)
            iph_len = (iph[0] & 0x0F) * 4
            # 接下来提取icmp header，8bytes
            icmpHeader = packet[iph_len:iph_len + 8]
            icmph = struct.unpack('!BBHHH', icmpHeader)
            icmpType, code = icmph[0], icmph[1] #判断收到的icmp响应类型
            '''
            构造一个结果字典，包含当前ttl，rtt string（保留三位小数），回复包发送者的ip
            '''
            result = {
                'ttl':ttl,
                'rtt':f'{rtt:.3f}ms',
                'addr':addr[0]
            }
            if icmpType == 11:
                # time exceeded
                result['type'] = 'time_exceeded'
            elif icmpType == 3:
                # code == 3表示到达了目标主机
                if code == 3:
                    result['type'] = 'destination_reached'
                else:
                    result['type'] = 'destination_unreachable'
            else:
                result['type'] = f'icmp_type_{icmpType}'
            return result
        except socket.timeout:
            return{
                'ttl':ttl,
                'type':'timeout'
            }
        finally:
            rsock.close()
    
    def get_results(self):
        return self._results
    def print_results(self):
        for result in self._results:
            print(
                f"TTL: {result['ttl']:3}\nAddr: {result.get('addr', '*'):<15}\nResponse: {result['type']}\nRTT: {result.get('rtt', '')}"
                )

if __name__ == "__main__":

    destination = 'www.google.com'
    # destination = '8.8.8.8'
    tracer = Traceroute(destination)
    tracer.perform_traceroute()
    tracer.print_results()