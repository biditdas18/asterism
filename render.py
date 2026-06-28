import json
import os
import random
from graph import graph_summary

OUTPUT_PATH = os.path.expanduser("~/.asterism/constellation.html")

# -- static background stars (data, not graph nodes) --
def _bg_stars(n=200):
    rng = random.Random(42)
    return [{"x": round(rng.random()*100, 3),
             "y": round(rng.random()*100, 3),
             "r": round(rng.uniform(0.3, 1.1), 2),
             "o": round(rng.uniform(0.08, 0.38), 2)}
            for _ in range(n)]


HTML_HEAD = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>❆ Asterism</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:100%;height:100%;overflow:hidden;background:#000000}
#bg{position:fixed;inset:0;pointer-events:none}
#c{position:fixed;inset:0;touch-action:none}
#hud{position:fixed;top:14px;left:50%;transform:translateX(-50%);
  color:#2a1f5a;font:12px/1 monospace;letter-spacing:.14em;pointer-events:none}
#tip{position:fixed;display:none;pointer-events:none;
  background:rgba(8,8,20,0.72);border:1px solid rgba(150,150,255,0.3);
  border-radius:8px;padding:10px 14px;font:12px/1.4 monospace;
  color:#aaaaff;max-width:220px;max-height:120px;overflow:hidden;z-index:20;
  backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px)}
#tip b{color:#ffffff;font-size:12px;font-weight:600;
  letter-spacing:0.03em;display:block;margin-bottom:2px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:196px}
#tip .tip-type{color:#8888cc;font-size:10px;text-transform:uppercase;
  letter-spacing:0.1em;display:block;margin-bottom:3px}
#tip .bar-bg{background:rgba(255,255,255,0.1);border-radius:2px;height:2px;margin-top:6px}
#tip .bar-fill{background:#8b5cf6;border-radius:2px;height:2px;transition:width .3s}
#pin{position:fixed;top:20px;right:20px;display:none;
  background:#0d0a1a;border:1px solid #3d2a7a;border-radius:12px;
  padding:14px 18px;font:12px/1.8 monospace;color:#c4b5fd;
  max-width:220px;z-index:30}
#pin b{color:#ffffff;font-size:14px;display:block;margin-bottom:4px}
#pin .close{float:right;cursor:pointer;color:#4a3a7a;font-size:16px;line-height:1}
</style>
</head>
<body>
<svg id="bg" xmlns="http://www.w3.org/2000/svg" width="100%" height="100%">
  <defs>
    <radialGradient id="sky" cx="50%" cy="50%" r="60%">
      <stop offset="0%" stop-color="#00000f"/>
      <stop offset="100%" stop-color="#000005"/>
    </radialGradient>
  </defs>
  <rect width="100%" height="100%" fill="url(#sky)"/>
"""

HTML_STARS_CLOSE = """\
</svg>
<canvas id="c"></canvas>
<div id="hud">❆ ASTERISM &nbsp;·&nbsp; scroll to zoom &nbsp;·&nbsp; drag to pan &nbsp;·&nbsp; click node to focus</div>
<div id="tip">
  <b id="tip-label"></b>
  <span class="tip-type" id="tip-type"></span>
  <span id="tip-w" style="font-size:11px"></span>
  <div class="bar-bg"><div class="bar-fill" id="tip-bar"></div></div>
</div>
<div id="pin">
  <span class="close" id="pin-close">&times;</span>
  <b id="pin-label"></b>
  <span id="pin-body" style="color:#9d8fcc;font-size:11px"></span>
</div>
<script>
"""

HTML_JS = """\
const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');
const tip = document.getElementById('tip');
const pin = document.getElementById('pin');
document.getElementById('pin-close').onclick = function() { pin.style.display='none'; };

let W, H;
function resize() {
  W = canvas.width = window.innerWidth;
  H = canvas.height = window.innerHeight;
}
resize();
window.addEventListener('resize', resize);

