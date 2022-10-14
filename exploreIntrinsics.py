# https://github.com/PerForm-Lab-RIT/pupil-core-pipeline/blob/7d9ad4591151fac4f2bc50b6e18491b7c96ff6b1/src/core/pupil_detection.py#L446

import logging

# from pyglui import ui
#
# import file_methods as fm
# from pye3d.detector_3d import CameraModel, Detector3D, DetectorMode
#
# import data_changed

import os
CUSTOM_TOPIC = "custom_topic"

logger = logging.getLogger(__name__)





def load_intrinsics(intrinsics_loc, resolution=None):  # (640, 480)):
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


rec_dir = 'D:\\Data\\Integration\\005_400_2\\S001\\PupilData\\000 - proc - Copy'

cam = load_intrinsics(rec_dir + "\\world.intrinsics")
# cam.K[0,0] = 207.8461
# cam.K[1,1] = 207.8461

cam.K[1,1] = 425.0

save_intrinsics(rec_dir,cam)
logger.debug(
    f"**************** Adjusted world camera intrinsics ***************"
)
