# https://github.com/PerForm-Lab-RIT/pupil-core-pipeline/blob/7d9ad4591151fac4f2bc50b6e18491b7c96ff6b1/src/core/pupil_detection.py#L446


import logging
from plugin import Plugin
from pyglui import ui
from pupil_detector_plugins.pye3d_plugin import Pye3DPlugin
import pye3d


import file_methods as fm
from pye3d.detector_3d import CameraModel, Detector3D, DetectorMode


#import data_changed
import os
CUSTOM_TOPIC = "custom_topic"

logger = logging.getLogger(__name__)


class pye3d_custom(Pye3DPlugin):

    def __init__(self, g_pool=None, **kwargs):

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

    def __init__(self, g_pool=None):
        super().__init__(g_pool=g_pool)

        self.menu = None
        self._set_time_range_from_trim()
        self.pupilDatum_conf_threshold = 0.8

        self.model_fit_conf_threshold = {}
        self.model_fit_conf_threshold['value'] = 0.9
        self.model_fit_conf_threshold['min'] = 0.6
        self.model_fit_conf_threshold['max'] = 1.0
        self.model_fit_conf_threshold['step'] =  0.05

        self.aspectThreshold = {}
        self.aspectThreshold['value'] = 0.9
        self.aspectThreshold['min'] = 0.85
        self.aspectThreshold['max'] = 1.0
        self.aspectThreshold['step'] =  0.01

        # initialize empty menu
        self.menu = None
        self.order = 0.9

        # self.init_eye_pye3d()

    def init_eye_pye3d(self):

        def load_intrinsics(intrinsics_loc, resolution=None):  # (640, 480)):

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

        def create_fake_gpool(cam_intrinsics, eye_id, app="player", min_calibration_confidence=0.0,
                              realtime_ref=None):
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


        eye0_intrinsics_loc = self.g_pool.rec_dir + "\\eye0.intrinsics"
        eye0_intrinsics = load_intrinsics(eye0_intrinsics_loc)
        self.eye0_pye3d = pye3d_custom(g_pool=create_fake_gpool(eye0_intrinsics, eye_id="0"))

        eye1_intrinsics_loc = self.g_pool.rec_dir + "\\eye1.intrinsics"
        eye1_intrinsics = load_intrinsics(eye1_intrinsics_loc)
        self.eye1_pye3d = pye3d_custom(g_pool=create_fake_gpool(eye1_intrinsics, eye_id="1"))

        setattr(self.eye0_pye3d.detector, "is_long_term_model_frozen", False)
        setattr(self.eye1_pye3d.detector, "is_long_term_model_frozen", False)

    def _recalc_pupil_positions(self):
        self._fit_model_to_range()
        self._produce_3D_pupil_data()


    def _get_rel_time_trim_range_string(self,ts):
        time_fmt = ""
        min_ts = self.g_pool.timestamps[0]

        ts -= min_ts
        minutes = ts // 60
        seconds = ts - (minutes * 60.0)
        micro_seconds_e1 = int((seconds - int(seconds)) * 1e3)
        time_fmt += "{:02.0f}:{:02d}.{:03d} - ".format(
            abs(minutes), int(seconds), micro_seconds_e1
        )

        return time_fmt[:-3]

    def _set_time_range_from_trim(self):

        logger.info("Model fitting time range updated.")

        self.start_time = self.g_pool.timestamps[self.g_pool.seek_control.trim_left]
        self.end_time = self.g_pool.timestamps[self.g_pool.seek_control.trim_right]

        if self.menu:
            self.remove_menu()
            self.init_ui()


    def _fit_model_to_range(self):

        import numpy as np

        logger.info("Fitting eye models to data from specified range.")

        self.init_eye_pye3d()

        pupil_data = self.g_pool.pupil_positions

        for datum_2d in pupil_data:

            py3d_detector = None

            # Set the appropriate eye detector
            if datum_2d["topic"] == 'pupil.0.2d':
                py3d_detector = self.eye0_pye3d
            elif datum_2d["topic"] == 'pupil.1.2d':
                py3d_detector = self.eye1_pye3d
            else:
                continue # Likely a 3D pupil datum

            # Filter by trim range
            if datum_2d["timestamp"] < self.start_time and datum_2d["timestamp"] > self.end_time:
                continue

            # Filter by confidence
            if datum_2d["confidence"] < self.model_fit_conf_threshold['value']:
                continue

            # Filter by pupil ellipse aspect ratio
            # The pye3D model has trouble estimating orientation when the ar is close to 1
            aspect_ratio = np.min(datum_2d["ellipse"]["axes"]) / np.max(datum_2d["ellipse"]["axes"])
            if aspect_ratio >= self.aspectThreshold['value']:
                continue

            # Fit model
            py3d_detector.detector.update_and_detect(datum_2d, None)

        setattr(self.eye0_pye3d.detector, "is_long_term_model_frozen", True)
        setattr(self.eye1_pye3d.detector, "is_long_term_model_frozen", True)


    def _produce_3D_pupil_data(self):


        ##  Example code provided by papr, after I wrote the code below.
        # from player_methods import Bisector, PupilDataBisector
        #
        # original = PupilDataBisector.load_from_file(rec_dir, "pupil")
        # for key in tuple(original._bisectors.keys()):
        #     if "3d" in key:
        #         del original._bisectors[key]
        # original._bisectors["pupil.0.3d"] = Bisector(data_eye0, timestamps_eye0)
        # original._bisectors["pupil.1.3d"] = Bisector(data_eye1, timestamps_eye1)

        logger.info("Producing new 3D pupil data for entire recording from updated model.")

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
        import numpy as np
        for datum_2d in self.g_pool.pupil_positions:

            if '2d' in datum_2d["topic"]:

                py3d_detector = None
                topic = None
                id = None

                if( datum_2d["topic"] == 'pupil.0.2d' ):
                    py3d_detector = self.eye0_pye3d
                    topic = "pupil.0.3d"
                    id = 0

                elif( datum_2d["topic"] == 'pupil.1.2d' ):
                    py3d_detector = self.eye1_pye3d
                    topic = "pupil.1.3d"
                    id = 1

                new_pupil_data.append([datum_2d, datum_2d['timestamp'], datum_2d['topic']])

                pupil_frame = lambda: None
                setattr(pupil_frame, "gray", gray)
                setattr(pupil_frame, "bgr", bgr)
                setattr(pupil_frame, "width", width)
                setattr(pupil_frame, "height", height)
                setattr(pupil_frame, "timestamp", datum_2d['timestamp'])

                datum_3d = py3d_detector.detect(pupil_frame, **{"previous_detection_results": [datum_2d], "threshold_swirski": 0.0})
                datum_3d['id'] = id
                datum_3d['topic'] = topic
                datum_3d['method'] = py3d_detector.pupil_detection_method
                new_pupil_data.append([Serialized_Dict(datum_3d), datum_3d['timestamp'], datum_3d['topic']])



        new_pupil_data = np.array(new_pupil_data)
        self.g_pool.pupil_positions = PupilDataBisector(PLData(new_pupil_data[:,0],new_pupil_data[:,1],new_pupil_data[:,2]))

        self.save_offline_data()

    def save_offline_data(self):

        offline_data_dir = os.path.join(self.g_pool.rec_dir, "offline_data")
        self.g_pool.pupil_positions.save_to_file(offline_data_dir,'offline_pupil')

        session_data = {}
        session_data["detection_status"] = "complete"
        session_data["version"] = 4

        cache_path = os.path.join(offline_data_dir, "offline_pupil.meta")
        fm.save_object(session_data, cache_path)
        logger.info(f"Cached detected pupil data to {cache_path}")


        # TODO:  Announce pupil change
        # self._pupil_changed_announcer = data_changed.Announcer(
        #     "pupil_positions", self.g_pool.rec_dir, plugin=self
        # )
        #
        # self._pupil_changed_announcer.announce_new()

        logger.info("New 3D pupil positions saved to offline_pupil data")



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

        start_time_hms = self._get_rel_time_trim_range_string(self.start_time)
        end_time_hms = self._get_rel_time_trim_range_string(self.end_time)
        trimText = ui.Info_Text(f"Current trim range: {start_time_hms} - {end_time_hms}")
        self.menu.append(trimText)

        self.menu.append(ui.Separator())

        self.menu.append(ui.Button("Update model fitting range", self._set_time_range_from_trim))
        self.menu.append(ui.Button("Fit model", self._recalc_pupil_positions))



        # self.menu.append(ui.Info_Text(f"Model fit aspect ratio threshold: {self.aspectThreshold}"))

        self.menu.append(
            ui.Slider(
                "value",
                self.aspectThreshold,
                label="Aspect ratio threshold",
                min=self.aspectThreshold['min'],
                max=self.aspectThreshold['max'],
                step=self.aspectThreshold['step'],
            )
        )

        self.menu.append(
            ui.Slider(
                "value",
                self.model_fit_conf_threshold,
                label="Model fit confidence threshold",
                min=self.model_fit_conf_threshold['min'],
                max=self.model_fit_conf_threshold['max'],
                step=self.model_fit_conf_threshold['step'],
            )
        )


        # self.menu.append(info)


    def deinit_ui(self):
        self.remove_menu()

    def cleanup(self):
        pass