// ---- node setup ----
var nodes = NODES.map(function(n) {
  var delay = Math.random() * 6000;
  var phase = Math.random() * Math.PI * 2;
  var isUser = n.node_type === 'user';
  return Object.assign({}, n, {
    x: (Math.random()-0.5)*500,
    y: (Math.random()-0.5)*500,
    vx: 0, vy: 0,
    r: nodeRadius(n.weight, isUser),
    isUser: isUser,
    animDelay: delay,
    animPhase: phase,
    alpha: 0
  });
});
var nodeIndex = {};
nodes.forEach(function(n,i){ nodeIndex[n.id] = i; });

var edges = EDGES.map(function(e) {
  return { s: nodeIndex[e.source], t: nodeIndex[e.target], weight: e.weight };
}).filter(function(e){ return e.s !== undefined && e.t !== undefined; });

function nodeRadius(w, isUser) {
  if (isUser) return 32;
  return Math.max(3.5, Math.min(32, 3.5 + (w / 100) * 28.5));
}

function nodeAlpha(w) {
  return Math.max(0.4, Math.min(1.0, 0.4 + (w / 100) * 0.6));
}

function lerp_f(a,b,t){ return a+(b-a)*t; }
function lerp(a,b,t){ return Math.round(a+(b-a)*t); }

function edgeStyle(aw, bw, ew) {
  var w = Math.max(0.5, Math.min(2.5, 0.5 + (ew / 5) * 2.0));
  return { color:'170,170,170', op:0.45, w:w };
}

function pulseAlpha(n, t) {
  var p = (t + n.animPhase) / 1000;
  if (n.isUser || n.weight >= 3.0) {
    return 0.85 + 0.15 * Math.sin(p / 1.5);
  } else if (n.weight >= 1.5) {
    return 0.88 + 0.12 * Math.sin(p / 2.0 + n.animDelay/1000);
  } else {
    return 0.85 + 0.15 * Math.abs(Math.sin(p / 3.0 + n.animDelay/1000));
  }
}

// ---- simulation ----
var REPEL=2200, SPRING=0.035, DAMP=0.80, CENTER=0.002;

function tick() {
  for (var i=0; i<nodes.length; i++) {
    for (var j=i+1; j<nodes.length; j++) {
      var dx=nodes[j].x-nodes[i].x, dy=nodes[j].y-nodes[i].y;
      var d2=dx*dx+dy*dy+1;
      var f=REPEL/d2;
      nodes[i].vx-=f*dx; nodes[i].vy-=f*dy;
      nodes[j].vx+=f*dx; nodes[j].vy+=f*dy;
    }
  }
  edges.forEach(function(e) {
    var a=nodes[e.s], b=nodes[e.t];
    var dx=b.x-a.x, dy=b.y-a.y;
    var d=Math.sqrt(dx*dx+dy*dy)||1;
    var target=100+50/Math.max(e.weight,0.1);
    var f=(d-target)*SPRING;
    a.vx+=f*dx/d; a.vy+=f*dy/d;
    b.vx-=f*dx/d; b.vy-=f*dy/d;
  });
  nodes.forEach(function(n) {
    n.vx-=n.x*CENTER; n.vy-=n.y*CENTER;
    n.vx*=DAMP; n.vy*=DAMP;
    n.x+=n.vx; n.y+=n.vy;
  });
}

// pre-settle
for (var i=0; i<300; i++) tick();

// ---- camera ----
var cam = {x:0, y:0, z:1};
function toScreen(x,y){ return [x*cam.z+W/2+cam.x, y*cam.z+H/2+cam.y]; }
function toWorld(sx,sy){ return [(sx-W/2-cam.x)/cam.z, (sy-H/2-cam.y)/cam.z]; }

// ---- hit test ----
function hitTest(sx,sy) {
  var wp=toWorld(sx,sy), wx=wp[0], wy=wp[1];
  for (var i=nodes.length-1;i>=0;i--) {
    var n=nodes[i], dx=n.x-wx, dy=n.y-wy;
    var hit_r = Math.max(n.r/cam.z, 12/cam.z);
    if (Math.sqrt(dx*dx+dy*dy)<hit_r) return i;
  }
  return -1;
}

// ---- interaction state ----
var dragging=null, dragOx=0, dragOy=0;
var panStart=null, camStart=null;
var focusNode=null;
var hoverNode=-1;
var hoverPathNodes=null; // Set of node indices on BFS path from Bidit
var hoverPathEdges=null; // Set of edge indices on that path
var settled=true;

