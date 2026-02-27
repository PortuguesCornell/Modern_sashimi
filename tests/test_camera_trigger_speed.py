"""
Standalone test to measure camera trigger performance.
Tests if the camera can keep up with external triggers without the full application.
"""
import ctypes
import time
import numpy as np
from sashimi.hardware.cameras.hamamatsu.interface import HamamatsuCamera, TriggerMode

print("\n" + "="*60)
print("CAMERA TRIGGER SPEED TEST")
print("="*60)

# Initialize camera
print("\n[1] Initializing camera...")
cam = HamamatsuCamera(0, (2048, 2048))

# Configure camera settings
print("[2] Configuring camera settings...")
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

print("\n[5a] Capturing frames for 5 seconds...")
frame_count = 0
start_time = time.time()

while time.time() - start_time < 5:
    frames = cam.get_frames()
    if len(frames) > 0:
        frame_count += len(frames)
        print(f"  Received {len(frames)} frame(s) - Total: {frame_count}")
    time.sleep(0.01)

cam.stop_acquisition()

print(f"\n[RESULT] Free-running mode: {frame_count} frames in 5s ({frame_count/5:.1f} fps)")

if frame_count == 0:
    print("\n[ERROR] Camera is not acquiring frames even in free-running mode!")
    print("        This indicates a camera/driver problem.")
    cam.shutdown()
    exit(1)
else:
    print("[OK] Camera can acquire frames successfully!")

# TEST 2: External trigger mode
print("\n" + "="*60)
print("TEST 2: EXTERNAL TRIGGER MODE")
print("="*60)

# Set to external trigger mode
print("\n[3b] Setting trigger mode to EXTERNAL...")
cam.trigger_mode = TriggerMode.EXTERNAL_TRIGGER

# Verify trigger settings
print("\n[4b] Verifying trigger configuration...")
trigger_source = cam.get_property_value("trigger_source")
trigger_mode = cam.get_property_value("trigger_mode")
trigger_active = cam.get_property_value("trigger_active")
trigger_polarity = cam.get_property_value("trigger_polarity")

trigger_source_text = cam.get_property_text("trigger_source")
trigger_mode_text = cam.get_property_text("trigger_mode")
trigger_active_text = cam.get_property_text("trigger_active")
trigger_polarity_text = cam.get_property_text("trigger_polarity")

def get_text_name(value, text_dict):
    for name, val in text_dict.items():
        if val == value:
            return name
    return f"<unknown:{value}>"

print(f"    trigger_source: {get_text_name(trigger_source, trigger_source_text)} ({trigger_source})")
print(f"    trigger_mode: {get_text_name(trigger_mode, trigger_mode_text)} ({trigger_mode})")
print(f"    trigger_active: {get_text_name(trigger_active, trigger_active_text)} ({trigger_active})")
print(f"    trigger_polarity: {get_text_name(trigger_polarity, trigger_polarity_text)} ({trigger_polarity})")

expected_source = 2  # EXTERNAL
expected_polarity = 2  # POSITIVE

if trigger_source != expected_source:
    print(f"\n[WARNING] trigger_source is {trigger_source}, expected {expected_source} (EXTERNAL)")
if trigger_polarity != expected_polarity:
    print(f"[WARNING] trigger_polarity is {trigger_polarity}, expected {expected_polarity} (POSITIVE)")

# Start acquisition
print("\n[5b] Starting acquisition in external trigger mode...")
cam.start_acquisition()
print("    Camera is now waiting for external triggers...")
print("\n    >>> START YOUR VOLUME PREVIEW NOW <<<")
print("    >>> Make sure NI DAQ is generating triggers! <<<\n")

# Wait for user to start triggers
input("Press ENTER when triggers are running...")

# Monitor frames for 30 seconds
print("\n[6b] Monitoring frames for 30 seconds...")
print("    Press Ctrl+C to stop early\n")

frame_count = 0
last_frame_time = None
intervals = []
start_time = time.time()

try:
    while time.time() - start_time < 30:
        # Get frames
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
        
        # Small delay to avoid busy-waiting
        time.sleep(0.001)

except KeyboardInterrupt:
    print("\n\n[!] Stopped by user")

# Stop acquisition
print("\n[7] Stopping acquisition...")
cam.stop_acquisition()

# Calculate statistics
print("\n" + "="*60)
print("RESULTS")
print("="*60)
print(f"\nTotal frames received: {frame_count}")
print(f"Test duration: {time.time() - start_time:.1f}s")

if frame_count == 0:
    print("\n[ERROR] No frames received with external triggers!")
    print("\nPossible issues:")
    print("  1. No trigger signal reaching camera")
    print("  2. Wrong trigger connector/wiring")
    print("  3. Trigger voltage too low (<3V)")
    print("  4. NI DAQ not generating triggers")
    print("  5. Camera trigger input not configured correctly")
elif frame_count > 0:
    avg_fps = frame_count / (time.time() - start_time)
    print(f"Average frame rate: {avg_fps:.2f} fps")

if len(intervals) > 0:
    intervals = np.array(intervals)
    print(f"\nFrame interval statistics:")
    print(f"  Mean:   {np.mean(intervals):.1f}ms ({1000/np.mean(intervals):.1f} fps)")
    print(f"  Median: {np.median(intervals):.1f}ms ({1000/np.median(intervals):.1f} fps)")
    print(f"  Min:    {np.min(intervals):.1f}ms ({1000/np.max(intervals):.1f} fps)")
    print(f"  Max:    {np.max(intervals):.1f}ms ({1000/np.min(intervals):.1f} fps)")
    print(f"  StdDev: {np.std(intervals):.1f}ms")
    
    # Histogram of intervals
    print(f"\nInterval distribution:")
    bins = [0, 50, 100, 150, 200, 250, 300, 500, 1000]
    for i in range(len(bins)-1):
        count = np.sum((intervals >= bins[i]) & (intervals < bins[i+1]))
        pct = 100 * count / len(intervals)
        print(f"  {bins[i]:4d}-{bins[i+1]:4d}ms: {count:4d} frames ({pct:5.1f}%)")

# Shutdown
print("\n[8] Shutting down camera...")
cam.shutdown()

print("\n" + "="*60)
print("TEST COMPLETE")
print("="*60)
print("\nExpected results for 3 Hz volume x 4 planes:")
print("  - Frame rate: ~12 Hz (83ms intervals)")
print("  - All intervals should be ~83ms ± 10ms")
print("\nIf you see consistent intervals, the camera hardware is fine.")
print("If you see erratic intervals, there may be a camera/driver issue.")
print("="*60 + "\n")
