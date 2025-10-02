/**
 * FlashNet Screen Data Transmitter
 * Transmits data packets by flashing a screen element for photocell reception
 * Shea M Puckett 2025
 * Apache 2.0 e.g. you're on your own
 *
 * PROTOCOL OVERVIEW:
 * - 8 sync pulses (width 1) establish timing reference
 * - 1 start pulse (width 3) indicates data transmission begins
 * - Data bits encoded as pulse widths: 0-bit = width 1, 1-bit = width 2  
 * - Checksum byte (sum of all data bytes, low 8 bits) for validation
 * - Final pulse (width 4) marks end of transmission
 * 
 * INTEGRATION INSTRUCTIONS:
 * 1. Ensure target element exists in DOM and is visible to photocell
 * 2. Set pulsewidth to 60-100ms for reliable reception (e.g., 80)
 * 3. Data should be array of integers 0-255 (bytes)
 * 4. Element will flash between #888 (dark) and #eee (light) states
 * 5. Transmission is asynchronous - function returns immediately
 * 6. Element returns to neutral #ccc color when complete
 * 
 * Example Usage:
 *   const data = [0x48, 0x65, 0x6C, 0x6C, 0x6F]; // "Hello" in ASCII
 *   const flashDiv = document.getElementById('transmitter');
 *   flashnetSend(80, data, flashDiv); // 80ms pulses
 * 
 * @param {number} pulsewidth - Pulse duration in milliseconds (60-100ms recommended)
 * @param {Array<number>} data - Data bytes to transmit (0-255 each)  
 * @param {HTMLElement} elem - DOM element to flash for transmission
 */
flashnetSend = function(pulsewidth, data, elem) {
    let state = 0;        // Current flash state (0=dark, 1=light)
    let checksum = 0;     // Running checksum of data bytes
    
    // Transmission queue: each number represents pulse width in timer ticks
    // Start with a series of >8 sync pulses to ensure lock (width 1) + 1 start pulse (width 3)
    let queue = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,3]; 
    
    /**
     * Encode single byte into transmission queue
     * Adds byte to checksum and converts to bit pulses (MSB first)
     */
    let encode = function(b) { 
        checksum += b;
        // Encode each bit: 1-bits as width 2 pulses, 0-bits as width 1 pulses
        for (let mask = 0x80; mask; mask >>= 1) 
            queue.push((b & mask) ? 2 : 1); 
    }
    
    // Encode all data bytes
    data.forEach(encode);
    
    // Append checksum byte (low 8 bits of sum)
    encode(checksum & 0xff);
    
    // End transmission marker (width 4 pulse)
    queue.push(4);
    
    // Timer-based transmission: toggle element state according to pulse widths
    let timer = setInterval(() => {
        if (!queue.length) {
            // Transmission complete
            elem.style.backgroundColor = "#ccc";  // Neutral color
            clearInterval(timer);
        } else if (--queue[0] <= 0) {
            // Current pulse complete - move to next pulse and toggle state
            queue.shift();
            state = !state;
            elem.style.backgroundColor = state ? "#888" : "#eee";  // Dark/Light
        }
        // else: continue current pulse (decrement counter)
    }, pulsewidth);
}