function bfsPath(src, dst) {
  if (src===dst) return [src];
  var prev=new Int32Array(nodes.length).fill(-1);
  var seen=new Uint8Array(nodes.length);
  seen[src]=1;
  var q=[src], qi=0;
  outer: while (qi<q.length) {
    var u=q[qi++];
    for (var i=0;i<edges.length;i++) {
      var e=edges[i], v=-1;
      if (e.s===u&&!seen[e.t]) v=e.t;
      else if (e.t===u&&!seen[e.s]) v=e.s;
      if (v<0) continue;
      seen[v]=1; prev[v]=u; q.push(v);
      if (v===dst) break outer;
    }
  }
  if (prev[dst]<0&&dst!==src) return null;
  var path=[]; var c=dst;
  while (c>=0){ path.unshift(c); c=prev[c]; }
  return path;
}

function computeHoverPath(hit) {
  var userIdx=-1;
  for (var i=0;i<nodes.length;i++){ if (nodes[i].node_type==='user'){userIdx=i;break;} }
  if (userIdx<0||hit<0){ hoverPathNodes=null; hoverPathEdges=null; return; }
  if (hit===userIdx){ hoverPathNodes=new Set([userIdx]); hoverPathEdges=new Set(); return; }
  var path=bfsPath(userIdx,hit);
  if (!path){ hoverPathNodes=null; hoverPathEdges=null; return; }
  hoverPathNodes=new Set(path);
  hoverPathEdges=new Set();
  // mark edges along the BFS path
  for (var k=0;k<path.length-1;k++) {
    var a=path[k], b=path[k+1];
    for (var i=0;i<edges.length;i++) {
      var e=edges[i];
      if ((e.s===a&&e.t===b)||(e.s===b&&e.t===a)) { hoverPathEdges.add(i); break; }
    }
  }
  // if hovered node is a cluster hub, expand all its children into the highlight
  if (nodes[hit].node_type==='cluster') {
    for (var i=0;i<edges.length;i++) {
      var e=edges[i];
      var child=-1;
      if (e.s===hit) child=e.t;
      else if (e.t===hit) child=e.s;
      if (child>=0&&child!==userIdx) {
        hoverPathNodes.add(child);
        hoverPathEdges.add(i);
      }
    }
  }
}

// pointer
canvas.addEventListener('pointerdown', function(e) {
  var hit=hitTest(e.clientX,e.clientY);
  if (hit>=0) {
    dragging=hit;
    var wp=toWorld(e.clientX,e.clientY);
    dragOx=nodes[hit].x-wp[0]; dragOy=nodes[hit].y-wp[1];
  } else {
    panStart=[e.clientX,e.clientY];
    camStart=[cam.x,cam.y];
  }
});
canvas.addEventListener('pointermove', function(e) {
  if (dragging!==null) {
    var wp=toWorld(e.clientX,e.clientY);
    nodes[dragging].x=wp[0]+dragOx; nodes[dragging].y=wp[1]+dragOy;
    nodes[dragging].vx=nodes[dragging].vy=0;
  } else if (panStart) {
    cam.x=camStart[0]+e.clientX-panStart[0];
    cam.y=camStart[1]+e.clientY-panStart[1];
  }
  var hit=hitTest(e.clientX,e.clientY);
  if (dragging===null&&hit!==hoverNode){ hoverNode=hit; computeHoverPath(hit); }
  if (hit>=0) {
    var n=nodes[hit];
    var tipLabel=document.getElementById('tip-label');
    var fullLabel=n.label.replace(/^💬\s*/,'');
    tipLabel.textContent=fullLabel.length>40?fullLabel.slice(0,40)+'…':fullLabel;
    tipLabel.title=fullLabel;
    document.getElementById('tip-type').textContent=n.node_type;
    document.getElementById('tip-w').textContent='weight '+n.weight.toFixed(1);
    document.getElementById('tip-bar').style.width=Math.min(100,n.weight/5*100)+'%';
    tip.style.display='block';
    tip.style.left=(e.clientX+16)+'px';
    tip.style.top=(e.clientY-8)+'px';
    canvas.style.cursor='pointer';
  } else {
    tip.style.display='none';
    canvas.style.cursor='default';
  }
});
canvas.addEventListener('pointerleave', function() { hoverNode=-1; hoverPathNodes=null; hoverPathEdges=null; tip.style.display='none'; });
canvas.addEventListener('pointerup', function(e) {
  if (dragging===null && panStart===null) {
    // click
    var hit=hitTest(e.clientX,e.clientY);
    if (hit>=0) {
      focusNode=(focusNode===hit)?null:hit;
    } else {
      focusNode=null;
    }
  }
  dragging=null; panStart=null;
});

// double-click pin
canvas.addEventListener('dblclick', function(e) {
  var hit=hitTest(e.clientX,e.clientY);
  if (hit>=0) {
    var n=nodes[hit];
    document.getElementById('pin-label').textContent=n.label;
    document.getElementById('pin-body').innerHTML=
      'type: '+n.node_type+'<br>weight: '+n.weight.toFixed(2)+
      '<br>connections: '+edges.filter(function(e){return e.s===hit||e.t===hit;}).length;
    pin.style.display='block';
  }
});

canvas.addEventListener('wheel', function(e) {
  e.preventDefault();
  var factor=e.deltaY<0?1.12:0.90;
  var wp=toWorld(e.clientX,e.clientY);
  cam.z*=factor;
  cam.z=Math.max(0.1,Math.min(8,cam.z));
  cam.x=e.clientX-W/2-wp[0]*cam.z;
  cam.y=e.clientY-H/2-wp[1]*cam.z;
},{passive:false});

// touch: drag + pinch
var touches={}, lastPinchDist=null;
canvas.addEventListener('touchstart',function(e){
  e.preventDefault();
  Array.from(e.changedTouches).forEach(function(t){touches[t.identifier]={x:t.clientX,y:t.clientY};});
  if (Object.keys(touches).length===1) {
    var t=e.changedTouches[0];
    var hit=hitTest(t.clientX,t.clientY);
    if (hit>=0) { dragging=hit; var wp=toWorld(t.clientX,t.clientY); dragOx=nodes[hit].x-wp[0]; dragOy=nodes[hit].y-wp[1]; }
    else { panStart=[t.clientX,t.clientY]; camStart=[cam.x,cam.y]; }
  }
},{passive:false});
canvas.addEventListener('touchmove',function(e){
  e.preventDefault();
  Array.from(e.changedTouches).forEach(function(t){touches[t.identifier]={x:t.clientX,y:t.clientY};});
  var ids=Object.keys(touches);
  if (ids.length===2) {
    var a=touches[ids[0]], b=touches[ids[1]];
    var dist=Math.hypot(a.x-b.x,a.y-b.y);
    if (lastPinchDist) { cam.z*=dist/lastPinchDist; cam.z=Math.max(0.1,Math.min(8,cam.z)); }
    lastPinchDist=dist;
  } else if (ids.length===1) {
    var t=e.changedTouches[0];
    if (dragging!==null) { var wp=toWorld(t.clientX,t.clientY); nodes[dragging].x=wp[0]+dragOx; nodes[dragging].y=wp[1]+dragOy; }
    else if (panStart) { cam.x=camStart[0]+t.clientX-panStart[0]; cam.y=camStart[1]+t.clientY-panStart[1]; }
  }
},{passive:false});
canvas.addEventListener('touchend',function(e){
  e.preventDefault();
  Array.from(e.changedTouches).forEach(function(t){delete touches[t.identifier];});
  if (Object.keys(touches).length<2) lastPinchDist=null;
  dragging=null; panStart=null;
},{passive:false});

// ---- label rendering with collision avoidance ----
var _labelSlots = [];  // [{x,y,w,h}] per frame, reset each draw call

function _labelPriority(n) {
  if (n.isUser)               return 4;
  if (n.node_type==='domain') return 3;
  if (n.node_type==='theme')  return 2;
  return 1;
}

function _labelProps(n, cz) {
  if (n.isUser)               return {size:14*cz, bold:true,  color:'255,255,255', shadow:'rgba(0,0,0,0.9)', shadowBlur:8};
  if (n.node_type==='domain') return {size:13*cz, bold:true,  color:'255,255,255', shadow:'rgba(150,150,255,0.6)', shadowBlur:12};
  if (n.node_type==='theme')  return {size:11*cz, bold:true,  color:'204,204,255', shadow:'rgba(0,0,0,0.9)', shadowBlur:8};
  return                             {size:9*cz,  bold:false, color:'170,170,204', shadow:'rgba(0,0,0,0.9)', shadowBlur:8};
}

