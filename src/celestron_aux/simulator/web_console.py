"""
Web-based 3D visualization console for the Celestron AUX Simulator.
"""

import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn
import os

app = FastAPI()

# Connected WebSocket clients
clients = set()
# Global geometry config
mount_geometry = {}


class WebConsole:
    def __init__(self, telescope, host="127.0.0.1", port=8080):
        self.telescope = telescope
        self.host = host
        self.port = port
        self.server_task = None

        # Load geometry from telescope config
        global mount_geometry
        mount_geometry = self.telescope.config.get("simulator", {}).get(
            "geometry",
            {
                "base_height": 0.2,
                "fork_height": 0.45,
                "fork_width": 0.35,
                "ota_radius": 0.12,
                "ota_length": 0.45,
                "camera_length": 0.15,
            },
        )

    async def broadcast_state(self):
        """Broadcasts telescope state to all connected clients."""
        while True:
            if clients:
                state = {
                    "azm": self.telescope.azm * 360.0,
                    "alt": self.telescope.alt * 360.0,
                    "slewing": self.telescope.slewing,
                    "guiding": self.telescope.guiding,
                    "timestamp": self.telescope.sim_time,
                }
                message = json.dumps(state)
                disconnected = set()
                for client in clients:
                    try:
                        await client.send_text(message)
                    except:
                        disconnected.add(client)

                for d in disconnected:
                    clients.remove(d)

            await asyncio.sleep(0.1)

    def run(self):
        """Starts the uvicorn server in the background."""
        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="error")
        server = uvicorn.Server(config)
        self.server_task = asyncio.create_task(server.serve())
        asyncio.create_task(self.broadcast_state())


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        clients.remove(websocket)


@app.get("/")
async def get():
    # Inject geometry into the HTML
    html = INDEX_HTML.replace("MOUNT_GEOMETRY_PLACEHOLDER", json.dumps(mount_geometry))
    return HTMLResponse(content=html)


INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Celestron AUX 3D Console</title>
    <style>
        body { margin: 0; overflow: hidden; background: #1a1b26; color: #7aa2f7; font-family: monospace; }
        #info { position: absolute; top: 10px; left: 10px; background: rgba(26, 27, 38, 0.8); padding: 15px; border: 1px solid #414868; border-radius: 4px; pointer-events: none; }
        #controls { position: absolute; bottom: 10px; left: 10px; color: #565f89; font-size: 12px; }
        canvas { display: block; }
        .warning { color: #f7768e; font-weight: bold; }
        .cyan { color: #7dcfff; }
        .green { color: #9ece6a; }
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
</head>
<body>
    <div id="info">
        <h2 style="margin-top:0">Celestron AUX Digital Twin</h2>
        <div id="telemetry">
            AZM: <span id="azm" class="cyan">0.00</span>°<br>
            ALT: <span id="alt" class="cyan">0.00</span>°<br>
            Status: <span id="status" class="green">IDLE</span>
        </div>
        <div id="collision" class="warning" style="display:none; margin-top:10px">
            ⚠️ POTENTIAL COLLISION DETECTED
        </div>
    </div>
    <div id="controls">Mouse: Rotate | Scroll: Zoom | Right Click: Pan</div>
    <script>
        const geo = MOUNT_GEOMETRY_PLACEHOLDER;
        
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        document.body.appendChild(renderer.domElement);

        const controls = new THREE.OrbitControls(camera, renderer.domElement);

        // Lighting
        const light = new THREE.DirectionalLight(0xffffff, 1);
        light.position.set(5, 10, 5).normalize();
        scene.add(light);
        scene.add(new THREE.AmbientLight(0x404040));

        // Grid & Axis
        scene.add(new THREE.GridHelper(10, 20, 0x414868, 0x24283b));
        
        // --- Mount Model ---
        const mountMaterial = new THREE.MeshPhongMaterial({ color: 0x414868 });
        const otaMaterial = new THREE.MeshPhongMaterial({ color: 0x7aa2f7 });
        const cameraMaterial = new THREE.MeshPhongMaterial({ color: 0xbb9af7 });

        // Base
        const base = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.4, geo.base_height, 32), mountMaterial);
        base.position.y = geo.base_height / 2;
        scene.add(base);

        // Azimuth Group (Rotates around Y)
        const azmGroup = new THREE.Group();
        azmGroup.position.y = geo.base_height;
        scene.add(azmGroup);

        // Fork Arm (Vertical)
        const arm = new THREE.Mesh(new THREE.BoxGeometry(0.15, geo.fork_height, 0.2), mountMaterial);
        arm.position.set(geo.fork_width, geo.fork_height/2, 0);
        azmGroup.add(arm);

        // Pivot Axis (Horizontal connector)
        const pivot = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, geo.fork_width, 16), mountMaterial);
        pivot.rotation.z = Math.PI / 2;
        pivot.position.set(geo.fork_width/2, geo.fork_height * 0.8, 0);
        azmGroup.add(pivot);

        // Altitude Group (Rotates around X in local space)
        const altGroup = new THREE.Group();
        altGroup.position.set(0, geo.fork_height * 0.8, 0);
        azmGroup.add(altGroup);

        // OTA
        const ota = new THREE.Mesh(new THREE.CylinderGeometry(geo.ota_radius, geo.ota_radius, geo.ota_length, 32), otaMaterial);
        // Point OTA along Z-axis at Alt=0
        ota.rotation.x = Math.PI / 2;
        altGroup.add(ota);

        // Visual Back / Camera
        const cam = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.1, geo.camera_length), cameraMaterial);
        // Position at the back of the OTA (negative Z)
        cam.position.set(0, 0, -geo.ota_length/2 - geo.camera_length/2);
        altGroup.add(cam);

        camera.position.set(1.5, 1.5, 1.5);
        controls.target.set(0, 0.5, 0);
        controls.update();

        function animate() {
            requestAnimationFrame(animate);
            renderer.render(scene, camera);
        }
        animate();

        // WebSocket handling
        const ws = new WebSocket('ws://' + window.location.host + '/ws');
        ws.onmessage = function(event) {
            const data = JSON.parse(event.data);
            document.getElementById('azm').innerText = data.azm.toFixed(2);
            document.getElementById('alt').innerText = data.alt.toFixed(2);
            document.getElementById('status').innerText = data.slewing ? 'SLEWING' : (data.guiding ? 'TRACKING' : 'IDLE');

            // Apply rotations
            // Azimuth: Telescope Azm 0 is North (Z+ in our model). 
            azmGroup.rotation.y = -THREE.MathUtils.degToRad(data.azm);
            // Altitude: 0 is Horizontal (Z+), 90 is Zenith (Y+).
            // This is a negative rotation around local X.
            altGroup.rotation.x = -THREE.MathUtils.degToRad(data.alt);

            // Simple Collision Detection
            // Check if camera or back of OTA is too low
            const worldPos = new THREE.Vector3();
            cam.getWorldPosition(worldPos);
            const isCollision = (worldPos.y < geo.base_height + 0.05);
            document.getElementById('collision').style.display = isCollision ? 'block' : 'none';
            otaMaterial.color.setHex(isCollision ? 0xf7768e : 0x7aa2f7);
        };

        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });
    </script>
</body>
</html>
"""
