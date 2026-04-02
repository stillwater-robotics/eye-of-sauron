import socket
import threading
import csv
import os
import time
import subprocess
import tkinter as tk
from tkinter import scrolledtext, ttk
from datetime import datetime
import cv2
import numpy as np
import math
from PIL import Image, ImageTk
from dataclasses import dataclass

# --- THEME DEFINITIONS ---
THEMES = {
    "light": {
        "main": "#FFFFFF",
        "sidebar": "#F5F5F7",
        "card_bg": "#FFFFFF",      
        "text": "#1D1D1F",
        "entry_bg": "#FFFFFF",
        "entry_fg": "#000000",
        "terminal_bg": "#1C1C1E",
        "terminal_fg": "#FFFFFF",
        "accent": "#007AFF",
        "border": "#D1D1D6",
        "tx_color": "#28A745",
        "rx_color": "#007AFF",
        "err_color": "#FF3B30",
        "sys_color": "#8E8E93"
    },
    "dark": {
        "main": "#1C1C1E",
        "sidebar": "#2C2C2E",
        "card_bg": "#3A3A3C",      
        "text": "#FFFFFF",
        "entry_bg": "#3A3A3C",
        "entry_fg": "#FFFFFF",
        "terminal_bg": "#000000",
        "terminal_fg": "#FFFFFF",
        "accent": "#0A84FF",
        "border": "#636366",
        "tx_color": "#34C759",
        "rx_color": "#0A84FF",
        "err_color": "#FF453A",
        "sys_color": "#98989D"
    }
}

COMMAND_HELP = {
    "gps": "gps <x> <y>",
    "sw":  "sw <x> <y> <z> <theta>",
    "in":  "in <left> <right> <ballast>",
    "tog": "tog <flag_char>"
}

# ------ Constants ------
# Networking
UDP_IP = "192.168.0.101"
UDP_PORT = 8888
LOCAL_PORT = 10000 
BROADCAST_RATE = 1  # 1 Hz for Swarm
GPS_BROADCAST_PERIOD = 2.0  # 0.5 Hz for GPS

CSV_WRITE_RATE = 10  # Hz
CSV_PERIOD = 1.0 / CSV_WRITE_RATE

# Camera setup
WEBCAM_ID = 0
FRAME_WIDTH_PX = 640
FRAME_HEIGHT_PX = 480

CENTER_X_PX = FRAME_WIDTH_PX / 2
CENTER_Y_PX = FRAME_HEIGHT_PX / 2

CAM_HEIGHT_METERS = 0.7
CAM_FOV_DEG = 77
FOV_LENGTH_PX = (FRAME_WIDTH_PX / 2) / math.tan(math.radians(CAM_FOV_DEG) / 2)

REFERENCE_CONTOUR = "contour_refs/auv_contour.png"

@dataclass
class SwarmMember:
    x: float
    y: float

class SwarmManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Swarm Manager with Eye of Sauron")
        self.root.geometry("1600x900")
        
        # State
        self.current_theme = "light"
        self.target_ip = "192.168.0.101"
        self.target_port = 8888
        self.local_port = 9999
        self.sock = None
        self.running = True
        
        # Camera state
        self.camera_id = 0
        self.new_camera_id = 0
        self.camera_id_changed = False
        self.capture = None
        self.prev_robot_px = None
        self.last_reset_time = 0
        self.RESET_DURATION = 10
        self.swarm_members = []
        self.last_gps_tx = 0
        self.last_member_tx = 0
        self.last_csv_write = 0
        self.mouse_hover = False
        self.mouse_x = 0
        self.mouse_y = 0
        self.robot_position = "X: --  Y: --"
        
        self.setup_csv()
        self.setup_styles()
        self.build_ui()
        self.init_socket()
        self.init_camera()
        self.apply_theme()
        
        # Start threads
        threading.Thread(target=self.camera_loop, daemon=True).start()

    def setup_csv(self):
        os.makedirs("csvs", exist_ok=True)
        self.csv_filename = os.path.join("csvs", f"swarm_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        with open(self.csv_filename, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Unix_Timestamp", "Direction", "IP", "Port", "Message"])

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure("Flat.TButton", padding=8, relief="flat")
        self.style.configure("Primary.TButton", padding=10, relief="flat", foreground="white")

    def build_ui(self):
        # --- SIDEBAR ---
        self.sidebar = tk.Frame(self.root, width=280, padx=20, pady=25)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        self.title_label = tk.Label(self.sidebar, text="Swarm Config", font=("Inter", 11, "bold"))
        self.title_label.pack(anchor=tk.W, pady=(0, 20))

        # Target Selection
        self.lbl_robot = tk.Label(self.sidebar, text="Swarm Member Select", font=("Inter", 9))
        self.lbl_robot.pack(anchor=tk.W)
        self.swarm_select = ttk.Combobox(self.sidebar, values=[self.target_ip], font=("Inter", 10))
        self.swarm_select.set(self.target_ip)
        self.swarm_select.pack(fill=tk.X, pady=(5, 10))

        ttk.Button(self.sidebar, text="Scan Network", style="Flat.TButton", command=self.scan_network).pack(fill=tk.X, pady=(0, 20))

        # Ports
        self.lbl_tport = tk.Label(self.sidebar, text="Target Port (Robot)", font=("Inter", 9))
        self.lbl_tport.pack(anchor=tk.W)
        self.t_port_ent = tk.Entry(self.sidebar, font=("Inter", 10), relief="flat", highlightthickness=1)
        self.t_port_ent.insert(0, str(self.target_port))
        self.t_port_ent.pack(fill=tk.X, pady=(5, 15), ipady=4)

        self.lbl_lport = tk.Label(self.sidebar, text="Local Port (Laptop)", font=("Inter", 9))
        self.lbl_lport.pack(anchor=tk.W)
        self.l_port_ent = tk.Entry(self.sidebar, font=("Inter", 10), relief="flat", highlightthickness=1)
        self.l_port_ent.insert(0, str(self.local_port))
        self.l_port_ent.pack(fill=tk.X, pady=(5, 15), ipady=4)

        ttk.Button(self.sidebar, text="Update Connection", style="Primary.TButton", command=self.update_ports).pack(fill=tk.X, pady=10)
        
        # Dark Mode Toggle
        self.theme_btn = ttk.Button(self.sidebar, text="Toggle Dark Mode", style="Flat.TButton", command=self.toggle_theme)
        self.theme_btn.pack(fill=tk.X, pady=(0, 20))

        # --- INPUT (Sidebar) ---
        self.input_container = tk.Frame(self.sidebar, pady=25)
        self.input_container.pack(fill=tk.X, side=tk.BOTTOM)

        self.hint_var = tk.StringVar(value="Select a member or type a command...")
        self.hint_label = tk.Label(self.input_container, textvariable=self.hint_var, font=("Inter", 9, "italic"))
        self.hint_label.pack(anchor=tk.W)
        
        self.entry = tk.Entry(self.input_container, font=("JetBrains Mono", 13), relief="flat", highlightthickness=1)
        self.entry.pack(fill=tk.X, pady=8, ipady=10)
        
        self.entry.bind("<KeyRelease>", self.update_hint)
        self.entry.bind("<Return>", lambda e: self.send_command())

        # --- RIGHT PANEL ---
        self.right_panel = tk.Frame(self.root)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Camera Container (Top Half)
        self.camera_container = tk.Frame(self.right_panel)
        self.camera_container.pack(fill=tk.X, pady=(10, 0))

        # 1. Left Side: Viewer
        self.viewer_frame = tk.Frame(self.camera_container)
        self.viewer_frame.pack(side=tk.LEFT)
        
        self.viewer_title = tk.Label(self.viewer_frame, text="Overhead Viewer", font=("Inter", 12, "bold"))
        self.viewer_title.pack(anchor=tk.W, pady=(0, 5))

        self.camera_frame = tk.Frame(self.viewer_frame, width=FRAME_WIDTH_PX, height=FRAME_HEIGHT_PX)
        self.camera_frame.pack()
        self.camera_frame.pack_propagate(False) # Force exact CV2 size
        
        self.camera_label = tk.Label(self.camera_frame)
        self.camera_label.pack(fill=tk.BOTH, expand=True)
        self.camera_label.bind("<Double-Button-1>", self.spawn_member)
        self.camera_label.bind("<Motion>", self.on_mouse_motion)
        self.camera_label.bind("<Enter>", self.on_mouse_enter)
        self.camera_label.bind("<Leave>", self.on_mouse_leave)

        # 2. Right Side: Management
        self.management_frame = tk.Frame(self.camera_container)
        self.management_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(20, 0))

        self.management_title = tk.Label(self.management_frame, text="Overhead Management", font=("Inter", 12, "bold"))
        self.management_title.pack(anchor=tk.W, pady=(0, 5))

        self.side_panel = tk.Frame(self.management_frame, width=250)
        self.side_panel.pack(fill=tk.BOTH, expand=True)
        self.side_panel.pack_propagate(False)

        self.camera_select_label = tk.Label(self.side_panel, text="Camera Select", font=("Inter", 9))
        self.camera_select_label.pack(anchor=tk.W, pady=(10, 5))
        self.camera_select = ttk.Combobox(self.side_panel, values=[str(i) for i in range(5)], font=("Inter", 10))
        self.camera_select.set(str(self.camera_id))
        self.camera_select.pack(fill=tk.X, pady=(0, 15))
        self.camera_select.bind("<<ComboboxSelected>>", self.on_camera_change)

        self.position_label = tk.Label(self.side_panel, text=self.robot_position, font=("Inter", 10, "bold"))
        self.position_label.pack(anchor=tk.W, pady=(10, 5))

        self.agents_label = tk.Label(self.side_panel, text="Simulated Agents", font=("Inter", 9))
        self.agents_label.pack(anchor=tk.W, pady=(10, 5))
        self.agent_frame = tk.Frame(self.side_panel)
        self.agent_frame.pack(fill=tk.BOTH, expand=True)

        # --- MESSAGES (Bottom Half - Unified Feed) ---
        self.messages_frame = tk.Frame(self.right_panel)
        self.messages_frame.pack(fill=tk.BOTH, expand=True, pady=(20, 0))

        self.terminal_label = tk.Label(self.messages_frame, text="Unified Comms Feed", font=("Inter", 12, "bold"))
        self.terminal_label.pack(anchor=tk.W, pady=(0, 5))
        
        self.terminal_area = scrolledtext.ScrolledText(self.messages_frame, state='disabled', font=("JetBrains Mono", 10),
                                                       padx=12, pady=12, relief="flat")
        self.terminal_area.pack(fill=tk.BOTH, expand=True)

    def toggle_theme(self):
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        self.apply_theme()

    def apply_theme(self):
        t = THEMES[self.current_theme]
        self.root.configure(bg=t["main"])
        self.sidebar.configure(bg=t["sidebar"])
        self.right_panel.configure(bg=t["main"])
        
        self.camera_container.configure(bg=t["main"])
        self.viewer_frame.configure(bg=t["main"])
        self.management_frame.configure(bg=t["main"])
        self.camera_frame.configure(bg=t["main"])
        self.camera_label.configure(bg=t["main"]) 
        self.side_panel.configure(bg=t["sidebar"])
        
        self.messages_frame.configure(bg=t["main"])
        self.input_container.configure(bg=t["sidebar"])
        self.agent_frame.configure(bg=t["sidebar"])
        
        # Labels
        for lbl in [self.title_label, self.lbl_robot, self.lbl_tport, self.lbl_lport, self.camera_select_label, self.position_label, self.agents_label, self.hint_label]:
            bg_color = t["sidebar"] if lbl.master in [self.sidebar, self.side_panel, self.input_container] else t["main"]
            lbl.configure(bg=bg_color, fg=t["text"])
            
        for lbl in [self.terminal_label, self.viewer_title, self.management_title]:
            lbl.configure(bg=t["main"], fg=t["text"])
        
        # Entries and Combobox
        for ent in [self.t_port_ent, self.l_port_ent, self.entry]:
            ent.configure(bg=t["entry_bg"], fg=t["entry_fg"], insertbackground=t["text"], highlightbackground=t["border"])
        self.camera_select.configure(background=t["entry_bg"], foreground=t["entry_fg"])
        
        # Messages
        self.terminal_area.configure(bg=t["terminal_bg"], fg=t["terminal_fg"], insertbackground=t["text"])
        
        # Style buttons
        self.style.configure("Flat.TButton", background=t["border"], foreground=t["text"])
        self.style.configure("Primary.TButton", background=t["accent"])
        
        # Re-render agents to apply new theme colors
        self.update_agent_list()

    def get_msg_color(self, msg):
        t = THEMES[self.current_theme]
        if "TX" in msg:
            return t["tx_color"]
        elif "RX" in msg:
            return t["rx_color"]
        elif "ERROR" in msg:
            return t["err_color"]
        elif "SYSTEM" in msg:
            return t["sys_color"]
        return t["terminal_fg"]

    def init_socket(self):
        if self.sock:
            self.running = False
            self.sock.close()
            time.sleep(0.1)
        try:
            # Reverted to match Stillwater perfectly
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind(('', self.local_port))
            self.running = True
            
            # Start listener immediately BEFORE sending anything
            threading.Thread(target=self.rx_loop, daemon=True).start()
            
            # Startup ping
            startup_msg = f"STARTUP_PORT:{self.local_port}"
            self.sock.sendto(startup_msg.encode('utf-8'), (UDP_IP, self.target_port))
            self.log_display(f"SYSTEM TX: {startup_msg}")
            
        except Exception as e:
            self.log_display(f"SYSTEM ERROR: {e}")

    def init_camera(self):
        self.capture = cv2.VideoCapture(WEBCAM_ID)
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH_PX)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT_PX)

    def on_camera_change(self, event):
        try:
            self.new_camera_id = int(self.camera_select.get())
            self.camera_id_changed = True
        except ValueError:
            pass

    def on_mouse_motion(self, event):
        self.mouse_x = event.x
        self.mouse_y = event.y

    def on_mouse_enter(self, event):
        self.mouse_hover = True

    def on_mouse_leave(self, event):
        self.mouse_hover = False

    def update_ports(self):
        try:
            self.target_port = int(self.t_port_ent.get())
            self.local_port = int(self.l_port_ent.get())
            self.init_socket()
            self.log_display("SYSTEM: Connection settings updated.")
        except ValueError:
            self.log_display("SYSTEM ERROR: Invalid Port.")

    def scan_network(self):
        self.log_display("SYSTEM: Scanning network...")
        def run_scan():
            found = []
            param = '-n' if os.name == 'nt' else '-c'
            for i in range(100, 120):
                ip = f"192.168.0.{i}"
                if subprocess.call(['ping', param, '1', '-w', '100', ip], stdout=subprocess.DEVNULL) == 0:
                    found.append(ip)
            self.root.after(0, lambda: self.swarm_select.configure(values=found))
            self.log_display(f"SYSTEM: Found {len(found)} members.")
        threading.Thread(target=run_scan, daemon=True).start()

    def update_hint(self, event):
        val = self.entry.get().strip().split(' ')[0].lower()
        if val in COMMAND_HELP:
            self.hint_var.set(f"Target: {self.swarm_select.get()} | {COMMAND_HELP[val]}")
        else:
            self.hint_var.set("Commands: gps, sw, in, tog")

    def send_command(self):
        raw = self.entry.get().strip()
        if not raw: return
        parts = raw.split()
        formatted = f"{parts[0].lower()}_{int(time.time())}_{'_'.join(parts[1:])}"
        try:
            self.sock.sendto(formatted.encode('utf-8'), (self.swarm_select.get(), self.target_port))
            self.log_to_csv("TX", formatted, self.swarm_select.get())
            self.log_display(f"TX >> {formatted}")
            self.entry.delete(0, tk.END)
        except Exception as e:
            self.log_display(f"TX ERROR: {e}")

    def log_display(self, msg):
        self.terminal_area.configure(state='normal')
        color = self.get_msg_color(msg)
        tag = f"tag_{color}"
        self.terminal_area.tag_config(tag, foreground=color)
        self.terminal_area.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n", tag)
        self.terminal_area.see(tk.END)
        self.terminal_area.configure(state='disabled')

    def log_to_csv(self, direction, message, ip):
        with open(self.csv_filename, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([time.time(), direction, ip, self.target_port, message])

    def rx_loop(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(1024)
                msg = data.decode('utf-8', errors='ignore')
                self.root.after(0, lambda m=msg, a=addr: self.log_display(f"RX << {m} ({a[0]})"))
                self.log_to_csv("RX", msg, addr[0])
            except Exception as e:
                # The crucial fix: Windows ICMP rejections trigger a ConnectionResetError.
                # If the socket is still meant to be running, we pass/ignore it instead of breaking!
                if not self.running:
                    break
                pass

    def remove_agent(self, idx):
        if 0 <= idx < len(self.swarm_members):
            self.swarm_members.pop(idx)
            self.update_agent_list()

    def update_agent_list(self):
        for widget in self.agent_frame.winfo_children():
            widget.destroy()
        
        t = THEMES[self.current_theme]
        for i, mem in enumerate(self.swarm_members):
            card = tk.Frame(self.agent_frame, bg=t["card_bg"], padx=8, pady=6)
            card.pack(fill=tk.X, pady=(0, 6), padx=4)
            
            info_frame = tk.Frame(card, bg=t["card_bg"])
            info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            lbl = tk.Label(info_frame, text=f"Agent {i+1}", font=("Inter", 9, "bold"), bg=t["card_bg"], fg=t["text"])
            lbl.pack(anchor=tk.W)
            
            pos = tk.Label(info_frame, text=f"X: {mem.x:.1f}  Y: {mem.y:.1f}", font=("JetBrains Mono", 8), bg=t["card_bg"], fg=t["border"])
            pos.pack(anchor=tk.W)
            
            btn = tk.Button(card, text="✕", command=lambda idx=i: self.remove_agent(idx),
                            font=("Inter", 12), relief="flat", bg=t["card_bg"], fg="#FF3B30", 
                            activebackground=t["card_bg"], activeforeground="red", bd=0, cursor="hand2")
            btn.pack(side=tk.RIGHT, padx=(5, 0))

    def spawn_member(self, event):
        label_w = self.camera_label.winfo_width()
        label_h = self.camera_label.winfo_height()
        if label_w <= 1 or label_h <= 1:
            return
        scale_x = FRAME_WIDTH_PX / label_w
        scale_y = FRAME_HEIGHT_PX / label_h
        x = event.x * scale_x
        y = event.y * scale_y
        
        for i, mem in enumerate(self.swarm_members):
            dist = math.hypot(mem.x - x, mem.y - y)
            if dist <= 10:
                self.swarm_members.pop(i)
                self.update_agent_list()
                return

        self.swarm_members.append(SwarmMember(x, y))
        self.update_agent_list()

    def broadcast_swarm_member(self, member):
        x, y = self.px_to_m(member.x, member.y)
        payload = f"sw_{time.time():.0f}_{x:.3f}_{y:.3f}_0_0"
        try:
            self.sock.sendto(payload.encode(), (UDP_IP, self.target_port))
            self.log_to_csv("TX", payload, UDP_IP)
            self.log_display(f"TX >> {payload}")
            return payload
        except Exception as e:
            self.log_display(f"SYSTEM ERROR: {e}")
            return None

    def udp_mock_gps_position(self, x, y):
        payload = f"gps_{time.time():.0f}_{x:.3f}_{y:.3f}"
        try:
            self.sock.sendto(payload.encode(), (UDP_IP, self.target_port))
            self.log_to_csv("TX", payload, UDP_IP)
            self.log_display(f"TX >> {payload}")
            return payload
        except Exception as e:
            self.log_display(f"SYSTEM ERROR: {e}")
            return None

    def px_to_m(self, u, v):
        x_px = u - CENTER_X_PX
        y_px = CENTER_Y_PX - v
        
        x_m = (x_px * CAM_HEIGHT_METERS) / FOV_LENGTH_PX
        y_m = (y_px * CAM_HEIGHT_METERS) / FOV_LENGTH_PX
        
        return x_m, y_m

    def camera_loop(self):
        try:
            from sauronlib.find_robot import find_robot
        except ImportError:
            find_robot = None

        while self.running:
            if self.camera_id_changed:
                self.capture.release()
                self.capture = cv2.VideoCapture(self.new_camera_id)
                self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH_PX)
                self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT_PX)
                self.camera_id = self.new_camera_id
                self.camera_id_changed = False
            ret, frame = self.capture.read()
            if not ret:
                continue
            
            cv2.circle(frame, (int(FRAME_WIDTH_PX // 2), int(FRAME_HEIGHT_PX // 2)), 3, (0, 0, 255), 2)
            cv2.arrowedLine(frame, (int(FRAME_WIDTH_PX // 2), int(FRAME_HEIGHT_PX // 2)), (int(FRAME_WIDTH_PX // 2), int(FRAME_HEIGHT_PX // 2) + 15), (0, 255, 0), 2, tipLength=0.3)
            cv2.arrowedLine(frame, (int(FRAME_WIDTH_PX // 2), int(FRAME_HEIGHT_PX // 2)), (int(FRAME_WIDTH_PX // 2) + 15, int(FRAME_HEIGHT_PX // 2)), (255, 0, 0), 2, tipLength=0.3)

            for member in self.swarm_members:
                cv2.circle(frame, (int(member.x), int(member.y)), 10, (0, 255, 0), 2)
                cv2.circle(frame, (int(member.x), int(member.y)), 8, (55, 200, 0), -1)
                
                if (time.time() - self.last_member_tx) > BROADCAST_RATE:
                    self.broadcast_swarm_member(member)
                    self.last_member_tx = time.time()
                    
                if self.prev_robot_px:
                    cv2.arrowedLine(frame, (int(member.x), int(member.y)), self.prev_robot_px, (55, 200, 0), 1, tipLength=0.2)
            
            allow_reset = (time.time() - self.last_reset_time) < self.RESET_DURATION
            
            if find_robot:
                contours, robot_px, binary = find_robot(frame, REFERENCE_CONTOUR, debug=False, prev_center=self.prev_robot_px, allow_reset=allow_reset)
            else:
                robot_px = None
            
            if robot_px:
                self.prev_robot_px = robot_px
            
            if robot_px:
                robot_x_m, robot_y_m = self.px_to_m(robot_px[0], robot_px[1])
                
                self.robot_position = f"X: {robot_x_m:.2f}m  Y: {robot_y_m:.2f}m"
                self.root.after(0, lambda: self.position_label.config(text=self.robot_position))
                
                current_time = time.time()
                if (current_time - self.last_gps_tx) > GPS_BROADCAST_PERIOD:
                    self.udp_mock_gps_position(robot_x_m, robot_y_m)
                    self.last_gps_tx = current_time

                if (current_time - self.last_csv_write) >= CSV_PERIOD:
                    timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                    with open(self.csv_filename.replace('swarm_log', 'robot_pos'), mode='a', newline='') as file:
                        writer = csv.writer(file)
                        writer.writerow([timestamp_str, f"{robot_x_m:.3f}", f"{robot_y_m:.3f}"])
                    self.last_csv_write = current_time

                cv2.circle(frame, robot_px, 10, (0, 0, 255), 2)
                cv2.circle(frame, robot_px, 8, (0, 100, 255), -1)
            
            if self.mouse_hover:
                label_w = self.camera_label.winfo_width()
                label_h = self.camera_label.winfo_height()
                if label_w > 1 and label_h > 1:
                    scale_x = FRAME_WIDTH_PX / label_w
                    scale_y = FRAME_HEIGHT_PX / label_h
                    px_x = int(self.mouse_x * scale_x)
                    px_y = int(self.mouse_y * scale_y)
                    cv2.line(frame, (px_x - 10, px_y), (px_x + 10, px_y), (255, 255, 255), 1)
                    cv2.line(frame, (px_x, px_y - 10), (px_x, px_y + 10), (255, 255, 255), 1)
            
            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(image)
            photo = ImageTk.PhotoImage(image)
            self.root.after(0, lambda: self.camera_label.config(image=photo))
            self.root.after(0, lambda: setattr(self.camera_label, 'image', photo))

if __name__ == "__main__":
    root = tk.Tk()
    app = SwarmManager(root)
    root.mainloop()