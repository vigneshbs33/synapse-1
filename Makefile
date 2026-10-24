sim:
	mkdir -p build
	iverilog -g2012 -o build/synapse1.vvp mac.v weights_rom.v synapse1.v tb_synapse1.v
	vvp build/synapse1.vvp
clean:
	rm -rf build synapse1.vcd
