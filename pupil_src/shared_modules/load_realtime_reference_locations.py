import msgpack
import gc
from pathlib import Path


# Path("D:\\Data\\Integration\\003_400_2\\S001\\PupilData\\000 - Copy\\offline_data\\reference_locations.msgpack").expanduser().open("rb")

refererence_path ="D:\\Data\\Integration\\003_400_2\\S001\\PupilData\\000 - Copy\\offline_data\\//"
rt_reference_path = "D:\\Data\\Integration\\003_400_2\\S001\\PupilData\\000 - Copy\\realtime_calib_points.msgpack"

# file_path = Path(refererence_path).expanduser()
# with file_path.open("rb") as fh:
#     gc.disable()  # speeds deserialization up.
#     data = msgpack.unpack(fh, strict_map_key=False)

# key #, screen_pos [],  frame_index, timestamp
file_path = Path(rt_reference_path).expanduser()
with file_path.open("rb") as fh:
    gc.disable()  # speeds deserialization up.
    data = msgpack.unpack(fh, strict_map_key=False)

a=1