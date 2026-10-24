`timescale 1ns/1ps
// One shared multiplier: unsigned 8-bit pixel/activation x signed 8-bit weight.
module mac (
    input  wire [7:0]        x_u,
    input  wire signed [7:0] w,
    output wire signed [31:0] prod
);
    assign prod = $signed({1'b0, x_u}) * $signed(w);
endmodule
