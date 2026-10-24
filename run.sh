#!/bin/sh
# Terminal run. The Tickwave app compiles and runs this project by itself.
set -e
mkdir -p build
iverilog -g2012 -o build/synapse1.vvp rtl/mac.v rtl/weights_rom.v rtl/synapse1.v tb/tb_synapse1.v
vvp build/synapse1.vvp
