import socket
import threading
import csv
import os
import time
import subprocess
import tkinter as tk
from tkinter import scrolledtext, ttk
from datetime import datetime

# --- THEME DEFINITIONS ---
THEMES = {
    "light": {
        "main": "#FFFFFF",
        "sidebar": "#F5F5F7",
        "text": "#1D1D1F",
        "entry_bg": "#FFFFFF",
        "entry_fg": "#000000",
        "terminal_bg": "#1C1C1E",
        "terminal_fg": "#FFFFFF",
        "accent": "#007AFF",
        "border": "#D1D1D6"
    },
    "dark": {
        "main": "#1C1C1E",
        "sidebar": "#2C2C2E",
        "text": "#FFFFFF",
        "entry_bg": "#3A3A3C",
        "entry_fg": "#FFFFFF",
        "terminal_bg": "#000000",
        "terminal_fg": "#34C759", # Matrix green for dark mode
        "accent": "#0A84FF",
        "border": "#48484A"
    }
}

COMMAND_HELP = {
    "gps": "gps <x> <y>",
    "sw":  "sw <x> <y> <z> <theta>",
    "in":  "in <left> <right> <ballast>",
    "tog": "tog <flag_char>"
}

class StillwaterControl:
    def __init__(self, root):
        self.root = root
        self.root.title("Stillwater Swarm Control")
        self.root.geometry("1050x750")
        
        # State
        self.current_theme = "light"
        self.target_ip = "192.168.0.101"
        self.target_port = 8888
        self.local_port = 9999
        self.sock = None
        self.running = True
        
        self.setup_csv()
        self.setup_styles()
        self.build_ui()
        self.init_socket()
        self.apply_theme()

    def setup_csv(self):
        os.makedirs("csvs", exist_ok=True)
        self.csv_filename = os.path.join("csvs", f"stillwater_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
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

        # --- MAIN PANEL ---
        self.main_content = tk.Frame(self.root, padx=30, pady=25)
        self.main_content.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.feed_label = tk.Label(self.main_content, text="Swarm Comms Feed", font=("Inter", 16, "bold"))
        self.feed_label.pack(anchor=tk.W, pady=(0,15))

        self.rx_area = scrolledtext.ScrolledText(self.main_content, state='disabled', font=("JetBrains Mono", 10),
                                                padx=12, pady=12, relief="flat")
        self.rx_area.pack(fill=tk.BOTH, expand=True)

        # --- INPUT ---
        self.input_container = tk.Frame(self.main_content, pady=25)
        self.input_container.pack(fill=tk.X)

        self.hint_var = tk.StringVar(value="Select a member or type a command...")
        self.hint_label = tk.Label(self.input_container, textvariable=self.hint_var, font=("Inter", 9, "italic"))
        self.hint_label.pack(anchor=tk.W)
        
        self.entry = tk.Entry(self.input_container, font=("JetBrains Mono", 13), relief="flat", highlightthickness=1)
        self.entry.pack(fill=tk.X, pady=8, ipady=12)
        
        self.entry.bind("<KeyRelease>", self.update_hint)
        self.entry.bind("<Return>", lambda e: self.send_command())

    def toggle_theme(self):
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        self.apply_theme()

    def apply_theme(self):
        t = THEMES[self.current_theme]
        self.root.configure(bg=t["main"])
        self.sidebar.configure(bg=t["sidebar"])
        self.main_content.configure(bg=t["main"])
        self.input_container.configure(bg=t["main"])
        
        # Labels
        for lbl in [self.title_label, self.lbl_robot, self.lbl_tport, self.lbl_lport, self.feed_label, self.hint_label]:
            lbl.configure(bg=t["sidebar"] if lbl.master == self.sidebar else t["main"], fg=t["text"])
        
        # Entries
        for ent in [self.t_port_ent, self.l_port_ent, self.entry]:
            ent.configure(bg=t["entry_bg"], fg=t["entry_fg"], insertbackground=t["text"], highlightbackground=t["border"])
        
        # Terminal
        self.rx_area.configure(bg=t["terminal_bg"], fg=t["terminal_fg"])
        
        # Style buttons
        self.style.configure("Flat.TButton", background=t["border"], foreground=t["text"])
        self.style.configure("Primary.TButton", background=t["accent"])

    def init_socket(self):
        if self.sock:
            self.running = False
            self.sock.close()
            time.sleep(0.1)
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind(('', self.local_port))
            self.running = True
            threading.Thread(target=self.rx_loop, daemon=True).start()
        except Exception as e:
            self.log_display(f"SYSTEM ERROR: {e}", "#FF3B30")

    def update_ports(self):
        try:
            self.target_port = int(self.t_port_ent.get())
            self.local_port = int(self.l_port_ent.get())
            self.init_socket()
            self.log_display("SYSTEM: Connection settings updated.", THEMES[self.current_theme]["accent"])
        except ValueError:
            self.log_display("SYSTEM ERROR: Invalid Port.", "#FF3B30")

    def scan_network(self):
        self.log_display("SYSTEM: Scanning network...", "gray")
        def run_scan():
            found = []
            param = '-n' if os.name == 'nt' else '-c'
            for i in range(100, 120):
                ip = f"192.168.0.{i}"
                if subprocess.call(['ping', param, '1', '-w', '100', ip], stdout=subprocess.DEVNULL) == 0:
                    found.append(ip)
            self.root.after(0, lambda: self.swarm_select.configure(values=found))
            self.log_display(f"SYSTEM: Found {len(found)} members.", THEMES[self.current_theme]["accent"])
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
            self.log_display(f"TX >> {formatted}", "#34C759")
            self.entry.delete(0, tk.END)
        except Exception as e:
            self.log_display(f"TX ERROR: {e}", "#FF3B30")

    def log_display(self, msg, color="white"):
        self.rx_area.configure(state='normal')
        tag = f"tag_{color}"
        self.rx_area.tag_config(tag, foreground=color)
        self.rx_area.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n", tag)
        self.rx_area.see(tk.END)
        self.rx_area.configure(state='disabled')

    def log_to_csv(self, direction, message, ip):
        with open(self.csv_filename, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([time.time(), direction, ip, self.target_port, message])

    def rx_loop(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(1024)
                msg = data.decode('utf-8')
                self.root.after(0, lambda m=msg, a=addr: self.log_display(f"RX << {m} ({a[0]})"))
                self.log_to_csv("RX", msg, addr[0])
            except: break

if __name__ == "__main__":
    root = tk.Tk()
    app = StillwaterControl(root)
    root.mainloop()