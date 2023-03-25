# https://github.com/PerForm-Lab-RIT/pupil-core-pipeline/blob/7d9ad4591151fac4f2bc50b6e18491b7c96ff6b1/src/core/pupil_detection.py#L446

import logging
import sys
from datetime import datetime as dt

sys.path.append("pupil_src/shared_modules")
import shutil

# from pyglui import ui
#
# import file_methods as fm
# from pye3d.detector_3d import CameraModel, Detector3D, DetectorMode
#
# import data_changed

import os
CUSTOM_TOPIC = "custom_topic"

logger = logging.getLogger(__name__)

def load_intrinsics(intrinsics_loc, resolution=None):
    import pupil_src.shared_modules.camera_models as cm
    import pathlib
    from pupil_src.shared_modules.file_methods import load_object
    import ast

    intrinsics_loc = pathlib.Path(intrinsics_loc)
    intrinsics_dict = load_object(intrinsics_loc, allow_legacy=False)

    if resolution is None:
        for key in intrinsics_dict.keys():
            if key != 'version':
                res = ast.literal_eval(key)
                if type(res) == type((1, 2)):
                    resolution = res
                    break

    return cm.Camera_Model.from_file(
        intrinsics_loc.parent, intrinsics_loc.stem, resolution
    )

def save_intrinsics(directory: str, cam):
    """
    Saves the current intrinsics to corresponding camera's intrinsics file. For each
    unique camera name we maintain a single file containing all intrinsics
    associated with this camera name.
    :param directory: save location
    :return:
    """
    cam_name = cam.name
    intrinsics = {
        "camera_matrix": cam.K.tolist(),
        "dist_coefs": cam.D.tolist(),
        "resolution": cam.resolution,
        "cam_type": cam.cam_type,
    }

    # Try to load previously recorded camera intrinsics
    save_path = os.path.join(
        directory, "{}.intrinsics".format(cam_name.replace(" ", "_"))
    )

    intrinsics_dict = {}

    intrinsics_dict["version"] = 1
    intrinsics_dict[str(cam.resolution)] = intrinsics

    from pupil_src.shared_modules.file_methods import save_object
    save_object(intrinsics_dict, save_path)

    logger.debug(
        f"Saved camera intrinsics for {cam_name} {cam.resolution} to {save_path}"
    )


from tkinter import Tk
from tkinter.filedialog import askopenfilename

Tk().withdraw()  # we don't want a full GUI, so keep the root window from appearing
full_path = askopenfilename()  # show an "Open" dialog box and return the path to the selected file


file_path, file_name = os.path.split(full_path)
backup_dir = os.path.join(file_path, 'world_intrinsics_backups')
if os.path.exists(backup_dir) is False:
            os.mkdir(backup_dir)

shutil.copy(full_path, os.path.join(backup_dir,'world-intrinsics-' + dt.now().strftime("%m-%d-%Y-%H-%M")))

cam = load_intrinsics(full_path)
# cam.K[0,0] = 207.8461
# cam.K[1,1] = 207.8461

cam.K[1,1] = 550.0
#cam.K[1,1] =415.69219971


save_intrinsics(file_path, cam)

print(cam.K)

logger.debug(
    f"**************** Adjusted world camera intrinsics ***************"
)