function _slotFree(x, y, w, h) {
  for (var k=0; k<_labelSlots.length; k++) {
    var s=_labelSlots[k];
    if (Math.abs(x-s.x)<(w+s.w)/2+4 && Math.abs(y-s.y)<(h+s.h)/2+4) return false;
  }
  return true;
}

function _drawLabel(ctx, n, idx, sx, sy, r, baseA, cz) {
  if (baseA < 0.05) return;
  var p=_labelProps(n, cz);
  var isDomain=(n.node_type==='domain');
  ctx.font=(p.bold?'bold ':'')+p.size+'px monospace';
  var tw=ctx.measureText(n.label).width;
  var th=p.size;
  // try below first, then above for lower-priority nodes
  var yBelow=sy+r+(3+p.size);
  var yAbove=sy-r-3;
  var chosen=null;
  if (_slotFree(sx, yBelow, tw, th)) {
    chosen=yBelow;
  } else if (!isDomain && _slotFree(sx, yAbove, tw, th)) {
    chosen=yAbove;
  } else if (isDomain) {
    chosen=yBelow; // domain labels always render, even if overlapping
  }
  if (chosen===null) return;
  _labelSlots.push({x:sx, y:chosen, w:tw, h:th});
  ctx.save();
  ctx.shadowColor=p.shadow; ctx.shadowBlur=p.shadowBlur;
  var alpha=isDomain?Math.max(0.85,baseA):Math.min(1,baseA);
  ctx.fillStyle='rgba('+p.color+','+alpha+')';
  ctx.textAlign='center';
  ctx.fillText(n.label, sx, chosen);
  ctx.restore();
}

