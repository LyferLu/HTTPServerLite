#!/usr/bin/env python3
import os
import io
import urllib
from http.server import SimpleHTTPRequestHandler, HTTPServer
import sys
from email.parser import BytesParser
from email.policy import default
import shutil
import argparse

class FileServerHandler(SimpleHTTPRequestHandler):

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed_path.query)

        # 处理删除文件的请求（?delete=filename）
        if 'delete' in query:
            filename = query['delete'][0]
            filename = os.path.basename(filename)  # 确保安全
            file_path = os.path.join(os.getcwd(), filename)
            if os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                    print(f"删除文件: {file_path}")
                except Exception as e:
                    print(f"删除文件失败: {e}")
                    self.send_error(500, "删除文件失败")
                    return
            else:
                self.send_error(404, "文件未找到")
                return
            # 重定向回根目录
            self.send_response(303)
            self.send_header('Location', '/')
            self.end_headers()
            return

        # 处理预览文件的请求（?preview=filename）
        if 'preview' in query:
            filename = query['preview'][0]
            filename = os.path.basename(filename)
            file_path = os.path.join(os.getcwd(), filename)
            if not os.path.isfile(file_path):
                self.send_error(404, "文件未找到")
                return

            # 根据扩展名判断文件类型
            ext = os.path.splitext(filename)[1].lower()
            preview_html = self.generate_preview_page(filename, ext)
            preview_bytes = preview_html.encode('utf-8')

            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(preview_bytes)))
            self.end_headers()
            self.wfile.write(preview_bytes)
            return

        # 无特殊参数，则正常列目录或返回文件
        super().do_GET()

    def generate_preview_page(self, filename, ext):
        # 简单判断文件类型
        if ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
            content_tag = f'<img src="{urllib.parse.quote(filename)}" style="max-width:90%;height:auto;">'
        elif ext in ['.mp4', '.webm', '.ogg', '.avi', '.mov', '.flv', '.mkv', '.rmvb', '.wmv', '.mpg', '.mpeg', '.m4v', '.3gp', '.f4v', '.rm', '.ts', '.swf', '.vob', '.asf', '.divx', '.xvid', '.mpv', '.m2v']:
            content_tag = f'<video src="{urllib.parse.quote(filename)}" controls style="max-width:90%;height:auto;"></video>'
        elif ext in ['.mp3', '.wav', '.ogg', '.flac', '.ape', '.wma', '.aac', '.m4a', '.aiff', '.au', '.mid', '.midi', '.ra', '.ram', '.rm', '.vqf', '.amr', '.cda']:
            content_tag = f'<audio src="{urllib.parse.quote(filename)}" controls></audio>'
        else:
            # 不支持的文件类型，显示为下载链接
            content_tag = f'<p>无法预览此文件类型，请下载查看: <a href="{urllib.parse.quote(filename)}" download>下载</a></p>'

        html = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>预览 {filename}</title>
</head>
<body>
<h2>预览：{filename}</h2>
<hr>
{content_tag}
<hr>
<p><a href="/">返回文件列表</a></p>
</body>
</html>
'''
        return html

    def list_directory(self, path):
        try:
            list_dir = os.listdir(path)
        except OSError:
            self.send_error(404, "无法列出目录")
            return None
        list_dir.sort(key=lambda a: a.lower())

        f = io.BytesIO()
        html = []
        html.append('<!DOCTYPE html>\n')
        html.append("<html>\n<head>\n")
        html.append('<meta charset="utf-8">')
        html.append("<title>文件列表</title>\n</head>\n<body>\n")
        html.append("<h2>当前目录: %s</h2>\n" % os.path.basename(os.getcwd()))
        html.append("<hr>\n")

        # 文件上传表单 (使用 AJAX 和进度条)
        html.append('''
<form id="uploadForm" enctype="multipart/form-data" method="post">
  <input name="file" type="file" multiple />
  <input type="submit" value="上传"/>
