`timescale 1ns/1ps
// Synapse-1: a neural network frozen into hardware.
// 64 inputs (8x8 pixel glyph) -> 16 hidden neurons (ReLU) -> 10 class scores -> argmax.
// One shared multiplier, sequential schedule: address one clock, accumulate the next,
// so the ROM lookup and the multiply each get a full clock (targets 100 MHz, 10 ns).
module synapse1 (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,
    input  wire [7:0]  pix_data,
    input  wire        pix_valid,
    output wire        pix_ready,
    output reg         done,
    output reg  [3:0]  digit,
    output wire        busy,
    output wire [2:0]  state_o,
    output reg  [15:0] cycles_o
);
    parameter SHIFT1 = 11; // GENERATED default - patched by train/train.py, must match its report

    localparam S_IDLE = 3'd0, S_LOAD = 3'd1, S_L1 = 3'd2,
               S_L2   = 3'd3, S_SCAN = 3'd4, S_DONE = 3'd5;

    reg [2:0] state;
    reg [5:0] t;                 // tap index
    reg [3:0] ni;                // neuron / class index
    reg       phase;             // 0 = present address, 1 = multiply-accumulate
    reg [6:0] load_cnt;
    reg [7:0] pix  [0:63];
    reg [7:0] hact [0:15];
    reg signed [31:0] acc;
    reg signed [31:0] score [0:9];
    reg signed [7:0]  w_d;
    reg [7:0] x_d;
    reg signed [31:0] best;

    wire [9:0] w1_addr = {ni, t};              // 16 neurons x 64 taps
    wire [7:0] w2_addr = {ni, t[3:0]};         // 10 classes x 16 taps (ni = class)
    wire [4:0] bias_addr = (state == S_L2) ? (5'd16 + {1'b0, ni}) : {1'b0, ni};
    wire signed [7:0]  w1_q, w2_q;
    wire signed [31:0] bias_q;

    w1_rom   u_w1   (.addr(w1_addr),  .data(w1_q));
    w2_rom   u_w2   (.addr(w2_addr),  .data(w2_q));
    bias_rom u_bias (.addr(bias_addr), .data(bias_q));

    wire signed [7:0] w_sel = (state == S_L2) ? w2_q : w1_q;
    wire [7:0]        x_sel = (state == S_L2) ? hact[t[3:0]] : pix[t];

    wire signed [31:0] prod;
    mac u_mac (.x_u(x_d), .w(w_d), .prod(prod));

    wire signed [31:0] next_acc = (t == 6'd0) ? (bias_q + prod) : (acc + prod);
    wire signed [31:0] shifted  = next_acc >>> SHIFT1;
    wire [7:0] relu_clip = (next_acc < 0) ? 8'd0 :
                           (shifted > 127) ? 8'd127 : shifted[7:0];

    assign pix_ready = (state == S_LOAD);
    assign busy      = (state != S_IDLE) && (state != S_DONE);
    assign state_o   = state;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= S_IDLE; done <= 1'b0; digit <= 4'd0; cycles_o <= 16'd0;
            t <= 6'd0; ni <= 4'd0; phase <= 1'b0; load_cnt <= 7'd0;
            acc <= 32'sd0; best <= 32'sh80000000;
        end else begin
            if (state != S_IDLE && state != S_DONE) cycles_o <= cycles_o + 16'd1;
            case (state)
            S_IDLE: if (start) begin
                state <= S_LOAD; load_cnt <= 7'd0; done <= 1'b0; cycles_o <= 16'd0;
            end
            S_LOAD: if (pix_valid) begin
                pix[load_cnt] <= pix_data;
                if (load_cnt == 7'd63) begin
                    state <= S_L1; t <= 6'd0; ni <= 4'd0; phase <= 1'b0;
                end else load_cnt <= load_cnt + 7'd1;
            end
            S_L1: begin
                if (phase == 1'b0) begin
                    w_d <= w_sel; x_d <= x_sel; phase <= 1'b1;
                end else begin
                    acc <= next_acc;
                    if (t == 6'd63) begin
                        hact[ni] <= relu_clip;
                        t <= 6'd0;
                        if (ni == 4'd15) begin state <= S_L2; ni <= 4'd0; end
                        else ni <= ni + 4'd1;
                    end else t <= t + 6'd1;
                    phase <= 1'b0;
                end
            end
            S_L2: begin
                if (phase == 1'b0) begin
                    w_d <= w_sel; x_d <= x_sel; phase <= 1'b1;
                end else begin
                    acc <= next_acc;
                    if (t == 6'd15) begin
                        score[ni] <= next_acc;
                        t <= 6'd0;
                        if (ni == 4'd9) begin
                            state <= S_SCAN; ni <= 4'd0; best <= 32'sh80000000;
                        end else ni <= ni + 4'd1;
                    end else t <= t + 6'd1;
                    phase <= 1'b0;
                end
            end
            S_SCAN: begin
                if (score[ni] > best) begin best <= score[ni]; digit <= ni; end
                if (ni == 4'd9) state <= S_DONE; else ni <= ni + 4'd1;
            end
            S_DONE: begin
                done <= 1'b1;
                if (start) begin
                    state <= S_LOAD; load_cnt <= 7'd0; done <= 1'b0; cycles_o <= 16'd0;
                end
            end
            default: state <= S_IDLE;
            endcase
        end
    end
endmodule
