"""
Hamamatsu Camera Trigger Configuration Tool

This script helps configure the Hamamatsu camera for external trigger mode.
It will show all trigger-related settings and help you enable external triggering.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sashimi.config import read_config
from sashimi.hardware.cameras import camera_class_dict
from sashimi.hardware.cameras.interface import TriggerMode

print("=" * 70)
print("HAMAMATSU CAMERA TRIGGER CONFIGURATION")
print("=" * 70)

# Load camera
conf = read_config()
camera_name = conf['camera']['name']
CameraClass = camera_class_dict[camera_name]

print(f"\nInitializing {camera_name} camera...")
camera = CameraClass(
    camera_id=conf['camera']['id'],
    max_sensor_resolution=tuple(conf['camera']['max_sensor_resolution'])
)
print("OK - Camera connected\n")

# Show all available properties
print("=" * 70)
print("ALL CAMERA PROPERTIES")
print("=" * 70)

if hasattr(camera, 'properties') and camera.properties:
    for prop_name in sorted(camera.properties.keys()):
        try:
            # Try to get current value
            prop_value = camera.get_property_value(prop_name)
            print(f"{prop_name}: {prop_value}")
        except:
            print(f"{prop_name}: (unable to read)")
else:
    print("Properties not available in standard format.")
    print("Checking Hamamatsu-specific properties...")

# For Hamamatsu cameras, check trigger-specific properties
print("\n" + "=" * 70)
print("TRIGGER-RELATED SETTINGS")
print("=" * 70)

trigger_properties = [
    'trigger_source',
    'trigger_mode', 
    'trigger_polarity',
    'trigger_active',
    'trigger_connector',
    'trigger_times',
    'trigger_delay',
    'triggermode',
    'triggersource',
    'triggerpolarity',
    'triggeractive',
]

print("\nSearching for trigger properties...")
for prop in trigger_properties:
    try:
        val = camera.get_property_value(prop)
        print(f"  {prop}: {val}")
    except:
        pass

# Get available options for trigger properties
print("\n" + "=" * 70)
print("CONFIGURING EXTERNAL TRIGGER")
print("=" * 70)

# Try to enumerate trigger source options
print("\nChecking trigger_source options...")
try:
    if 'trigger_source' in camera.properties:
        prop_info = camera.properties['trigger_source']
        print(f"Available options: {prop_info}")
        
        # Try to set to external
        print("\nAttempting to set trigger_source to 'external' or '2' (external)...")
        try:
            camera.set_property_value('trigger_source', 'external')
            print("  SUCCESS - Set to 'external'")
        except:
            try:
                camera.set_property_value('trigger_source', 2)  # Usually 1=internal, 2=external, 3=software
                print("  SUCCESS - Set to mode 2 (external)")
            except Exception as e:
                print(f"  FAILED: {e}")
                
        # Verify
        current = camera.get_property_value('trigger_source')
        print(f"  Current value: {current}")
except Exception as e:
    print(f"Could not configure trigger_source: {e}")

# Try trigger polarity
print("\nChecking trigger_polarity...")
try:
    if 'trigger_polarity' in camera.properties:
        current = camera.get_property_value('trigger_polarity')
        print(f"  Current: {current}")
        print("  Trying to set to 'positive' (rising edge)...")
        try:
            camera.set_property_value('trigger_polarity', 'positive')
            print("  SUCCESS")
        except:
            try:
                camera.set_property_value('trigger_polarity', 2)  # 2 often = positive/rising
                print("  SUCCESS - Set to mode 2")
            except Exception as e:
                print(f"  FAILED: {e}")
except Exception as e:
    print(f"Could not check trigger_polarity: {e}")

# Try trigger active
print("\nChecking trigger_active (edge vs level)...")
try:
    if 'trigger_active' in camera.properties:
        current = camera.get_property_value('trigger_active')
        print(f"  Current: {current}")
        print("  Trying to set to 'edge' trigger...")
        try:
            camera.set_property_value('trigger_active', 'edge')
            print("  SUCCESS")
        except:
            try:
                camera.set_property_value('trigger_active', 1)  # 1 often = edge
                print("  SUCCESS - Set to mode 1")
            except Exception as e:
                print(f"  Could not set: {e}")
except Exception as e:
    print(f"Could not check trigger_active: {e}")

# Set to external trigger mode via API
print("\n" + "=" * 70)
print("SETTING EXTERNAL TRIGGER MODE VIA API")
print("=" * 70)

try:
    print(f"\nCurrent trigger_mode: {camera.trigger_mode}")
    print("Setting to EXTERNAL_TRIGGER...")
    camera.trigger_mode = TriggerMode.EXTERNAL_TRIGGER
    print(f"New trigger_mode: {camera.trigger_mode}")
    print("SUCCESS")
except Exception as e:
    print(f"FAILED: {e}")

# Show final configuration
print("\n" + "=" * 70)
print("FINAL CONFIGURATION")
print("=" * 70)

for prop in trigger_properties:
    try:
        val = camera.get_property_value(prop)
        print(f"  {prop}: {val}")
    except:
        pass

print("\n" + "=" * 70)
print("RECOMMENDATION")
print("=" * 70)

print("""
If trigger properties are not showing or cannot be set:

1. Camera needs to be configured via DCAM Configurator or HCImage software:
   - Open DCAM Configurator (usually installed with DCAM drivers)
   - Find your camera
   - Look for Trigger settings
   - Enable: External Trigger
   - Set: Rising Edge / Positive Edge
   - Set: Edge Trigger (not Level)
   - Save settings to camera

2. Check camera documentation for trigger input requirements:
   - Voltage level (TTL 5V should work)
   - Minimum pulse width (NI DAQ uses ~2ms, should be fine)
   - Input connector (which pin/port)

3. Alternative: Check if camera has DIP switches or front panel settings
   for trigger mode

4. Verify in camera manual which trigger connector to use:
   - Some cameras have multiple trigger inputs (Trigger 1, Trigger 2, etc.)
   - Make sure you're wired to the correct one
""")

print("=" * 70)
print("Configuration attempt complete!")
print("=" * 70)

# Cleanup
try:
    del camera
except:
    pass
