#!/usr/bin/env python3
"""
Synapse-1 trainer.
Trains a 64->16->10 MLP to recognize 8x8 handwritten-style digit glyphs,
quantizes it to the exact integer arithmetic the RTL implements, verifies
bit-exact accuracy, and emits:
  rtl/weights_rom.v   - trained weights frozen into synthesizable Verilog ROMs
  data/test_images.hex, data/test_labels.hex - verified demo images
Deterministic (fixed seed). Re-run: python3 train.py
"""
import numpy as np, os, math

SEED = 7
HIDDEN = 16
WQ1 = 64.0     # layer-1 weight quantization scale (weights ~ Q2.6)
WQ2 = 64.0     # layer-2 weight quantization scale
N_TRAIN = 8000
N_TEST  = 2000
EPOCHS  = 60
LR      = 0.05
BATCH   = 256

rng = np.random.default_rng(SEED)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- 8x8 base glyphs (8 cols x 8 rows) ----
GLYPHS = [
 ["........",".XXXXXX.","XX....XX","XX....XX","XX....XX","XX....XX",".XXXXXX.","........"],  # wait need exact 8x8; replaced below
]
GLYPHS = [
 [".XXXXXX.","XX....XX","XX....XX","XX....XX","XX....XX","XX....XX","XX....XX",".XXXXXX."],  # 0
 ["...XX...","..XXX...",".XXXX...","...XX...","...XX...","...XX...","...XX...",".XXXXXX."],  # 1
 [".XXXXXX.","XX....XX","......XX",".....XX.","....XX..","...XX...","..XX....","XXXXXXXX"],  # 2
 [".XXXXXX.","XX....XX","......XX","..XXXXX.","......XX","......XX","XX....XX",".XXXXXX."],  # 3
 ["....XXX.","...XXXX.","..XX.XX.",".XX..XX.","XX...XX.","XXXXXXXX",".....XX.",".....XX."],  # 4
 ["XXXXXXXX","XX......","XXXXXXX.","XX....XX","......XX","......XX","XX....XX",".XXXXXX."],  # 5
 ["..XXXX..",".XX.....","XX......","XXXXXXX.","XX....XX","XX....XX","XX....XX",".XXXXXX."],  # 6
 ["XXXXXXXX","XX....XX",".....XX.","....XX..","...XX...","...XX...","..XX....","..XX...."],  # 7
 [".XXXXXX.","XX....XX","XX....XX",".XXXXXX.","XX....XX","XX....XX","XX....XX",".XXXXXX."],  # 8
 [".XXXXXX.","XX....XX","XX....XX","XX....XX",".XXXXXXX","......XX","....XX..",".XXXX..."],  # 9
]
for g in GLYPHS:
    assert len(g) == 8 and all(len(r) == 8 for r in g), "glyph must be 8x8"

def render(d, r):
    img = np.array([[1.0 if c == 'X' else 0.0 for c in row] for row in GLYPHS[d]])
    dy, dx = int(r.integers(-1, 2)), int(r.integers(-1, 2))
    img = np.roll(img, (dy, dx), (0, 1))
    if dy > 0: img[:dy, :] = 0
    elif dy < 0: img[dy:, :] = 0
    if dx > 0: img[:, :dx] = 0
    elif dx < 0: img[:, dx:] = 0
    img *= r.uniform(0.55, 1.0)                              # brightness
    img += (r.random((8, 8)) < r.uniform(0.0, 0.05)) * r.uniform(0.2, 0.6, (8, 8))  # salt
    erase = (r.random((8, 8)) < r.uniform(0.0, 0.03)) & (img > 0.5)                 # pepper
    img[erase] = 0.0
    return np.clip(img, 0.0, 1.0)

def make_set(n, r):
    X = np.empty((n, 64)); y = np.empty(n, dtype=int)
    for i in range(n):
        d = i % 10
        X[i] = render(d, r).reshape(-1)
        y[i] = d
    p = r.permutation(n)
    return X[p], y[p]

Xtr, ytr = make_set(N_TRAIN, rng)
Xte, yte = make_set(N_TEST, rng)

