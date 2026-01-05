#!/bin/env python3
"""
NexStar AUX Simulator Main Entry Point

This script starts an asynchronous server simulating a Celestron mount.
It supports:
    - AUX bus emulation on port 2000 (default)
    - Stellarium protocol emulation on port 10001 (default)
    - Headless mode (-t) for background execution
    - TUI mode (default) using curses
"""

import asyncio
import signal
import socket
import sys
import argparse
import yaml
import os
from socket import SOL_SOCKET, SO_BROADCAST, SO_REUSEADDR
from nse_telescope import NexStarScope, repr_angle

import curses

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

async def broadcast(sport=2000, dport=55555, host='255.255.255.255', seconds_to_sleep=5):
    """Broadcasts UDP packets to simulate a WiFly discovery service."""
    sck = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sck.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    sck.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
    msg = 110 * b'X'
    sck.bind(('', sport))
    if telescope:
        telescope.print_msg(f'Broadcasting to port {dport}')
    while True:
        sck.sendto(msg, (host, dport))
        await asyncio.sleep(seconds_to_sleep)

async def timer(seconds_to_sleep=1.0, telescope=None):
    """Timer loop to trigger physical model updates (ticks)."""
    from time import time
    t = time()
    while True:
        await asyncio.sleep(seconds_to_sleep)
        cur_t = time()
        if telescope:
            telescope.tick(cur_t - t)
        t = cur_t

async def handle_port2000(reader, writer):
    """Handles communication on the AUX port (2000)."""
    transparent = True
    global telescope
    connected = False
    
    while True:
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

def to_le(n, size):
    """Converts int to Little-Endian bytes."""
    return n.to_bytes(size, 'little')

def from_le(b):
    """Converts Little-Endian bytes to int."""
    return int.from_bytes(b, 'little')

def handle_stellarium_cmd(tel, d):
    """Parses incoming Stellarium Goto commands."""
    import time
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
    import ephem
    from math import pi
    import time
    import math
    
    obs.date = ephem.now()
    rajnow, decjnow = obs.radec_of(tel.azm * 2 * pi, tel.alt * 2 * pi)
    
    msg = bytearray(24)
    msg[0:2] = to_le(24, 2)
    msg[2:4] = to_le(0, 2)
    msg[4:12] = to_le(int(time.time()), 8)
    msg[12:16] = to_le(int(math.floor((rajnow / (2*pi)) * 4294967296.0)), 4)
    msg[16:20] = to_le(int(math.floor((decjnow / (2*pi)) * 4294967296.0)), 4)
    return msg

connections = []

async def report_scope_pos(sleep=0.1, scope=None, obs=None):
    """Broadcasts current position to all connected Stellarium clients."""
    while True:
        await asyncio.sleep(sleep)
        for tr in connections:
            try: tr.write(make_stellarium_status(scope, obs))
            except: pass

class StellariumServer(asyncio.Protocol):
    """Asynchronous protocol implementation for Stellarium TCP server."""
    def __init__(self, *arg, **kwarg):
        import ephem
        global telescope, obs_cfg
        self.obs = ephem.Observer()
        self.obs.lat = str(obs_cfg.get("latitude", 50.1822))
        self.obs.lon = str(obs_cfg.get("longitude", 19.7925))
        self.obs.elevation = float(obs_cfg.get("elevation", 400))
        self.telescope = telescope
        asyncio.Protocol.__init__(self, *arg, **kwarg)

    def connection_made(self, transport):
        connections.append(transport)
        if self.telescope: self.telescope.print_msg('Stellarium client connected.')
        
    def connection_lost(self, exc):
        try: connections.remove(self.transport)
        except: pass

    def data_received(self, data):
        if self.telescope: handle_stellarium_cmd(self.telescope, data)
    
def main(stdscr, args):
    """Main application loop."""
    import ephem
    global telescope, obs_cfg

    obs = ephem.Observer()
    obs.lat = str(obs_cfg.get("latitude", 50.1822))
    obs.lon = str(obs_cfg.get("longitude", 19.7925))
    obs.elevation = float(obs_cfg.get("elevation", 400))

    telescope = NexStarScope(stdscr=stdscr, tui=not args.text)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    scope = loop.run_until_complete(
                asyncio.start_server(handle_port2000, host='', port=args.port))
    stell = loop.run_until_complete(
                loop.create_server(StellariumServer, host='', port=args.stellarium))
    
    telescope.print_msg(f'NSE simulator started on port {args.port}.')
    
    asyncio.ensure_future(broadcast(sport=args.port))
    asyncio.ensure_future(timer(0.1, telescope))
    asyncio.ensure_future(report_scope_pos(0.1, telescope, obs))

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        scope.close()
        stell.close()
        loop.close()

def start_simulator():
    """Parses arguments and launches the simulator."""
    global config
    sim_cfg = config.get("simulator", {})
    parser = argparse.ArgumentParser(description='NexStar AUX Simulator')
    parser.add_argument('-t', '--text', action='store_true', help='Use text mode (headless)')
    parser.add_argument('-p', '--port', type=int, default=sim_cfg.get("aux_port", 2000), help='AUX port')
    parser.add_argument('-s', '--stellarium', type=int, default=sim_cfg.get("stellarium_port", 10001), help='Stellarium port')
    args = parser.parse_args()

    if args.text:
        main(None, args)
    else:
        curses.wrapper(main, args)

if __name__ == "__main__":
    start_simulator()
