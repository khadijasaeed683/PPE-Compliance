import streamlit as st
from PIL import Image, ImageDraw
import json, os, base64
from io import BytesIO
import streamlit.components.v1 as components

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
SAVE_FILE = "annotations.json"
CLASSES   = ["Mask", "Goggles", "Gloves", "Gown"]
COLOR_MAP = {
    "Mask":    "#FF0000",
    "Goggles": "#00FF00",
    "Gloves":  "#0000FF",
    "Gown":    "#FFFF00",
}
os.makedirs("outputs", exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def load_annotations() -> dict:
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_annotations(data: dict):
    with open(SAVE_FILE, "w") as f:
        json.dump(data, f, indent=4)

def pil_to_b64(img: Image.Image) -> str:
    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def render_boxes(base_img: Image.Image, boxes: list) -> Image.Image:
    img  = base_img.convert("RGB").copy()
    draw = ImageDraw.Draw(img)
    for box in boxes:
        x1, y1, x2, y2 = box["bbox"]
        color = COLOR_MAP.get(box["class_name"], "#FF0000")
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
        label = box["class_name"]
        draw.rectangle([x1, y1, x1 + len(label)*8 + 6, y1 + 18], fill=color)
        draw.text((x1 + 3, y1 + 2), label, fill="black")
    return img

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────
for k, v in [("boxes", []), ("img_bytes", None), ("filename", None),
             ("saved_preview", None)]:
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────────────────────────────────────
# PAGE
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="PPE-Watch Annotator", layout="wide")
st.title("🏥 PPE-Watch: Medical Annotation Web Portal")

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
st.sidebar.header("Control Panel")
uploaded   = st.sidebar.file_uploader("Upload Image", type=["jpg","jpeg","png","jfif"])
class_name = st.sidebar.selectbox("PPE Class", CLASSES)

st.sidebar.markdown("---")
st.sidebar.markdown("**Legend**")
for name, color in COLOR_MAP.items():
    st.sidebar.markdown(
        f"<span style='color:{color};font-size:18px;'>■</span> {name}",
        unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Instructions**\n\n"
    "1. Upload an image\n"
    "2. Pick a PPE class\n"
    "3. Click & drag to draw boxes\n"
    "4. Switch class and draw more\n"
    "5. Click **Undo Last** to remove a box\n"
    "6. Click **Save All Boxes** when done")

