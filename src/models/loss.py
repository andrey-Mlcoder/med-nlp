import torch
import torch.nn as nn
import segmentation_models_pytorch as smp


class DiceFocalLoss(nn.Module):
    """
    Комбинация Dice Loss + Focal Loss (как в FUSeg Rank 1).

    Args:
        dice_weight: вес Dice-компоненты 
        focal_weight: вес Focal-компоненты
        focal_gamma: параметр фокусировки
        focal_alpha: баланс классов для Focal
    """
    def __init__(self, dice_weight=1.0, focal_weight=0.5,
                 focal_gamma=2.0, focal_alpha=0.25):
        super().__init__()
        self.dice_weight = dice_weight
        self.focal_weight = focal_weight
        self.dice_loss = smp.losses.DiceLoss(mode='binary', smooth=1.0)
        self.focal_loss = smp.losses.FocalLoss(
            mode='binary',
            gamma=focal_gamma,
            alpha=focal_alpha
        )

    def forward(self, logits, targets):
        targets = targets.float()
        loss_dice = self.dice_loss(torch.sigmoid(logits), targets)
        loss_focal = self.focal_loss(logits, targets)
        return self.dice_weight * loss_dice + self.focal_weight * loss_focal
        