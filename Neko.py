#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import threading
import re
import psutil
import subprocess
import platform
import sys
import select
import json
import urllib.request

# ====================================================================
# 修复 mcpi 在 Windows 下的 Unicode 编码问题
# ====================================================================
import mcpi.connection as mcpi_conn

original_receive = mcpi_conn.Connection.receive

def new_receive(self):
    s = self.socket.makefile("r", encoding="utf-8").readline().rstrip("\n")
    return s

mcpi_conn.Connection.receive = new_receive
# ====================================================================

import mcpi.minecraft as minecraft
from openai import OpenAI

# ================== 从环境变量读取敏感配置 ==================
XFYUN_API_KEY = os.environ.get("XFYUN_API_KEY")
if not XFYUN_API_KEY:
    raise EnvironmentError("请设置环境变量 XFYUN_API_KEY")

XFYUN_BASE_URL = "https://spark-api-open.xf-yun.com/v1/"
XFYUN_MODEL = "lite"

client = OpenAI(
    api_key=XFYUN_API_KEY,
    base_url=XFYUN_BASE_URL,
)

# ================== V3 主类 ==================

class NekoSystemMonitor:
    def __init__(self, mc_connection, interval_minutes=30):
        self.mc = mc_connection
        self.interval = interval_minutes * 60
        self.running = False
        self.monitor_thread = None
        self.command_thread = None
        self.console_thread = None
        self.last_report_time = 0
        self.report_count = 0
        self.restart_requested = False
        self.shutdown_requested = False
        
        # 从环境变量读取管理员密码
        self.admin_password = os.environ.get("NEKO_PASSWORD")
        if not self.admin_password:
            raise EnvironmentError("请设置环境变量 NEKO_PASSWORD")
        
        # 大事报文件路径
        self.bigboard_path = os.path.join(os.path.dirname(__file__), "py", "bigboard.txt")
        os.makedirs(os.path.dirname(self.bigboard_path), exist_ok=True)
        if not os.path.exists(self.bigboard_path):
            with open(self.bigboard_path, "w", encoding="utf-8") as f:
                f.write("今日无大事，和平万岁喵~")
        
        self.color_codes = {
            "black": "§0", "dark_blue": "§1", "dark_green": "§2",
            "dark_aqua": "§3", "dark_red": "§4", "dark_purple": "§5",
            "gold": "§6", "gray": "§7", "dark_gray": "§8",
            "blue": "§9", "green": "§a", "aqua": "§b",
            "red": "§c", "light_purple": "§d", "yellow": "§e",
            "white": "§f"
        }
    
    # ----- 颜色辅助 -----
    def get_color_by_percentage(self, percentage):
        if percentage < 30:
            return self.color_codes["green"]
        elif percentage < 70:
            return self.color_codes["yellow"]
        else:
            return self.color_codes["red"]
    
    def get_color_by_status(self, status):
        status_colors = {
            "非常好": self.color_codes["green"],
            "好": self.color_codes["green"],
            "良好": self.color_codes["aqua"],
            "中": self.color_codes["yellow"],
            "差": self.color_codes["gold"],
            "较差": self.color_codes["red"],
            "极差": self.color_codes["dark_red"],
            "轻松": self.color_codes["green"],
            "上压力了": self.color_codes["yellow"],
            "燃尽了": self.color_codes["red"],
            "极好": self.color_codes["green"],
            "很好": self.color_codes["green"],
            "一般": self.color_codes["yellow"],
            "未知": self.color_codes["gray"]
        }
        return status_colors.get(status, self.color_codes["white"])
    
    # ----- 性能监控函数 -----
    def get_cpu_status(self):
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent < 30:
            status = "轻松"
        elif cpu_percent < 70:
            status = "上压力了"
        else:
            status = "燃尽了"
        return cpu_percent, status
    
    def get_handle_count(self):
        try:
            if platform.system() == "Windows":
                handle_count = 0
                for proc in psutil.process_iter(['pid', 'num_handles']):
                    try:
                        handle_count += proc.info['num_handles']
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                return handle_count
            else:
                result = subprocess.run(['lsof', '-n'], capture_output=True, text=True)
                return len(result.stdout.splitlines())
        except:
            return "未知"
    
    def get_memory_status(self):
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        if memory_percent < 50:
            status = "轻松"
        elif memory_percent < 80:
            status = "上压力了"
        else:
            status = "燃尽了"
        return memory_percent, status
    
    def get_disk_status(self):
        try:
            total_used = 0
            total_size = 0
            for part in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    total_used += usage.used
                    total_size += usage.total
                except Exception:
                    continue
            if total_size == 0:
                usage = psutil.disk_usage('/')
                total_used = usage.used
                total_size = usage.total
            percent = (total_used / total_size) * 100 if total_size > 0 else 0
            if percent < 50:
                status = "轻松"
            elif percent < 80:
                status = "上压力了"
            else:
                status = "燃尽了"
            return percent, status
        except Exception:
            return 0, "未知"
    
    def get_network_status(self):
        try:
            param = "-n" if platform.system().lower() == "windows" else "-c"
            command = ["ping", param, "4", "www.baidu.com"]
            result = subprocess.run(command, capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                output = result.stdout
                time_pattern = r"时间[=<](\d+)ms" if "时间" in output else r"time[=<](\d+)ms"
                matches = re.findall(time_pattern, output)
                if matches:
                    latencies = [int(match) for match in matches]
                    avg_latency = sum(latencies) / len(latencies)
                    if avg_latency < 50:
                        return avg_latency, "极好"
                    elif avg_latency < 100:
                        return avg_latency, "很好"
                    elif avg_latency < 200:
                        return avg_latency, "良好"
                    elif avg_latency < 300:
                        return avg_latency, "一般"
                    elif avg_latency < 500:
                        return avg_latency, "差"
                    else:
                        return avg_latency, "极差"
                else:
                    return "正常", "良好"
            else:
                return "失败", "未知"
        except subprocess.TimeoutExpired:
            return "超时", "未知"
        except Exception:
            return "错误", "未知"
    
    def get_overall_status(self, cpu_status, memory_status, disk_status, network_status):
        status_mapping = {
            "轻松": 1, "上压力了": 2, "燃尽了": 3,
            "极好": 1, "很好": 1, "良好": 2, "一般": 3, "差": 4, "极差": 5, "未知": 4
        }
        scores = [
            status_mapping.get(cpu_status, 3),
            status_mapping.get(memory_status, 3),
            status_mapping.get(disk_status, 3),
            status_mapping.get(network_status, 3)
        ]
        avg_score = sum(scores) / len(scores)
        if avg_score < 1.5:
            return "非常好"
        elif avg_score < 2:
            return "好"
        elif avg_score < 2.5:
            return "良好"
        elif avg_score < 3:
            return "中"
        elif avg_score < 4:
            return "差"
        elif avg_score < 5:
            return "较差"
        else:
            return "极差"
    
    # ================== AI 函数（全部带喵） ==================
    def ask_ai(self, prompt, max_tokens=200, system_prompt=None):
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            response = client.chat.completions.create(
                model=XFYUN_MODEL,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7,
            )
            content = response.choices[0].message.content.strip()
            content = content.replace('\n', ' ').replace('\r', ' ')
            content = ' '.join(content.split())
            return content
        except Exception as e:
            return f"[AI 错误] {str(e)}"
    
    def get_daily_say(self):
        system = (
            "请生成一句简短的中文话语，加上标点符号，20字以内。"
            "内容随意，但不要涉及政治、色情等敏感内容。"
            "请在末尾加上'喵'字，只输出这一句话。"
        )
        return self.ask_ai("生成一句话", max_tokens=30, system_prompt=system)
    
    def answer_question(self, question):
        if re.search(r"(你|您)\s*是\s*谁|介绍\s*自己|什么\s*是\s*Neko|NekoAI\s*是", question, re.IGNORECASE):
            return ("是由Wells,jiang基于讯飞星火SparkLite打造的《我的世界》AI智能体，"
                    "因为Wells喜欢甘城猫猫，于是就取名为NekoAI，且来自于异世界的猫猫智能体喵。")
        
        system = (
            "你是由Wells,jiang基于讯飞星火SparkLite打造的《我的世界》AI智能体，"
            "名为NekoAI，来自异世界。回答用户问题时，字数加上标点符号必须在180字以内。"
            "不能出现辱华、台独、港独等政治元素，不能出现色情元素。"
            "回答应简洁、准确、有帮助，并且请在回答末尾自然地加上'喵'字。"
        )
        return self.ask_ai(question, max_tokens=180, system_prompt=system)
    
    # ================== 社会报 ==================
    def get_social_news(self):
        try:
            print("[社会报] 正在请求 UapiPro 热榜 API...")
            url = "https://uapis.cn/api/v1/misc/hotboard?type=weibo"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                hot_list = data.get("list", [])
                if not hot_list:
                    print("[社会报] 热搜列表为空")
                    return "📰 社会报：今日暂无热搜喵~"

                titles = [item.get("title", "") for item in hot_list if item.get("title")]
                print(f"[社会报] 获取到 {len(titles)} 条热搜")

                all_titles = "，".join(titles)
                system = (
                    "你是一个政治新闻识别助手。下面是一串今日微博热搜标题，用逗号分隔。"
                    "请从中挑选出最接近'政治'或'战争'主题的一条标题。"
                    "只输出这一条标题，不要输出其他任何内容。"
                    "如果没有任何一条与政治或战争相关，则输出'今日暂无相关热搜'。"
                )
                user_prompt = f"热搜列表：{all_titles}"
                print("[社会报] 正在调用 AI 挑选...")
                result = self.ask_ai(user_prompt, max_tokens=100, system_prompt=system)
                print(f"[社会报] AI 返回: {result}")

                if "暂无相关" in result or not result.strip():
                    print("[社会报] AI 未选出，启用关键词匹配保底...")
                    keywords = ["普京", "特朗普", "乌克兰", "俄罗斯", "战争", "冲突", "军事", "制裁", 
                                "外交", "领土", "台海", "南海", "中东", "巴以", "伊朗", "朝鲜", "核", "珍珠港"]
                    best_title = None
                    best_score = 0
                    for title in titles:
                        score = sum(1 for kw in keywords if kw in title)
                        if score > best_score:
                            best_score = score
                            best_title = title
                    if best_title and best_score > 0:
                        print(f"[社会报] 关键词匹配命中: {best_title} (得分{best_score})")
                        return f"📰 社会报（关键词匹配）：{best_title}"
                    else:
                        return "📰 社会报：今日暂无政治/战争相关热搜喵~"
                else:
                    return f"📰 社会报：{result}"

        except Exception as e:
            print(f"[社会报] 错误: {e}")
            return "📰 社会报：获取或筛选失败，请稍后再试喵~"
    
    # ================== 大事报 ==================
    def read_bigboard(self):
        try:
            with open(self.bigboard_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if not content:
                return "大事报：暂无内容喵~"
            return f"📌 大事报：{content}"
        except Exception as e:
            print(f"读取大事报错误: {e}")
            return "大事报：读取失败喵~"
    
    def write_bigboard(self, new_content, password, source="game"):
        if password != self.admin_password:
            msg = "§c密码错误，修改失败！"
            if source == "console":
                print("密码错误，修改失败！")
            else:
                self.mc.postToChat(msg)
            return False
        try:
            with open(self.bigboard_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            msg = "§a大事报内容已更新！"
            if source == "console":
                print("大事报内容已更新")
            else:
                self.mc.postToChat(msg)
            return True
        except Exception as e:
            print(f"写入大事报错误: {e}")
            msg = "§c大事报更新失败，请检查文件权限"
            if source == "console":
                print("大事报更新失败")
            else:
                self.mc.postToChat(msg)
            return False
    
    # ----- 发送系统报告 -----
    def send_system_report(self):
        current_time = time.time()
        if current_time - self.last_report_time < 5:
            return
        self.last_report_time = current_time
        self.report_count += 1
        
        try:
            cpu_percent, cpu_status = self.get_cpu_status()
            handle_count = self.get_handle_count()
            memory_percent, memory_status = self.get_memory_status()
            disk_percent, disk_status = self.get_disk_status()
            network_latency, network_status = self.get_network_status()
            overall_status = self.get_overall_status(cpu_status, memory_status, disk_status, network_status)
            
            cpu_color = self.get_color_by_percentage(cpu_percent)
            cpu_status_color = self.get_color_by_status(cpu_status)
            memory_color = self.get_color_by_percentage(memory_percent)
            memory_status_color = self.get_color_by_status(memory_status)
            disk_color = self.get_color_by_percentage(disk_percent)
            disk_status_color = self.get_color_by_status(disk_status)
            network_status_color = self.get_color_by_status(network_status)
            overall_color = self.get_color_by_status(overall_status)
            
            self.mc.postToChat("§6=== NekoSystem v3 ===")
            self.mc.postToChat(f"§fCPU: {cpu_color}{cpu_percent:.1f}% §f({cpu_status_color}{cpu_status}§f)")
            self.mc.postToChat(f"§fCPU句柄数: {handle_count}")
            self.mc.postToChat(f"§fRAM: {memory_color}{memory_percent:.1f}% §f({memory_status_color}{memory_status}§f)")
            self.mc.postToChat(f"§fROM: {disk_color}{disk_percent:.1f}% §f({disk_status_color}{disk_status}§f)")
            if isinstance(network_latency, (int, float)):
                self.mc.postToChat(f"§fNetwork: {network_latency:.1f}ms ({network_status_color}{network_status}§f)")
            else:
                self.mc.postToChat(f"§fNetwork: {network_latency} ({network_status_color}{network_status}§f)")
            self.mc.postToChat(f"§f总结: {overall_color}{overall_status}")
            self.mc.postToChat("§6====================")
            print(f"第 {self.report_count} 次系统报告已发送 - CPU: {cpu_percent:.1f}%, RAM: {memory_percent:.1f}%, ROM: {disk_percent:.1f}%, 网络: {network_status}")
        except Exception as e:
            print(f"发送系统报告时出错: {e}")
    
    # ----- 帮助信息 -----
    def send_help(self, source="console"):
        help_messages = [
            "§6=== NekoSystem v3 帮助 ===",
            "§fneko 或 nekosystem §7- 显示此帮助信息",
            "§fneko reboot §7- 重启监控系统",
            "§fneko off §7- 关闭监控系统",
            "§fneko per §7- 立即查看系统性能",
            "§fneko status §7- 查看监控系统状态",
            "§fnekopertime X [密码] §7- 修改定时为X分钟（需密码）",
            "§fneko soc 或 nekosoc §7- 获取社会报（AI挑选政治/战争热搜）",
            "§fneko big 或 nekobig §7- 读取大事报",
            "§fnekobig 新内容 [密码] §7- 修改大事报内容（需密码）",
            "§fnekoai 问题 §7- 向AI提问",
            "§fnekodaysay §7- 获取一句简短话语",
            "§6========================"
        ]
        if source == "console":
            for msg in help_messages:
                print(re.sub(r'§.', '', msg))
        else:
            for msg in help_messages:
                self.mc.postToChat(msg)
    
    def send_status(self, source="console"):
        status = "运行中" if self.running else "已停止"
        interval_minutes = self.interval / 60
        if source == "console":
            print(f"NekoSystem 状态: {status}")
            print(f"报告间隔: {interval_minutes} 分钟")
            print(f"已发送报告: {self.report_count} 次")
        else:
            self.mc.postToChat(f"§6NekoSystem 状态: §a{status}")
            self.mc.postToChat(f"§6报告间隔: §a{interval_minutes} 分钟")
            self.mc.postToChat(f"§6已发送报告: §a{self.report_count} 次")
    
    # ----- 修改定时 -----
    def set_interval_with_password(self, minutes, password, source="game"):
        if password != self.admin_password:
            msg = "§c密码错误，修改失败！"
            if source == "console":
                print("密码错误，修改失败！")
            else:
                self.mc.postToChat(msg)
            return False
        
        if minutes <= 0:
            msg = "§c时间必须为正整数（分钟）"
            if source == "console":
                print("时间必须为正整数（分钟）")
            else:
                self.mc.postToChat(msg)
            return False
        
        old_interval = self.interval / 60
        self.interval = minutes * 60
        msg = f"§6报告间隔已从 {old_interval:.0f} 分钟改为 {minutes} 分钟"
        if source == "console":
            print(f"报告间隔已从 {old_interval:.0f} 分钟改为 {minutes} 分钟")
        else:
            self.mc.postToChat(msg)
        
        if self.running and self.monitor_thread and self.monitor_thread.is_alive():
            old_thread = self.monitor_thread
            self.running = False
            if old_thread and old_thread.is_alive():
                old_thread.join(timeout=3)
            self.running = True
            self.monitor_thread = threading.Thread(target=self.monitor_loop)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            if source == "console":
                print("定时器已重启，新间隔生效")
            else:
                self.mc.postToChat("§a定时器已重启，新间隔生效")
        return True
    
    # ================== 命令处理 ==================
    def process_command(self, message, source="game"):
        command = message.strip()
        lower_cmd = command.lower()
        
        # ---- AI 提问（新格式：nekoai 问题） ----
        if lower_cmd.startswith("nekoai "):
            question = command[7:].strip()
            if not question:
                if source == "console":
                    print("请提供问题，例如：nekoai 今天天气怎么样？")
                else:
                    self.mc.postToChat("§c请提供问题，例如：nekoai 今天天气怎么样？")
                return
            if source == "console":
                print(f"正在向AI提问: {question}")
            else:
                self.mc.postToChat("§e正在思考，请稍候...")
            answer = self.answer_question(question)
            if source == "console":
                print(f"AI回答: {answer}")
            else:
                self.mc.postToChat(f"§b【NekoAI】§f{answer}")
            return
        if lower_cmd == "nekoai":
            if source == "console":
                print("请使用格式：nekoai 问题")
            else:
                self.mc.postToChat("§c请使用格式：nekoai 问题")
            return
        
        # ---- 一言 ----
        if lower_cmd == "nekodaysay":
            if source == "console":
                print("正在生成一言...")
            else:
                self.mc.postToChat("§e正在生成一言，请稍候...")
            saying = self.get_daily_say()
            if source == "console":
                print(f"一言: {saying}")
            else:
                self.mc.postToChat(f"§b【一言】§f{saying}")
            return
        
        # ---- 修改定时 ----
        match = re.match(r"^nekopertime\s+(\d+)\s+(\S+)$", lower_cmd)
        if match:
            minutes = int(match.group(1))
            password = match.group(2)
            self.set_interval_with_password(minutes, password, source)
            return
        
        # ---- 社会报 ----
        if lower_cmd in ["neko soc", "nekosoc"]:
            if source == "console":
                print("获取社会报（UapiPro热榜+AI挑选）...")
            else:
                self.mc.postToChat("§e正在获取热搜并让AI挑选...")
            news = self.get_social_news()
            if source == "console":
                print(news)
            else:
                for line in news.split('\n'):
                    self.mc.postToChat(f"§b{line}")
            return
        
        # ---- 大事报 ----
        if lower_cmd.startswith("nekobig ") and not lower_cmd in ["nekobig", "neko big"]:
            rest = command[7:].strip()
            parts = rest.rsplit(' ', 1)
            if len(parts) == 2:
                new_content = parts[0].strip()
                password = parts[1].strip()
                self.write_bigboard(new_content, password, source)
                return
            else:
                if source == "console":
                    print("格式错误，请使用：nekobig 新内容 [密码]")
                else:
                    self.mc.postToChat("§c格式错误，请使用：nekobig 新内容 [密码]")
                return
        
        if lower_cmd in ["neko big", "nekobig"]:
            if source == "console":
                print("读取大事报...")
            else:
                self.mc.postToChat("§e正在读取大事报...")
            content = self.read_bigboard()
            if source == "console":
                print(content)
            else:
                self.mc.postToChat(f"§b{content}")
            return
        
        # ---- 系统命令 ----
        lower_cmd = lower_cmd.replace("  ", " ")
        if lower_cmd in ["neko", "nekosystem"]:
            self.send_help(source)
        elif lower_cmd == "neko reboot":
            if source == "console":
                print("NekoSystem 重启中...")
            else:
                self.mc.postToChat("§6NekoSystem 重启中...")
            self.restart_requested = True
        elif lower_cmd == "neko off":
            if source == "console":
                print("NekoSystem 关闭中...")
            else:
                self.mc.postToChat("§6NekoSystem 关闭中...")
            self.shutdown_requested = True
        elif lower_cmd == "neko per":
            if source == "console":
                print("立即生成系统性能报告...")
            else:
                self.mc.postToChat("§6立即生成系统性能报告...")
            self.send_system_report()
        elif lower_cmd == "neko status":
            self.send_status(source)
        else:
            if source == "console":
                print("未知命令，输入 'neko' 查看帮助")
            else:
                self.mc.postToChat("§c未知命令，输入 'neko' 查看帮助")
    
    # ----- 监听线程 -----
    def command_listener(self):
        print("游戏命令监听器已启动")
        while self.running:
            try:
                if self.restart_requested:
                    self._perform_restart()
                    continue
                elif self.shutdown_requested:
                    self._perform_shutdown()
                    break
                events = self.mc.events.pollChatPosts()
                for event in events:
                    message = event.message
                    if message.lower().startswith(('neko', 'nekosystem', 'nekoai', 'nekodaysay', 'nekopertime', 'nekobig', 'nekosoc')):
                        print(f"收到游戏命令: {message}")
                        self.process_command(message, "game")
                time.sleep(1)
            except Exception as e:
                print(f"游戏命令监听错误: {e}")
                time.sleep(5)
    
    def console_listener(self):
        print("控制台命令监听器已启动")
        print("输入 'neko' 查看可用命令")
        while self.running:
            try:
                if self.restart_requested:
                    self._perform_restart()
                    continue
                elif self.shutdown_requested:
                    self._perform_shutdown()
                    break
                if sys.platform == "win32":
                    import msvcrt
                    if msvcrt.kbhit():
                        command = input().strip()
                        if command:
                            print(f"收到控制台命令: {command}")
                            self.process_command(command, "console")
                else:
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        command = sys.stdin.readline().strip()
                        if command:
                            print(f"收到控制台命令: {command}")
                            self.process_command(command, "console")
                time.sleep(0.1)
            except Exception as e:
                print(f"控制台命令监听错误: {e}")
                time.sleep(5)
    
    def _perform_restart(self):
        try:
            self.running = False
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=5)
            self.running = True
            self.restart_requested = False
            self.monitor_thread = threading.Thread(target=self.monitor_loop)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            self.mc.postToChat("§aNekoSystem v3 重启完成！")
            print("NekoSystem v3 重启完成")
            time.sleep(2)
            self.send_system_report()
        except Exception as e:
            print(f"重启错误: {e}")
            self.mc.postToChat("§c重启失败，请检查控制台")
    
    def _perform_shutdown(self):
        try:
            self.running = False
            self.shutdown_requested = False
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=5)
            self.mc.postToChat("§cNekoSystem v3 已关闭")
            print("NekoSystem v3 已关闭")
        except Exception as e:
            print(f"关闭错误: {e}")
    
    def monitor_loop(self):
        while self.running:
            self.send_system_report()
            for _ in range(self.interval):
                if not self.running:
                    break
                time.sleep(1)
    
    def start(self):
        if self.running:
            print("监控已经在运行中")
            return
        self.running = True
        self.monitor_thread = threading.Thread(target=self.monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        self.command_thread = threading.Thread(target=self.command_listener)
        self.command_thread.daemon = True
        self.command_thread.start()
        self.console_thread = threading.Thread(target=self.console_listener)
        self.console_thread.daemon = True
        self.console_thread.start()
        print(f"NekoSystem v3 已启动，每 {self.interval/60} 分钟报告一次")
        self.mc.postToChat(f"§aNekoSystem v3 已启动，每 {self.interval/60} 分钟报告一次")
        self.mc.postToChat("§a输入 'neko' 查看可用命令")
    
    def stop(self):
        self.running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        if self.command_thread and self.command_thread.is_alive():
            self.command_thread.join(timeout=5)
        if self.console_thread and self.console_thread.is_alive():
            self.console_thread.join(timeout=5)
        print(f"NekoSystem v3 已停止，共发送了 {self.report_count} 次报告")
    
    def get_report_count(self):
        return self.report_count


# ================== 主程序入口 ==================
if __name__ == "__main__":
    try:
        mc = minecraft.Minecraft.create(address="127.0.0.1", port=4711)
        monitor = NekoSystemMonitor(mc, interval_minutes=30)
        monitor.start()
        print("监控系统正在运行，按 Ctrl+C 停止")
        print("可以在 Minecraft 聊天栏或此控制台输入命令")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止监控...")
        monitor.stop()
    except Exception as e:
        print(f"连接失败: {e}")