# ---- float training (ReLU MLP, cross-entropy, SGD+momentum) ----
W1 = rng.normal(0, 0.15, (HIDDEN, 64)); b1 = np.zeros(HIDDEN)
W2 = rng.normal(0, 0.15, (10, HIDDEN)); b2 = np.zeros(10)
vW1 = np.zeros_like(W1); vb1 = np.zeros_like(b1)
vW2 = np.zeros_like(W2); vb2 = np.zeros_like(b2)
MOM = 0.9
for ep in range(EPOCHS):
    p = rng.permutation(N_TRAIN)
    for s in range(0, N_TRAIN, BATCH):
        idx = p[s:s+BATCH]
        x = Xtr[idx]; t = ytr[idx]
        h_pre = x @ W1.T + b1
        h = np.maximum(h_pre, 0)
        z = h @ W2.T + b2
        z -= z.max(axis=1, keepdims=True)
        e = np.exp(z); sm = e / e.sum(axis=1, keepdims=True)
        sm[np.arange(len(t)), t] -= 1
        sm /= len(t)
        gW2 = sm.T @ h; gb2 = sm.sum(0)
        dh = (sm @ W2) * (h_pre > 0)
        gW1 = dh.T @ x; gb1 = dh.sum(0)
        vW1 = MOM*vW1 - LR*gW1; W1 += vW1
        vb1 = MOM*vb1 - LR*gb1; b1 += vb1
        vW2 = MOM*vW2 - LR*gW2; W2 += vW2
        vb2 = MOM*vb2 - LR*gb2; b2 += vb2
    if (ep+1) % 20 == 0:
        h = np.maximum(Xte @ W1.T + b1, 0)
        acc = (np.argmax(h @ W2.T + b2, 1) == yte).mean()
        print(f"epoch {ep+1:3d}  float test acc {acc*100:.2f}%")

def float_acc(X, y):
    h = np.maximum(X @ W1.T + b1, 0)
    return (np.argmax(h @ W2.T + b2, 1) == y).mean()

facc = float_acc(Xte, yte)
print(f"FINAL float test acc {facc*100:.2f}%")

# ---- quantize to the RTL's exact integer arithmetic ----
W1q = np.clip(np.round(W1 * WQ1), -127, 127).astype(np.int64)
W2q = np.clip(np.round(W2 * WQ2), -127, 127).astype(np.int64)
K1 = 255.0 * WQ1                       # pix(0..255)*W1q approx 255*WQ1*(W1.x)
B1q = np.round(b1 * K1).astype(np.int64)

PIXte = np.round(Xte * 255).astype(np.int64)
A1max = (PIXte @ W1q.T + B1q).max()
S1 = max(0, int(math.floor(math.log2(max(A1max, 1) / 110.0))))  # headroom to 127
HG = K1 / (2 ** S1)                    # hidden gain: h ~= HG * relu(y1)
B2q = np.round(b2 * WQ2 * HG).astype(np.int64)

def int_forward(pix):
    """pix: (64,) uint8 values 0..255. Bit-exact with rtl/synapse1.v."""
    A1 = W1q @ pix.astype(np.int64) + B1q            # (16,) int32-range
    h = np.where(A1 < 0, 0, A1 >> S1)
    h = np.minimum(h, 127).astype(np.int64)
    A2 = W2q @ h + B2q                               # (10,)
    return int(np.argmax(A2)), A2, h

preds = np.array([int_forward(p)[0] for p in PIXte])
iacc = (preds == yte).mean()
print(f"integer (RTL-exact) test acc {iacc*100:.2f}%  | shift S1={S1}, A1max={A1max}")
assert iacc >= 0.95, "quantized accuracy too low - retrain/tune"

# ---- pick 20 demo images: 2 per digit, integer-verified correct ----
demo_idx, per_digit = [], {d: 0 for d in range(10)}
for i in range(N_TEST):
    d = yte[i]
    if per_digit[d] < 2 and preds[i] == d:
        demo_idx.append(i); per_digit[d] += 1
    if len(demo_idx) == 20: break
assert len(demo_idx) == 20, "could not find 20 verified demo images"

# ---- emit rtl/weights_rom.v ----
def s8(v):  return f"8'sd{v}" if v >= 0 else f"-8'sd{-v}"
def s32(v): return f"32'sd{v}" if v >= 0 else f"-32'sd{-v}"
os.makedirs(ROOT, exist_ok=True)
with open(os.path.join(ROOT, "weights_rom.v"), "w") as f:
    f.write("// GENERATED by train/train.py - trained Synapse-1 weights frozen in silicon.\n")
    f.write("// Do not hand-edit; re-run the trainer to regenerate. Seed %d, int acc %.2f%%.\n\n" % (SEED, iacc*100))
    f.write("module w1_rom(input wire [9:0] addr, output reg signed [7:0] data);\nalways @* begin\n  case (addr)\n")
    for n in range(HIDDEN):
        for t in range(64):
            f.write(f"    10'd{n*64+t}: data = {s8(int(W1q[n,t]))};\n")
    f.write("    default: data = 8'sd0;\n  endcase\nend\nendmodule\n\n")
    f.write("module w2_rom(input wire [7:0] addr, output reg signed [7:0] data);\nalways @* begin\n  case (addr)\n")
    for k in range(10):
        for n in range(HIDDEN):
            f.write(f"    8'd{k*HIDDEN+n}: data = {s8(int(W2q[k,n]))};\n")
    f.write("    default: data = 8'sd0;\n  endcase\nend\nendmodule\n\n")
    f.write("module bias_rom(input wire [4:0] addr, output reg signed [31:0] data);\nalways @* begin\n  case (addr)\n")
    for n in range(HIDDEN):
        f.write(f"    5'd{n}: data = {s32(int(B1q[n]))};\n")
    for k in range(10):
        f.write(f"    5'd{HIDDEN+k}: data = {s32(int(B2q[k]))};\n")
    f.write("    default: data = 32'sd0;\n  endcase\nend\nendmodule\n")

