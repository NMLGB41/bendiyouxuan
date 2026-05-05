import asyncio
import time
import json
import os
import sys
import re
import requests
import ssl
import subprocess
from typing import List, Dict

# ================= 核心运行参数 =================
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
OUTPUT_FILE = "ip.txt"

MAX_CONCURRENT_TCP = 50       
MAX_CONCURRENT_SPEED = 2      
TCP_TIMEOUT = 3.0             
SPEED_TIMEOUT = 5.0           

CN_TO_CODE = {
    "美国": "US", "日本": "JP", "香港": "HK", "新加坡": "SG",
    "韩国": "KR", "台湾": "TW", "英国": "GB", "德国": "DE",
    "加拿大": "CA", "澳大利亚": "AU", "法国": "FR", "荷兰": "NL"
}

# ================= 节点解析、过滤与同步模块 =================

def extract_country_code(tag: str) -> str:
    if not tag: return ""
    tag_upper = tag.upper()
    match = re.search(r'\b([A-Z]{2})\b', tag_upper)
    if match: return match.group(1)
    for cn_name, code in CN_TO_CODE.items():
        if cn_name in tag: return code
    return ""

def load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        print(f"❌ 未找到 {CONFIG_FILE}")
        sys.exit(1)
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_and_filter_sources(cfg: dict) -> List[str]:
    filter_enabled = cfg.get("FILTER_COUNTRIES_ENABLED", False)
    allowed_countries = set([c.upper() for c in cfg.get("ALLOWED_COUNTRIES", ["US"])])
    sources = cfg.get("ADDITIONAL_SOURCES", [])
    
    if filter_enabled:
        print(f"🌍 启用了国家过滤: {', '.join(allowed_countries)}")
    
    raw_nodes = set()
    print(f"🔄 开始从 {len(sources)} 个数据源拉取节点...")
    
    for source in sources:
        if not source.get("enabled", True) or not source.get("url"): continue
        url = source.get("url")
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                found = re.findall(r"(\d+\.\d+\.\d+\.\d+:\d+)(?:#([^,\s]+))?", resp.text)
                for ip_port, tag in found:
                    if filter_enabled:
                        code = extract_country_code(tag)
                        if not code or code not in allowed_countries: continue
                    raw_nodes.add(ip_port)
                print(f"  ✅ 成功处理: {url}")
        except Exception as e:
            print(f"  ❌ 拉取失败: {url} ({e})")
            
    final_list = list(raw_nodes)
    print(f"\n🎯 过滤完毕，共有 {len(final_list)} 个节点进入测试。")
    return final_list

def git_push_result(cfg: dict):
    """将结果同步到 GitHub"""
    if not cfg.get("GITHUB_SYNC_ENABLED", False):
        return

    token = cfg.get("GITHUB_TOKEN")
    repo = cfg.get("GITHUB_REPO")
    branch = cfg.get("GITHUB_BRANCH", "main")

    if not token or not repo or token.startswith("你的"):
        print("⚠️ 未配置有效 GitHub Token 或 Repo，跳过同步。")
        return

    print("\n📤 正在同步结果到 GitHub...")
    # 构造带 Token 的远程地址以实现免密推送
    remote_url = f"https://{token}@{repo.replace('https://', '').replace('http://', '')}"
    
    try:
        subprocess.run(["git", "add", OUTPUT_FILE], check=True)
        commit_msg = f"Auto-update IP list: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        result = subprocess.run(["git", "push", remote_url, f"HEAD:{branch}", "--force"], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("🚀 同步成功！仓库已更新。")
        else:
            print(f"❌ 推送失败: {result.stderr}")
    except Exception as e:
        print(f"❌ Git 操作异常: {e}")

# ================= 异步核心引擎 =================

class AsyncCFOptimizer:
    async def _tcp_ping(self, ip: str, port: int, semaphore: asyncio.Semaphore) -> Dict:
        async with semaphore:
            start = time.perf_counter()
            try:
                conn = asyncio.open_connection(ip, port)
                _, writer = await asyncio.wait_for(conn, timeout=TCP_TIMEOUT)
                writer.close()
                await writer.wait_closed()
                latency = (time.perf_counter() - start) * 1000
                return {"ip": ip, "port": port, "latency": latency, "status": "ok"}
            except Exception:
                return {"ip": ip, "port": port, "latency": float('inf'), "status": "fail"}

    async def _speed_test(self, ip: str, port: int) -> float:
        """原生 TLS/SNI 注入底层测速"""
        start = time.perf_counter()
        try:
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
            
            conn = asyncio.open_connection(ip, port, ssl=ssl_ctx, server_hostname="speed.cloudflare.com")
            reader, writer = await asyncio.wait_for(conn, timeout=SPEED_TIMEOUT)
            
            req = (f"GET /__down?bytes=1048576 HTTP/1.1\r\nHost: speed.cloudflare.com\r\nConnection: close\r\n\r\n")
            writer.write(req.encode('utf-8'))
            await writer.drain()
            
            total_bytes = 0
            while True:
                chunk = await asyncio.wait_for(reader.read(8192), timeout=SPEED_TIMEOUT)
                if not chunk: break
                total_bytes += len(chunk)
                
            writer.close()
            await writer.wait_closed()
            
            duration = time.perf_counter() - start
            if total_bytes > 500000:
                return round((total_bytes * 8) / (duration * 1024 * 1024), 2)
        except Exception: 
            pass
        return 0.0

    async def execute(self, raw_nodes: List[str], cfg: dict):
        if not raw_nodes: return
        
        tcp_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TCP)
        tasks = [self._tcp_ping(n.split(":")[0], int(n.split(":")[1]), tcp_semaphore) for n in raw_nodes if ":" in n]
        
        print(f"📡 探测 TCP 延迟...")
        tcp_results = await asyncio.gather(*tasks)
        valid_nodes = sorted([r for r in tcp_results if r["status"] == "ok"], key=lambda x: x["latency"])
        candidates = valid_nodes[:30]
        
        print(f"✅ 选出 {len(candidates)} 个节点进行测速...")
        speed_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SPEED)
        
        async def bounded_test(item):
            async with speed_semaphore:
                speed = await self._speed_test(item["ip"], item["port"])
                if speed > 0:
                    print(f"  ➡️ {item['ip']:<15} | {item['latency']:>6.2f}ms | {speed:>5.2f} Mbps")
                    return {"node": f"{item['ip']}:{item['port']}", "latency": item["latency"], "speed": speed}
                return None

        results = await asyncio.gather(*[bounded_test(i) for i in candidates])
        final_results = sorted([r for r in results if r], key=lambda x: x["speed"], reverse=True)

        print("\n🏆 Top 10 优选结果:")
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            for i, res in enumerate(final_results[:10], 1):
                line = f"{res['node']}"
                print(f"{i:02d}. {line:<20} | {res['latency']:>6.2f}ms | {res['speed']:>5.2f} Mbps")
                f.write(f"{line}\n")
        
        git_push_result(cfg)

# ================= 启动 =================
def main():
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    cfg = load_config()
    nodes = load_and_filter_sources(cfg)
    if nodes:
        optimizer = AsyncCFOptimizer()
        asyncio.run(optimizer.execute(nodes, cfg))

if __name__ == "__main__":
    main()