#!/usr/bin/env python3
"""Standalone LD2410 web tuner.

This is intentionally separate from the HUB75 clock runtime, MQTT, and HA.
Stop the clock first so this process owns the LD2410 UART, then run:

  sudo systemctl stop hub75-clock hub75-ld2410-tuner
  sudo python3 tools/ld2410-web-tuner.py

Open http://hub75-clock.local:8766/ from your phone/computer.
"""

from __future__ import annotations

import argparse
import json
import struct
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

try:
    import serial
except Exception as exc:
    raise SystemExit(f"pyserial is required for the LD2410 web tuner: {exc}")


CMD_HEAD = b"\xFD\xFC\xFB\xFA"
CMD_TAIL = b"\x04\x03\x02\x01"
DATA_HEAD = b"\xF4\xF3\xF2\xF1"
DATA_TAIL = b"\xF8\xF7\xF6\xF5"


def hex_bytes(data):
    if not data:
        return ""
    return bytes(data).hex(" ")


def command_name(cmd):
    names = {
        0xFF: "enter_config",
        0xFE: "end_config",
        0x62: "engineering_on",
        0x63: "engineering_off",
        0x64: "write_gate",
        0x61: "read_parameters",
    }
    return names.get(cmd[0], f"cmd_0x{cmd[0]:02x}")


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LD2410 Direct Tuner</title>
<style>
:root{--bg:#101116;--panel:#1b1c24;--panel2:#242630;--border:#393b49;--text:#e3e5ee;--dim:#8d91a6;--move:#68d391;--still:#63b3ed;--move-thresh:#f6ad55;--still-thresh:#f687b3;--danger:#fc8181;--accent:#a3bffa}
*{box-sizing:border-box;margin:0;padding:0}
body{min-height:100vh;background:var(--bg);color:var(--text);font:14px/1.4 system-ui,-apple-system,Segoe UI,sans-serif}
.app{max-width:980px;margin:0 auto;padding:12px;display:flex;flex-direction:column;gap:12px}
.top{display:flex;gap:8px;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:2;background:linear-gradient(var(--bg),rgba(16,17,22,.92));padding:6px 0 10px}
h1{font-size:18px;color:#c7d2fe}.state{font-size:12px;color:var(--dim)}
.card{background:var(--panel);border:1px solid var(--border);border-radius:8px;overflow:hidden}
.card-h{padding:10px 12px;background:var(--panel2);font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--dim);font-weight:700}
.card-b{padding:12px}.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.btn{border:1px solid var(--border);border-radius:6px;background:#2b2d38;color:var(--text);padding:10px 12px;font:inherit;box-shadow:0 2px 0 #171923;transition:transform .05s ease,box-shadow .05s ease,background .12s ease}.btn:hover{background:#343744}.btn:active{transform:translateY(2px);box-shadow:0 0 0 #171923;background:#242631}.btn.primary{border-color:var(--accent);background:#30364a}.btn.primary:hover{background:#39415a}.btn.primary:active{background:#283047}.btn.danger{border-color:var(--danger)}.btn.danger:hover{background:#3a2d36}.btn.danger:active{background:#2f252d}
.metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.metric{background:#14151c;border:1px solid #2b2d38;border-radius:6px;padding:8px}.metric span{display:block;color:var(--dim);font-size:11px}.metric strong{font-size:20px}.warn{display:none;margin-top:8px;color:#fbd38d;font-size:12px}.warn.show{display:block}.hex{display:block;max-height:80px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;color:#cbd5e1;font:11px/1.35 ui-monospace,SFMono-Regular,Consolas,monospace}
canvas{width:100%;height:auto;display:block;background:#08090d;border-radius:6px;border:1px solid #2b2d38;touch-action:none;cursor:crosshair}
.gate-readout{margin-top:10px;display:grid;grid-template-columns:repeat(9,minmax(72px,1fr));gap:6px}.gate-cell{background:#14151c;border:1px solid #2b2d38;border-radius:6px;padding:7px;font-variant-numeric:tabular-nums}.gate-cell strong{display:block;color:#cbd5e1;font-size:13px}.gate-cell span{display:block;color:var(--dim);font-size:11px}.gate-cell b{font-weight:700}.gate-cell .mv{color:var(--move)}.gate-cell .st{color:var(--still)}.gate-cell .th{color:var(--dim)}
.gate{display:grid;grid-template-columns:64px 1fr 46px;gap:8px;align-items:center;padding:9px 0;border-bottom:1px solid #2b2d38}.gate:last-child{border-bottom:0}.gate label{font-weight:700;color:#cbd5e1;line-height:1.1}.gate label span{display:block;margin-top:2px;color:var(--dim);font-size:11px;font-weight:500}.gate .value{text-align:right;color:var(--dim);font-variant-numeric:tabular-nums}
input[type=range]{width:100%;accent-color:var(--move-thresh)}.hint{color:var(--dim);font-size:12px}.legend{display:flex;gap:12px;flex-wrap:wrap}.key{display:inline-flex;gap:6px;align-items:center}.dot{width:12px;height:12px;border-radius:3px}.move{background:var(--move)}.still{background:var(--still)}.move-thresh{background:var(--move-thresh)}.still-thresh{background:var(--still-thresh)}
@media (max-width:840px){.gate-readout{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media (max-width:640px){.app{padding:8px}.top{align-items:flex-start}.metrics{grid-template-columns:1fr}.card-b{padding:10px}.btn{flex:1}.gate{grid-template-columns:58px 1fr 42px}.gate-readout{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
</head>
<body>
<main class="app">
  <div class="top">
    <div><h1>LD2410 Direct Tuner</h1><div class="state" id="status">Connecting...</div></div>
    <div class="row"><button class="btn" id="btn-read">Read Thresholds</button><button class="btn primary" id="btn-save">Save Thresholds</button><button class="btn danger" id="btn-engineering">Engineering</button><button class="btn danger" id="btn-stop">Stop Tuner</button></div>
  </div>

  <section class="card">
    <div class="card-h">Live Gate Energy</div>
    <div class="card-b">
      <canvas id="graph" width="900" height="360"></canvas>
      <div class="legend" style="margin-top:10px">
        <span class="key"><span class="dot move"></span>Move energy</span>
        <span class="key"><span class="dot still"></span>Still energy</span>
        <span class="key"><span class="dot move-thresh"></span>Move threshold</span>
        <span class="key"><span class="dot still-thresh"></span>Still threshold</span>
      </div>
      <div class="gate-readout" id="gate-readout"></div>
    </div>
  </section>

  <section class="card">
    <div class="card-h">Current Target</div>
    <div class="card-b metrics">
      <div class="metric"><span>Presence</span><strong id="presence">-</strong></div>
      <div class="metric"><span>Target State</span><strong id="target">-</strong></div>
      <div class="metric"><span>Move Distance</span><strong id="move-distance">-</strong></div>
      <div class="metric"><span>Still Distance</span><strong id="still-distance">-</strong></div>
      <div class="metric"><span>Max Move Gate</span><strong id="max-move-gate">-</strong></div>
      <div class="metric"><span>Max Still Gate</span><strong id="max-still-gate">-</strong></div>
    </div>
  </section>

  <section class="card">
    <div class="card-h">Protocol Debug</div>
    <div class="card-b">
      <div class="metrics">
        <div class="metric"><span>Report Type</span><strong id="report-type">-</strong></div>
        <div class="metric"><span>Target State</span><strong id="debug-target">-</strong></div>
        <div class="metric"><span>Last Command</span><strong id="last-command">-</strong></div>
        <div class="metric"><span>Last ACK</span><code class="hex" id="last-ack">-</code></div>
      </div>
      <div class="metric" style="margin-top:8px"><span>Last Data Frame</span><code class="hex" id="last-data-frame">-</code></div>
      <div class="warn" id="engineering-warning">Engineering mode is on, but only basic frames are arriving.</div>
    </div>
  </section>

  <section class="card">
    <div class="card-h">Move Thresholds</div>
    <div class="card-b" id="move-sliders"></div>
  </section>

  <section class="card">
    <div class="card-h">Still Thresholds</div>
    <div class="card-b" id="still-sliders"></div>
  </section>

  <section class="card">
    <div class="card-h">Notes</div>
    <div class="card-b">
      <p class="hint">This standalone tuner talks directly to the LD2410 UART. Stop hub75-clock before using it. Read and save thresholds with the buttons at the top.</p>
    </div>
  </section>
</main>
<script>
'use strict';
const state={move_gates:Array(9).fill(0),still_gates:Array(9).fill(0),move_thresholds:Array(9).fill(50),still_thresholds:Array(9).fill(30),engineering:false,engineering_verified:false,engineering_warning:'',presence:null,last_report_type:null,last_target_state:null,last_data_frame_hex:'',last_command_ack_hex:'',last_command_name:''};
const el=id=>document.getElementById(id);
let activeSlider=null,graphDrag=null;
const holdUntil={};
function clamp(v,min,max){return Math.max(min,Math.min(max,v))}
function ft(cm){return (Number(cm||0)/30.48).toFixed(1)+' ft'}
function gateFt(i){return ((i*0.75)/0.3048).toFixed(1)+' ft'}
function sliderKey(kind,i){return `${kind}:${i}`}
function holdSlider(kind,i,ms=2000){holdUntil[sliderKey(kind,i)]=Date.now()+ms}
function releaseSlider(kind,i,ms=900){const key=sliderKey(kind,i);holdSlider(kind,i,ms);if(activeSlider===key)setTimeout(()=>{if(activeSlider===key)activeSlider=null},ms)}
function sliderHeld(kind,i){const key=sliderKey(kind,i);return activeSlider===key||(holdUntil[key]||0)>Date.now()}
function graphLayout(){const c=el('graph'),pad=34,plotW=c.width-pad*2,plotH=c.height-pad*2,group=plotW/9;return {c,pad,plotW,plotH,group}}
function yForThreshold(v){const g=graphLayout();return g.pad+g.plotH-(clamp(v,0,100)/100)*g.plotH}
function thresholdFromY(y){const g=graphLayout();return Math.round(clamp(((g.pad+g.plotH-y)/g.plotH)*100,0,100))}
function graphPoint(evt){const c=el('graph'),r=c.getBoundingClientRect();return {x:(evt.clientX-r.left)*(c.width/r.width),y:(evt.clientY-r.top)*(c.height/r.height)}}
function graphGateFromX(x){const g=graphLayout();return clamp(Math.floor((x-g.pad)/g.group),0,8)}
function setLocalThreshold(kind,i,value){value=clamp(parseInt(value)||0,0,100);state[kind+'_thresholds'][i]=value;holdSlider(kind,i,2500);const row=el(kind+'-sliders').querySelectorAll('.gate')[i];if(row){row.querySelector('input').value=value;row.querySelector('.value').textContent=value}updateGateReadout();draw()}
function nearestThreshold(pt){const gate=graphGateFromX(pt.x);let best=null;for(const kind of ['move','still']){const value=state[kind+'_thresholds'][gate]??0;const dist=Math.abs(pt.y-yForThreshold(value));if(!best||dist<best.dist)best={kind,gate,dist}}return best&&best.dist<=28?best:{kind:'move',gate,dist:999}}
function gateRow(kind,i){const row=document.createElement('div');row.className='gate';row.innerHTML=`<label>G${i}<span>${gateFt(i)}</span></label><input type="range" min="0" max="100" step="1" value="${state[kind+'_thresholds'][i]}"><span class="value">${state[kind+'_thresholds'][i]}</span>`;const input=row.querySelector('input');const begin=()=>{activeSlider=sliderKey(kind,i);holdSlider(kind,i,2500)};const end=()=>releaseSlider(kind,i,1600);input.addEventListener('pointerdown',begin);input.addEventListener('touchstart',begin,{passive:true});input.addEventListener('focus',begin);input.addEventListener('pointerup',end);input.addEventListener('pointercancel',end);input.addEventListener('blur',end);input.oninput=()=>{begin();setLocalThreshold(kind,i,input.value)};input.onchange=()=>{releaseSlider(kind,i,3000)};return row}
function buildGateReadout(){const wrap=el('gate-readout');wrap.innerHTML='';for(let i=0;i<9;i++){const cell=document.createElement('div');cell.className='gate-cell';cell.innerHTML=`<strong>G${i} <span>${gateFt(i)}</span></strong><span>Move <b class="mv" data-field="move">0</b> / <b class="th" data-field="move-thresh">0</b></span><span>Still <b class="st" data-field="still">0</b> / <b class="th" data-field="still-thresh">0</b></span>`;wrap.appendChild(cell)}}
function buildSliders(){const m=el('move-sliders'),s=el('still-sliders');m.innerHTML='';s.innerHTML='';for(let i=0;i<9;i++){m.appendChild(gateRow('move',i));s.appendChild(gateRow('still',i))}}
function updateGateReadout(){[...el('gate-readout').querySelectorAll('.gate-cell')].forEach((cell,i)=>{cell.querySelector('[data-field="move"]').textContent=state.move_gates[i]??0;cell.querySelector('[data-field="still"]').textContent=state.still_gates[i]??0;cell.querySelector('[data-field="move-thresh"]').textContent=state.move_thresholds[i]??0;cell.querySelector('[data-field="still-thresh"]').textContent=state.still_thresholds[i]??0})}
function updateSliderValues(){for(const kind of ['move','still']){const wrap=el(kind+'-sliders');[...wrap.querySelectorAll('.gate')].forEach((row,i)=>{const input=row.querySelector('input'), value=row.querySelector('.value');const v=state[kind+'_thresholds'][i]??0;if(sliderHeld(kind,i)){value.textContent=input.value;return}input.value=v;value.textContent=v})}}
function mergeThresholds(kind,values){if(!Array.isArray(values))return;const key=kind+'_thresholds';state[key]=state[key]||Array(9).fill(0);for(let i=0;i<9;i++){if(sliderHeld(kind,i))continue;if(values[i]!==undefined)state[key][i]=values[i]}}
async function api(path,body){const ctrl=new AbortController();const timer=setTimeout(()=>ctrl.abort(),20000);const opts=body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{cache:'no-store'};try{opts.signal=ctrl.signal;const r=await fetch(path,opts);const d=await r.json();if(!r.ok||!d.ok)throw new Error(d.error||'request failed');return d}catch(e){if(e.name==='AbortError')throw new Error('request timed out');throw e}finally{clearTimeout(timer)}}
async function saveThresholds(){try{const d=await api('/api/thresholds',{move:state.move_thresholds,still:state.still_thresholds});applyState(d.state,true);el('status').textContent='Saved thresholds'}catch(e){el('status').textContent=e.message}}
async function setEngineering(enable){try{await api('/api/engineering',{enable});state.engineering=enable;updateEngineeringButton()}catch(e){el('status').textContent=e.message}}
async function readSensor(){try{const d=await api('/api/read',{read:true});applyState(d.state,true);el('status').textContent=d.read?'Read thresholds':'No threshold response'}catch(e){el('status').textContent=e.message}}
async function stopTuner(){try{await api('/api/stop',{stop:true});el('status').textContent='Tuner stopping...'}catch(e){el('status').textContent=e.message}}
function updateEngineeringButton(){const b=el('btn-engineering');b.textContent=state.engineering?'Engineering On':'Engineering Off';b.classList.toggle('primary',state.engineering)}
function targetLabel(v){return {0:'0 = Clear',1:'1 = Moving',2:'2 = Still',3:'3 = Moving + Still'}[Number(v)]??(v==null?'-':String(v))}
function reportLabel(v){return {1:'0x01 = Engineering',2:'0x02 = Basic'}[Number(v)]??(v==null?'-':'0x'+Number(v).toString(16).padStart(2,'0'))}
function draw(){const layout=graphLayout(),c=layout.c,ctx=c.getContext('2d'),w=c.width,h=c.height,pad=layout.pad,plotH=layout.plotH;ctx.clearRect(0,0,w,h);ctx.fillStyle='#08090d';ctx.fillRect(0,0,w,h);ctx.strokeStyle='#242630';ctx.lineWidth=1;ctx.font='18px system-ui';ctx.fillStyle='#8d91a6';for(let v=0;v<=100;v+=25){const y=pad+plotH-(v/100)*plotH;ctx.beginPath();ctx.moveTo(pad,y);ctx.lineTo(w-pad,y);ctx.stroke();ctx.fillText(v,6,y+6)}const group=layout.group,barW=Math.max(10,group*.24);for(let i=0;i<9;i++){const x=pad+i*group+group*.18;ctx.fillStyle='#8d91a6';ctx.fillText('G'+i,x+group*.2,h-8);bar(x,state.move_gates[i],barW,'#68d391');bar(x+barW+4,state.still_gates[i],barW,'#63b3ed');line(x,state.move_thresholds[i],group*.75,'#f6ad55');line(x,state.still_thresholds[i],group*.75,'#f687b3')}function yFor(v){return pad+plotH-(clamp(v,0,100)/100)*plotH}function bar(x,v,bw,color){ctx.fillStyle=color;const y=yFor(v);ctx.fillRect(x,y,bw,pad+plotH-y)}function line(x,v,len,color){ctx.strokeStyle=color;ctx.lineWidth=4;const y=yFor(v);ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x+len,y);ctx.stroke()}}
function applyState(d,updateThresholds=false){const next=Object.assign({},d);delete next.move_thresholds;delete next.still_thresholds;Object.assign(state,next);if(updateThresholds){mergeThresholds('move',d.move_thresholds);mergeThresholds('still',d.still_thresholds)}el('presence').textContent=state.presence===null?'-':(state.presence?'Yes':'No');el('target').textContent=targetLabel(state.target_state);el('move-distance').textContent=state.move_distance==null?'-':ft(state.move_distance);el('still-distance').textContent=state.still_distance==null?'-':ft(state.still_distance);el('max-move-gate').textContent=state.max_move_gate==null?'-':'G'+state.max_move_gate+' / '+gateFt(state.max_move_gate);el('max-still-gate').textContent=state.max_still_gate==null?'-':'G'+state.max_still_gate+' / '+gateFt(state.max_still_gate);el('report-type').textContent=reportLabel(state.last_report_type);el('debug-target').textContent=targetLabel(state.last_target_state);el('last-command').textContent=state.last_command_name||'-';el('last-ack').textContent=state.last_command_ack_hex||'-';el('last-data-frame').textContent=state.last_data_frame_hex||'-';el('engineering-warning').textContent=state.engineering_warning||'Engineering mode is on, but only basic frames are arriving.';el('engineering-warning').classList.toggle('show',!!state.engineering_warning);updateSliderValues();updateGateReadout();updateEngineeringButton();draw()}
async function poll(){try{const d=await api('/api/state');applyState(d.state);el('status').textContent='Live'}catch(e){el('status').textContent=e.message}}
function graphPointerDown(evt){const hit=nearestThreshold(graphPoint(evt));graphDrag={kind:hit.kind,gate:hit.gate};activeSlider=sliderKey(hit.kind,hit.gate);el('graph').setPointerCapture?.(evt.pointerId);graphPointerMove(evt)}
function graphPointerMove(evt){if(!graphDrag)return;evt.preventDefault();setLocalThreshold(graphDrag.kind,graphDrag.gate,thresholdFromY(graphPoint(evt).y))}
async function graphPointerUp(evt){if(!graphDrag)return;const drag=graphDrag;graphPointerMove(evt);graphDrag=null;releaseSlider(drag.kind,drag.gate,3000)}
el('btn-engineering').onclick=()=>setEngineering(!state.engineering);el('btn-read').onclick=()=>readSensor();el('btn-save').onclick=()=>saveThresholds();el('btn-stop').onclick=()=>stopTuner();el('graph').addEventListener('pointerdown',graphPointerDown);el('graph').addEventListener('pointermove',graphPointerMove);el('graph').addEventListener('pointerup',graphPointerUp);el('graph').addEventListener('pointercancel',graphPointerUp);buildGateReadout();buildSliders();draw();poll();setInterval(poll,500);
</script>
</body>
</html>"""


def clamp(value, low=0, high=100):
    return max(low, min(high, int(value)))


def json_response(handler, status, payload):
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class DirectTuner:
    def __init__(self, port, baud):
        self.port = port
        self.baud = baud
        self.serial = serial.Serial(port, baud, timeout=0.05)
        self.lock = threading.Lock()
        self.write_lock = threading.Lock()
        self.command_lock = threading.Lock()
        self.responses = deque(maxlen=20)
        self.buf = bytearray()
        self.running = True
        self.engineering_enabled_at = None
        self.data = {
            "move_gates": [0] * 9,
            "still_gates": [0] * 9,
            "move_thresholds": [50] * 9,
            "still_thresholds": [30] * 9,
            "presence": None,
            "target_state": None,
            "move_distance": None,
            "still_distance": None,
            "engineering": False,
            "engineering_verified": False,
            "engineering_warning": "",
            "max_gate": 8,
            "max_move_gate": 8,
            "max_still_gate": 8,
            "timeout_seconds": None,
            "updated_at": None,
            "last_report_type": None,
            "last_target_state": None,
            "last_data_frame_hex": "",
            "last_command_ack_hex": "",
            "last_command_name": "",
        }
        self.thread = threading.Thread(target=self.read_loop, daemon=True)
        self.thread.start()
        self.ensure_engineering(True)

    def close(self):
        try:
            self.set_engineering(False)
        except Exception:
            pass
        self.running = False
        self.thread.join(timeout=1.0)
        self.serial.close()

    def snapshot(self):
        with self.lock:
            existing_warning = self.data.get("engineering_warning", "")
            if (
                self.data["engineering"]
                and not self.data["engineering_verified"]
                and self.engineering_enabled_at
                and time.time() - self.engineering_enabled_at > 2.0
            ):
                self.data["engineering_warning"] = "Engineering mode is on, but no engineering frames have arrived yet."
            elif self.data["engineering"] and self.data.get("last_report_type") == 0x02:
                self.data["engineering_warning"] = "Engineering mode is on, but the latest frame is still a basic report."
            elif not existing_warning:
                self.data["engineering_warning"] = ""
            return json.loads(json.dumps(self.data))

    def send_cmd(self, cmd, data=b""):
        payload = cmd + data
        frame = CMD_HEAD + struct.pack("<H", len(payload)) + payload + CMD_TAIL
        with self.write_lock:
            self.serial.write(frame)
            self.serial.flush()
        time.sleep(0.08)

    def send_cmd_wait(self, cmd, data=b"", timeout=1.0, name=None, expected_cmds=None, require_ok=False):
        expected_cmds = tuple(expected_cmds or (cmd[0],))
        cmd_name = name or command_name(cmd)
        with self.lock:
            self.responses.clear()
            self.data["last_command_name"] = cmd_name
        self.send_cmd(cmd, data)
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self.lock:
                for response in list(self.responses):
                    if len(response) >= 2 and response[0] in expected_cmds and response[1] == ((cmd[1] + 1) & 0xFF):
                        self.data["last_command_ack_hex"] = hex_bytes(response)
                        if require_ok and (len(response) < 4 or response[2:4] != b"\x00\x00"):
                            return None
                        return response
            time.sleep(0.02)
        return None

    def drain_responses(self):
        with self.lock:
            self.responses.clear()

    def enter_config(self):
        for _ in range(3):
            ack = self.send_cmd_wait(b"\xFF\x00", timeout=2.5, require_ok=True)
            if ack:
                return ack
            time.sleep(0.15)
        raise RuntimeError("LD2410 did not enter config mode")

    def end_config(self):
        for _ in range(3):
            ack = self.send_cmd_wait(b"\xFE\x00", timeout=2.5, require_ok=True)
            if ack:
                return ack
            time.sleep(0.15)
        raise RuntimeError("LD2410 did not exit config mode")

    def ensure_engineering(self, enable):
        try:
            self.set_engineering(enable)
            return True
        except Exception as exc:
            with self.lock:
                self.data["engineering"] = False
                self.data["engineering_verified"] = False
                self.data["last_command_name"] = "engineering_on" if enable else "engineering_off"
                self.data["engineering_warning"] = str(exc)
                self.engineering_enabled_at = None
            return False

    def set_engineering(self, enable):
        with self.command_lock:
            self.enter_config()
            cmd = b"\x62\x00" if enable else b"\x63\x00"
            expected = (0x62,) if enable else (0x63, 0x62)
            ack = self.send_cmd_wait(
                cmd,
                timeout=1.5,
                expected_cmds=expected,
                require_ok=True,
                name="engineering_on" if enable else "engineering_off",
            )
            self.end_config()
        if not ack:
            raise RuntimeError("LD2410 rejected engineering mode command")
        with self.lock:
            self.data["engineering"] = bool(enable)
            self.data["engineering_verified"] = False if enable else True
            self.data["engineering_warning"] = ""
            self.engineering_enabled_at = time.time() if enable else None

    def set_gate(self, gate, kind, value):
        gate = int(gate)
        value = clamp(value)
        if gate < 0 or gate > 8 or kind not in ("move", "still"):
            raise ValueError("invalid gate threshold")
        with self.lock:
            move = int(self.data["move_thresholds"][gate])
            still = int(self.data["still_thresholds"][gate])
        if kind == "move":
            move = value
        else:
            still = value
        payload = struct.pack("<HIHIHI", 0, gate, 1, move, 2, still)
        with self.command_lock:
            self.enter_config()
            ack = self.send_cmd_wait(b"\x64\x00", payload, timeout=1.5, require_ok=True)
            self.end_config()
        if not ack or len(ack) < 4 or ack[2:4] != b"\x00\x00":
            raise RuntimeError("LD2410 rejected gate threshold write")
        with self.lock:
            self.data["move_thresholds"][gate] = move
            self.data["still_thresholds"][gate] = still

    def set_thresholds(self, move, still):
        if not isinstance(move, list) or not isinstance(still, list):
            raise ValueError("move and still thresholds must be arrays")
        if len(move) < 9 or len(still) < 9:
            raise ValueError("threshold arrays must have 9 values")
        with self.command_lock:
            self.enter_config()
            for gate in range(9):
                m = clamp(move[gate])
                s = clamp(still[gate])
                payload = struct.pack("<HIHIHI", 0, gate, 1, m, 2, s)
                ack = self.send_cmd_wait(b"\x64\x00", payload, timeout=1.5, require_ok=True)
                if not ack:
                    self.end_config()
                    raise RuntimeError(f"LD2410 rejected G{gate} threshold write")
                with self.lock:
                    self.data["move_thresholds"][gate] = m
                    self.data["still_thresholds"][gate] = s
            self.end_config()

    def read_parameters(self):
        with self.command_lock:
            self.drain_responses()
            self.enter_config()
            time.sleep(0.3)
            response = self.send_cmd_wait(b"\x61\x00", timeout=3.0, name="read_parameters")
            self.end_config()
        if not response or len(response) < 26 or response[2] != 0xAA:
            return False
        max_gate = int(response[3])
        max_move_gate = int(response[4])
        max_still_gate = int(response[5])
        gate_count = max(0, min(9, max_gate + 1))
        move = [int(v) for v in response[6 : 6 + gate_count]]
        still_start = 6 + gate_count
        still = [int(v) for v in response[still_start : still_start + gate_count]]
        while len(move) < 9:
            move.append(0)
        while len(still) < 9:
            still.append(0)
        timeout_idx = still_start + gate_count
        timeout_seconds = None
        if timeout_idx + 1 < len(response):
            timeout_seconds = response[timeout_idx] | (response[timeout_idx + 1] << 8)
        with self.lock:
            self.data["max_gate"] = max_gate
            self.data["max_move_gate"] = max_move_gate
            self.data["max_still_gate"] = max_still_gate
            self.data["move_thresholds"] = move[:9]
            self.data["still_thresholds"] = still[:9]
            self.data["timeout_seconds"] = timeout_seconds
        return True

    def read_loop(self):
        while self.running:
            try:
                chunk = self.serial.read(128)
            except Exception:
                time.sleep(0.1)
                continue
            if chunk:
                self.buf.extend(chunk)
                self.process_buf()

    def process_buf(self):
        while True:
            cmd_idx = self.buf.find(CMD_HEAD)
            data_idx = self.buf.find(DATA_HEAD)
            if cmd_idx >= 0 and (data_idx < 0 or cmd_idx < data_idx):
                if cmd_idx:
                    del self.buf[:cmd_idx]
                if len(self.buf) < 10:
                    return
                dl = self.buf[4] | (self.buf[5] << 8)
                total = 10 + dl
                if len(self.buf) < total:
                    return
                frame = bytes(self.buf[:total])
                del self.buf[:total]
                if frame[-4:] == CMD_TAIL:
                    response = frame[6 : 6 + dl]
                    with self.lock:
                        self.responses.append(response)
                        self.data["last_command_ack_hex"] = hex_bytes(response)
                continue
            if data_idx < 0:
                if len(self.buf) > 1024:
                    del self.buf[:-4]
                return
            if data_idx:
                del self.buf[:data_idx]
            if len(self.buf) < 10:
                return
            dl = self.buf[4] | (self.buf[5] << 8)
            total = 10 + dl
            if len(self.buf) < total:
                return
            frame = bytes(self.buf[:total])
            del self.buf[:total]
            if frame[-4:] == DATA_TAIL:
                with self.lock:
                    self.data["last_data_frame_hex"] = hex_bytes(frame)
                self.parse_data(frame[6 : 6 + dl])

    def parse_data(self, data):
        if len(data) < 13 or data[1] != 0xAA or data[0] not in (0x01, 0x02):
            return
        target = data[2]
        update = {
            "presence": target != 0,
            "target_state": int(target),
            "last_report_type": int(data[0]),
            "last_target_state": int(target),
            "move_distance": data[3] | (data[4] << 8),
            "still_distance": data[6] | (data[7] << 8),
            "updated_at": time.time(),
        }
        if data[0] == 0x01 and len(data) >= 31:
            update["max_move_gate"] = int(data[11])
            update["max_still_gate"] = int(data[12])
            update["move_gates"] = list(data[13:22])
            update["still_gates"] = list(data[22:31])
            update["engineering_verified"] = True
            update["engineering_warning"] = ""
        else:
            update["move_gates"] = [int(data[5])] + [0] * 8
            update["still_gates"] = [int(data[8])] + [0] * 8
        with self.lock:
            self.data.update(update)


class Handler(BaseHTTPRequestHandler):
    server_version = "LD2410DirectWebTuner/0.1"

    def log_message(self, fmt, *args):
        print("[ld2410-web-tuner] " + fmt % args)

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == "/":
            body = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/state":
            return json_response(self, 200, {"ok": True, "state": self.server.tuner.snapshot()})
        self.send_error(404, "Not found")

    def do_POST(self):
        path = unquote(urlparse(self.path).path)
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            if path == "/api/engineering":
                self.server.tuner.set_engineering(bool(payload.get("enable")))
                return json_response(self, 200, {"ok": True})
            if path == "/api/read":
                ok = self.server.tuner.read_parameters()
                return json_response(self, 200, {"ok": True, "read": ok, "state": self.server.tuner.snapshot()})
            if path == "/api/gate":
                self.server.tuner.set_gate(payload.get("gate"), payload.get("kind"), payload.get("value"))
                return json_response(self, 200, {"ok": True})
            if path == "/api/thresholds":
                self.server.tuner.set_thresholds(payload.get("move"), payload.get("still"))
                return json_response(self, 200, {"ok": True, "state": self.server.tuner.snapshot()})
            if path == "/api/stop":
                json_response(self, 200, {"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
        except Exception as exc:
            return json_response(self, 400, {"ok": False, "error": str(exc)})
        self.send_error(404, "Not found")


def main():
    parser = argparse.ArgumentParser(description="Serve a standalone direct-UART LD2410 tuning web app.")
    parser.add_argument("--port", default="/dev/serial0", help="LD2410 UART path")
    parser.add_argument("--baud", type=int, default=256000)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--web-port", type=int, default=8766)
    args = parser.parse_args()

    tuner = DirectTuner(args.port, args.baud)
    httpd = ThreadingHTTPServer((args.host, args.web_port), Handler)
    httpd.tuner = tuner
    print(f"[ld2410-web-tuner] opened {args.port} at {args.baud}")
    print(f"[ld2410-web-tuner] serving http://{args.host}:{args.web_port}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[ld2410-web-tuner] stopping")
    finally:
        httpd.server_close()
        tuner.close()


if __name__ == "__main__":
    main()
