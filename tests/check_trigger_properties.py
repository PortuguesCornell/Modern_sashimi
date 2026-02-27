"""Check available trigger properties on the Hamamatsu camera."""
import ctypes
import sys
sys.path.insert(0, r'c:\Users\Cornell\Downloads\tumsashimiPrt2')

# Import SDK structures directly
from sashimi.hardware.cameras.hamamatsu import sdk
DCAMAPI_INIT = sdk.DCAMAPI_INIT
DCAMDEV_OPEN = sdk.DCAMDEV_OPEN
DCAMPROP_OPTION_NEAREST = sdk.DCAMPROP_OPTION_NEAREST
DCAMPROP_OPTION_NEXT = sdk.DCAMPROP_OPTION_NEXT
DCAMPROP_ATTR_HASVALUETEXT = sdk.DCAMPROP_ATTR_HASVALUETEXT
DCAMPROP_ATTR = sdk.DCAMPROP_ATTR
DCAMPROP_VALUETEXT = sdk.DCAMPROP_VALUETEXT

# Initialize DCAM API
dcam = ctypes.windll.dcamapi
paraminit = DCAMAPI_INIT(0, 0, 0, 0, None, None)
paraminit.size = ctypes.sizeof(paraminit)
dcam.dcamapi_init(ctypes.byref(paraminit))

# Open camera
paramopen = DCAMDEV_OPEN(0, 0, None)
paramopen.size = ctypes.sizeof(paramopen)
dcam.dcamdev_open(ctypes.byref(paramopen))
camera_handle = ctypes.c_void_p(paramopen.hdcam)

# Get all properties
c_buf_len = 64
c_buf = ctypes.create_string_buffer(c_buf_len)
properties = {}
prop_id = ctypes.c_int32(0)

dcam.dcamprop_getnextid(camera_handle, ctypes.byref(prop_id), ctypes.c_uint32(DCAMPROP_OPTION_NEAREST))

while True:
    ret = dcam.dcamprop_getnextid(camera_handle, ctypes.byref(prop_id), ctypes.c_int32(DCAMPROP_OPTION_NEXT))
    if ret != 1:
        break
    dcam.dcamprop_getname(camera_handle, prop_id, c_buf, ctypes.c_int32(c_buf_len))
    prop_name = c_buf.value.decode("utf-8")
    properties[prop_name.lower().replace(" ", "_")] = prop_id.value

# Helper function to get property text options
def get_property_text(prop_id_val):
    """Get text options for a property."""
    # Get property attributes
    p_attr = DCAMPROP_ATTR()
    p_attr.cbSize = ctypes.sizeof(p_attr)
    p_attr.iProp = prop_id_val
    ret = dcam.dcamprop_getattr(camera_handle, ctypes.byref(p_attr))
    
    if not (p_attr.attribute & DCAMPROP_ATTR_HASVALUETEXT):
        return None
    
    # Get text options
    v = ctypes.c_double(p_attr.valuemin)
    prop_text = DCAMPROP_VALUETEXT()
    c_buf_text = ctypes.create_string_buffer(64)
    prop_text.cbSize = ctypes.c_int32(ctypes.sizeof(prop_text))
    prop_text.iProp = ctypes.c_int32(prop_id_val)
    prop_text.value = v
    prop_text.text = ctypes.addressof(c_buf_text)
    prop_text.textbytes = 64
    
    text_options = {}
    while True:
        dcam.dcamprop_getvaluetext(camera_handle, ctypes.byref(prop_text))
        text_options[c_buf_text.value.decode("utf-8")] = int(v.value)
        
        ret = dcam.dcamprop_queryvalue(camera_handle, ctypes.c_int32(prop_id_val), 
                                       ctypes.byref(v), ctypes.c_int32(DCAMPROP_OPTION_NEXT))
        prop_text.value = v
        if ret != 1:
            break
    
    return text_options

# Get current value of a property
def get_current_value(prop_id_val):
    c_value = ctypes.c_double(0)
    dcam.dcamprop_getvalue(camera_handle, ctypes.c_int32(prop_id_val), ctypes.byref(c_value))
    return int(c_value.value)

# Check key trigger properties
print("\n=== KEY TRIGGER PROPERTIES ===\n")
key_props = ['trigger_source', 'trigger_mode', 'trigger_active', 'trigger_polarity']

for prop_name in key_props:
    if prop_name in properties:
        prop_id_val = properties[prop_name]
        current = get_current_value(prop_id_val)
        text_opts = get_property_text(prop_id_val)
        
        if text_opts:
            current_name = [name for name, val in text_opts.items() if val == current]
            current_name = current_name[0] if current_name else f"<unknown:{current}>"
            print(f"{prop_name}:")
            print(f"  Current: {current_name} ({current})")
            print(f"  Options: {text_opts}")
        else:
            print(f"{prop_name}: {current}")
        print()

# Close camera
dcam.dcamdev_close(camera_handle)
dcam.dcamapi_uninit()
