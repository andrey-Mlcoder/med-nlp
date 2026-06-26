"""Метрики для оценки качества сегментации."""
import torch


def compute_metrics(pred: torch.Tensor, target: torch.Tensor,
                   eps: float = 1e-6) :
    """
    Вычисление Dice, IoU, Precision, Recall.
    
    Args:
        pred: предсказание (B, 1, H, W) после threshold
        target: (B, 1, H, W)
    """
    tp = (pred * target).sum().item()
    fp = (pred * (1 - target)).sum().item()
    fn = ((1 - pred) * target).sum().item()
    
    return {
        'dice': 2 * tp / (2 * tp + fp + fn + eps),
        'iou': tp / (tp + fp + fn + eps),
        'precision': tp / (tp + fp + eps),
        'recall': tp / (tp + fn + eps),
    }


class MetricsAccumulator:
    """Накопитель метрик по всему даталоадеру."""
    
    def __init__(self):
        self.tp = self.fp = self.fn = self.tn = 0
    
    def update(self, pred: torch.Tensor, target: torch.Tensor):
        self.tp += (pred * target).sum().item()
        self.fp += (pred * (1 - target)).sum().item()
        self.fn += ((1 - pred) * target).sum().item()
        self.tn += ((1 - pred) * (1 - target)).sum().item()
    
    def compute(self, eps: float = 1e-6):
        return {
            'dice': 2 * self.tp / (2 * self.tp + self.fp + self.fn + eps),
            'iou': self.tp / (self.tp + self.fp + self.fn + eps),
            'precision': self.tp / (self.tp + self.fp + eps),
            'recall': self.tp / (self.tp + self.fn + eps),
        }
    
    def reset(self):
        self.tp = self.fp = self.fn = self.tn = 0
        