# ---- emit demo images + labels ----
os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
with open(os.path.join(ROOT, "data", "test_images.hex"), "w") as f:
    for i in demo_idx:
        for v in PIXte[i]:
            f.write(f"{int(v):02x}\n")
with open(os.path.join(ROOT, "data", "test_labels.hex"), "w") as f:
    for i in demo_idx:
        f.write(f"{int(yte[i]):x}\n")
with open(os.path.join(ROOT, "TRAINING.md"), "w") as f:
    f.write(f"Synapse-1 training report (seed {SEED})\n")
    f.write(f"float test acc {facc*100:.2f}% | integer RTL-exact acc {iacc*100:.2f}% | shift S1={S1}\n")
    f.write(f"demo images: 20 (2 per digit), all verified correct by the integer model\n\n")
    for j, i in enumerate(demo_idx):
        f.write(f"image {j:2d}: label {yte[i]} pred {preds[i]}\n")

print("wrote weights_rom.v, data/test_images.hex, data/test_labels.hex, TRAINING.md")
print(f"demo images verified: {[int(yte[i]) for i in demo_idx]}")

# ---- held-out evaluation with a different seed (fresh noise instances) ----
rng_hold = np.random.default_rng(99)
Xh, yh = make_set(2000, rng_hold)
PIXh = np.round(Xh * 255).astype(np.int64)
predh = np.array([int_forward(p)[0] for p in PIXh])
hacc = (predh == yh).mean()
print(f"held-out seed-99 integer acc {hacc*100:.2f}%")
with open(os.path.join(ROOT, "TRAINING.md"), "a") as f:
    f.write(f"\nheld-out seed-99 integer acc {hacc*100:.2f}%\n")

# ---- patch rtl/synapse1.v SHIFT1 to match this run ----
import re
RTLP = os.path.join(ROOT, "synapse1.v")
with open(RTLP) as f: rtxt = f.read()
rtxt2 = re.sub(r"parameter SHIFT1 = \d+;", f"parameter SHIFT1 = {S1};", rtxt)
assert rtxt2 != rtxt or f"parameter SHIFT1 = {S1};" in rtxt, "SHIFT1 patch failed"
with open(RTLP, "w") as f: f.write(rtxt2)

# ---- embed verified demo data into tb/tb_synapse1.v ----
TB = os.path.join(ROOT, "tb_synapse1.v")
BEGIN = "// ====BEGIN GENERATED DATA===="
ENDM = "// ====END GENERATED DATA===="
lines = []
lines.append(f"    localparam NIMG = {len(demo_idx)};")
lines.append(f"    reg [7:0] img [0:{len(demo_idx)*64-1}];")
lines.append(f"    reg [3:0] exp_label [0:{len(demo_idx)-1}];")
lines.append( "    reg [7:0] exp_h [0:3];")
lines.append( "    reg signed [31:0] exp_s [0:2];")
lines.append( "    initial begin")
for jj, ii in enumerate(demo_idx):
    for kk, vv in enumerate(PIXte[ii]):
        lines.append(f"        img[{jj*64+kk}] = 8'h{int(vv):02x};")
for jj, ii in enumerate(demo_idx):
    lines.append(f"        exp_label[{jj}] = 4'd{int(yte[ii])};")
pred0, A2_0, h_0 = int_forward(PIXte[demo_idx[0]])
for m in range(4):
    lines.append(f"        exp_h[{m}] = 8'd{int(h_0[m])};")
for m in range(3):
    v = int(A2_0[m])
    lines.append(f"        exp_s[{m}] = 32'sd{v};" if v >= 0 else f"        exp_s[{m}] = -32'sd{-v};")
lines.append( "    end")
block = "\n".join(lines) + "\n"
with open(TB) as f: ttxt = f.read()
bi = ttxt.index(BEGIN); ei = ttxt.index(ENDM)
ttxt = ttxt[:bi+len(BEGIN)] + "\n" + block + ttxt[ei:]
with open(TB, "w") as f: f.write(ttxt)
print(f"patched SHIFT1={S1} into synapse1.v and embedded {len(demo_idx)} images into tb_synapse1.v")
