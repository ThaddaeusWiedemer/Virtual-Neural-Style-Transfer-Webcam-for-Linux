import os
import threading
import time

import cv2
import numpy as np
from PIL import Image

from akvcam import AkvCameraWriter
from realcam import RealCam
# from style_transfer.neural_style import StyleTransfer
from style_transfer.neural_style_unoptimized import StyleTransferUnoptimized


class FakeCam:
    def __init__(
            self,
            fps: int,
            width: int,
            height: int,
            codec: str,
            scale_factor: float,
            webcam1_path: str,
            webcam2_path: str,
            akvcam_path: str,
            style_model_dir: str,
            noise_suppressing_factor: float,
            overlay_path: str
    ) -> None:
        self.check_webcam_existing(webcam1_path)
        self.check_webcam_existing(webcam2_path)
        self.check_webcam_existing(akvcam_path)
        self.scale_factor = scale_factor
        self.real_cam1 = RealCam(webcam1_path, width, height, fps, codec)
        self.real_cam2 = RealCam(webcam2_path, width, height, fps, codec)
        self.active_cam = self.real_cam1
        # In case the real webcam does not support the requested mode.
        self.width = self.active_cam.get_frame_width()
        self.height = self.active_cam.get_frame_height()
        self.fake_cam_writer = AkvCameraWriter(akvcam_path, self.width, self.height)
        self.style_number = 0
        self.model_dir = style_model_dir
        self.styler_lock = threading.Lock()
        self.is_stop = False
        self.styler = None
        self.set_style_number(self.style_number)
        self.is_styling = True
        # self.optimize_models()  # only needed for TensorRT-optimized models
        self.current_fps = 0
        self.last_frame = None
        self.noise_epsilon = noise_suppressing_factor
        self.overlay_path = overlay_path
        self.display_overlay = True

    @staticmethod
    def check_webcam_existing(path):
        if not os.path.exists(path):
            error = "cam path not existing: " + path
            print(error)
            raise Exception(error)

    def put_frame(self, frame):
        self.fake_cam_writer.schedule_frame(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    def stop(self):
        with self.styler_lock:
            self.is_stop = True

    def run(self):
        self.real_cam1.start()
        self.real_cam2.start()
        t0 = time.monotonic()
        print_fps_period = .5
        frame_count = 0

        # prepare static overlay frame
        overlay = np.array(Image.open(self.overlay_path))
        overlay = np.pad(overlay, ((0, self.height - overlay.shape[0]), (self.width - overlay.shape[1], 0), (0, 0)))
        # overlay = self.styler._resize_crop(overlay)

        while not self.is_stop:
            current_frame = self.active_cam.read()
            if current_frame is None:
                time.sleep(0.1)
                continue

            with self.styler_lock:
                if self.display_overlay:
                    current_frame = self._overlay_images(current_frame, overlay)
                # superfluos, style transfer resizes to 720px along shortest dimension
                # current_frame = cv2.resize(current_frame, (0, 0), fx=self.scale_factor, fy=self.scale_factor)
                if self.is_styling:
                    current_frame = self._supress_noise(current_frame)
                    try:
                        current_frame = self.styler.stylize(current_frame)
                        # current_frame = overlay
                        # current_frame = self._overlay_images(current_frame, overlay)

                    except Exception as e:
                        print("error during style transfer", e)
                        pass
            # print(current_frame.shape)
            # current_frame = self._overlay_images(current_frame, overlay)
            # print(current_frame.shape)
            self.put_frame(current_frame)
            frame_count += 1
            td = time.monotonic() - t0
            if td > print_fps_period:
                self.current_fps = frame_count / td
                print(f"{self.current_fps:6.2f} FPS", end="\r")
                frame_count = 0
                t0 = time.monotonic()
        print("stopped fake cam")
        self.real_cam1.stop()
        self.real_cam2.stop()
        self.fake_cam_writer.stop()

    def _supress_noise(self, current_frame):
        if self.last_frame is not None and self.last_frame.shape == current_frame.shape:
            delta = np.abs(self.last_frame - current_frame) <= self.noise_epsilon
            current_frame[delta] = self.last_frame[delta]
        self.last_frame = current_frame
        return current_frame

    def _overlay_images(self, background, overlay):
        alpha_mask = np.broadcast_to(overlay[:, :, 3][..., None], (overlay.shape[0], overlay.shape[1], 3)) / 255.

        composite = background * (1 - alpha_mask) + overlay[:, :, :3] * alpha_mask

        return np.uint8(composite)

    def _get_list_of_all_models(self, model_dir, file_endings=[".index", ".pth", ".model"]):
        list_of_paths = []
        for dir_path, dir_name, file_names in os.walk(model_dir):
            for file_name in file_names:
                for file_ending in file_endings:
                    if file_name.endswith(file_ending):
                        list_of_paths.append(os.path.join(dir_path, file_name))
                        break
                if len(file_endings) == 0:
                    list_of_paths.append(os.path.join(dir_path, file_name))
        list_of_paths.sort()
        return list_of_paths

    def add_to_scale_factor(self, addend=0.1):
        proposed_scale_factor = round(self.scale_factor + addend, 1)
        if proposed_scale_factor <= 0:
            print("scale factor cannot be smaller than 0")
        else:
            with self.styler_lock:
                self.scale_factor = proposed_scale_factor
                print("new scale factor is: ", self.scale_factor)

    def add_to_noise_factor(self, addend=5):
        proposed_noise_factor = round(self.noise_epsilon + addend, 1)
        if proposed_noise_factor <= 0:
            print("noise factor cannot be smaller than 0")
        else:
            with self.styler_lock:
                self.noise_epsilon = proposed_noise_factor
                print("new noise factor is: ", self.noise_epsilon)

    def set_next_style(self):
        model_paths = self._get_list_of_all_models(self.model_dir)
        number = self.style_number
        if self.style_number + 1 > len(model_paths) - 1:
            number = 0
        else:
            number += 1
        self.set_style_number(number, model_paths)
        print(f"{f'switched to style {model_paths[self.style_number]}': >80}", end='\r')

    def set_previous_style(self):
        model_paths = self._get_list_of_all_models(self.model_dir)
        number = self.style_number
        if self.style_number - 1 == -1:
            number = len(model_paths) - 1
        else:
            number -= 1
        self.set_style_number(number, model_paths)
        print(f"{f'switched to style {model_paths[self.style_number]}': >80}", end='\r')

    def optimize_models(self):
        print("-" * 50)
        print("optimizing models for your graphics card. This might take several minutes for the first time.")
        print("-" * 50)
        model_paths = self._get_list_of_all_models(self.model_dir)
        for model_path in model_paths:
            self.styler.optimize_model(model_path)

    def set_style_number(self, number, model_paths=None):
        if model_paths is None:
            model_paths = self._get_list_of_all_models(self.model_dir)
        if number < len(model_paths) and number > -1:
            model_path = model_paths[number]
            try:
                with self.styler_lock:
                    if self.styler is None:
                        # Use StyleTransfer here for TensorRT-optimized models
                        self.styler = StyleTransferUnoptimized(model_path)
                    else:
                        self.styler.load_model(model_path)
                # print(f"switched to style {model_path}", end='\r')
                self.style_number = number
            except Exception as e:
                raise e
        else:
            print("model with number {} does not exist".format(number))

    def toggle_styling(self):
        with self.styler_lock:
            self.is_styling = not self.is_styling
            if self.is_styling:
                print(f"{'styling activated': >80}", end='\r')
            else:
                print(f"{'styling deactivated': >80}", end='\r')
    
    def switch_real_cam(self):
        with self.styler_lock:
            if self.active_cam == self.real_cam1:
                self.active_cam = self.real_cam2
                print(f"{'switched to cam 2': >80}", end='\r')
            else:
                self.active_cam = self.real_cam1
                print(f"{'switched to cam 1': >80}", end='\r')
    
    def mirror_active_cam(self):
        with self.styler_lock:
            self.active_cam.toggle_mirror()
        if self.active_cam.mirror:
            print(f"{'set cam to mirror': >80}", end='\r')
        else:
            print(f"{'set cam to original': >80}", end='\r')
    
    def toggle_overlay(self):
        with self.styler_lock:
            self.display_overlay = not self.display_overlay
        if self.display_overlay:
            print(f"{'display overlay': >80}", end='\r')
        else:
            print(f"{'hide overlay': >80}", end='\r')

    # speed test style transfer:
    # gpu pytorch  11.6
    # gpu onnx     ca 3.0 FAIL!!!
    # gpu tensorrt 16.8 with float16: 22
    # cpu pytorch  0.45 fps
    # cpu onnx     0.75 fps
    # gpu GeForce 3080   13~14 fps
