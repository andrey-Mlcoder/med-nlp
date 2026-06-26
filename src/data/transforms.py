"""Все трансформы (аугментации) для проекта."""
import albumentations as A
import cv2

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def train_tf(image_size=512):
    return A.Compose([
        A.HorizontalFlip(p=0.5),
        A.VerticalFlip(p=0.5),
        A.Affine(scale=(0.85, 1.15), rotate=20, 
                 translate_percent=0.05, p=0.5), 
        A.CLAHE(clip_limit=2.0, tile_grid_size=(8, 8), p=0.3),
        A.ColorJitter(brightness=0.15, contrast=0.15, 
                      saturation=0.15, hue=0.05, p=0.4),
        A.Resize(image_size, image_size),
        A.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
    ], additional_targets={'mask': 'mask'})

def val_tf(image_size=512):
    return A.Compose([
        A.Resize(image_size, image_size, interpolation=cv2.INTER_AREA),
        A.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
    ], additional_targets={'mask':'mask'})

test_tf = val_tf()