</form>
<progress id="uploadProgress" value="0" max="100" style="width:300px; display:none;"></progress>
<script>
document.getElementById('uploadForm').addEventListener('submit', function(e) {
    e.preventDefault();
    var form = e.target;
    var files = form.querySelector('input[type="file"]').files;
    if (files.length === 0) {
        alert("请选择文件后再上传");
        return;
    }

    var formData = new FormData(form);
    var xhr = new XMLHttpRequest();
    var progressBar = document.getElementById('uploadProgress');
    progressBar.style.display = 'block';

    var currentPercent = 0;  // 当前显示的进度条百分比
    var targetPercent = 0;   // 实际需要显示的目标百分比（来自上传进度）
    
    // 每100毫秒将 currentPercent 慢慢靠近 targetPercent
    var intervalId = setInterval(function() {
        if (currentPercent < targetPercent) {
            currentPercent++;
            progressBar.value = currentPercent;
        }
    }, 100);

    xhr.upload.onprogress = function(e) {
        if (e.lengthComputable) {
            var realPercent = Math.round((e.loaded / e.total) * 100);
            // 在文件上传完成前最多显示到96%
            if (realPercent >= 100) {
                realPercent = 96;
            }
            targetPercent = realPercent;
        }
    };

    xhr.onload = function() {
        // 上传完成后，马上把目标值设为100%
        targetPercent = 100;
        // 稍等片刻等待进度条跑到100%，再刷新页面
        intervalId = setInterval(function() {
            if (currentPercent < targetPercent) {
                currentPercent++;
                progressBar.value = currentPercent;
            }
        }, 1);
        setTimeout(function() {
            clearInterval(intervalId);
            window.location.reload();
        }, 1000);  // 这里延迟2秒刷新，你可根据需要调整
    };

    xhr.onerror = function() {
        alert("上传出错，请稍后重试。");
        clearInterval(intervalId);
    };

    xhr.open('POST', '/', true);
    xhr.send(formData);
});
</script>

''')

        html.append("<hr>\n")

        # 文件列表
        html.append('<ul>\n')
        for name in list_dir:
            fullname = os.path.join(path, name)
            display_name = name
            linkname = urllib.parse.quote(name)
            if os.path.isdir(fullname):
                html.append('<li><b><a href="%s/">%s/</a></b></li>\n' % (linkname, display_name))
            else:
                # 添加预览链接 '?preview=filename'
                html.append('<li><a href="?preview=%s">%s</a> ' % (linkname, display_name))
                # 下载和删除链接
                html.append('[<a href="%s" download>下载</a>]' % linkname)
                html.append(' [<a href="?delete=%s" onclick="return confirm(\'确认删除此文件?\');">删除</a>]' % linkname)
                html.append('</li>\n')
        html.append('</ul>\n')

        html.append("<hr>\n</body>\n</html>\n")

        html_bytes = "".join(html).encode('utf-8')
        f.write(html_bytes)
        f.seek(0)

        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html_bytes)))
        self.end_headers()
        return f

    def do_POST(self):
        # 处理文件上传
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            self.send_error(400, "未检测到上传文件")
            return
        body = self.rfile.read(content_length)

        # 使用 email 库解析 multipart/form-data
        headers = f"Content-Type: {self.headers['Content-Type']}\r\nMIME-Version: 1.0\r\n\r\n"
        try:
            msg = BytesParser(policy=default).parsebytes(headers.encode('utf-8') + body)
        except Exception as e:
            self.send_error(400, f"解析上传文件失败: {e}")
            return

        # 多文件上传
        if msg.is_multipart():
            for part in msg.iter_parts():
                filename = part.get_filename()
                if filename:
                    filename = os.path.basename(filename)
                    file_path = os.path.join(os.getcwd(), filename)
                    file_data = part.get_payload(decode=True)
                    if file_data:
                        try:
                            with open(file_path, 'wb') as f:
                                f.write(file_data)
                            print(f"上传文件: {file_path}")
                        except Exception as e:
                            print(f"上传文件失败: {e}")
                            self.send_error(500, f"上传文件失败: {e}")
                            return

        # 上传完成后返回303重定向至根目录
        self.send_response(303)
        self.send_header('Location', '/')
        self.end_headers()

def run(server_class=HTTPServer, handler_class=FileServerHandler, port=8000, directory=None):
    server_address = ('', port)
    if directory:
        # 验证目录是否存在
        if not os.path.exists(directory):
            print(f"错误: 指定的目录 '{directory}' 不存在。")
            sys.exit(1)
        if not os.path.isdir(directory):
            print(f"错误: 指定的路径 '{directory}' 不是一个目录。")
            sys.exit(1)
        # 切换到指定目录
        os.chdir(directory)
    else:
        # 默认使用脚本所在目录
        directory = os.getcwd()

    httpd = server_class(server_address, handler_class)
    print(f"Serving HTTP on port {port} from directory '{directory}'...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        httpd.server_close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="简易文件服务器，支持多文件上传、下载、删除、预览和上传进度显示功能。")
    parser.add_argument('--port', type=int, default=8000, help='指定服务器端口，默认是8000')
    parser.add_argument('--dir', type=str, default=None, help='指定要共享的目录，默认是脚本所在目录')
    args = parser.parse_args()

    run(port=args.port, directory=args.dir)
