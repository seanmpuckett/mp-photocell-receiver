# pc_receiver
# Photocell-based data receiver for MicroPython
# 2025 Shea M Puckett
# Apache 2.0 license

"""
THEORY OF OPERATION:
This module implements a digital data receiver that uses light pulses (LED/screen flashing)
detected by a photocell to transmit binary data packets. The protocol uses pulse width
modulation where different pulse durations represent different bit values or control signals.

Protocol Structure:
1. SYNC PHASE: 8 consistent sync pulses establish timing reference
2. START PULSE: Longer pulse indicates data transmission begins  
3. DATA PHASE: Short pulses = 0 bits, medium pulses = 1 bits
4. CHECKSUM: Last byte is sum of all data bytes for validation

Signal Processing Chain:
- Raw ADC values → DC bias removal → Z-score normalization → Digital filtering
- Pulse width measurement → Protocol decoding → Packet assembly → Checksum validation

INTEGRATION INSTRUCTIONS:
1. Sample photocell ADC at consistent ~10ms intervals (100Hz recommended)
2. Light transitions should be 60-100ms minimum for reliable detection
3. Create handler function: handler(event_type, data)
   - event_type 0: Sync detected (data=None)
   - event_type 1: Byte received (data=byte_value) 
   - event_type 2: Valid packet (data=bytearray)
   - event_type 3: Invalid packet/checksum fail (data=bytearray)
4. Call process(adc_value) for each sample
5. Can batch process buffered samples - timing is not critical at process level

Example Usage:
    def my_handler(event, data):
        if event == 2:  # Valid packet received
            print(f"Received: {data}")
    
    receiver = pc_receiver(my_handler)
    # In main loop or timer interrupt:
    receiver.process(adc_reading)
"""

import math

# Protocol Constants
LR_SYNCS = const(8)        # Number of sync pulses required
LR_PULSEMAX = const(200)   # Maximum pulse width (~2 seconds at 10ms sampling)
LR_MAXDATA = const(70)     # Maximum data packet length

# Debug flags (set to 0 for production)
DEBUG = const(0)
SCOPE_SCALE = 50 / 3000    # ASCII oscilloscope scaling factor

