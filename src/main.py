import os

os.environ["CUDA_VISIBLE_DEVICES"] = "0"

import signal
import sys
from argparse import ArgumentParser
from functools import partial

import pynput.keyboard as keyboard

from fakecam import FakeCam


# TODO make deepfake version https://www.youtube.com/watch?v=mUfJOQKdtAk
# todo build tensorrt docker container ( get rid of cartoon style transfer)
# todo suppress all pixel changes smaller than c

def parse_args():
    parser = ArgumentParser(description="Applying stylees to your web cam image under \
                            GNU/Linux. For more information, please refer to: \
                            TODO")
    parser.add_argument("-W", "--width", default=1280, type=int,
                        help="Set real webcam width")
    parser.add_argument("-H", "--height", default=720, type=int,
                        help="Set real webcam height")
    parser.add_argument("-F", "--fps", default=30, type=int,
                        help="Set real webcam FPS")
    parser.add_argument("-C", "--codec", default='MJPG', type=str,
                        help="Set real webcam codec")
    parser.add_argument("-S", "--scale-factor", default=0.7, type=float,
                        help="Scale factor of the image sent the neural network")
    parser.add_argument("-w", "--webcam-path", default="/dev/video0",
                        help="Set real webcam path")
    parser.add_argument("-v", "--akvcam-path", default="/dev/video13",
                        help="virtual akvcam output device path")
    parser.add_argument("-s", "--style-model-dir", default="./data/style_transfer_models",
                        help="Folder which (subfolders) contains saved style transfer networks. Have to end with '.model' or '.pth'. Own styles created with https://github.com/pytorch/examples/tree/master/fast_neural_style can be used.")
    return parser.parse_args()


def main():
    args = parse_args()
    cam = FakeCam(
        fps=args.fps,
        width=args.width,
        height=args.height,
        codec=args.codec,
        scale_factor=args.scale_factor,
        webcam_path=args.webcam_path,
        akvcam_path=args.akvcam_path,
        style_model_dir=args.style_model_dir,
    )

    def sig_interrupt_handler(signal_, frame_, cam_):
        print("Stopping fake cam process")
        cam_.stop()

    signal.signal(signal.SIGINT, partial(sig_interrupt_handler, cam=cam))

    keyboard.GlobalHotKeys({
        '<ctrl>+<alt>+1': cam.switch_is_styling,
        '<ctrl>+<alt>+2': cam.set_previous_style,
        '<ctrl>+<alt>+3': cam.set_next_style,
        '<ctrl>+<alt>+4': partial(cam.add_to_scale_factor, -0.1),
        '<ctrl>+<alt>+5': partial(cam.add_to_scale_factor, 0.1),
    }).start()

    # keyboard.KeyboardListener(on_press=on_press).start()
    print("Running...")
    print("Press CTRL+ALT+1 to deactivate and activate styling")
    print("Press CTRL+ALT+2 to load the previous style")
    print("Press CTRL+ALT+3 to load the next style")
    print("Press CTRL+ALT+4 to decrease the scale factor of the model input")
    print("Press CTRL+ALT+5 to increase the scale factor of the model input")
    print("Please CTRL-c to exit")

    cam.run()  # loops

    print("exit 0")

    sys.exit(0)


if __name__ == "__main__":
    main()
