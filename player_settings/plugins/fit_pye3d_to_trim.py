# https://github.com/PerForm-Lab-RIT/pupil-core-pipeline/blob/7d9ad4591151fac4f2bc50b6e18491b7c96ff6b1/src/core/pupil_detection.py#L446

import logging
from plugin import Plugin
from pyglui import ui
from pupil_detector_plugins.pye3d_plugin import Pye3DPlugin
import pye3d

from gaze_producer import model
from gaze_mapping.notifications import (
    CalibrationSetupNotification,
    CalibrationResultNotification,
)
import file_methods as fm
from pye3d.detector_3d import CameraModel, Detector3D, DetectorMode



CUSTOM_TOPIC = "custom_topic"

logger = logging.getLogger(__name__)

# refererence_path = "D:\\Data\\Integration\\003_400_2\\S001\\PupilData\\000 - Copy\\offline_data\\//"
# rt_reference_path = "D:\\Data\\Integration\\003_400_2\\S001\\PupilData\\000 - Copy\\realtime_calib_points.msgpack"


class pye3d_custom(Pye3DPlugin):

    def __init__(self, g_pool=None, **kwargs):
        # TODO: Create artificial gpool object here and load in eye camera intrinsics

        @property
        def pupil_detector(self):
            return self.detector

        super(pye3d_custom,self).__init__(g_pool=g_pool)


        self.pupil_detection_method = f"perform_pye3d_{pye3d.__version__}_post-hoc"
        self.detector = Detector3D(camera=self.camera, long_term_mode=DetectorMode.blocking)



