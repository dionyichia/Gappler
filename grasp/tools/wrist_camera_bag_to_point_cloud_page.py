#!/usr/bin/env python3
"""Turn one frame of a wrist camera bag into an interactive 3D point cloud page (T1.32).

Uses the same maths as anygrasp_detection_node.py build_point_cloud, so what you see is what
AnyGrasp gets, before the SAM 3 mask. Open the page in a browser, drag to rotate. Needs ROS 2
(rosbag2_py), so run it on the lab box, then copy the page to your machine:

  source /opt/ros/humble/setup.bash
  python3 grasp/tools/wrist_camera_bag_to_point_cloud_page.py assets/recordings/wrist_camera \
      /tmp/wrist_camera_point_cloud.html [FRAME]        FRAME default: the middle one

The bag needs colour, aligned depth and colour camera info, as record_wrist_camera.sh records.
Every 2nd pixel each way is kept, points 0 to 1.5 m (the node's depth range), about 3 MB a page.
"""
import json
import os
import sys

import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import CameraInfo, Image

COLOUR = "/camera/camera/color/image_raw"
DEPTH = "/camera/camera/aligned_depth_to_color/image_raw"
INFO = "/camera/camera/color/camera_info"
DEPTH_SCALE_M = 0.001  # shared/global_config.yaml wrist_camera.depth_scale_m
MAX_Z_M = 1.5          # anygrasp_detection_node.py keeps depth under 1.5 m


def stamp(m):
    return m.header.stamp.sec + m.header.stamp.nanosec * 1e-9


def main(bag, out, frame=None):
    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=bag, storage_id="sqlite3"),
                rosbag2_py.ConverterOptions("", ""))
    types = {COLOUR: Image, DEPTH: Image, INFO: CameraInfo}
    msgs = {t: [] for t in types}
    while reader.has_next():
        topic, data, _ = reader.read_next()
        if topic in types:
            msgs[topic].append(deserialize_message(data, types[topic]))
    n = len(msgs[DEPTH]) // 2 if frame is None else int(frame)
    d = msgs[DEPTH][n]
    c = min(msgs[COLOUR], key=lambda m: abs(stamp(m) - stamp(d)))
    k = msgs[INFO][0].k
    fx, fy, cx, cy = k[0], k[4], k[2], k[5]
    z = np.frombuffer(d.data, np.uint16).reshape(d.height, d.width) * DEPTH_SCALE_M
    rgb = np.frombuffer(c.data, np.uint8).reshape(c.height, c.width, 3)
    if c.encoding == "bgr8":
        rgb = rgb[:, :, ::-1]
    v, u = np.mgrid[0:d.height, 0:d.width]
    keep = (z > 0) & (z < MAX_Z_M)
    keep[1::2, :] = keep[:, 1::2] = False
    pts = np.stack([(u - cx) * z / fx, (v - cy) * z / fy, z], -1)[keep]
    data = {"name": f"{os.path.basename(os.path.normpath(bag))}, frame {n} of {len(msgs[DEPTH])}",
            "intr": [fx, fy, cx, cy], "w": d.width, "h": d.height,
            "p": np.round(pts, 4).ravel().tolist(), "c": rgb[keep].ravel().tolist()}
    with open(out, "w") as f:
        f.write(PAGE.replace("__DATA__", json.dumps(data)))
    print(f"{out}: frame {n}, {len(pts)} points, z {z[keep].min():.3f} to {z[keep].max():.3f} m")


