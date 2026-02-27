"""
Camera Trigger Configuration Diagnostics

This script helps you:
1. Check camera trigger configuration
2. View all camera properties
3. Test which NI DAQ channel is connected to camera
4. Scan all output channels to find the working connection
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sashimi.config import read_config
from sashimi.hardware.cameras import camera_class_dict
from sashimi.hardware.cameras.interface import TriggerMode

print("=" * 70)
print("CAMERA TRIGGER CONFIGURATION DIAGNOSTICS")
print("=" * 70)

# Load config
conf = read_config()
camera_name = conf['camera']['name']
CameraClass = camera_class_dict[camera_name]

print(f"\n[STEP 1] Initializing {camera_name} camera...")
camera = CameraClass(
    camera_id=conf['camera']['id'],
    max_sensor_resolution=tuple(conf['camera']['max_sensor_resolution'])
)
print("    OK - Camera connected")

# Show all camera properties
print(f"\n[STEP 2] Camera Properties and Settings")
print("=" * 70)

try:
    if hasattr(camera, 'properties'):
        print("\nAvailable Camera Properties:")
        print("-" * 70)
        for prop_name, prop_info in camera.properties.items():
            print(f"\n{prop_name}:")
            if isinstance(prop_info, dict):
                for key, value in prop_info.items():
                    print(f"  {key}: {value}")
            else:
                print(f"  Value: {prop_info}")
    
    # Show specific trigger-related settings
    print("\n" + "=" * 70)
    print("CURRENT TRIGGER CONFIGURATION:")
    print("=" * 70)
    
    print(f"\nTrigger Mode: {camera.trigger_mode.name}")
    print(f"Exposure Time: {camera.exposure_time} ms")
    print(f"Binning: {camera.binning}")
    print(f"ROI: {camera.roi}")
    
    # Try to get trigger-specific properties from Hamamatsu SDK
    if camera_name == 'hamamatsu':
        print("\n" + "-" * 70)
        print("Hamamatsu-Specific Trigger Properties:")
        print("-" * 70)
        
        # Look for trigger properties
        trigger_props = ['TRIGGER SOURCE', 'TRIGGER MODE', 'TRIGGER POLARITY', 
                        'TRIGGER ACTIVE', 'TRIGGER CONNECTOR']
        
        for prop in trigger_props:
            try:
                if prop in camera.properties:
                    val = camera.get_property_value(prop.lower().replace(' ', '_'))
                    print(f"  {prop}: {val}")
            except:
                pass
                
except Exception as e:
    print(f"Note: Could not enumerate all properties: {e}")

# Test NI DAQ channels
print("\n" + "=" * 70)
print("[STEP 3] NI DAQ OUTPUT CHANNEL SCAN")
print("=" * 70)

if conf['scanning'] == 'ni':
    try:
        import nidaqmx
        from nidaqmx.task import Task
        
        device_name = conf['z_board']['write']['channel'].split('/')[0]
        
        print(f"\nScanning device: {device_name}")
        print(f"Testing analog outputs (ao0 through ao7)...")
        print(f"\nThis will pulse each channel while camera is in external trigger mode.")
        print(f"Watch for which channel makes the camera capture frames.\n")
        
        input("Press ENTER to start channel scan (make sure camera can see test target)...")
        
        # Set camera to external trigger
        camera.trigger_mode = TriggerMode.EXTERNAL_TRIGGER
        camera.exposure_time = 10
        camera.start_acquisition()
        
        results = {}
        
        for channel_num in range(8):  # Test ao0 through ao7
            channel_name = f"{device_name}/ao{channel_num}"
            
            print(f"\nTesting {channel_name}...", end=" ", flush=True)
            
            try:
                with Task() as task:
                    task.ao_channels.add_ao_voltage_chan(
                        channel_name,
                        min_val=0.0,
                        max_val=5.0
                    )
                    
                    # Clear any pending frames
                    _ = camera.get_frames()
                    time.sleep(0.05)
                    
                    # Send 5 test pulses
                    for i in range(5):
                        task.write(5.0)
                        time.sleep(0.005)
                        task.write(0.0)
                        time.sleep(0.095)  # 100ms interval
                    
                    # Wait for frames
                    time.sleep(0.2)
                    
                    # Check for frames
                    frames = camera.get_frames()
                    frame_count = len(frames) if frames else 0
                    
                    results[channel_name] = frame_count
                    
                    if frame_count > 0:
                        print(f"[FOUND!] Got {frame_count} frames - THIS IS YOUR TRIGGER CHANNEL!")
                    else:
                        print(f"[No frames]")
                        
            except Exception as e:
                print(f"[Error: {e}]")
                results[channel_name] = -1
        
        camera.stop_acquisition()
        
        # Summary
        print("\n" + "=" * 70)
        print("SCAN RESULTS:")
        print("=" * 70)
        
        working_channels = [ch for ch, count in results.items() if count > 0]
        
        if working_channels:
            print(f"\n*** CAMERA TRIGGER DETECTED ON: {working_channels[0]} ***\n")
            print(f"To fix your configuration:")
            print(f"1. Note this channel: {working_channels[0]}")
            print(f"2. This is the physical output connected to your camera")
            print(f"3. Update your code to use this channel for camera triggers")
            print(f"\nThe camera trigger in volumetric scanning uses index 3 of the")
            print(f"z_array (board.camera_trigger), which corresponds to the 4th")
            print(f"channel of the z_board write task.")
        else:
            print("\n*** NO WORKING TRIGGER CHANNEL FOUND ***\n")
            print("Possible issues:")
            print("1. No physical connection from NI DAQ to camera trigger input")
            print("2. Camera trigger input not enabled in camera settings")
            print("3. Wrong device being tested")
            print("4. Cable/wiring problem")
            print("\nCheck:")
            print("- Physical BNC/terminal connections")
            print("- Camera front panel or DCAM Configurator settings")
            print("- Ground connection between DAQ and camera")
        
        print("\nAll channels tested:")
        for ch, count in results.items():
            status = f"{count} frames" if count >= 0 else "Error"
            marker = " <-- WORKING" if count > 0 else ""
            print(f"  {ch}: {status}{marker}")
            
    except ImportError:
        print("\nERROR: NI-DAQmx not installed")
    except Exception as e:
        print(f"\nERROR during scan: {e}")
        import traceback
        traceback.print_exc()
        
else:
    print("\nScanning skipped - not using NI hardware (scanning mode: {conf['scanning']})")

# Cleanup
try:
    camera.stop_acquisition()
except:
    pass

print("\n" + "=" * 70)
print("Diagnostics complete!")
print("=" * 70)
