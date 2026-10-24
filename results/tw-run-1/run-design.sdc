# Written by Tickwave. Units: ns and pF.
create_clock [get_ports clk] -name clk -period 10
set_clock_uncertainty 0.25 [get_clocks clk]
set clk_in [get_ports clk]
set clk_idx [lsearch [all_inputs] $clk_in]
set data_in [lreplace [all_inputs] $clk_idx $clk_idx ""]
set_input_delay 2 -clock [get_clocks clk] $data_in
set_output_delay 2 -clock [get_clocks clk] [all_outputs]
set_driving_cell -lib_cell sky130_fd_sc_hd__inv_2 -pin Y $data_in
set_load 0.033 [all_outputs]
