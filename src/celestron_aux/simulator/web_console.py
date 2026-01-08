"""
Web-based 3D visualization console for the Celestron AUX Simulator.
"""

import asyncio
import json
import math
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
    def __init__(self, telescope, obs, host="127.0.0.1", port=8080):
        self.telescope = telescope
        self.obs = obs
        self.host = host
        self.port = port
        self.server_task = None

        # Load geometry from telescope config
        global mount_geometry
        mount_geometry = self.telescope.config.get("simulator", {}).get(
            "geometry",
            {
                "base_height": 0.18,
                "fork_height": 0.42,
                "fork_width": 0.22,
                "arm_thickness": 0.1,
                "ota_radius": 0.125,  # Slightly larger for better visual 8" look
                "ota_length": 0.43,
                "camera_length": 0.12,
            },
        )

    async def broadcast_state(self):
        """Broadcasts telescope state to all connected clients."""
        from math import pi, degrees, cos, radians
        import ephem

        while True:
            if clients:
                # Update observer time
                self.obs.date = ephem.now()
                self.obs.epoch = self.obs.date

                sky_azm, sky_alt = self.telescope.get_sky_altaz()
                ra, dec = self.obs.radec_of(sky_azm * 2 * pi, sky_alt * 2 * pi)

                # Get nearby stars for schematic sky view
                stars = []
                fov_deg = 30.0  # 30 degree field of view
                for name, body in [
                    ("Polaris", ephem.star("Polaris")),
                    ("Sirius", ephem.star("Sirius")),
                    ("Vega", ephem.star("Vega")),
                    ("Arcturus", ephem.star("Arcturus")),
                    ("Capella", ephem.star("Capella")),
                    ("Rigel", ephem.star("Rigel")),
                    ("Betelgeuse", ephem.star("Betelgeuse")),
                    ("Procyon", ephem.star("Procyon")),
                    ("Altair", ephem.star("Altair")),
                    ("Deneb", ephem.star("Deneb")),
                    ("Spica", ephem.star("Spica")),
                    ("Antares", ephem.star("Antares")),
                    ("Pollux", ephem.star("Pollux")),
                    ("Castor", ephem.star("Castor")),
                ]:
                    try:
                        body.compute(self.obs)
                        # Check if within FOV
                        dist = ephem.separation(
                            (body.az, body.alt), (sky_azm * 2 * pi, sky_alt * 2 * pi)
                        )
                        if dist < radians(fov_deg):
                            # Calculate relative X, Y in FOV [-1, 1]
                            dx = (degrees(body.az) - sky_azm * 360.0) * cos(body.alt)
                            dy = degrees(body.alt) - sky_alt * 360.0
                            stars.append(
                                {
                                    "name": name,
                                    "x": dx / (fov_deg / 2),
                                    "y": dy / (fov_deg / 2),
                                    "mag": body.mag,
                                }
                            )
                    except:
                        continue

                state = {
                    "azm": sky_azm * 360.0,
                    "alt": sky_alt * 360.0,
                    "ra": str(ra),
                    "dec": str(dec),
                    "v_azm": self.telescope.azm_rate * 360.0,
                    "v_alt": self.telescope.alt_rate * 360.0,
                    "slewing": self.telescope.slewing,
                    "guiding": self.telescope.guiding,
                    "voltage": self.telescope.bat_voltage / 1e6,
                    "current": 0.2 + (1.0 if self.telescope.slewing else 0.0),
                    "timestamp": self.telescope.sim_time,
                    "stars": stars,
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
        #info { position: absolute; top: 10px; left: 10px; background: rgba(26, 27, 38, 0.8); padding: 15px; border: 1px solid #414868; border-radius: 4px; pointer-events: none; width: 280px; }
        #sky-view { position: absolute; top: 10px; right: 10px; background: rgba(0, 0, 0, 0.8); border: 1px solid #414868; width: 300px; height: 300px; border-radius: 50%; overflow: hidden; }
        #controls { position: absolute; bottom: 10px; left: 10px; color: #565f89; font-size: 12px; }
        canvas { display: block; }
        .warning { color: #f7768e; font-weight: bold; }
        .cyan { color: #7dcfff; }
        .green { color: #9ece6a; }
        .blue { color: #7aa2f7; }
        .yellow { color: #e0af68; }
        .magenta { color: #bb9af7; }
        .telemetry-row { display: flex; justify-content: space-between; margin-bottom: 4px; }
        .sky-label { position: absolute; bottom: 5px; width: 100%; text-align: center; font-size: 10px; color: #565f89; pointer-events: none; }
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
</head>
<body>
    <div id="info">
        <h2 style="margin-top:0; border-bottom: 1px solid #414868; padding-bottom: 5px;">AUX Digital Twin</h2>
        <div id="telemetry">
            <div class="telemetry-row"><span>AZM:</span> <span id="azm" class="cyan">0.00</span>° (<span id="v_azm" class="blue">0.0</span>°/s)</div>
            <div class="telemetry-row"><span>ALT:</span> <span id="alt" class="cyan">0.00</span>° (<span id="v_alt" class="blue">0.0</span>°/s)</div>
            <div class="telemetry-row"><span>RA:</span> <span id="ra" class="yellow">00:00:00</span></div>
            <div class="telemetry-row"><span>DEC:</span> <span id="dec" class="yellow">+00:00:00</span></div>
            <div class="telemetry-row"><span>Power:</span> <span id="pwr" class="magenta">0.0V</span></div>
            <div class="telemetry-row"><span>Status:</span> <span id="status" class="green">IDLE</span></div>
        </div>
        <div id="collision" class="warning" style="display:none; margin-top:10px">
            ⚠️ POTENTIAL COLLISION DETECTED
        </div>
    </div>
    <div id="sky-view">
        <canvas id="sky-canvas" width="300" height="300"></canvas>
        <div class="sky-label">FOV 30°</div>
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
        
        // --- Utility for text labels ---
        function createLabel(text, color = '#7aa2f7') {
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            canvas.width = 64;
            canvas.height = 64;
            ctx.fillStyle = color;
            ctx.font = 'bold 32px monospace';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(text, 32, 32);
            const texture = new THREE.CanvasTexture(canvas);
            const spriteMaterial = new THREE.SpriteMaterial({ map: texture });
            const sprite = new THREE.Sprite(spriteMaterial);
            sprite.scale.set(0.2, 0.2, 1);
            return sprite;
        }

        // --- Mount Model ---
        const mountMaterial = new THREE.MeshPhongMaterial({ color: 0x414868 });
        const otaMaterial = new THREE.MeshPhongMaterial({ color: 0x7aa2f7 });
        const cameraMaterial = new THREE.MeshPhongMaterial({ color: 0xbb9af7 });
        const scaleMaterial = new THREE.LineBasicMaterial({ color: 0x565f89 });

        // Base
        const base = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.4, geo.base_height, 32), mountMaterial);
        base.position.y = geo.base_height / 2;
        scene.add(base);

        // Azimuth Scale (Ticks every 10 deg)
        const azTicks = new THREE.Group();
        for (let i = 0; i < 360; i += 10) {
            const isMajor = i % 30 === 0;
            const length = isMajor ? 0.1 : 0.05;
            const tickGeom = new THREE.BufferGeometry().setFromPoints([
                new THREE.Vector3(0.45, 0, 0),
                new THREE.Vector3(0.45 + length, 0, 0)
            ]);
            const tick = new THREE.Line(tickGeom, scaleMaterial);
            tick.rotation.y = THREE.MathUtils.degToRad(-i);
            azTicks.add(tick);
            
            if (isMajor) {
                const label = createLabel(i.toString(), '#565f89');
                label.position.set(Math.cos(THREE.MathUtils.degToRad(i)) * 0.65, 0, -Math.sin(THREE.MathUtils.degToRad(i)) * 0.65);
                azTicks.add(label);
            }
        }
        azTicks.position.y = geo.base_height;
        scene.add(azTicks);

        // Cardinal points
        const cardinalN = createLabel("N", "#f7768e"); cardinalN.position.set(0, geo.base_height, 0.8); scene.add(cardinalN);
        const cardinalS = createLabel("S", "#7aa2f7"); cardinalS.position.set(0, geo.base_height, -0.8); scene.add(cardinalS);
        const cardinalE = createLabel("E", "#7aa2f7"); cardinalE.position.set(0.8, geo.base_height, 0); scene.add(cardinalE);
        const cardinalW = createLabel("W", "#7aa2f7"); cardinalW.position.set(-0.8, geo.base_height, 0); scene.add(cardinalW);

        // Azimuth Group (Rotates around Y)
        const azmGroup = new THREE.Group();
        azmGroup.position.y = geo.base_height;
        scene.add(azmGroup);

        // Fork Arm (Vertical)
        const arm = new THREE.Mesh(new THREE.BoxGeometry(geo.arm_thickness, geo.fork_height, 0.2), mountMaterial);
        arm.position.set(geo.fork_width, geo.fork_height/2, 0);
        azmGroup.add(arm);

        // Pivot Axis (Horizontal connector)
        const pivot = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, geo.fork_width, 16), mountMaterial);
        pivot.rotation.z = Math.PI / 2;
        pivot.position.set(geo.fork_width/2, geo.fork_height * 0.8, 0);
        azmGroup.add(pivot);

        // Altitude Scale (Ticks every 10 deg)
        const altTicks = new THREE.Group();
        for (let i = -20; i <= 90; i += 10) {
            const isMajor = i % 30 === 0;
            const length = isMajor ? 0.1 : 0.05;
            const tickGeom = new THREE.BufferGeometry().setFromPoints([
                new THREE.Vector3(0, 0, 0.25),
                new THREE.Vector3(0, length, 0.25)
            ]);
            const tick = new THREE.Line(tickGeom, scaleMaterial);
            tick.position.set(geo.fork_width + geo.arm_thickness/2, geo.fork_height * 0.8, 0);
            tick.rotation.x = THREE.MathUtils.degToRad(-i);
            altTicks.add(tick);
            
            if (isMajor) {
                const label = createLabel(i.toString(), '#565f89');
                label.position.set(geo.fork_width + 0.15, geo.fork_height * 0.8 + Math.sin(THREE.MathUtils.degToRad(i)) * 0.4, Math.cos(THREE.MathUtils.degToRad(i)) * 0.4);
                altTicks.add(label);
            }
        }
        azmGroup.add(altTicks);

        // Altitude Group (Rotates around X in local space)
        const altGroup = new THREE.Group();
        altGroup.position.set(0, geo.fork_height * 0.8, 0);
        azmGroup.add(altGroup);

        // OTA
        const ota = new THREE.Mesh(new THREE.CylinderGeometry(geo.ota_radius, geo.ota_radius, geo.ota_length, 32), otaMaterial);
        ota.rotation.x = Math.PI / 2;
        altGroup.add(ota);

        // Visual Back / Camera
        const cam = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.12, geo.camera_length), cameraMaterial);
        cam.position.set(0, 0, -geo.ota_length/2 - geo.camera_length/2);
        altGroup.add(cam);

        camera.position.set(2, 2, 2);
        controls.target.set(0, 0.5, 0);
        controls.update();

        // Sky View Canvas
        const skyCanvas = document.getElementById('sky-canvas');
        const ctx = skyCanvas.getContext('2d');

        function drawSky(stars) {
            const w = skyCanvas.width;
            const h = skyCanvas.height;
            const center = w / 2;
            
            ctx.fillStyle = 'black';
            ctx.fillRect(0, 0, w, h);
            
            // Draw crosshair
            ctx.strokeStyle = '#414868';
            ctx.beginPath();
            ctx.moveTo(center, center - 30); ctx.lineTo(center, center + 30);
            ctx.moveTo(center - 30, center); ctx.lineTo(center + 30, center);
            ctx.stroke();

            stars.forEach(s => {
                const px = center + s.x * center;
                const py = center - s.y * center;
                // Clip stars outside circular FOV
                const dist = Math.sqrt(Math.pow(px-center, 2) + Math.pow(py-center, 2));
                if (dist > center) return;

                const size = Math.max(1, 7 - s.mag);
                ctx.fillStyle = 'white';
                ctx.beginPath();
                ctx.arc(px, py, size, 0, Math.PI*2);
                ctx.fill();
                if (s.mag < 2.5) {
                    ctx.font = '12px monospace';
                    ctx.fillText(s.name, px + 5, py + 5);
                }
            });
        }

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
            document.getElementById('v_azm').innerText = data.v_azm.toFixed(2);
            document.getElementById('alt').innerText = data.alt.toFixed(2);
            document.getElementById('v_alt').innerText = data.v_alt.toFixed(2);
            document.getElementById('ra').innerText = data.ra;
            document.getElementById('dec').innerText = data.dec;
            document.getElementById('pwr').innerText = data.voltage.toFixed(1) + 'V (' + data.current.toFixed(1) + 'A)';
            document.getElementById('status').innerText = data.slewing ? 'SLEWING' : (data.guiding ? 'TRACKING' : 'IDLE');

            // Apply rotations
            azmGroup.rotation.y = -THREE.MathUtils.degToRad(data.azm);
            altGroup.rotation.x = -THREE.MathUtils.degToRad(data.alt);

            // Collision Detection
            const worldPos = new THREE.Vector3();
            cam.getWorldPosition(worldPos);
            const isCollision = (worldPos.y < geo.base_height + 0.05);
            document.getElementById('collision').style.display = isCollision ? 'block' : 'none';
            otaMaterial.color.setHex(isCollision ? 0xf7768e : 0x7aa2f7);

            // Draw sky view
            drawSky(data.stars || []);
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
