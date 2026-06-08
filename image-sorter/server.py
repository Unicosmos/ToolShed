#!/usr/bin/env python3
import os
import shutil
from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
from urllib.parse import urlparse, parse_qs

# 根目录（提供 index.html）
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
# 图片目录（默认当前目录）
current_base_dir = ROOT_DIR
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")

current_port = 8081  # 默认端口，启动时覆盖

def load_pending():
    pending_file = os.path.join(ROOT_DIR, f'pending_moves_{current_port}.json')
    if os.path.exists(pending_file):
        try:
            with open(pending_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_pending(moves):
    pending_file = os.path.join(ROOT_DIR, f'pending_moves_{current_port}.json')
    with open(pending_file, 'w', encoding='utf-8') as f:
        json.dump(moves, f, ensure_ascii=False)


class ImageHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT_DIR, **kwargs)

    def do_GET(self):
        parsed_path = urlparse(self.path)

        # 检查是否是图片文件请求
        if parsed_path.path.lower().endswith(IMAGE_EXTENSIONS):
            # 从 current_base_dir 提供图片，先解码 URL
            from urllib.parse import unquote

            image_path = os.path.join(
                current_base_dir, unquote(parsed_path.path.lstrip("/"))
            )
            if os.path.exists(image_path):
                self.send_response(200)
                ext = os.path.splitext(image_path)[1].lower()
                if ext in [".jpg", ".jpeg"]:
                    self.send_header("Content-type", "image/jpeg")
                elif ext == ".png":
                    self.send_header("Content-type", "image/png")
                elif ext == ".gif":
                    self.send_header("Content-type", "image/gif")
                elif ext == ".webp":
                    self.send_header("Content-type", "image/webp")
                else:
                    self.send_header("Content-type", "image/bmp")
                self.end_headers()
                with open(image_path, "rb") as f:
                    self.wfile.write(f.read())
                return

        if parsed_path.path == "/api/folders":
            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            try:
                folders = []
                for d in os.listdir(current_base_dir):
                    full_path = os.path.join(current_base_dir, d)
                    if os.path.isdir(full_path) and not d.startswith("."):
                        count = 0
                        for f in os.listdir(full_path):
                            if f.lower().endswith(IMAGE_EXTENSIONS):
                                count += 1
                        folders.append({"name": d, "count": count})
            except:
                folders = []
            self.wfile.write(json.dumps(folders, ensure_ascii=False).encode("utf-8"))

        elif parsed_path.path == "/api/get_base_dir":
            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                json.dumps({"base_dir": current_base_dir}, ensure_ascii=False).encode(
                    "utf-8"
                )
            )

        elif parsed_path.path == "/api/pending/list":
            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(load_pending(), ensure_ascii=False).encode("utf-8"))

        elif parsed_path.path == "/api/images":
            query = parse_qs(parsed_path.query)
            folder = query.get("folder", [""])[0]
            page = int(query.get("page", [1])[0])
            per_page = int(query.get("per_page", [50])[0])

            folder_path = os.path.join(current_base_dir, folder)
            if not os.path.isdir(folder_path):
                self.send_response(404)
                self.end_headers()
                return

            images = []
            for f in os.listdir(folder_path):
                if f.lower().endswith(IMAGE_EXTENSIONS):
                    images.append(f)
            images.sort()

            total = len(images)
            start = (page - 1) * per_page
            end = start + per_page
            paginated_images = images[start:end]

            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {
                        "images": paginated_images,
                        "total": total,
                        "page": page,
                        "per_page": per_page,
                        "total_pages": (total + per_page - 1) // per_page,
                    },
                    ensure_ascii=False,
                ).encode("utf-8")
            )

        else:
            super().do_GET()

    def do_POST(self):
        parsed_path = urlparse(self.path)

        if parsed_path.path == "/api/set_base_dir":
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode("utf-8"))

            new_dir = data.get("base_dir", "")
            if os.path.isdir(new_dir):
                global current_base_dir
                current_base_dir = new_dir
                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    json.dumps(
                        {"success": True, "base_dir": current_base_dir},
                        ensure_ascii=False,
                    ).encode("utf-8")
                )
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(
                    json.dumps(
                        {"success": False, "error": "目录不存在"}, ensure_ascii=False
                    ).encode("utf-8")
                )

        elif parsed_path.path == "/api/move":
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode("utf-8"))

            src_folder = data.get("src_folder")
            filename = data.get("filename")

            src_path = os.path.join(current_base_dir, src_folder, filename)
            dst_dir = os.path.join(current_base_dir, src_folder, "others")

            if not os.path.exists(dst_dir):
                os.makedirs(dst_dir)

            dst_path = os.path.join(dst_dir, filename)

            if os.path.exists(src_path):
                shutil.move(src_path, dst_path)
                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    json.dumps({"success": True}, ensure_ascii=False).encode("utf-8")
                )
            else:
                self.send_response(404)
                self.end_headers()

        elif parsed_path.path == "/api/pending":
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode("utf-8"))
            action = data.get("action")

            if action == "add":
                moves = load_pending()
                new_move = {"folder": data["folder"], "file": data["file"]}
                if new_move not in moves:
                    moves.append(new_move)
                    save_pending(moves)
                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    json.dumps({"success": True, "count": len(moves)}, ensure_ascii=False).encode("utf-8")
                )

            elif action == "execute":
                moves = load_pending()
                success = 0
                failed = []
                success_items = []
                
                target_base_dir = os.path.join(ROOT_DIR, "others")
                
                for m in moves:
                    folder = m["folder"]
                    filename = m["file"]
                    
                    src_path = os.path.join(current_base_dir, folder, filename)
                    dst_dir = os.path.join(target_base_dir, folder)
                    dst_path = os.path.join(dst_dir, filename)
                    
                    try:
                        if os.path.exists(src_path):
                            os.makedirs(dst_dir, exist_ok=True)
                            
                            if os.path.exists(dst_path):
                                base, ext = os.path.splitext(filename)
                                counter = 1
                                while os.path.exists(os.path.join(dst_dir, f"{base}_{counter}{ext}")):
                                    counter += 1
                                dst_path = os.path.join(dst_dir, f"{base}_{counter}{ext}")
                            
                            shutil.move(src_path, dst_path)
                            success += 1
                            success_items.append(m)
                        else:
                            failed.append(m["file"])
                    except Exception as e:
                        failed.append(f"{m['file']} ({str(e)})")
                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    json.dumps({"success": True, "moved": success, "failed": failed, "success_items": success_items}, ensure_ascii=False).encode("utf-8")
                )

            elif action == "clear":
                save_pending([])
                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    json.dumps({"success": True}, ensure_ascii=False).encode("utf-8")
                )

            elif action == "remove":
                moves = load_pending()
                moves = [m for m in moves if not (m["folder"] == data["folder"] and m["file"] == data["file"])]
                save_pending(moves)
                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    json.dumps({"success": True, "count": len(moves)}, ensure_ascii=False).encode("utf-8")
                )

            elif action == "remove_batch":
                moves = load_pending()
                remove_items = data.get("items", [])
                remaining = [m for m in moves if not any(r["folder"] == m["folder"] and r["file"] == m["file"] for r in remove_items)]
                save_pending(remaining)
                self.send_response(200)
                self.send_header("Content-type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    json.dumps({"success": True, "remaining": len(remaining)}, ensure_ascii=False).encode("utf-8")
                )

        elif parsed_path.path == "/api/move_batch":
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode("utf-8"))

            src_folder = data.get("src_folder")
            filenames = data.get("filenames", [])

            dst_dir = os.path.join(current_base_dir, src_folder, "others")
            if not os.path.exists(dst_dir):
                os.makedirs(dst_dir)

            moved = 0
            for filename in filenames:
                src_path = os.path.join(current_base_dir, src_folder, filename)
                dst_path = os.path.join(dst_dir, filename)
                if os.path.exists(src_path):
                    shutil.move(src_path, dst_path)
                    moved += 1

            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {"success": True, "moved": moved}, ensure_ascii=False
                ).encode("utf-8")
            )

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()


def run_server(port=8000):
    global current_port
    current_port = port
    
    server_address = ("", port)
    httpd = HTTPServer(server_address, ImageHandler)
    print(f"Server running at http://localhost:{port}")
    print(f"Current base dir: {current_base_dir}")
    print(f"Pending moves file: pending_moves_{port}.json")
    try:
        print(
            f'Available folders: {[d for d in os.listdir(current_base_dir) if os.path.isdir(os.path.join(current_base_dir, d)) and not d.startswith(".")]}'
        )
    except:
        print("No folders found or base dir not set")
    httpd.serve_forever()


if __name__ == "__main__":
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8081
    run_server(port=port)
