"""Инференс: TTA, постобработка."""
import torch
import numpy as np
import cv2


def tta_predict(model, img_tensor, device, threshold=0.5):
    """TTA с 5 аугментациями + усреднение вероятностей."""
    preds = []
    transforms = [
        lambda x: x,
        lambda x: torch.flip(x, [-1]),
        lambda x: torch.rot90(x, k=1, dims=[-2, -1]),
        lambda x: torch.rot90(x, k=2, dims=[-2, -1]),
        lambda x: torch.rot90(x, k=3, dims=[-2, -1]),
    ]
    inverses = [
        lambda x: x,
        lambda x: torch.flip(x, [-1]),
        lambda x: torch.rot90(x, k=-1, dims=[-2, -1]),
        lambda x: torch.rot90(x, k=-2, dims=[-2, -1]),
        lambda x: torch.rot90(x, k=-3, dims=[-2, -1]),
    ]
    
    with torch.no_grad():
        for t, inv in zip(transforms, inverses):
            aug = t(img_tensor.to(device))
            prob = torch.sigmoid(model(aug)).cpu()
            preds.append(inv(prob))
    
    prob_map = torch.stack(preds).mean(dim=0)
    mask = (prob_map > threshold).float()
    return prob_map, mask


def postprocess_mask(mask: np.ndarray, min_area: int = 100,
                    kernel_size: int = 5):
    """Постобработка: удаление мелких объектов + морфологическое закрытие."""
    # Удаление мелких объектов
    contours, _ = cv2.findContours(
        mask * 255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    for cnt in contours:
        if cv2.contourArea(cnt) < min_area:
            cv2.drawContours(mask, [cnt], -1, 0, -1)
    
    # Заполнение дырок
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    
    return mask
    