# ─────────────────────────────────────────────────────────────────────────────
# LOAD IMAGE
# ─────────────────────────────────────────────────────────────────────────────
if uploaded:
    if uploaded.name != st.session_state.filename:
        raw      = uploaded.read()
        existing = load_annotations().get(uploaded.name, [])
        st.session_state.img_bytes    = raw
        st.session_state.filename     = uploaded.name
        st.session_state.boxes        = existing
        st.session_state.saved_preview = None

    base_img = Image.open(BytesIO(st.session_state.img_bytes)).convert("RGB")
    W, H     = base_img.size
    b64_src  = pil_to_b64(base_img)

    # Pass existing boxes and active class into the canvas
    boxes_json   = json.dumps(st.session_state.boxes)
    active_color = COLOR_MAP[class_name]
    class_index  = CLASSES.index(class_name)
    canvas_h     = min(H, 650)

    # ─────────────────────────────────────────────────────────────────────────
    # HTML5 CANVAS
    # All box state lives in JS. Python only gets involved when the user
    # clicks "Save All Boxes" — the button serialises the JS box array into
    # a hidden <textarea>, then submits a real HTML form whose POST value
    # Streamlit reads via st.query_params after a page navigation.
    #
    # Simpler and more reliable: we use st.session_state + a text_area as
    # a "mailbox". The JS writes JSON into the textarea via DOM manipulation,
    # and a Streamlit button reads it. This avoids any postMessage trickery.
    #
    # ACTUAL approach used here:
    # - JS canvas handles all drawing and keeps boxes[] array internally
    # - A visible <textarea id="out"> always contains the JSON of current boxes
    # - Streamlit renders a normal st.text_area pointed at the same key
    # - The user clicks a plain st.button; Python reads the textarea value
    #   from st.session_state and processes it
    # ─────────────────────────────────────────────────────────────────────────

    canvas_html = f"""
<!DOCTYPE html>
<html>
<head>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:#1a1a1a; font-family:monospace; color:#eee; }}
#toolbar {{
  display:flex; gap:10px; align-items:center;
  padding:8px 10px; background:#2a2a2a; border-bottom:1px solid #444;
  flex-wrap:wrap;
}}
#toolbar span {{ font-size:13px; }}
#coords {{ font-size:12px; color:#aaa; margin-left:auto; }}
#canvaswrap {{ overflow:auto; background:#111; }}
canvas {{ display:block; cursor:crosshair; }}
#boxlist {{
  padding:8px 10px; background:#222; max-height:140px;
  overflow-y:auto; font-size:12px; border-top:1px solid #333;
}}
.boxrow {{ display:flex; justify-content:space-between;
           padding:2px 0; border-bottom:1px solid #333; }}
.boxrow button {{
  background:#c0392b; color:white; border:none;
  border-radius:3px; cursor:pointer; padding:1px 7px; font-size:11px;
}}
#jsonout {{
  width:100%; height:60px; background:#111; color:#0f0;
  border:1px solid #333; font-size:11px; padding:4px;
  resize:none; margin-top:4px;
}}
</style>
</head>
<body>

<div id="toolbar">
  <span>Class: <b style="color:{active_color}">{class_name}</b></span>
  <span id="count">Boxes: 0</span>
  <span id="coords">x: 0  y: 0</span>
</div>

<div id="canvaswrap">
  <canvas id="c"></canvas>
</div>

<div id="boxlist" id="boxlist"></div>

<textarea id="jsonout" readonly placeholder="Box JSON will appear here..."></textarea>

<script>
// ── init ──────────────────────────────────────────────────────────────────
const IMG_SRC    = "data:image/png;base64,{b64_src}";
const INIT_BOXES = {boxes_json};
const COLOR      = "{active_color}";
const CLASS_NAME = "{class_name}";
const CLASS_ID   = {class_index};
const COLOR_MAP  = {{
  Mask:"#FF0000", Goggles:"#00FF00", Gloves:"#0000FF", Gown:"#FFFF00"
}};

const canvas  = document.getElementById("c");
const ctx     = canvas.getContext("2d");
const jsonOut = document.getElementById("jsonout");
const countEl = document.getElementById("count");
const coordEl = document.getElementById("coords");
const listEl  = document.getElementById("boxlist");

let boxes   = JSON.parse(JSON.stringify(INIT_BOXES)); // deep copy
let dragging = false, sx=0, sy=0, ex=0, ey=0;

const img = new Image();
img.onload = () => {{
  canvas.width  = img.naturalWidth;
  canvas.height = img.naturalHeight;
  redraw();
  updateUI();
}};
img.src = IMG_SRC;

// ── draw ──────────────────────────────────────────────────────────────────
function redraw(live) {{
  ctx.clearRect(0,0,canvas.width,canvas.height);
  ctx.drawImage(img,0,0);

  boxes.forEach(b => {{
    const [x1,y1,x2,y2] = b.bbox;
    const c = COLOR_MAP[b.class_name] || "#FFF";
    ctx.strokeStyle = c; ctx.lineWidth = 3;
    ctx.strokeRect(x1,y1,x2-x1,y2-y1);
    ctx.fillStyle = c;
    ctx.fillRect(x1,y1, b.class_name.length*8+6, 18);
    ctx.fillStyle = "black";
    ctx.font = "bold 13px monospace";
    ctx.fillText(b.class_name, x1+3, y1+13);
  }});

  if (live) {{
    const {{x,y,w,h}} = live;
    ctx.strokeStyle = COLOR; ctx.lineWidth = 2;
    ctx.setLineDash([6,3]); ctx.strokeRect(x,y,w,h); ctx.setLineDash([]);
    // show live dimensions
    ctx.fillStyle = COLOR;
    ctx.font = "12px monospace";
    ctx.fillText(`${{Math.abs(w)}} x ${{Math.abs(h)}}`, x + 4, y - 4);
  }}
}}

// ── mouse ─────────────────────────────────────────────────────────────────
function clamp(v,lo,hi){{ return Math.max(lo,Math.min(hi,v)); }}
function pos(e) {{
  const r = canvas.getBoundingClientRect();
  return {{
    x: clamp(Math.round((e.clientX-r.left) * canvas.width /r.width), 0, canvas.width-1),
    y: clamp(Math.round((e.clientY-r.top)  * canvas.height/r.height),0, canvas.height-1),
  }};
}}

canvas.addEventListener("mousedown", e => {{
  const p=pos(e); dragging=true; sx=p.x; sy=p.y; ex=p.x; ey=p.y;
}});

canvas.addEventListener("mousemove", e => {{
  const p=pos(e);
  coordEl.textContent = `x: ${{p.x}}  y: ${{p.y}}`;
  if (!dragging) return;
  ex=p.x; ey=p.y;
  redraw({{ x:Math.min(sx,ex), y:Math.min(sy,ey),
            w:Math.abs(ex-sx), h:Math.abs(ey-sy) }});
}});

canvas.addEventListener("mouseup", e => {{
  if (!dragging) return;
  dragging=false;
  const x1=Math.min(sx,ex), y1=Math.min(sy,ey);
  const x2=Math.max(sx,ex), y2=Math.max(sy,ey);
  if (x2-x1 < 5 || y2-y1 < 5) {{ redraw(); return; }}

  boxes.push({{ class_id:CLASS_ID, class_name:CLASS_NAME, bbox:[x1,y1,x2,y2] }});
  redraw();
  updateUI();
}});

canvas.addEventListener("mouseleave", () => {{
  if (dragging) {{ dragging=false; redraw(); }}
}});

// ── undo ──────────────────────────────────────────────────────────────────
function deleteBox(i) {{
  boxes.splice(i,1);
  redraw();
  updateUI();
}}

// ── sync textarea + box list (Streamlit reads the textarea) ───────────────
function updateUI() {{
  jsonOut.value = JSON.stringify(boxes);
  countEl.textContent = `Boxes: ${{boxes.length}}`;

  listEl.innerHTML = "";
  if (boxes.length === 0) {{
    listEl.innerHTML = "<span style='color:#666'>No boxes yet — drag on the image above.</span>";
    return;
  }}
  boxes.forEach((b,i) => {{
    const c = COLOR_MAP[b.class_name]||"#fff";
    const row = document.createElement("div");
    row.className = "boxrow";
    row.innerHTML =
      `<span><span style="color:${{c}}">■ ${{b.class_name}}</span> &nbsp;
       [${{b.bbox.join(", ")}}]</span>
       <button onclick="deleteBox(${{i}})">✕ delete</button>`;
    listEl.appendChild(row);
  }});
}}
updateUI();
</script>
</body>
</html>
"""

    # Render the canvas (display only — no return value used)
    components.html(canvas_html, height=canvas_h + 220, scrolling=False)

    st.markdown("---")
    st.markdown(
        "📋 **After drawing all boxes above, paste the JSON from the box "
        "below into this field and click Save:**")

    # The user copies JSON from the canvas textarea into this Streamlit widget
    raw_json = st.text_area(
        "Box data (copy from the green box above ↑)",
        value=json.dumps(st.session_state.boxes) if st.session_state.boxes else "",
        height=80,
        key="box_json_input",
        help="The canvas textarea above auto-updates. Copy its content here then save."
    )

    col1, col2 = st.columns([1,1])

    with col1:
        if st.button("🚀 Save All Boxes"):
            try:
                parsed = json.loads(raw_json)
                if not isinstance(parsed, list) or len(parsed) == 0:
                    st.warning("No boxes found. Draw some boxes first.")
                else:
                    st.session_state.boxes = parsed
                    all_data = load_annotations()
                    all_data[uploaded.name] = parsed
                    save_annotations(all_data)

                    labeled = render_boxes(base_img, parsed)
                    out_path = f"outputs/labeled_{uploaded.name}"
                    labeled.save(out_path)
                    st.session_state.saved_preview = pil_to_b64(labeled)

                    st.success(f"✅ Saved {len(parsed)} annotation(s)!")
            except json.JSONDecodeError:
                st.error("Invalid JSON. Make sure you copied the full content from the green box.")

    with col2:
        if st.button("🔄 Reset / Clear All"):
            st.session_state.boxes = []
            st.session_state.saved_preview = None
            all_data = load_annotations()
            all_data[uploaded.name] = []
            save_annotations(all_data)
            st.rerun()

    # Show saved preview
    if st.session_state.saved_preview:
        st.image(
            base64.b64decode(st.session_state.saved_preview),
            caption="Last saved labeled image",
            use_container_width=True)

    # All annotations viewer
    with st.expander("📋 View All Saved Annotations"):
        all_data = load_annotations()
        if all_data:
            for fname, boxes in all_data.items():
                st.markdown(f"**{fname}** — {len(boxes)} box(es)")
                for b in boxes:
                    color = COLOR_MAP.get(b.get("class_name",""), "#fff")
                    st.markdown(
                        f"&nbsp;&nbsp;<span style='color:{color};'>■ {b.get('class_name')}</span>"
                        f" bbox: {b.get('bbox')}",
                        unsafe_allow_html=True)
        else:
            st.write("No annotations saved yet.")

else:
    st.info("⬅ Upload an image from the sidebar to begin annotating.")