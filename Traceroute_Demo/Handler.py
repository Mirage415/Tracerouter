# handler.py
import os
import json
import csv
import random
from typing import List, Dict, Union
from My_traceroute_fixed import Traceroute  # 假设您的traceroute类在traceroute.py中
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict


class TracerouteHandler:
    def __init__(self, output_dir: str = "results"):
        """
        初始化处理器
        :param output_dir: 结果输出目录
        """
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def read_targets(self, input_file: str) -> List[str]:
        """
        读取目标文件，支持txt和csv格式
        :param input_file: 输入文件路径
        :return: 目标列表
        """
        targets = []

        if not os.path.exists(input_file):
            raise FileNotFoundError(f"Input file {input_file} not found")

        try:
            if input_file.endswith('.csv'):
                with open(input_file, 'r') as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if row and row[0].strip() and not row[0].startswith('#'):
                            targets.append(row[0].strip())
            else:  # 默认为txt格式处理
                with open(input_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            targets.append(line)
        except Exception as e:
            raise IOError(f"Error reading input file: {str(e)}")

        if not targets:
            raise ValueError("No valid targets found in input file")

        return targets

    def process_target(self, target: str, options: Dict) -> Dict:
        """
        处理单个目标
        :param target: 目标地址
        :param options: traceroute选项字典
        :return: 追踪结果
        """
        tracer = Traceroute()

        # 设置选项
        for opt, value in options.items():
            if hasattr(tracer.options, opt):
                setattr(tracer.options, opt, value)

        # 设置目标
        tracer.options.host = target
        tracer.options.input_file = None  # 确保使用单个目标模式

        # 执行追踪
        return tracer.run()

    def save_results(self, target: str, results: Dict, format: str = "json"):
        """
        保存结果到文件
        :param target: 目标地址
        :param results: 追踪结果
        :param format: 输出格式(json/text)
        """
        safe_name = "".join(c if c.isalnum() else "_" for c in target)
        filename = f"traceroute_{safe_name}.{format}"
        filepath = os.path.join(self.output_dir, filename)

        try:
            if format == "json":
                with open(filepath, 'w') as f:
                    json.dump(results, f, indent=2)
            else:  # 文本格式
                with open(filepath, 'w') as f:
                    self._write_text_results(f, results, target)
        except Exception as e:
            raise IOError(f"Failed to save results for {target}: {str(e)}")

    def _write_text_results(self, file_obj, results: Dict, target: str):
        """
        将结果写入文本文件
        :param file_obj: 文件对象
        :param results: 追踪结果
        :param target: 目标地址
        """
        file_obj.write(f"Traceroute results for {target}\n")
        file_obj.write("=" * 50 + "\n\n")

        metadata = results.get('metadata', {})
        file_obj.write(f"Target: {metadata.get('target', 'N/A')}\n")
        file_obj.write(f"Series: {metadata.get('series', 'N/A')}\n")
        file_obj.write(f"IP Version: {metadata.get('ip_version', 'N/A')}\n")
        file_obj.write(f"Timestamp: {metadata.get('timestamp', 'N/A')}\n")
        file_obj.write(f"Reached Target: {'Yes' if metadata.get('reached_target') else 'No'}\n\n")

        # 按TTL排序
        ttl_keys = [k for k in results.keys() if isinstance(k, int)]
        for ttl in sorted(ttl_keys):
            hop_data = results[ttl]
            file_obj.write(f"Hop {ttl}:\n")

            for proto in ['udp', 'tcp', 'icmp']:
                if proto in hop_data:
                    self._write_proto_results(file_obj, hop_data[proto], proto.upper())

            if hop_data.get('extensions'):
                self._write_extensions(file_obj, hop_data['extensions'])

            file_obj.write("\n")

    def _write_proto_results(self, file_obj, proto_data: Dict, proto_name: str):
        """
        写入协议特定的结果
        """
        file_obj.write(f"  {proto_name}:\n")
        stats = proto_data.get('stats', {})

        file_obj.write("    Statistics:\n")
        file_obj.write(f"      Probes sent: {stats.get('count', 0)}\n")
        file_obj.write(f"      Responses: {stats.get('responses', 0)}\n")
        file_obj.write(f"      Loss: {stats.get('loss', 0):.1%}\n")

        if stats.get('responses', 0) > 0:
            file_obj.write(f"      Min RTT: {stats.get('min', 0):.2f} ms\n")
            file_obj.write(f"      Avg RTT: {stats.get('avg', 0):.2f} ms\n")
            file_obj.write(f"      Max RTT: {stats.get('max', 0):.2f} ms\n")

        file_obj.write("    Probe details:\n")
        for i, probe in enumerate(proto_data.get('probes', []), 1):
            file_obj.write(f"      Probe {i}: ")
            if probe['rtt'] is not None:
                file_obj.write(f"RTT: {probe['rtt']:.2f} ms from {probe['from']} ")
                file_obj.write("(Reached)" if probe['reached'] else "")
            else:
                file_obj.write("Timeout")
            file_obj.write("\n")

    def _write_extensions(self, file_obj, extensions: Dict):
        """
        写入扩展信息
        """
        file_obj.write("  Extensions:\n")
        if extensions.get('mpls'):
            file_obj.write("    MPLS Labels:\n")
            for mpls in extensions['mpls']:
                file_obj.write(f"      Label={mpls['label']}, TC={mpls['tc']}, ")
                file_obj.write(f"S={mpls['s']}, TTL={mpls['ttl']}\n")

        if extensions.get('other'):
            file_obj.write("    Other Extensions:\n")
            for ext in extensions['other']:
                file_obj.write(f"      Type={ext['type']}, Length={ext['length']}\n")




    def batch_trace(self, input_file: str, options: Dict, output_format: str = "json") -> Dict[str, Dict]:
        all_results = {}

        try:
            targets = self.read_targets(input_file)
            print(f"Found {len(targets)} targets to trace")

            max_workers = 100

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_target = {
                    executor.submit(
                        self._process_single_target,
                        target,
                        options,
                        output_format
                    ): target
                    for i, target in enumerate(targets)
                }

                # 按完成顺序处理结果
                for future in as_completed(future_to_target):
                    target = future_to_target[future]
                    # 获取结果（内部已处理异常）
                    _, result = future.result()
                    all_results[target] = result
        except Exception as e:
            print(f"Batch tracing failed: {str(e)}")
            raise
        return all_results

    def _process_single_target(self, target: str, options: Dict, output_format: str) -> tuple:
        try:
            results = self.process_target(target, options)
            self.save_results(target, results, output_format)
            print(f"Completed tracing to {target}")
            return (target, results)
        except Exception as e:
            print(f"Failed to trace {target}: {str(e)}")
            return (target, {"error": str(e)})

def Handler_run(options:dict, input_file:str, output_format="json", output_dir="traceroute_results"):
    handler = TracerouteHandler(output_dir=output_dir)
    all_results = handler.batch_trace(input_file, options, output_format=output_format)
    print("\nBatch tracing completed. Results saved to:", handler.output_dir)


# 使用示例
if __name__ == "__main__":
    # 示例选项 (对应traceroute命令行参数)
    options = {
        "probe_sequence":["udp", "tcp", "icmp"],
        "max_hops": 30,  # 最大跳数
        "wait": 2000,  # 等待时间(ms)
        "no_resolve": True,  # 解析主机名
        "extensions": False  # 记录扩展信息
    }
    # 处理输入文件
    dir = '/Users/mac/Documents/GitHub/Tracerouter/targets-2.txt'
    input_file = dir # 或 targets.csv
    Handler_run(options, input_file, output_format="json")



