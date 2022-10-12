import logging
from plugin import Plugin
from pyglui import ui
from pupil_detector_plugins.pye3d_plugin import Pye3DPlugin

from gaze_producer import model
from gaze_mapping.notifications import (
    CalibrationSetupNotification,
    CalibrationResultNotification,
)
import file_methods as fm

import av
import numpy as np

CUSTOM_TOPIC = "custom_topic"

logger = logging.getLogger(__name__)

# refererence_path = "D:\\Data\\Integration\\003_400_2\\S001\\PupilData\\000 - Copy\\offline_data\\//"
# rt_reference_path = "D:\\Data\\Integration\\003_400_2\\S001\\PupilData\\000 - Copy\\realtime_calib_points.msgpack"

class load_3d_references(Plugin):

    # uniqueness = "by_class"
    icon_font = "pupil_icons"
    icon_chr = chr(0xEC18)
    label = "3D Reference Loader"


    @property
    def pretty_class_name(self):
        return "Calib from trim"

    def __init__(self, g_pool=None):
        super().__init__(g_pool=g_pool)

        self.start_time, self.end_time = self._set_time_range_from_trim()
        self.pupilDatum_conf_threshold = 0.8

        self.pupil_0_2d_data = []
        self.pupil_1_2d_data = []

        self.pupil_0_3d_data = []
        self.pupil_1_3d_data = []

        self.eye0_detector3d = Pye3DPlugin(g_pool=g_pool).pupil_detector
        self.eye1_detector3d = Pye3DPlugin(g_pool=g_pool).pupil_detector

        self._stop_other_pupil_detectors()
        self._load_2D_pupil_datum()
        self._produce_3D_pupil_data()

        # initialize empty menu
        self.menu = None
        self.order = 0.9

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

    def _load_2D_pupil_datum(self):

        pupil_data = self.g_pool.pupil_positions

        for loaded_datum in pupil_data:

            if loaded_datum["topic"]=='pupil.0.2d' and loaded_datum["timestamp"] >= self.start_time and loaded_datum["timestamp"] <= self.end_time and loaded_datum["confidence"] >= self.pupilDatum_conf_threshold:
                self.pupil_0_2d_data.append(loaded_datum)
                observation = self.eye0_detector3d._extract_observation(loaded_datum)
                self.eye0_detector3d.update_models(observation)

            elif loaded_datum["topic"] == 'pupil.1.2d' and loaded_datum["timestamp"] >= self.start_time and loaded_datum[ "timestamp"] <= self.end_time and loaded_datum["confidence"] >= self.pupilDatum_conf_threshold:
                self.pupil_1_2d_data.append(loaded_datum)
                observation = self.eye0_detector3d._extract_observation(loaded_datum)
                self.eye1_detector3d.update_models(observation)

        setattr(self.eye0_detector3d, "is_long_term_model_frozen", True)
        setattr(self.eye1_detector3d, "is_long_term_model_frozen", True)

    def _remove_3D_pupil_data(self):
        pass

    def _produce_3D_pupil_data(self):

        # eye0VidCap = cv2.VideoCapture(self.g_pool.rec_dir  + 'eye0.mp4')
        # eye1VidCap = cv2.VideoCapture(self.g_pool.rec_dir)

        eye0_cont = av.open(self.g_pool.rec_dir + '\\eye0.mp4')
        stream = eye0_cont.streams.video[0]

        for datum_2D, frame in zip(self.pupil_0_2d_data, eye0_cont.decode(video=0)):

            frame_bgr = frame.reformat(frame.width, frame.height, 'bgr24')
            frame_gray = frame.reformat(frame.width, frame.height, 'gray')

            bgr = frame_bgr.to_nd_array()
            gray = frame_gray.to_nd_array()
            height, width = gray.shape

            timestamp = datum_2D['timestamp']

            # for count, timestamp in enumerate(self.g_pool.timestamps):
            pupil_frame = lambda: None
            setattr(pupil_frame, "gray", gray)
            setattr(pupil_frame, "bgr", bgr)
            setattr(pupil_frame, "width", width)
            setattr(pupil_frame, "height", height)
            setattr(pupil_frame, "timestamp", timestamp)

            pupil3d_datum = self.eye0_detector3d.detect(
                pupil_frame, **{"previous_detection_results": [datum_2D]}
            )

            self.pupil_0_3d_data.append(fm.Serialized_Dict(python_dict=pupil3d_datum))



    def init_ui(self):
        self.add_menu()
        self.menu.label = "Calib from trim"
        ref3D_menu = ui.Growing_Menu("3D Ref Points")
        ref3D_menu.collapsed = True
        ref3D_menu.append(
            ui.Info_Text("Imports 3D reference poinst from notifications")

        )
        # ref3D_menu.append(ui.Button("Reset 3D model", self.reset_model))

        # super().init_ui()
        # self.menu.label = self.pretty_class_name
        # self.menu_icon.label_font = "pupil_icons"
        # info = ui.Info_Text("Load 3D Reference Points from Unity")
        # self.menu.append(info)



    def deinit_ui(self):
        self.remove_menu()

    def cleanup(self):
        pass

