# Synapse-1

A neural network frozen into silicon - designed and simulated in
[Tickwave](https://tickwaveeda.vercel.app), and taken all the way to a real
sky130 layout with the same open silicon flow the app drives.

Synapse-1 is a tiny inference chip that recognizes hand-drawn digit glyphs
(8x8 pixels, 0-9). A two-layer neural network (64 -> 16 -> 10) is trained in
Python, quantized to integers, and compiled into Verilog ROMs - the trained
weights are literally synthesized into the chip. Feed it pixels, it tells you
the digit.

## Demo in Tickwave (2 minutes)

1. Clone this repo and open the folder in Tickwave.
2. Press **Run**. The console renders each glyph as ASCII art, then the chip's
   prediction: `RESULT: 20/20 PASS`. It also cross-checks the chip's internal
   neuron activations bit-for-bit against the Python trainer's integer model.
3. The **waveform** opens automatically: watch `state_o` walk through
   LOAD -> L1 (hidden layer) -> L2 (output scores) -> SCAN (argmax) -> DONE,
   and `cycles_o` count the exact inference latency.
4. Open the **Gates** pane to see the synthesized netlist, then run the
   **chip flow** (where the chip backend is installed) to place and route it
   to a sky130 layout. A precomputed GDS from a Linux run of this exact
   design (see "Silicon run" below) also exists as a private build artifact
   and can be opened in the Layout view if the backend is not installed.

Terminal alternative (any Icarus Verilog):

    ./run.sh

## Measured numbers

| Fact | Value | Where measured |
|---|---|---|
| Demo accuracy | 20/20 correct | Icarus Verilog sim (Linux) |
| Integer-model accuracy | 99.8% on 2000-image held-out synthetic set (99.75% on a second held-out seed) | trainer |
| Latency per inference | 2443 clocks | measured in simulation |
| Latency in time | 24.4 us at 100 MHz | the design closes 100 MHz at typical/fast corners (real STA below); slow/hot corner does NOT close |
| Throughput | ~41,000 inferences/s at 100 MHz | same corner caveat; not measured on silicon |
| Sim wall-clock, all 20 images | ~1.3 s inside the app's own run path | Tickwave app integration run, Linux |
| Generic synthesis (Gates pane) | 6,652 cells / ~11.7k gate-equivalents / logic depth 74, ~12 s | Tickwave app integration run, Linux WASM Yosys; area/routability unverified until the physical flow runs |

## Silicon run (actual, precomputed on Linux)

A full RTL-to-GDS flow of this exact tree was run with LibreLane 3.0.16 +
sky130A (sky130_fd_sc_hd), using the app's generated config and SDC
(10 ns clock target). This was a Linux command-line run of the same flow
the app drives - not a Windows laptop run, and not driven end-to-end from
the app UI.

| Check | Result |
|---|---|
| GDS | produced, 13,120,198 bytes (private build artifact, stored gzipped at results/tw-run-1/synapse1.gds.gz) |
| Die | 377.2 x 387.9 um, core utilization 59.4% |
| Instances | 24,562 placed (8,276 standard cells; rest are filler/tap/buffer) |
| Power (typical corner) | ~35.8 mW total (16.0 internal + 19.9 switching) |
| DRC | 0 errors - detailed route, Magic and KLayout |
| LVS | 0 errors |
| Antenna | 0 violations |
| Hold timing | clean at every corner (worst slack +0.068 ns) |
| Setup @ 100 MHz, typical (tt 25C 1.8V) | PASS: +0.651 ns slack (nominal view), +0.479 ns (max view) |
| Setup @ 100 MHz, fast (ff -40C 1.95V) | PASS: +4.06 ns slack (max view) |
| Setup @ 100 MHz, slow/hot (ss 100C 1.6V) | FAIL: -8.153 ns worst slack (max view; -7.794 ns in the nominal view), 1,272 setup violations counted across the three ss STA views (429 max / 428 nom / 415 min; a sum of per-view counts, not unique endpoints), plus 806 slew and 72 max-cap violations at the max ss view |

What this means, honestly: the layout is real - DRC/LVS/antenna
clean and meets its 100 MHz target on typical and fast silicon. It is NOT
closed across all corners and NOT fab-ready; the slow/hot corner would need
deeper pipelining or a relaxed clock. For the demo, the typical-corner
numbers stand and the slow-corner miss is on the table. (Overall worst
setup slack across all corners: -8.153 ns, from the run's metrics.json -
`timing__setup__ws__corner:max_ss_100C_1v60`.)

Manual reproduction (same commands the app flow used):

    mkdir -p src && cp synapse1.v mac.v weights_rom.v src/
    librelane config.json   # LibreLane 3.0.16 with the sky130A PDK installed

## Honest scope

- Trained on **synthetic** 8x8 glyph data (procedural digit templates plus
  noise, shifts and brightness jitter), not MNIST or general handwriting.
  It is a real trained network and a real chip flow - at demo scale.
- Clock reality: the design uses a two-stage pipeline (ROM read, then
  multiply-accumulate), one stage per clock, targeting the app's 100 MHz
  default. Real signoff STA (below) shows 100 MHz closes at typical and
  fast corners and FAILS at the slow/hot corner - so microseconds and
  throughput hold for typical silicon, not worst-case silicon.
- Everything here is free/open tooling: Icarus Verilog, Yosys, LibreLane,
  sky130A.

## How it works

```
 pixel stream (64 x 8-bit)          weights: 1,184 trained int8 values
        |                            frozen into Verilog ROMs
        v                            (generated, do not hand-edit)
   +---------+     +-------+     +--------+     +---------+
   |  LOAD   | --> |  L1   | --> |  L2    | --> |  SCAN   | --> digit[3:0] + done
   | 64 cyc  |     | 16n x |     | 10 x   |     | argmax  |
   |         |     | 64 MAC|     | 16 MAC |     | 10 cyc  |
   +---------+     +-------+     +--------+     +---------+
                    ReLU, >>11                  scores[10]
```

All Verilog sits flat at the repository root (the app's Gates/flow engine
works on root-level sources):

- `synapse1.v` - top: control FSM, pixel buffer, hidden activations, scores
- `mac.v` - the one shared signed multiplier
- `weights_rom.v` - GENERATED: trained weights as synthesizable ROMs
- `tb_synapse1.v` - self-checking driver (embeds the 20 verified images,
  prints PASS/FAIL, exits with `$finish`)
- `TRAINING.md` - generated training/verification report
- `train/train.py` - regenerates everything: trains, quantizes, verifies the
  exact integer arithmetic the hardware uses, rewrites weights_rom.v and the
  testbench data block (`python3 train/train.py`, needs numpy). Raw hex copies
  of the images/labels are written to `data/` as local artifacts (gitignored;
  the demo does not read them - the testbench is self-contained)
- `config.json` + `design.sdc` - manual LibreLane config for command-line
  reproduction (the app's chip flow generates its own; these files are not
  app project files)

Private demo repository - all rights reserved.
