"""
NexStar AUX Simulator with Textual TUI

Modern TUI for the Celestron mount simulator using the Textual library.
"""

import asyncio
import argparse
import yaml
import os
import socket
from datetime import datetime, timezone
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Log
from textual.containers import Container, Horizontal, Vertical
from textual.binding import Binding
from textual.reactive import reactive
import ephem
from math import pi
import math

from nse_telescope import NexStarScope, repr_angle, trg_names, cmd_names

# Load configuration
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
DEFAULT_CONFIG = {
    "observer": {
        "latitude": 50.1822,
        "longitude": 19.7925,
        "elevation": 400
    }
}

def load_config():
    """Loads simulator and observer settings from config.yaml."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
    return DEFAULT_CONFIG

config = load_config()
obs_cfg = config.get("observer", DEFAULT_CONFIG["observer"])

telescope = None
connections = []

# --- Network Helpers ---

async def broadcast(sport=2000, dport=55555, host='255.255.255.255', seconds_to_sleep=5):
    """Broadcasts UDP packets to simulate a WiFly discovery service."""
    sck = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sck.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sck.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    msg = 110 * b'X'
    sck.bind(('', sport))
    while True:
        sck.sendto(msg, (host, dport))
        await asyncio.sleep(seconds_to_sleep)

async def timer(seconds_to_sleep=1.0, tel=None):
    """Timer loop to trigger physical model updates (ticks)."""
    from time import time
    t = time()
    while True:
        await asyncio.sleep(seconds_to_sleep)
        cur_t = time()
        if tel:
            tel.tick(cur_t - t)
        t = cur_t

async def handle_port2000(reader, writer):
    """Handles communication on the AUX port (2000)."""
    transparent = True
    global telescope
    connected = False
    
    while True:
        try:
            data = await reader.read(1024)
            if not data:
                writer.close()
                if telescope: telescope.print_msg('Connection closed.')
                return
            elif not connected:
                if telescope: telescope.print_msg(f'Client connected from {writer.get_extra_info("peername")}')
                connected = True
                
            resp = b''
            if transparent:
                if data[:3] == b'$$$':
                    transparent = False
                    resp = b'CMD\r\n'
                else:
                    if telescope: resp = telescope.handle_msg(data)
            else:
                message = data.decode('ascii', errors='ignore').strip()
                if message == 'exit':
                    transparent = True
                    resp = data + b'\r\nEXIT\r\n'
                else:
                    resp = data + b'\r\nAOK\r\n<2.40-CEL> '
            
            if resp:
                writer.write(resp)
                await writer.drain()
        except Exception as e:
            if telescope: telescope.print_msg(f"Error handling AUX port: {e}")
            break

def to_le(n, size):
    return n.to_bytes(size, 'little')

def from_le(b):
    return int.from_bytes(b, 'little')

def handle_stellarium_cmd(tel, d):
    """Parses incoming Stellarium Goto commands."""
    p = 0
    while p < len(d) - 2:
        psize = from_le(d[p:p+2]) 
        if (psize > len(d) - p): break
        ptype = from_le(d[p+2:p+4])
        if ptype == 0: # Goto
            targetra = from_le(d[p+12:p+16]) * 24.0 / 4294967296.0
            targetdec = from_le(d[p+16:p+20]) * 360.0 / 4294967296.0
            tel.print_msg(f'Stellarium GoTo: RA={targetra:.2f}h Dec={targetdec:.2f}deg')
            p += psize
        else:
            p += psize
    return p

def make_stellarium_status(tel, obs):
    """Generates Stellarium status packet (Position report)."""
    obs.date = ephem.now()
    rajnow, decjnow = obs.radec_of(tel.azm * 2 * pi, tel.alt * 2 * pi)
    
    msg = bytearray(24)
    msg[0:2] = to_le(24, 2)
    msg[2:4] = to_le(0, 2)
    msg[4:12] = to_le(int(datetime.now(timezone.utc).timestamp()), 8)
    msg[12:16] = to_le(int(math.floor((rajnow / (2*pi)) * 4294967296.0)), 4)
    msg[16:20] = to_le(int(math.floor((decjnow / (2*pi)) * 4294967296.0)), 4)
    return msg

async def report_scope_pos(sleep=0.1, scope=None, obs=None):
    """Broadcasts current position to all connected Stellarium clients."""
    while True:
        await asyncio.sleep(sleep)
        for tr in connections:
            try: tr.write(make_stellarium_status(scope, obs))
            except: pass

class StellariumServer(asyncio.Protocol):
    """Asynchronous protocol implementation for Stellarium TCP server."""
    def __init__(self, tel, obs):
        self.telescope = tel
        self.obs = obs

    def connection_made(self, transport):
        self.transport = transport
        connections.append(transport)
        if self.telescope: self.telescope.print_msg('Stellarium client connected.')
        
    def connection_lost(self, exc):
        try: connections.remove(self.transport)
        except: pass

    def data_received(self, data):
        if self.telescope: handle_stellarium_cmd(self.telescope, data)

# --- TUI App ---

class SimulatorApp(App):
    """Textual application for the NexStar AUX Simulator."""
    
    CSS = """
    Screen {
        background: #1a1b26;
    }
    
    #main-layout {
        height: 100%;
    }
    
    #left-panel {
        width: 30%;
        border: solid #414868;
        padding: 1;
    }
    
    #right-panel {
        width: 70%;
        border: solid #414868;
        padding: 1;
    }
    
    .panel-title {
        text-style: bold;
        color: #7aa2f7;
        margin-bottom: 1;
    }
    
    #log-view {
        height: 1fr;
        border: solid #414868;
    }
    
    .cyan { color: #7dcfff; }
    .yellow { color: #e0af68; }
    .green { color: #9ece6a; }
    .magenta { color: #bb9af7; }
    .red { color: #f7768e; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("p", "park", "Park", show=True),
        Binding("u", "unpark", "Unpark", show=True),
    ]

    def __init__(self, tel, obs, args):
        super().__init__()
        self.telescope = tel
        self.obs = obs
        self.args = args

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-layout"):
            with Vertical(id="left-panel"):
                yield Static("MOUNT POSITION", classes="panel-title")
                yield Static(id="pos-alt")
                yield Static(id="pos-azm")
                yield Static("")
                yield Static(id="pos-ra")
                yield Static(id="pos-dec")
                yield Static("")
                yield Static("STATUS & TELEMETRY", classes="panel-title")
                yield Static(id="status-mode")
                yield Static(id="status-tracking")
                yield Static(id="status-battery")
            
            with Vertical(id="right-panel"):
                yield Static("AUX BUS LOG", classes="panel-title")
                yield Log(id="aux-log")
                yield Static("")
                yield Static("SYSTEM MESSAGES", classes="panel-title")
                yield Log(id="sys-messages")
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(0.1, self.update_stats)
        self.log_sys(f"Simulator started on port {self.args.port}")
        self.log_sys(f"Stellarium server on port {self.args.stellarium}")
        self.log_sys(f"Location: {obs_cfg.get('name', 'Bębło')}")

    def update_stats(self) -> None:
        alt_str = repr_angle(self.telescope.alt)
        azm_str = repr_angle(self.telescope.azm)
        
        self.obs.date = ephem.now()
        rajnow, decjnow = self.obs.radec_of(self.telescope.azm * 2 * pi, self.telescope.alt * 2 * pi)
        
        mode = "SLEWING" if self.telescope.slewing else ("GUIDING" if self.telescope.guiding else "IDLE")
        tracking = "ON" if self.telescope.guiding else "OFF"
        battery = f"{self.telescope.bat_voltage / 1e6:.2f}V"

        self.query_one("#pos-alt").update(f"Alt: [cyan]{alt_str}[/cyan]")
        self.query_one("#pos-azm").update(f"Azm: [cyan]{azm_str}[/cyan]")
        self.query_one("#pos-ra").update(f"RA:  [yellow]{rajnow}[/yellow]")
        self.query_one("#pos-dec").update(f"Dec: [yellow]{decjnow}[/yellow]")
        self.query_one("#status-mode").update(f"Mode: [green]{mode}[/green]")
        self.query_one("#status-tracking").update(f"Tracking: [magenta]{tracking}[/magenta]")
        self.query_one("#status-battery").update(f"Battery: [red]{battery}[/red]")

        while self.telescope.cmd_log:
            entry = self.telescope.cmd_log.popleft()
            self.query_one("#aux-log").write_line(f"[blue]{datetime.now().strftime('%H:%M:%S')}[/blue] {entry}")
        
        while self.telescope.msg_log:
            msg = self.telescope.msg_log.popleft()
            self.log_sys(msg)

    def log_sys(self, message: str) -> None:
        self.query_one("#sys-messages").write_line(f"[blue]{datetime.now().strftime('%H:%M:%S')}[/blue] {message}")

    async def action_park(self) -> None:
        self.log_sys("Parking request...")
        self.telescope.trg_alt = 0
        self.telescope.trg_azm = 0
        self.telescope.slewing = self.telescope.goto = True

    async def action_unpark(self) -> None:
        self.log_sys("Unparking...")
        self.telescope.slewing = self.telescope.goto = False

async def main_async():
    parser = argparse.ArgumentParser(description='NexStar AUX Simulator (Textual)')
    sim_cfg = config.get("simulator", {})
    parser.add_argument('-t', '--text', action='store_true', help='Use text mode (headless)')
    parser.add_argument('-p', '--port', type=int, default=sim_cfg.get("aux_port", 2000), help='AUX port')
    parser.add_argument('-s', '--stellarium', type=int, default=sim_cfg.get("stellarium_port", 10001), help='Stellarium port')
    args = parser.parse_args()

    global telescope
    obs = ephem.Observer()
    obs.lat = str(obs_cfg.get("latitude", 50.1822))
    obs.lon = str(obs_cfg.get("longitude", 19.7925))
    obs.elevation = float(obs_cfg.get("elevation", 400))
    obs.pressure = 0

    telescope = NexStarScope(stdscr=None, tui=False)

    # background tasks
    asyncio.create_task(broadcast(sport=args.port))
    asyncio.create_task(timer(0.1, telescope))
    asyncio.create_task(report_scope_pos(0.1, telescope, obs))
    
    scope_server = await asyncio.start_server(handle_port2000, host='', port=args.port)
    
    loop = asyncio.get_running_loop()
    stell_server = await loop.create_server(lambda: StellariumServer(telescope, obs), host='', port=args.stellarium)

    if args.text:
        print(f"Simulator running in headless mode on port {args.port}")
        try:
            while True: await asyncio.sleep(3600)
        except asyncio.CancelledError: pass
    else:
        app = SimulatorApp(telescope, obs, args)
        await app.run_async()

    scope_server.close()
    stell_server.close()

if __name__ == "__main__":
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass
