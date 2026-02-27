"""
Standalone test to measure camera trigger performance.
Generates its own trigger pulses and monitors camera response.
"""
import time
import numpy as np
from nidaqmx.task import Task
from nidaqmx.constants import AcquisitionType, RegenerationMode
from sashimi.hardware.cameras.hamamatsu.interface import HamamatsuCamera, TriggerMode
from sashimi.config import read_config

print("\n" + "="*60)
print("CAMERA TRIGGER SPEED TEST - WITH TRIGGER GENERATION")
print("="*60)

# Load config
conf = read_config()

# Test parameters
SAMPLE_RATE = 40000  # 40 kHz
TRIGGER_FREQ = 12  # 12 Hz (4 planes × 3 Hz volume rate)
SAMPLES_PER_TRIGGER = int(SAMPLE_RATE / TRIGGER_FREQ)  # ~3333 samples @ 40kHz = 83.3ms
PULSE_WIDTH_SAMPLES = 100  # 2.5ms @ 40kHz
TOTAL_TRIGGERS = 4  # Generate 4 triggers per cycle
WAVEFORM_SAMPLES = TOTAL_TRIGGERS * SAMPLES_PER_TRIGGER

print(f"\n[CONFIG]")
print(f"  Sample rate: {SAMPLE_RATE} Hz")
print(f"  Trigger frequency: {TRIGGER_FREQ} Hz")
print(f"  Trigger interval: {SAMPLES_PER_TRIGGER} samples ({SAMPLES_PER_TRIGGER/SAMPLE_RATE*1000:.1f}ms)")
print(f"  Pulse width: {PULSE_WIDTH_SAMPLES} samples ({PULSE_WIDTH_SAMPLES/SAMPLE_RATE*1000:.1f}ms)")
print(f"  Waveform length: {WAVEFORM_SAMPLES} samples ({WAVEFORM_SAMPLES/SAMPLE_RATE*1000:.1f}ms)")

# Create trigger waveform
trigger_waveform = np.zeros((4, WAVEFORM_SAMPLES), dtype=np.float64)

# Generate trigger pulses on channel 3 (ao3 - camera trigger)
for i in range(TOTAL_TRIGGERS):
    start_idx = i * SAMPLES_PER_TRIGGER
    end_idx = start_idx + PULSE_WIDTH_SAMPLES
    trigger_waveform[3, start_idx:end_idx] = 5.0  # 5V trigger pulse

print(f"  Trigger pulse positions: ", end="")
for i in range(TOTAL_TRIGGERS):
    print(f"{i * SAMPLES_PER_TRIGGER} ", end="")
print()

# Initialize camera
print("\n[1] Initializing camera...")
cam = HamamatsuCamera(0, (2048, 2048))

# Configure camera settings
print("\n[2] Configuring camera settings...")
cam.binning = 4
cam.exposure_time = 10  # 10ms
cam.roi = (0, 0, 512, 512)
print(f"    Binning: {cam.binning}")
print(f"    Exposure: {cam.exposure_time}ms")
print(f"    ROI: {cam.roi}")
print(f"    Frame shape: {cam.frame_shape}")

# TEST 1: Internal/Free-running mode
print("\n" + "="*60)
print("TEST 1: FREE-RUNNING MODE (Internal Trigger)")
print("="*60)
print("\n[3a] Setting trigger mode to INTERNAL/FREE...")
cam.trigger_mode = TriggerMode.FREE

print("\n[4a] Starting acquisition in free-running mode...")
cam.start_acquisition()

print("\n[5a] Capturing frames for 3 seconds...")
frame_count = 0
start_time = time.time()

while time.time() - start_time < 3:
    frames = cam.get_frames()
    if len(frames) > 0:
        frame_count += len(frames)
        if frame_count <= 5:
            print(f"  Received {len(frames)} frame(s) - Total: {frame_count}")
    time.sleep(0.01)

cam.stop_acquisition()

print(f"\n[RESULT] Free-running mode: {frame_count} frames in 3s ({frame_count/3:.1f} fps)")

if frame_count == 0:
    print("\n[ERROR] Camera is not acquiring frames even in free-running mode!")
    print("        This indicates a camera/driver problem.")
    cam.shutdown()
    exit(1)
else:
    print("[OK] Camera can acquire frames successfully!")

# TEST 2: External trigger mode with NI DAQ
print("\n" + "="*60)
print("TEST 2: EXTERNAL TRIGGER MODE WITH NI DAQ")
print("="*60)

# Set to external trigger mode
print("\n[3b] Setting trigger mode to EXTERNAL...")
cam.trigger_mode = TriggerMode.EXTERNAL_TRIGGER

# Verify trigger settings
print("\n[4b] Current trigger configuration:")
trigger_source = cam.get_property_value("trigger_source")
trigger_mode_val = cam.get_property_value("trigger_mode")
trigger_active = cam.get_property_value("trigger_active")
trigger_polarity = cam.get_property_value("trigger_polarity")

def get_text_name(value, text_dict):
    for name, val in text_dict.items():
        if val == value:
            return name
    return f"<unknown:{value}>"

trigger_source_text = cam.get_property_text("trigger_source")
trigger_mode_text = cam.get_property_text("trigger_mode")
trigger_active_text = cam.get_property_text("trigger_active")
trigger_polarity_text = cam.get_property_text("trigger_polarity")