// ---- draw ----
function draw(t) {
  ctx.clearRect(0,0,W,H);

  // edges first
  var isHovering=(hoverPathNodes!==null);
  edges.forEach(function(e,ei) {
    var a=nodes[e.s], b=nodes[e.t];
    var as_=toScreen(a.x,a.y), bs_=toScreen(b.x,b.y);
    var style=edgeStyle(a.weight,b.weight,e.weight);
    var color=style.color, op, lw;
    if (isHovering) {
      if (hoverPathEdges.has(ei)) {
        color='255,255,255'; op=1.0; lw=2.5*cam.z;           // path beam
      } else if (e.s===hoverNode||e.t===hoverNode) {
        op=0.4; lw=style.w*cam.z;                             // direct neighbours
      } else {
        op=0.08; lw=style.w*cam.z;                            // everything else
      }
    } else {
      var focused=(focusNode===null)||(e.s===focusNode||e.t===focusNode);
      op=focused?style.op:style.op*0.2;
      lw=(focusNode!==null&&focused?style.w*1.8:style.w)*cam.z;
    }
    ctx.beginPath(); ctx.moveTo(as_[0],as_[1]); ctx.lineTo(bs_[0],bs_[1]);
    ctx.strokeStyle='rgba('+color+','+op+')';
    ctx.lineWidth=lw;
    ctx.stroke();
  });

  // nodes
  nodes.forEach(function(n,i) {
    var s=toScreen(n.x,n.y), sx=s[0], sy=s[1];
    var isHoveredNode=(i===hoverNode);
    var r=(isHoveredNode ? n.r+4 : n.r)*cam.z;
    var pulse=pulseAlpha(n,t);
    var dimFactor;
    if (isHovering) {
      if (isHoveredNode)                  dimFactor=1;   // hovered — full
      else if (hoverPathNodes.has(i))     dimFactor=1;   // on path — full
      else                                dimFactor=0.08; // off path — near invisible
    } else {
      var isFocused=(focusNode===null)||focusNode===i||
        edges.some(function(e){return (e.s===focusNode&&e.t===i)||(e.t===focusNode&&e.s===i);});
      dimFactor=isFocused?1:0.2;
    }
    var baseA=isHoveredNode?1.0:nodeAlpha(n.weight)*pulse*dimFactor;

    // glow — all nodes, stronger for user/heavy nodes
    var isStrong=(n.isUser||n.weight>=3.0);
    var glowR=r*(isStrong?4.0:2.2);
    var glowA=(isStrong?0.55:n.weight>=1.5?0.35:0.2)*pulse*dimFactor;
    var glow=ctx.createRadialGradient(sx,sy,0,sx,sy,glowR);
    glow.addColorStop(0,'rgba(255,255,255,'+glowA+')');
    glow.addColorStop(0.35,'rgba(200,220,255,'+(glowA*(isStrong?0.5:0.2))+')');
    glow.addColorStop(1,'rgba(0,0,0,0)');
    ctx.beginPath(); ctx.arc(sx,sy,glowR,0,Math.PI*2);
    ctx.fillStyle=glow; ctx.fill();

    // blue-purple glow fill at 2.5x radius — marks graph nodes vs bg stars
    ctx.beginPath(); ctx.arc(sx,sy,r*2.5,0,Math.PI*2);
    ctx.fillStyle='rgba(102,119,255,'+(0.12*dimFactor)+')';
    ctx.fill();

    // white border ring (2px)
    ctx.beginPath(); ctx.arc(sx,sy,r+2*cam.z,0,Math.PI*2);
    ctx.strokeStyle='rgba(255,255,255,'+(baseA*0.6)+')';
    ctx.lineWidth=2*cam.z;
    ctx.stroke();

    // inner core — low weight=#AAB8FF, high weight=#FFFFFF, interpolated
    var wt=Math.min(1,Math.max(0,(n.weight-0)/(70)));
    var cR=Math.round(170+wt*85), cG=Math.round(184+wt*71), cB=255;
    ctx.beginPath(); ctx.arc(sx,sy,r,0,Math.PI*2);
    ctx.fillStyle='rgba('+cR+','+cG+','+cB+','+baseA+')';
    ctx.fill();

    // store computed values for label pass
    n._sx=sx; n._sy=sy; n._r=r; n._baseA=baseA; n._onPath=isHovering&&hoverPathNodes&&hoverPathNodes.has(i);
  });

  // ---- label pass: priority order so domain/theme always win slots ----
  _labelSlots=[];
  var labelOrder=nodes.map(function(_,i){return i;});
  labelOrder.sort(function(a,b){ return _labelPriority(nodes[b])-_labelPriority(nodes[a]); });
  labelOrder.forEach(function(i) {
    var n=nodes[i];
    if (n._onPath&&i!==hoverNode) {
      // path hover label: above node, no slot tracking needed (transient)
      ctx.save();
      ctx.shadowColor='rgba(0,0,0,0.9)'; ctx.shadowBlur=8;
      ctx.fillStyle='rgba(204,204,255,0.9)';
      ctx.font='10px monospace';
      ctx.textAlign='center';
      ctx.fillText(n.label, n._sx, n._sy-n._r-8*cam.z);
      ctx.restore();
    } else if (!isHovering) {
      _drawLabel(ctx, n, i, n._sx, n._sy, n._r, n._baseA, cam.z);
    }
  });
}

function loop(t) {
  if (dragging!==null) tick();
  draw(t);
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);
</script>
</body>
</html>
"""


def render_graph() -> str:
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    summary = graph_summary()

    nodes_json = json.dumps([
        {"id": label, "label": label,
         "node_type": data.get("node_type", "concept"),
         "weight": round(data.get("weight", 1.0), 3)}
        for label, data in summary["node_list"]
    ])
    edges_json = json.dumps([
        {"source": src, "target": tgt,
         "weight": round(data.get("weight", 1.0), 3)}
        for src, tgt, data in summary["edge_list"]
    ])

    stars_svg = "\n".join(
        '  <circle cx="{x}%" cy="{y}%" r="{r}" fill="white" opacity="{o}"/>'.format(**s)
        for s in _bg_stars()
    )

    data_block = (
        "const NODES = " + nodes_json + ";\n"
        "const EDGES = " + edges_json + ";\n"
    )

    html = HTML_HEAD + stars_svg + "\n" + HTML_STARS_CLOSE + data_block + HTML_JS

    with open(OUTPUT_PATH, "w") as f:
        f.write(html)
    return OUTPUT_PATH
