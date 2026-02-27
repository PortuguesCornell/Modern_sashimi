"""
Standalone Camera Trigger Test Script

This script tests the TTL trigger signal path from NI DAQ to the camera
without requiring the full SASHIMI GUI application.

Usage:
    python test_camera_trigger.py

Tests performed:
1. NI DAQ device detection and configuration
2. Camera detection and connection
3. TTL pulse generation on trigger channel
4. Camera frame reception in external trigger mode
"""

import sys
import time
import numpy as np
from pathlib import Path

# Add sashimi to path
sys.path.insert(0, str(Path(__file__).parent))

from sashimi.config import read_config
from sashimi.hardware.cameras import camera_class_dict

print("=" * 70)
print("SASHIMI Camera Trigger Test")
print("=" * 70)

# Load configuration
print("\n[1/5] Loading configuration...")
try:
    conf = read_config()
    print(f"    OK - Configuration loaded")
    print(f"    Camera: {conf['camera']['name']}")
    print(f"    Scanning hardware: {conf['scanning']}")
except Exception as e:
    print(f"    ERROR - Failed to load config: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test NI DAQ availability
print("\n[2/5] Testing NI DAQ connection...")
try:
    if conf['scanning'] == 'ni':
        import nidaqmx
        from nidaqmx.constants import Edge
        
        # List available devices
        system = nidaqmx.system.System.local()
        devices = system.devices
        
        if len(devices) == 0:
            print(f"    ERROR - No NI DAQ devices found!")
            print(f"    Check NI MAX to verify device is detected")
            sys.exit(1)
        
        print(f"    OK - Found {len(devices)} NI DAQ device(s):")
        for dev in devices:
            print(f"         - {dev.name}: {dev.product_type}")
        
        # Check trigger output channel configuration
        trigger_channel = conf['z_board']['write']['channel']
        print(f"    Trigger output channel: {trigger_channel}")
        
    elif conf['scanning'] == 'mock':
        print(f"    WARNING - Using MOCK scanning hardware (no real TTL output)")
    else:
        print(f"    ERROR - Unknown scanning type: {conf['scanning']}")
        sys.exit(1)
        
except ImportError:
    print(f"    ERROR - NI-DAQmx not installed!")
    print(f"    Install with: pip install nidaqmx")
    sys.exit(1)
except Exception as e:
    print(f"    ERROR - NI DAQ test failed: {e}")
    sys.exit(1)

# Test camera connection
print("\n[3/5] Testing camera connection...")
try:
    camera_name = conf['camera']['name']
    CameraClass = camera_class_dict[camera_name]
    
    print(f"    Initializing {camera_name} camera...")
    camera = CameraClass(
        camera_id=conf['camera']['id'],
        max_sensor_resolution=tuple(conf['camera']['max_sensor_resolution'])
    )
    
    print(f"    OK - Camera connected")
    print(f"         Model: {camera_name}")
    print(f"         Resolution: {camera.max_sensor_resolution}")
    print(f"         Current trigger mode: {camera.trigger_mode.name}")
    
except Exception as e:
    print(f"    ERROR - Camera connection failed: {e}")
    print(f"    Check camera is powered on and connected")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test camera in free-run mode
print("\n[4/5] Testing camera in FREE-RUN mode...")
try:
    from sashimi.hardware.cameras.interface import TriggerMode
    
    # Set to free-run mode
    camera.trigger_mode = TriggerMode.FREE
    camera.exposure_time = 10  # 10ms
    
    print(f"    Starting acquisition in free-run mode...")
    camera.start_acquisition()
    
    time.sleep(0.5)  # Wait for camera to start
    
    # Try to get some frames
    frames_received = 0
    for i in range(10):
        frames = camera.get_frames()
        if frames:
            frames_received += len(frames)
        time.sleep(0.05)
    
    camera.stop_acquisition()
    
    if frames_received > 0:
        print(f"    OK - Received {frames_received} frames in free-run mode")
    else:
        print(f"    WARNING - No frames received in free-run mode")
        print(f"    Camera may not be functioning correctly")
    
except Exception as e:
    print(f"    ERROR - Free-run test failed: {e}")
    import traceback
    traceback.print_exc()
    try:
        camera.stop_acquisition()
    except:
        pass
    sys.exit(1)

# Test TTL trigger mode
print("\n[5/5] Testing EXTERNAL TRIGGER mode with TTL pulses...")
try:
    # Switch to external trigger mode
    camera.trigger_mode = TriggerMode.EXTERNAL_TRIGGER
    print(f"    Camera set to EXTERNAL_TRIGGER mode")
    
    if conf['scanning'] == 'ni':
        from nidaqmx.task import Task
        from nidaqmx.constants import AcquisitionType
        
        # Create a simple pulse generation task
        trigger_channel_config = conf['z_board']['write']['channel']
        
        # Parse device name from config (e.g., "Dev1/ao0:3" -> "Dev1")
        device_name = trigger_channel_config.split('/')[0]
        
        # Camera trigger is typically on ao3 (4th channel, index 3 in the z_array)
        camera_trigger_channel = f"{device_name}/ao3"
        
        print(f"    Generating TTL pulses on {camera_trigger_channel} (camera trigger)...")
        print(f"    Sending 10 test pulses at 5 Hz...")
        
        with Task() as task:
            # Add analog output channel for camera trigger
            task.ao_channels.add_ao_voltage_chan(
                camera_trigger_channel,
                min_val=0.0,
                max_val=5.0
            )
            
            # Start camera acquisition
            camera.start_acquisition()
            time.sleep(0.2)
            
            # Send 10 pulses at 5 Hz (200ms interval)
            frames_before = 0
            for i in range(10):
                # High pulse (5V)
                task.write(5.0)
                time.sleep(0.002)  # 2ms pulse width
                # Low (0V)
                task.write(0.0)
                time.sleep(0.198)  # Wait rest of 200ms period
                
                # Check for frames
                frames = camera.get_frames()
                if frames:
                    frames_before += len(frames)
            
            # Wait a bit more for any delayed frames
            time.sleep(0.3)
            
            # Count remaining frames
            frames_total = frames_before
            for i in range(20):
                frames = camera.get_frames()
                if frames:
                    frames_total += len(frames)
                time.sleep(0.01)
            
            camera.stop_acquisition()
            
            print(f"\n    Pulses sent: 10")
            print(f"    Frames received: {frames_total}")
            
            if frames_total > 0:
                print(f"\n    [SUCCESS] TTL triggers are working!")
                print(f"    Camera is receiving trigger pulses correctly.")
                if frames_total < 8:
                    print(f"    Note: Only {frames_total}/10 frames received")
                    print(f"    This might indicate timing issues or missed triggers")
            else:
                print(f"\n    [FAILED] No frames received!")
                print(f"\n    Camera is in external trigger mode but not receiving pulses.")
                print(f"\n    Troubleshooting steps:")
                print(f"    1. Verify physical wiring from NI DAQ ao3 to camera trigger input")
                print(f"    2. Check camera trigger input is configured correctly")
                print(f"    3. Verify camera trigger threshold voltage (should be < 5V)")
                print(f"    4. Use oscilloscope to verify pulses on ao3 output")
                print(f"    5. Check NI DAQ ground is connected to camera ground")
                
    else:
        print(f"    SKIPPED - Mock scanning hardware doesn't generate real TTL pulses")
        print(f"    Configure scanning='ni' in config to test real hardware")
        camera.stop_acquisition()
    
except Exception as e:
    print(f"    ERROR - External trigger test failed: {e}")
    import traceback
    traceback.print_exc()
    try:
        camera.stop_acquisition()
    except:
        pass
    sys.exit(1)

# Cleanup
print("\n" + "=" * 70)
print("Test complete!")
print("=" * 70)

try:
    camera.stop_acquisition()
    del camera
except:
    pass
