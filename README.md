# Synapse-1

A neural network frozen into silicon - designed, simulated and taken to layout
entirely in [Tickwave](https://tickwaveeda.vercel.app).

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
   to a sky130 layout.

Terminal alternative (any Icarus Verilog):

    ./run.sh

## Measured numbers

| Fact | Value | Where measured |
|---|---|---|
| Demo accuracy | 20/20 correct | Icarus Verilog sim (Linux) |
| Integer-model accuracy | 99.8% on 2000-image held-out synthetic set (99.75% on a second held-out seed) | trainer |
| Latency per inference | 2443 clocks | measured in simulation |
| Latency in time | 24.4 us ONLY IF timing closes at the app's 100 MHz default clock (STA has not run) | estimate |
| Throughput | ~41,000 inferences/s | conditional on the same 100 MHz closure; not measured silicon performance |
| Sim wall-clock, all 20 images | ~0.9 s | Linux sandbox, Icarus vvp |
| Size after synthesis | ~10.6k cells (generic Yosys logical map) | yosys synth; area/routability unverified until the physical flow runs |

Gates/area/power/timing on sky130 come from the app's own chip-flow run
(`runs/tw/final/metrics.json`) - no precomputed layout ships in this repo.

## Honest scope

- Trained on **synthetic** 8x8 glyph data (procedural digit templates plus
  noise, shifts and brightness jitter), not MNIST or general handwriting.
  It is a real trained network and a real chip flow - at demo scale.
- The design TARGETS the app's 100 MHz default clock with a two-stage
  pipeline (ROM read, then multiply-accumulate), one stage per clock - a
  structural intent, not a result. Whether it meets 100 MHz is decided by
  the app's OpenROAD timing analysis; no clock speed is claimed before that
  run. Cycle counts are exact; microseconds are conditional.
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

- `rtl/synapse1.v` - top: control FSM, pixel buffer, hidden activations, scores
- `rtl/mac.v` - the one shared signed multiplier
- `rtl/weights_rom.v` - GENERATED: trained weights as synthesizable ROMs
- `tb/tb_synapse1.v` - self-checking driver (embeds the 20 verified images,
  prints PASS/FAIL, exits with `$finish`)
- `data/` - the same demo images + labels as hex, plus the training report
- `train/train.py` - regenerates everything: trains, quantizes, verifies the
  exact integer arithmetic the hardware uses, rewrites weights_rom.v and the
  testbench data block (`python3 train/train.py`, needs numpy)
- `chip/config.json` - manual LibreLane config (the app's chip flow generates
  its own; this is for command-line reproduction)

Private demo repository - all rights reserved.
