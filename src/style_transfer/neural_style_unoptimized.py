import re

import cv2
import numpy as np

import torch
from torchvision import transforms

from style_transfer.transformer_net import TransformerNet

class StyleTransferUnoptimized:
    def __init__(self, style_model_path="style_transfer/saved_models/style1.model", device="cuda",
                 cam_resolution=(720, 1280)):
        self.min_scale_factor = 0.1
        self.max_scale_factor = 1.6
        self.device = device
        self.style_model_weights_path = style_model_path
        self.default_input_shape = [1, 3, *cam_resolution]
        self.style_model = TransformerNet().to(device)
        self.load_model(style_model_path)
    

    def load_model(self, style_model_path):
        self.is_new_model = True
        self.style_model_weights_path = style_model_path
        self._load_weights_into_model(self.style_model_weights_path, self.style_model)
        self.is_new_model = False
    

    @staticmethod
    def _load_weights_into_model(style_model_weights_path, style_model):
        state_dict = torch.load(style_model_weights_path)
        for k in list(state_dict.keys()):
            if re.search(r'in\d+\.running_(mean|var)$', k):
                del state_dict[k]
        style_model.load_state_dict(state_dict)
    
    @staticmethod
    def _resize_crop(image):
        h, w, c = np.shape(image)
        if min(h, w) > 720:
            if h > w:
                h, w = int(720 * h / w), 720
            else:
                h, w = 720, int(720 * w / h)
        image = cv2.resize(image, (w, h),
                           interpolation=cv2.INTER_AREA)
        h, w = (h // 8) * 8, (w // 8) * 8
        image = image[:h, :w, :]
        return image
    

    def stylize(self, frame):
        if self.is_new_model:
            self._load_weights_into_model(self.style_model_weights_path, self.style_model)
            self.is_new_model = False

        print(frame.shape)
        input = self._resize_crop(frame)
        print(frame.shape)
        input = input.astype(np.float32)  # / 127.5 - 1
        content_transform = transforms.Compose([
            transforms.ToTensor(),
        ])
        input = content_transform(input).unsqueeze(0).to(self.device)

        with torch.no_grad():
            output = self.style_model(input)
        
        output = output.squeeze().permute(1, 2, 0)  # change shape to [H, W, C]
        output = output[:, :, [2, 1, 0]]  # change to RGB
        output = output.clip(0, 255)
        output = output.cpu().numpy().astype(np.uint8)

        return output