print(f"    trigger_source: {get_text_name(trigger_source, trigger_source_text)} ({trigger_source})")
print(f"    trigger_mode: {get_text_name(trigger_mode_val, trigger_mode_text)} ({trigger_mode_val})")
print(f"    trigger_active: {get_text_name(trigger_active, trigger_active_text)} ({trigger_active})")
print(f"    trigger_polarity: {get_text_name(trigger_polarity, trigger_polarity_text)} ({trigger_polarity})")

# Initialize NI DAQ
print("\n[5b] Setting up NI DAQ for trigger generation...")
z_board_channel = conf["z_board"]["write"]["channel"]
print(f"    Using channel: {z_board_channel}")

with Task() as write_task:
    # Add all 4 analog output channels (ao0-ao3)
    write_task.ao_channels.add_ao_voltage_chan(
        z_board_channel,
        min_val=conf["z_board"]["write"]["min_val"],
        max_val=conf["z_board"]["write"]["max_val"],
    )
    
    # Configure timing for continuous regeneration
    write_task.timing.cfg_samp_clk_timing(
        rate=SAMPLE_RATE,
        sample_mode=AcquisitionType.CONTINUOUS,
        samps_per_chan=WAVEFORM_SAMPLES,
    )
    
    write_task.out_stream.regen_mode = RegenerationMode.ALLOW_REGENERATION
    
    print("\n[6b] Starting trigger generation and camera acquisition...")
    
    # Start camera acquisition
    cam.start_acquisition()
    
    # Write and start DAQ
    write_task.write(trigger_waveform, auto_start=False)
    write_task.start()
    
    print(f"    Generating {TRIGGER_FREQ} Hz triggers on {z_board_channel}/ao3")
    print("    Monitoring camera for 20 seconds...\n")
    
    # Monitor frames
    frame_count = 0
    last_frame_time = None
    intervals = []
    start_time = time.time()
    
    try:
        while time.time() - start_time < 20:
            frames = cam.get_frames()
            
            if len(frames) > 0:
                current_time = time.time()
                
                for frame in frames:
                    frame_count += 1
                    
                    if last_frame_time is not None:
                        interval_ms = (current_time - last_frame_time) * 1000
                        intervals.append(interval_ms)
                        fps = 1000 / interval_ms if interval_ms > 0 else 0
                        print(f"Frame #{frame_count:4d} - Interval: {interval_ms:6.1f}ms ({fps:5.1f} fps)")
                    else:
                        print(f"Frame #{frame_count:4d} - First frame received")
                    
                    last_frame_time = current_time
            
            time.sleep(0.001)
    
    except KeyboardInterrupt:
        print("\n[!] Stopped by user")
    
    # Stop everything
    print("\n[7] Stopping DAQ and camera...")
    write_task.stop()
    cam.stop_acquisition()

# Calculate statistics
print("\n" + "="*60)
print("RESULTS")
print("="*60)
print(f"\nTotal frames received: {frame_count}")
print(f"Expected frames: ~{int(20 * TRIGGER_FREQ)}")

if frame_count == 0:
    print("\n[ERROR] No frames received with external triggers!")
    print("\nPossible issues:")
    print("  1. Wrong trigger connector/wiring")
    print("  2. Trigger voltage too low/high")
    print("  3. Camera trigger polarity wrong")
    print("  4. NI DAQ channel mismatch")
elif frame_count > 0:
    avg_fps = frame_count / 20
    print(f"Average frame rate: {avg_fps:.2f} fps (expected: {TRIGGER_FREQ} fps)")
    efficiency = (avg_fps / TRIGGER_FREQ) * 100
    print(f"Trigger efficiency: {efficiency:.1f}%")
    
    if len(intervals) > 0:
        intervals = np.array(intervals)
        expected_interval = 1000 / TRIGGER_FREQ
        
        print(f"\nFrame interval statistics:")
        print(f"  Expected: {expected_interval:.1f}ms")
        print(f"  Mean:     {np.mean(intervals):.1f}ms ({1000/np.mean(intervals):.1f} fps)")
        print(f"  Median:   {np.median(intervals):.1f}ms ({1000/np.median(intervals):.1f} fps)")
        print(f"  Min:      {np.min(intervals):.1f}ms")
        print(f"  Max:      {np.max(intervals):.1f}ms")
        print(f"  StdDev:   {np.std(intervals):.1f}ms")
        
        # Histogram
        print(f"\nInterval distribution:")
        bins = [0, 50, 100, 150, 200, 300, 500, 1000, 10000]
        for i in range(len(bins)-1):
            count = np.sum((intervals >= bins[i]) & (intervals < bins[i+1]))
            if count > 0:
                pct = 100 * count / len(intervals)
                print(f"  {bins[i]:5d}-{bins[i+1]:5d}ms: {count:4d} frames ({pct:5.1f}%)")
        
        # Analysis
        consistent = np.sum(np.abs(intervals - expected_interval) < 20)
        consistency_pct = 100 * consistent / len(intervals)
        print(f"\nConsistency: {consistency_pct:.1f}% of intervals within ±20ms of expected")
        
        if consistency_pct > 90:
            print("\n✓ EXCELLENT: Camera is responding consistently to triggers")
        elif consistency_pct > 70:
            print("\n⚠ GOOD: Camera mostly responsive, some jitter present")
        else:
            print("\n✗ POOR: Significant trigger timing issues detected")

# Shutdown
print("\n[8] Shutting down camera...")
cam.shutdown()

print("\n" + "="*60)
print("TEST COMPLETE")
print("="*60 + "\n")
