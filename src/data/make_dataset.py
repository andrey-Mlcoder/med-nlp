"""Все Dataset классы для проекта DiaWatch."""
import numpy as np
import pandas as pd
import cv2
import torch
from pathlib import Path
from PIL import Image
from torch.utils.data import Dataset


class FUSegBaseline(Dataset): # класс для датасета FuSeg
    def __init__(self, root, split='train', transform=None):
        self.imgs = sorted((Path(root) / split / 'images').glob('*.png'))
        self.masks = [Path(root)/split/'labels'/f.name for f in self.imgs]
        self.transform = transform
        
    def __len__(self): return len(self.imgs)
        
    def __getitem__(self, i):
        img = torch.from_numpy(np.array(Image.open(self.imgs[i]).convert('RGB'))).permute(2,0,1).float()
        mask = torch.from_numpy(np.array(Image.open(self.masks[i]).convert('L')) > 127).long()
        if self.transform:
            aug = self.transform(image=img.numpy().transpose(1,2,0), mask=mask.numpy())
            img = torch.from_numpy(aug['image'].transpose(2,0,1)).float()
            mask = torch.from_numpy(aug['mask']).long()
            
        return {'image': img, 'mask': mask}


class DFUC(Dataset): # класс для датасета DFUC2022
    def __init__(self, root, transform=None):
        self.imgs = sorted((Path(root) / 'DFUC2022_train_images').glob('*.jpg'))
        self.masks = [Path(root) / 'DFUC2022_train_masks'/f.name.replace('.jpg','.png') for f in self.imgs]
        self.transform = transform
        
    def __len__(self): return len(self.imgs)
        
    def __getitem__(self, i):
        img = torch.from_numpy(np.array(Image.open(self.imgs[i]).convert('RGB'))).permute(2,0,1).float()
        mask = torch.from_numpy(np.array(Image.open(self.masks[i]).convert('L')) > 127).long()
        if self.transform:
            aug = self.transform(image=img.numpy().transpose(1,2,0), mask=mask.numpy())
            img = torch.from_numpy(aug['image'].transpose(2,0,1)).float()
            mask = torch.from_numpy(aug['mask']).long()
            
        return {'image': img, 'mask': mask}