class pc_receiver:
    def __init__(self, _handler):
        # Pulse width thresholds (calculated from sync pulses)
        self.p1 = 0            # Sync/data boundary (1.5x avg sync width)
        self.p2 = 0            # 0/1 bit boundary (2.5x avg sync width) 
        self.pmax = 0          # Maximum valid pulse (4x avg sync width)
        
        # Signal processing variables
        self.psampler = 0      # Accumulator for sync pulse measurements
        self.pavg = 0          # Running average of signal level (DC bias)
        self.pwidth = 0        # Current pulse width counter
        self.lsignal = 0       # Previous signal level (for edge detection)
        
        # Digital filter (debouncer) 
        self.db = 0            # Filtered signal level
        self.dc = 0            # Debounce counter
        
        # Protocol state machine
        self.rstate = 1        # Receive state (1=sync hunting, 8+=data reception)
        self.receiving = 0     # Public flag indicating active reception
        
        # Data assembly
        self.bits = 0          # Bits collected in current byte
        self.byte = 0          # Current byte being assembled
        self.inbuf = bytearray()  # Packet buffer
        
        # Event callback
        self.handler = _handler
        
        # Noise measurement (for development/tuning only)
        self.stdct = 0         # Sample count for standard deviation
        self.stdtotal = 0      # Sum of squared deviations
        self.stddev = 2        # Signal noise floor (in ADC units)

    def calcstdev(self, p):
        """Calculate signal standard deviation for noise floor estimation.
        Call during development to determine appropriate stddev value, then hardcode it.
        Do not use in production - adds computational overhead."""
        if self.stdct == 0:
            self.pavg = p
            psig = 0
        else:
            psig = p - self.pavg
        
        self.stdtotal += psig * psig
        self.stdct += 1
        
        if self.stdct >= 256:
            self.stddev = max(1, math.sqrt(self.stdtotal / self.stdct))
            print("Standard deviation is", self.stddev)
            # Decay accumulators to prevent overflow
            self.stdtotal >>= 1
            self.stdct >>= 1

    def process(self, p):
        """Process single ADC sample. Call at consistent intervals (~10ms).
        
        Args:
            p: Raw photocell ADC value (0-4095 typical for 12-bit ADC)
        """
        if DEBUG > 1:
            self.calcstdev(p)  # Remove in production
        
        # Normalize signal: remove DC bias and scale by noise floor
        psig = (p - self.pavg) / self.stddev
        
        # Convert to binary with hysteresis (Z-score > 2 = significant signal)
        if abs(psig) > 2:
            signal = 1 if psig > 0 else 0
        else:
            signal = self.lsignal  # Hold last state for weak signals
        
        # Digital low-pass filter to eliminate noise spikes
        if signal != self.db:
            self.dc += 1
            if self.dc > 1:  # Require 2 consistent samples to change
                self.db = signal
                self.dc = 0
            else:
                signal = self.db  # Use filtered value
        else:
            self.dc = 0
        
        # Update DC bias with adaptive time constant
        # Faster adaptation during sync (rstate 1), slower during data
        f = self.rstate * 4 + 8
        self.pavg = (p + self.pavg * f) // (f + 1)
        
        # Debug: ASCII oscilloscope display
        if DEBUG:
            scope = ['.'] * 50
            scope[int(self.pavg * SCOPE_SCALE)] = '|'  # DC level
            scope[int(p * SCOPE_SCALE)] = "*"          # Current sample
            print("".join(scope), "signal", signal)
        
        # Pulse width measurement and protocol processing
        done = 0
        if signal == self.lsignal:
            # Continue current pulse
            self.pwidth += 1
            # Timeout check during data reception
            if self.rstate >= LR_SYNCS and self.pwidth > self.pmax:
                done = 1  # Pulse too long - abort
        else:
            # Signal transition - process completed pulse
            if self.pwidth > LR_PULSEMAX:
                done = 1  # Pulse way too long - abort
            
            if self.rstate < LR_SYNCS:
                # SYNC PHASE: Accumulate consistent timing reference
                if self.rstate == 1:
                    # First pulse - initialize
                    self.psampler = self.pwidth
                    self.rstate = 1
                else:
                    # Check if pulse matches previous sync pulses (within 33% tolerance)
                    avw = self.psampler / (self.rstate - 1)
                    tolerance = abs(avw - self.pwidth) * 3
                    if tolerance <= avw:
                        # Good sync pulse
                        self.rstate += 1
                        self.psampler += self.pwidth
                        if self.rstate >= LR_SYNCS:
                            # Got enough sync pulses - calculate thresholds
                            avg_sync = self.psampler / self.rstate
                            self.p1 = int(avg_sync * 1.5 + 0.5)    # Sync/data boundary
                            self.p2 = int(avg_sync * 2.5 + 0.5)    # 0/1 bit boundary  
                            self.pmax = int(avg_sync * 4 + 0.5)    # Max valid pulse
                            self.handler(0, None)  # Signal sync complete
                    else:
                        # Bad sync - restart
                        self.psampler = self.pwidth
                        self.rstate = 1
            else:
                # DATA PHASE: Decode pulse widths to bits/control
                if self.pwidth < self.p1:
                    pulse_type = 0  # Short pulse (sync-like, shouldn't happen)
                elif self.pwidth < self.p2:
                    pulse_type = 1  # Medium pulse = data bit
                elif self.pwidth < self.pmax:
                    pulse_type = 2  # Long pulse = start/control
                else:
                    pulse_type = 3  # Too long = error
                
                if self.rstate > LR_SYNCS:
                    # Already receiving data
                    if pulse_type > 1:
                        done = 1  # Invalid pulse during data - abort
                    else:
                        # Assemble data bits (pulse_type 0=bit 0, pulse_type 1=bit 1)
                        self.byte = (self.byte << 1) | pulse_type
                        self.bits += 1
                        if self.bits >= 8:
                            # Complete byte received
                            if self.byte > 0:
                                self.receiving += 1  # Count non-zero bytes
                            self.handler(1, self.byte)  # Report byte
                            self.inbuf.append(self.byte)
                            self.byte = 0
                            self.bits = 0
                            if len(self.inbuf) >= LR_MAXDATA:
                                done = 1  # Buffer full - complete packet
                else:
                    # Waiting for start pulse after sync
                    if pulse_type == 3:
                        done = 1  # Error pulse - abort
                    elif pulse_type == 2:
                        # Start pulse received - begin data collection
                        self.rstate += 1
                        self.bits = 0
                        self.byte = 0
                        self.receiving = 1
                    # pulse_type 0,1 ignored (noise after sync)
            
            self.pwidth = 1  # Start counting new pulse
        
        self.lsignal = signal  # Remember current signal level
        
        # Packet completion and validation
        if done:
            if self.rstate > 1:  # Were we receiving something?
                if self.receiving > 2:  # Got substantial data
                    # Extract data and checksum
                    data = self.inbuf[0:-1]  # All but last byte
                    checksum = self.inbuf[-1] if self.inbuf else 0
                    # Validate checksum (sum of data bytes, low 8 bits)
                    valid = (sum(data) & 0xff) == checksum
                    self.handler(2 if valid else 3, data)  # Report result
                
                # Reset for next packet
                self.rstate = 1
                self.receiving = 0
                self.inbuf = bytearray()

