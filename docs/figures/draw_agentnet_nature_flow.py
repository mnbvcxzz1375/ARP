"""
AgentNet relay architecture & task lifecycle — Nature-style architecture diagram.
REWRITTEN: all box centers computed explicitly as (cx, cy).
Text is placed at (cx, cy) with ha='center', va='center'.
A post-generation check scans every FancyBboxPatch + Text pair and
reports the max center-offset in data-units.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, FancyArrow
import numpy as np

# ──────────────────────────────────────────────────────────────
# Nature rcParams
# ──────────────────────────────────────────────────────────────
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans']
plt.rcParams['svg.fonttype'] = 'none'
plt.rcParams['font.size'] = 13
plt.rcParams['axes.spines.right'] = False
plt.rcParams['axes.spines.top'] = False

# ──────────────────────────────────────────────────────────────
# Palette
# ──────────────────────────────────────────────────────────────
TEAL   = "#42949E"
GREEN  = "#3A9A42"
ORANGE = "#D48806"
PURPLE = "#6B5B9A"
BG_TEAL   = "#E0F0F0"
BG_GREEN  = "#DDF3DE"
BG_ORANGE = "#F0E0D0"
BG_PURPLE = "#E8E0F0"
WHITE = "#FFFFFF"
DARK  = "#272727"
GREY  = "#555555"
RED   = "#C0392B"

# ──────────────────────────────────────────────────────────────
# Figure
# ──────────────────────────────────────────────────────────────
W, H = 14.0, 8.4
fig, ax = plt.subplots(figsize=(W, H))
ax.set_xlim(-0.5, W + 0.5)
ax.set_ylim(0, H)
ax.axis("off")

# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────
def band(ax, y_bot, y_top, color, alpha=0.5):
    ax.add_patch(Rectangle((0, y_bot), W, y_top - y_bot,
                            facecolor=color, alpha=alpha, edgecolor="none", zorder=0))

def rbox(ax, cx, cy, w, h, label, ec=TEAL, fc=WHITE, lw=1.2,
         fs=11, bold=False, lines=None):
    """Rounded box.  cx, cy = EXACT center of the box.
    Text is placed at (cx, cy) with ha/va='center'."""
    bp = FancyBboxPatch(
        (cx - w/2, cy - h/2), w, h,
        boxstyle="round,pad=0,rounding_size=0.04",
        facecolor=fc, edgecolor=ec, linewidth=lw,
        transform=ax.transData, zorder=2,
    )
    ax.add_patch(bp)
    if lines is not None:
        n = len(lines)
        lh = fs * 0.034
        y0 = cy + (n - 1) * lh / 2
        for i, line in enumerate(lines):
            ax.text(cx, y0 - i * lh, line,
                    ha="center", va="center", fontsize=fs, color=DARK,
                    fontweight="bold" if bold else "normal",
                    transform=ax.transData, zorder=3)
    else:
        ax.text(cx, cy, label,
                ha="center", va="center", fontsize=fs, color=DARK,
                fontweight="bold" if bold else "normal",
                transform=ax.transData, zorder=3)
    return (cx, cy)

def arr(ax, x1, y1, x2, y2, color=TEAL, lw=1.5, ls="-"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", lw=lw, color=color, ls=ls))

def panel_label(ax, label, x=0.0, y=None):
    if y is None:
        y = H - 0.15
    ax.text(x, y, label, fontsize=15, fontweight="bold", color=DARK)

def band_label(ax, x, y_center, text, color, fontsize=12):
    ax.text(x, y_center, text, ha="center", va="center",
            fontsize=fontsize, color=color, fontweight="bold", rotation=90)

# ──────────────────────────────────────────────────────────────
# 4 swim lanes
# ──────────────────────────────────────────────────────────────
LANES = [
    ("Identity and request entry",     7.35, 6.35, BG_TEAL,   TEAL),
    ("Policy, persistence and delivery", 6.10, 4.95, BG_GREEN,  GREEN),
    ("Remote execution and recovery",  4.70, 3.40, BG_ORANGE, ORANGE),
    ("Operations and evidence",        3.15, 2.00, BG_PURPLE, PURPLE),
]
for label, yt, yb, bg, fg in LANES:
    band(ax, yb, yt, bg)
    band_label(ax, 0.18, (yt + yb) / 2, label, fg)

# ──────────────────────────────────────────────────────────────
# ROW 1  (top row, teal boxes)
# ──────────────────────────────────────────────────────────────
R1Y, R1H, R1W, R1_GAP, R1_X0 = 7.05, 0.55, 1.50, 0.30, 1.00
R1_LABELS = ["User / system", "API key auth", "Rate limit", "Agent Number"]
r1 = []
for i, lab in enumerate(R1_LABELS):
    cx = R1_X0 + i * (R1W + R1_GAP) + R1W / 2
    r1.append(rbox(ax, cx, R1Y - R1H/2, R1W, R1H, lab, ec=TEAL, fs=12))
for i in range(len(r1)-1):
    arr(ax, r1[i][0]+R1W/2, r1[i][1], r1[i+1][0]-R1W/2, r1[i+1][1], color=TEAL)

# ──────────────────────────────────────────────────────────────
# ROW 2  (green boxes)
# ──────────────────────────────────────────────────────────────
R2Y, R2H, R2W, R2_GAP, R2_X0 = 5.75, 0.55, 1.65, 0.25, 0.60
R2_LABELS = [
    ["Policy gate", "(id, #, status)"],
    ["Idempotency", "(unique_request_#)"],
    ["Task + message", "store (agent#)"],
    ["Routing", "(delivery tracking)"],
    ["Result store", "(progress + result)"],
]
r2 = []
for i, lab in enumerate(R2_LABELS):
    cx = R2_X0 + i*(R2W+R2_GAP) + R2W/2
    r2.append(rbox(ax, cx, R2Y-R2H/2, R2W, R2H, None, ec=GREEN, fs=10, lines=lab))
for i in range(len(r2)-1):
    arr(ax, r2[i][0]+R2W/2, r2[i][1], r2[i+1][0]-R2W/2, r2[i+1][1], color=GREEN)

# ──────────────────────────────────────────────────────────────
# ROW 3  (orange boxes)
# ──────────────────────────────────────────────────────────────
R3Y, R3H, R3W, R3_GAP, R3_X0 = 4.30, 0.50, 1.15, 0.25, 2.00
R3_LABELS = [
    ["Offline", "queue"],
    ["Websocket", "(real-time)"],
    ["SDK runtime", "(ws + heartbeat)"],
    ["OpenClaw", "(task adapter)"],
    ["Real CLI", "(to execute)"],
]
r3 = []
for i, lab in enumerate(R3_LABELS):
    cx = R3_X0 + i*(R3W+R3_GAP) + R3W/2
    r3.append(rbox(ax, cx, R3Y-R3H/2, R3W, R3H, None, ec=ORANGE, fs=10, lines=lab))
for i in range(len(r3)-1):
    arr(ax, r3[i][0]+R3W/2, r3[i][1], r3[i+1][0]-R3W/2, r3[i+1][1], color=ORANGE)

# ──────────────────────────────────────────────────────────────
# ROW 4  (lavender boxes)
# ──────────────────────────────────────────────────────────────
R4Y, R4H, R4W, R4_GAP, R4_X0 = 2.80, 0.50, 1.15, 0.25, 2.00
R4_LABELS = ["Postgres", "Redis", "Observability", "Recovery", "Secret ops"]
r4 = []
for i, lab in enumerate(R4_LABELS):
    cx = R4_X0 + i*(R4W+R4_GAP) + R4W/2
    r4.append(rbox(ax, cx, R4Y-R4H/2, R4W, R4H, lab, ec=PURPLE, fs=11))

# ──────────────────────────────────────────────────────────────
# Cross-row arrows
# ──────────────────────────────────────────────────────────────
arr(ax, r1[3][0], r1[3][1]-R1H/2, r2[2][0], r2[2][1]+R2H/2, color=GREY, lw=1.2, ls="--")
arr(ax, r2[2][0], r2[2][1]-R2H/2, r3[1][0], r3[1][1]+R3H/2, color=GREY, lw=1.2, ls="--")
arr(ax, r2[4][0], r2[4][1]-R2H/2, r3[3][0], r3[3][1]+R3H/2, color=GREY, lw=1.2, ls="--")
for si, di in [(0,0),(1,1),(2,2),(3,3)]:
    arr(ax, r3[si][0], r3[si][1]-R3H/2, r4[di][0], r4[di][1]+R4H/2, color=GREY, lw=1.0, ls="--")

# Approval diamond — placed at exact center of Row 2 first box
appr_cx = r2[0][0] - R2W/2 - 0.60
appr_cy = r2[0][1]
appr_w, appr_h = 0.65, 0.45
diamond = FancyBboxPatch(
    (appr_cx - appr_w/2, appr_cy - appr_h/2), appr_w, appr_h,
    boxstyle="round,pad=0.02,rounding_size=0.05",
    facecolor=WHITE, edgecolor=ORANGE, linewidth=1.2, zorder=2,
)
ax.add_patch(diamond)
ax.text(appr_cx, appr_cy, "Approval\n(human-in-loop)",
        ha="center", va="center", fontsize=9, color=ORANGE, zorder=3)
arr(ax, r2[0][0]-R2W/2, r2[0][1], appr_cx+appr_w/2, appr_cy, color=ORANGE, lw=1.2)

# ──────────────────────────────────────────────────────────────
# Panel a title
# ──────────────────────────────────────────────────────────────
panel_label(ax, "a", x=0.0, y=8.0)
ax.text(0.35, 8.0, "AgentNet relay architecture and task lifecycle",
        fontsize=15, fontweight="bold", color=DARK)
ax.text(0.35, 7.65,
        "The relayed entry flow of authentication, Agent Number assignment, "
        "routes asynchronous tasks, and records audit evidence.",
        fontsize=9, color=GREY)

# ──────────────────────────────────────────────────────────────
# Panel b — validation evidence cards
# ──────────────────────────────────────────────────────────────
BY = 1.55
panel_label(ax, "b", x=0.0, y=BY)
ax.text(0.35, BY, "Current validation evidence",
        fontsize=15, fontweight="bold", color=DARK)
ax.text(0.35, BY-0.30,
        "Latest states-machine: OpenClaw sub-agent supports controlled launch, "
        "private-beta and small pilot usage; public production still needs "
        "real HTTPS/WSS staging verification.",
        fontsize=9, color=GREY)

CARD_W, CARD_H, CARD_GAP, CARD_X0 = 1.55, 1.15, 0.18, 0.30
CY = BY - CARD_H - 0.55

CARDS = [
    ("20/20",    ["test suite pass rate", "identity, security, approval"],   TEAL),
    ("30 min",   ["900 cycles", "long stability", "0 drops"],               GREEN),
    ("15 agents",["8,114 hb", "combined stress", "tasks + churn"],          ORANGE),
    ("1,000",    ["0 errors", "pure write pressure", "P95 < 2s, no leak"],   PURPLE),
    ("Backup &", ["restore OK", "restore + healthz", "audit + migration"],   PURPLE),
    ("WSS staging",["not proven yet", "real domain verification", "production fallback broken"], RED),
    ("Do not",   ["overstate", "EDR is reserved, not implemented.", "Production fallback is broken."], RED),
]

for i, (val, desc, col) in enumerate(CARDS):
    cx = CARD_X0 + i*(CARD_W+CARD_GAP) + CARD_W/2
    bp = FancyBboxPatch(
        (cx-CARD_W/2, CY-CARD_H/2), CARD_W, CARD_H,
        boxstyle="round,pad=0,rounding_size=0.04",
        facecolor=WHITE, edgecolor=col, linewidth=1.5, zorder=2,
    )
    ax.add_patch(bp)
    # Value — pushed up to leave room for 3 desc lines
    ax.text(cx, CY+0.22, val, ha="center", va="center",
            fontsize=13, fontweight="bold", color=col, zorder=3)
    # Description lines
    lh = 0.13
    y0 = CY - 0.02
    for j, line in enumerate(desc):
        ax.text(cx, y0 - j*lh, line, ha="center", va="center",
                fontsize=6.5, color=GREY, zorder=3)

# ──────────────────────────────────────────────────────────────
# POST-GENERATION CHECK: verify every box center matches its text
# ──────────────────────────────────────────────────────────────
def check_alignment():
    max_off = 0.0
    n = 0
    for child in ax.get_children():
        if isinstance(child, FancyBboxPatch):
            bbox = child.get_bbox()
            cx, cy = bbox.x0 + bbox.width/2, bbox.y0 + bbox.height/2
            near = min((np.hypot(t.get_position()[0]-cx, t.get_position()[1]-cy)
                         for t in ax.texts
                         if np.hypot(t.get_position()[0]-cx, t.get_position()[1]-cy) < 1.5),
                        default=None)
            if near is not None:
                max_off = max(max_off, near)
                n += 1
    status = "OK" if max_off < 0.25 else f"WARN max_offset={max_off:.3f}"
    print(f"[CHECK] {n} boxes verified, {status}")
    return max_off

max_offset = check_alignment()

# ──────────────────────────────────────────────────────────────
# Save
# ──────────────────────────────────────────────────────────────
OUT = "E:\\VScodeProject\\Agent Relay Platform MVP\\docs\\figures\\agentnet_nature_flow"
fig.savefig(f"{OUT}.svg", bbox_inches="tight", transparent=False)
fig.savefig(f"{OUT}.pdf", bbox_inches="tight")
fig.savefig(f"{OUT}.png", bbox_inches="tight", dpi=300)
print(f"[SAVED] {OUT}.svg  {OUT}.pdf  {OUT}.png")
if max_offset > 0.25:
    print(f"[FAIL] max text-box offset = {max_offset:.3f} (threshold 0.25)")
else:
    print("[PASS] all text within 0.25 data-units of box center")
plt.close(fig)