class fit_pye3d_to_trim(Plugin):

    # uniqueness = "by_class"
    icon_font = "pupil_icons"
    icon_chr = chr(0xec19)
    label = "3D Reference Loader"


    @property
    def pretty_class_name(self):
        return "Calib from trim"

    def load_intrinsics(self,intrinsics_loc, resolution=None):  # (640, 480)):
        import camera_models as cm
        import pathlib
        from file_methods import load_object
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

    def create_fake_gpool(self, cam_intrinsics, eye_id, app="player", min_calibration_confidence=0.0, realtime_ref=None):
        import types, time
        g_pool = types.SimpleNamespace()
        g_pool.capture = types.SimpleNamespace()
        g_pool.capture.intrinsics = cam_intrinsics
        g_pool.capture.frame_size = cam_intrinsics.resolution
        g_pool.get_timestamp = time.perf_counter
        g_pool.app = app
        g_pool.min_calibration_confidence = min_calibration_confidence
        g_pool.eye_id = eye_id
        # g_pool.realtime_ref = realtime_ref
        return g_pool

    def __init__(self, g_pool=None):
        super().__init__(g_pool=g_pool)

        self.start_time, self.end_time = self._set_time_range_from_trim()
        self.pupilDatum_conf_threshold = 0.8

        self.pupil_0_2d_data = []
        self.pupil_1_2d_data = []
        self.pupil_data_2d = []

        self.pupil_0_3d_data = []
        self.pupil_1_3d_data = []

        eye0_intrinsics_loc = self.g_pool.rec_dir + "\\eye0.intrinsics"
        eye0_intrinsics = self.load_intrinsics(eye0_intrinsics_loc)
        self.eye0_pye3d = pye3d_custom(g_pool=self.create_fake_gpool(eye0_intrinsics,eye_id="0"))

        eye1_intrinsics_loc = self.g_pool.rec_dir + "\\eye1.intrinsics"
        eye1_intrinsics = self.load_intrinsics(eye1_intrinsics_loc)
        self.eye1_pye3d = pye3d_custom(g_pool=self.create_fake_gpool(eye1_intrinsics,eye_id="1"))


        # initialize empty menu
        self.menu = None
        self.order = 0.9

    def _recalc_pupil_positions(self):
        self._fit_model_to_range()
        self._produce_3D_pupil_data()

    def _stop_other_pupil_detectors(self):

        plugin_list = self.g_pool.plugins

        # Deactivate other PupilDetectorPlugin instances
        for plugin in plugin_list:
            if isinstance(plugin, Pye3DPlugin) and plugin is not self:
                plugin.alive = False

        # Force Plugin_List to remove deactivated plugins
        plugin_list.clean()

    def _set_time_range_from_trim(self):

        start_time = self.g_pool.timestamps[self.g_pool.seek_control.trim_left]
        end_time = self.g_pool.timestamps[self.g_pool.seek_control.trim_right]

        return start_time, end_time

    def _fit_model_to_range(self):

        pupil_data = self.g_pool.pupil_positions

        for datum_2d in pupil_data:

            if datum_2d["topic"]=='pupil.0.2d' and datum_2d["timestamp"] >= self.start_time and datum_2d["timestamp"] <= self.end_time and datum_2d["confidence"] >= self.pupilDatum_conf_threshold:

                self.pupil_0_2d_data.append(datum_2d)
                self.eye0_pye3d.detector.update_and_detect(datum_2d, None)

            elif datum_2d["topic"] == 'pupil.1.2d' and datum_2d["timestamp"] >= self.start_time and datum_2d["timestamp"] <= self.end_time  and datum_2d["confidence"] >= self.pupilDatum_conf_threshold:

                self.pupil_1_2d_data.append(datum_2d)
                self.eye1_pye3d.detector.update_and_detect(datum_2d, None)

        setattr(self.eye0_pye3d.detector, "is_long_term_model_frozen", True)
        setattr(self.eye1_pye3d.detector, "is_long_term_model_frozen", True)


    def _produce_3D_pupil_data(self):

        from player_methods import PupilDataBisector
        from file_methods import PLData, Serialized_Dict
        import av
        import cv2

        height,width = self.eye0_pye3d.camera.resolution
        frame = av.VideoFrame(height,width, 'bgr24')
        bgr = frame.to_ndarray()
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

        # datum_3d['id'] = '1'
        # datum_3d['topic'] = "pupil.1.3d"
        # datum_3d['method'] = self.eye1_pye3d.pupil_detection_method
        # new_pupil_data.append([Serialized_Dict(datum_3d), datum_3d['timestamp'], datum_3d['topic']])

        new_pupil_data = []

        for datum_2d in self.pupil_0_2d_data:

            new_pupil_data.append([datum_2d, datum_2d['timestamp'], datum_2d['topic']])

            pupil_frame = lambda: None
            setattr(pupil_frame, "gray", gray)
            setattr(pupil_frame, "bgr", bgr)
            setattr(pupil_frame, "width", width)
            setattr(pupil_frame, "height", height)
            setattr(pupil_frame, "timestamp", datum_2d['timestamp'])

            # pupil3d_datum = self.eye0_pye3d.detect(pupil_frame, **{"previous_detection_results": [datum_2d],"threshold_swirski": 0.0})
            # self.pupil_0_3d_data.append(fm.Serialized_Dict(python_dict=pupil3d_datum))
            # self.eye1_pye3d.detector.update_and_detect(datum_2d, None)

            datum_3d = self.eye0_pye3d.detect(pupil_frame, **{"previous_detection_results": [datum_2d],"threshold_swirski": 0.0})
            datum_3d['id'] = 0
            datum_3d['topic'] = "pupil.0.3d"
            datum_3d['method'] = self.eye0_pye3d.pupil_detection_method
            new_pupil_data.append([Serialized_Dict(datum_3d), datum_3d['timestamp'], datum_3d['topic']])

        for datum_2d in self.pupil_1_2d_data:

            new_pupil_data.append([datum_2d, datum_2d['timestamp'], datum_2d['topic']])

            pupil_frame = lambda: None
            setattr(pupil_frame, "gray", gray)
            setattr(pupil_frame, "bgr", bgr)
            setattr(pupil_frame, "width", width)
            setattr(pupil_frame, "height", height)
            setattr(pupil_frame, "timestamp", datum_2d['timestamp'])

            # pupil3d_datum = self.eye1_pye3d.detect(pupil_frame, **{"previous_detection_results": [datum_2d],"threshold_swirski": 0.0})
            # self.pupil_1_3d_data.append(fm.Serialized_Dict(python_dict=pupil3d_datum))

            datum_3d = self.eye1_pye3d.detect(pupil_frame,**{"previous_detection_results": [datum_2d], "threshold_swirski": 0.0})
            datum_3d['id'] = 1
            datum_3d['topic'] = "pupil.1.3d"
            datum_3d['method'] = self.eye1_pye3d.pupil_detection_method
            new_pupil_data.append([Serialized_Dict(datum_3d), datum_3d['timestamp'], datum_3d['topic']])

        import numpy as np
        new_pupil_data = np.array(new_pupil_data)
        self.g_pool.pupil_positions = PupilDataBisector(PLData(new_pupil_data[:,0],new_pupil_data[:,1],new_pupil_data[:,2]))

    def init_ui(self):

        # super().init_ui()

        self.add_menu()
        self.menu.label = self.pretty_class_name
        self.menu_icon.label_font = "pupil_icons"
        # self.menu.label = "Fit Pye3D model using time range"
        # self.menu = ui.Growing_Menu("Fit Pye3D model using time range")
        # self.menu.collapsed = True

        self.menu.append(
            ui.Info_Text("Imports 3D reference points from notifications")
        )

        self.menu.append(ui.Button("Fit model", self._recalc_pupil_positions))

        # info = ui.Info_Text("Load 3D Reference Points from Unity")
        # self.menu.append(info)



    def deinit_ui(self):
        self.remove_menu()

    def cleanup(self):
        pass

