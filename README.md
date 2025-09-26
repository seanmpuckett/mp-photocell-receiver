# FlashNet: Optical Data Transmission

A simple, reliable system for transmitting digital data using screen flashing and photocell reception. Ideal for air-gapped communication, IoT sensor data collection, and educational demonstrations.

## How It Works

FlashNet uses **pulse width modulation** over light signals to transmit binary data:

1. **JavaScript transmitter** flashes a screen element with precisely timed pulses
2. **MicroPython receiver** uses a photocell to detect light changes and decode data
3. Built-in **error detection** via checksum validation ensures data integrity

The protocol uses different pulse widths to represent sync signals, start markers, data bits (0/1), and transmission end markers.

## Quick Start

### Transmitter (JavaScript/Web)
```javascript
// Flash "Hello" message to connected microcontroller
const data = [0x48, 0x65, 0x6C, 0x6C, 0x6F]; // ASCII bytes
const flashDiv = document.getElementById('transmitter');
flashnetSend(80, data, flashDiv); // 80ms pulse width
```

### Receiver (MicroPython)
```python
def handle_data(event, data):
    if event == 2:  # Valid packet received
        print("Received:", ''.join(chr(b) for b in data))

receiver = pc_receiver(handle_data)

# In main loop (call every ~10ms)
adc_value = photocell.read_u16()  # Read photocell
receiver.process(adc_value)
```

## Use Cases

- **Air-gapped communication** - Send data to isolated systems
- **IoT sensor networks** - Collect data from battery-powered devices  
- **Educational projects** - Demonstrate optical communication principles
- **Backup data channels** - Secondary communication path when RF is unavailable
- **Screen-to-device configuration** - Transfer settings/credentials via display

## Technical Specifications

- **Data rate**: ~10-50 bytes/second (depending on pulse timing)
- **Range**: Limited by photocell sensitivity (typically 0.5-2 meters)
- **Error detection**: 8-bit checksum validation
- **Maximum packet**: 70 bytes
- **Timing**: 60-100ms pulses recommended for reliability

## Hardware Requirements

### Transmitter
- Any device with a web browser and display
- Smartphone, tablet, laptop, or desktop computer

### Receiver  
- Microcontroller with ADC input (Arduino, Raspberry Pi Pico, ESP32, etc.)
- Photocell/light-dependent resistor (LDR)
- Pull-up resistor (1-10kΩ typical)

### Simple Wiring
```
  V++
   |
 10kΩ
   |
   +---- Photocell ---- + ---- ADC Pin
                        |
                       10kΩ
                        |
                       GND
```

## Integration Guide

1. **Set up hardware** - Connect photocell to microcontroller ADC
2. **Install receiver code** - Copy `pc_receiver.py` to your MicroPython device
3. **Create handler** - Write function to process received data
4. **Sample consistently** - Call `receiver.process()` every 10ms with ADC readings
5. **Add transmitter** - Include JavaScript function in your web interface

## Protocol Details

- **Sync phase**: 8 consistent pulses establish timing reference
- **Start pulse**: Longer pulse indicates data transmission begins
- **Data encoding**: Short pulse = 0 bit, medium pulse = 1 bit
- **Checksum**: Last byte validates entire packet
- **Error handling**: Invalid packets are flagged and can be retransmitted

## Performance Tips

- **Consistent timing** - Sample photocell at regular intervals (timer interrupt recommended)
- **Stable lighting** - Minimize ambient light changes during transmission
- **Signal strength** - Position photocell close to display for best results
- **Noise filtering** - Built-in digital filtering handles minor interference

## License

Apache 2.0 - Use freely in personal and commercial projects

## Contributing

Issues and pull requests welcome! Potential improvements:
- Forward error correction
- Multi-channel transmission  
- Protocol optimization
- Additional platform support