PAGE = r"""<title>Wrist Camera Point Cloud</title>
<style>
/* Layout: a full-width 3D viewport with a slim control strip above it and short notes below. */
:root{
  --bg:#f4f6f8; --panel:#ffffff; --ink:#17202b; --ink-2:#4d5866; --line:#d6dce4;
  --accent:#0f6e8c; --view:#0b1016;
  --body:'IBM Plex Sans',-apple-system,'Segoe UI',sans-serif;
  --mono:'IBM Plex Mono','SF Mono',Consolas,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#12171d; --panel:#1a2129; --ink:#e6ebf0; --ink-2:#a3aeba; --line:#2c3540; --accent:#5cb8d6; color-scheme:dark}}
:root[data-theme="dark"]{--bg:#12171d; --panel:#1a2129; --ink:#e6ebf0; --ink-2:#a3aeba; --line:#2c3540; --accent:#5cb8d6; color-scheme:dark}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font-family:var(--body);font-size:15px;line-height:1.55;margin:0;padding-inline:16px;padding-block:20px 40px}
.wrap{max-width:1100px;margin:0 auto;display:flex;flex-direction:column;gap:14px}
h1{font-size:24px;margin:0;text-wrap:balance}
.meta{font-family:var(--mono);font-size:12.5px;color:var(--ink-2);display:flex;flex-wrap:wrap;gap:6px 18px}
.controls{display:flex;flex-wrap:wrap;gap:10px 22px;align-items:center;background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:10px 14px}
.controls label{font-size:13.5px;color:var(--ink-2);display:flex;gap:8px;align-items:center}
.controls input[type=range]{width:180px;accent-color:var(--accent)}
.controls output{font-family:var(--mono);font-size:12.5px;color:var(--ink);min-width:58px;font-variant-numeric:tabular-nums}
button{font:inherit;font-size:13.5px;padding:5px 12px;border-radius:4px;border:1px solid var(--line);background:var(--bg);color:var(--ink);cursor:pointer}
button[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:#fff}
button:focus-visible,input:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
#view{width:100%;aspect-ratio:16/10;max-width:100%;background:var(--view);border-radius:6px;overflow:hidden;touch-action:none}
#view canvas{display:block;width:100%!important;height:100%!important}
.hint{font-size:13px;color:var(--ink-2);margin:0}
.notes{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}
.notes section{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:14px 16px;min-width:0}
.notes h2{font-size:15px;margin:0 0 6px}
.notes p{margin:0 0 8px;color:var(--ink-2);font-size:14px;max-width:65ch}
code{font-family:var(--mono);font-size:.88em}
</style>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400&family=IBM+Plex+Sans:wght@400;600&display=swap">
<div class="wrap">
  <h1>Wrist camera point cloud</h1>
  <div class="meta" id="meta"></div>
  <div class="controls">
    <label for="far">Hide points further than <input id="far" type="range" min="0.40" max="1.50" step="0.01" value="0.70"><output id="farv"></output></label>
    <label for="size">Point size <input id="size" type="range" min="1" max="6" step="0.5" value="2"><output id="sizev"></output></label>
    <span style="display:flex;gap:6px"><button id="mRgb" aria-pressed="true">Camera colours</button><button id="mDepth" aria-pressed="false">Colour by depth</button></span>
    <button id="reset">Back to camera view</button>
  </div>
  <div id="view" role="img" aria-label="3D point cloud from the wrist camera, drag to rotate"></div>
  <p class="hint">Drag to rotate, scroll or pinch to zoom, right-drag or two-finger drag to pan. It opens from the camera's own viewpoint. Rotate sideways to see the depth: the box stands out as a block in front of the mat.</p>
  <div class="notes">
    <section><h2>What you are looking at</h2>
      <p>Every dot is one pixel of the colour image placed in 3D using its depth reading. Same maths as <code>anygrasp_detection_node.py:146-152</code>: x = (u - cx) z / fx, y = (v - cy) z / fy, z = depth.</p>
      <p>Every 2nd pixel each way is shown, so a quarter of the points. This is the whole scene. AnyGrasp only gets the points inside the SAM 3 mask, the box.</p></section>
    <section><h2>What to look for</h2>
      <p>Only the faces turned to the camera exist. The back of the box is missing, there is a shadow behind it on the mat where the camera could not see.</p>
      <p>Around the box edges you may see stray dots hanging between the box and the mat. These are flying pixels: the depth sensor mixes the near and far surface at an edge. They are why the width check uses percentiles, not the extreme points.</p></section>
    <section><h2>How the width check uses it (T1.32)</h2>
      <p>For each grasp, keep the box points inside the space the fingers sweep: the 50 mm inside the U, pad-tall, along the closing direction. Their spread along the closing direction is the width the pads close on. Over the limit, the grasp is dropped.</p></section>
  </div>
</div>
<script id="cloud" type="application/json">__DATA__</script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
(function(){
  const D = JSON.parse(document.getElementById('cloud').textContent);
  const n = D.p.length/3;
  const [fx,fy,cx,cy] = D.intr;
  document.getElementById('meta').innerHTML =
    `<span>${D.name}</span><span>${D.w}x${D.h}</span><span>fx ${fx.toFixed(1)} fy ${fy.toFixed(1)}</span><span>${n.toLocaleString()} points shown</span>`;
  const view = document.getElementById('view');
  const renderer = new THREE.WebGLRenderer({antialias:true});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio,2));
  view.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  const cam = new THREE.PerspectiveCamera(2*Math.atan(D.h/2/fy)*180/Math.PI, 16/10, 0.01, 20);
  // camera optical frame (x right, y down, z forward) -> three.js (x right, y up, looking along -z)
  const pos = new Float32Array(n*3), rgb = new Float32Array(n*3), dep = new Float32Array(n*3);
  let zs = [];
  for(let i=0;i<n;i++){
    const x=D.p[3*i], y=D.p[3*i+1], z=D.p[3*i+2];
    pos[3*i]=x; pos[3*i+1]=-y; pos[3*i+2]=-z; zs.push(z);
    rgb[3*i]=D.c[3*i]/255; rgb[3*i+1]=D.c[3*i+1]/255; rgb[3*i+2]=D.c[3*i+2]/255;
    const t=Math.min(1,Math.max(0,(z-0.35)/0.9)); const col=new THREE.Color().setHSL(0.55-0.55*t,0.85,0.55);
    dep[3*i]=col.r; dep[3*i+1]=col.g; dep[3*i+2]=col.b;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos,3));
  const colAttr = new THREE.BufferAttribute(rgb.slice(),3); geo.setAttribute('color', colAttr);
  const mat = new THREE.PointsMaterial({size:2, sizeAttenuation:false, vertexColors:true});
  scene.add(new THREE.Points(geo, mat));
  // a small marker at the camera lens
  const axes = new THREE.AxesHelper(0.05); scene.add(axes);
  const controls = new THREE.OrbitControls(cam, renderer.domElement);
  zs.sort((a,b)=>a-b); const zMed = zs[Math.floor(zs.length*0.2)];
  function home(){ cam.position.set(0,0,0.001); controls.target.set(0,0,-zMed); controls.update(); }
  home();
  const far=document.getElementById('far'), size=document.getElementById('size');
  function applyFar(){
    const f=+far.value; document.getElementById('farv').textContent=f.toFixed(2)+' m';
    const idx=[];
    for(let i=0;i<n;i++) if(-pos[3*i+2]<=f) idx.push(i);
    geo.setIndex(idx);
  }
  far.addEventListener('input',()=>{applyFar();draw();});
  size.addEventListener('input',()=>{mat.size=+size.value;document.getElementById('sizev').textContent=size.value+' px';draw();});
  document.getElementById('sizev').textContent=size.value+' px';
  const bR=document.getElementById('mRgb'), bD=document.getElementById('mDepth');
  function mode(d){ colAttr.array.set(d?dep:rgb); colAttr.needsUpdate=true; bR.setAttribute('aria-pressed',String(!d)); bD.setAttribute('aria-pressed',String(d)); draw(); }
  bR.onclick=()=>mode(false); bD.onclick=()=>mode(true);
  document.getElementById('reset').onclick=()=>{home();draw();};
  function resize(){ const w=view.clientWidth, h=view.clientHeight; renderer.setSize(w,h,false); cam.aspect=w/h; cam.updateProjectionMatrix(); draw(); }
  function draw(){ renderer.render(scene,cam); }
  controls.addEventListener('change',draw);
  window.addEventListener('resize',resize);
  applyFar(); resize();
})();
</script>
"""

if __name__ == "__main__":
    main(*sys.argv[1:])
