import argparse
import os
import re
import sys



class FileName:
    filename = ''
    default_filename = None

    def __init__(self):
        parser = argparse.ArgumentParser(description="从traceroute JSON提取IP并查询地理位置")
        parser.add_argument("filepath_name", help="用于识别traceroute JSON文件的域名")
        args = parser.parse_args()
        self.filename = args.filepath_name if args.filepath_name else None
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        self.default_filename = os.path.join(project_root, "Traceroute_Demo", "test_target_normal.txt")



    def write_filename(self):
        url_pattern = re.compile(
            r'^'
            r'(?!file://)'  # 排除file://协议
            r'(?![/\\])'  # 排除以/或\开头
            r'(?!\w:[/\\])'  # 排除Windows路径如C:\
            r'(https?://)?'
            r'(www\.)?'
            r'([a-zA-Z0-9-]+\.)+'
            r'[a-zA-Z]{2,}'
            r'(:\d+)?'
            r'(/[^\s?#]*)?'
            r'(\?[^\s#]*)?'
            r'(#[^\s]*)?'
            r'$',
            re.IGNORECASE
        )
        # test
        # self.filename = self.default_filename

        # 检测 self.filename 是否是文件路径
        if not url_pattern.match(self.filename):
            # 如果是文件路径，则创建 filename.txt 文件并写入文件路径
            if not os.path.isfile(self.filename):
                print(f"警告: 文件 {self.filename} 不存在")
                
                sys.exit(1)
            with open('filename.txt', 'w') as f:
                f.write(self.filename)
            print(f"已创建 filename.txt 文件，内容为：{self.filename}")
        else:
            # 如果是网址，则不创建文件
            print(f"parseargs 输入{self.filename} 是一个网址，不创建 filename.txt 文件")


if __name__ == "__main__":
    fn = FileName()
    fn.write_filename()

