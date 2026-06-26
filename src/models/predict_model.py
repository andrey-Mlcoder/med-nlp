"""
Скрипт оценки модели.
Режим и датасет выбираются переменными в начале файла.
"""

import random
import numpy as np
import torch
from pathlib import Path
from torch.utils.data import DataLoader, Subset
from tqdm import tqdm
from clearml import Task

# Наши модули
from src.data.make_dataset import FUSegBaseline, DFUC
from src.data.transforms import val_tf, test_tf
from .config import get_model
from src.inference.predictor import tta_predict, postprocess_mask

# ==================== НАСТРОЙКИ (менять здесь) ====================
MODE = "evaluate"           # "evaluate", "tta_evaluate"
MODEL_NAME = "unet_efficientnet"
CHECKPOINT_PATH = "../src/models/baseline_best.pth"
DATASET = "dfuc_test"       # "dfuc", "dfuc_test"
BATCH_SIZE = 8
THRESHOLD = 0.5
SEED = 42

# Пути
FUSEG_ROOT = Path("../../data/raw/Foot Ulcer Segmentation Challenge")
DFUC_ROOT = Path("../../data/raw/DFUC2022_train_release")

# Имя задачи в ClearML
TASK_NAME = f"predict_{MODE}_{MODEL_NAME}_{DATASET}"
# ===================================================================


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def main():
    set_seed(SEED)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # ClearML
    task = Task.init(
        project_name="DiaWatch_Wound_Segmentation",
        task_name=TASK_NAME,
        task_type=Task.TaskTypes.testing,
    )
    # Логируем параметры в ClearML
    task.connect({
        "mode": MODE,
        "model": MODEL_NAME,
        "checkpoint": CHECKPOINT_PATH,
        "dataset": DATASET,
        "batch_size": BATCH_SIZE,
        "threshold": THRESHOLD,
        "seed": SEED,
    })
    logger = task.get_logger()
    
    # Данные
    if DATASET == "dfuc":
        ds = DFUC(str(DFUC_ROOT), transform=test_tf())
    elif DATASET == "dfuc_test":
        dfuc_full = DFUC(DFUC_ROOT, transform=None)
        
        # 10% DFUC оставляем как тест
        indices = list(range(len(dfuc_full)))
        _, test_idx = train_test_split(indices, test_size=0.10, random_state=SEED)
        dfuc_test = Subset(DFUC(str(DFUC_ROOT), transform=test_tf()),test_idx)
    else:
        raise ValueError(f"Неизвестный датасет: {DATASET}")
    
    loader = DataLoader(ds, batch_size=BATCH_SIZE, shuffle=False,
                        num_workers=0, pin_memory=True)
    print(f"📊 Датасет '{DATASET}': {len(ds)} изображений")
    
    # === Загрузка модели ===
    model = get_model(MODEL_NAME).to(device)
    checkpoint = torch.load(CHECKPOINT_PATH, map_location=device, weights_only=False)
    if "model_state_dict" in checkpoint:
        model.load_state_dict(checkpoint["model_state_dict"])
    else:
        model.load_state_dict(checkpoint)
    model.eval()
    print(f"✅ Загружена модель: {MODEL_NAME} из {CHECKPOINT_PATH}")
    
    # === Оценка ===
    tp = fp = fn = tn = 0
    
    with torch.no_grad():
        for batch in tqdm(loader, desc=f"Оценка ({MODE})"):
            x = batch["image"].to(device)
            y = batch["mask"].float().unsqueeze(1).to(device)
            
            if MODE == "tta_evaluate":
                # TTA с 5 аугментациями
                _, pred = tta_predict(model, x, device, threshold=THRESHOLD)
            else:
                # Обычное предсказание
                logits = model(x)
                pred = (torch.sigmoid(logits) > THRESHOLD).float()
            
            # Постобработка (если нужно)
            if MODE == "postprocess":
                for i in range(pred.size(0)):
                    mask_np = pred[i, 0].cpu().numpy().astype(np.uint8)
                    mask_np = postprocess_mask(mask_np, min_area=100, kernel_size=5)
                    pred[i, 0] = torch.from_numpy(mask_np.astype(np.float32)).to(device)
            
            pred = pred.to(device).float()
            tp += (pred * y).sum().item()
            fp += (pred * (1 - y)).sum().item()
            fn += ((1 - pred) * y).sum().item()
            tn += ((1 - pred) * (1 - y)).sum().item()
    
    # === Метрики ===
    dice = 2 * tp / (2 * tp + fp + fn + 1e-6)
    iou = tp / (tp + fp + fn + 1e-6)
    precision = tp / (tp + fp + 1e-6)
    recall = tp / (tp + fn + 1e-6)
    
    # === Логирование в ClearML ===
    logger.report_single_value("Dice", dice)
    logger.report_single_value("IoU", iou)
    logger.report_single_value("Precision", precision)
    logger.report_single_value("Recall", recall)
    
    # === Вывод ===
    print("\n" + "=" * 60)
    print(f"📊 Результаты ({MODE} / {MODEL_NAME} / {DATASET})")
    print("=" * 60)
    print(f"  Dice:      {dice:.4f}")
    print(f"  IoU:       {iou:.4f}")
    print(f"  Precision: {precision:.4f}")
    print(f"  Recall:    {recall:.4f}")
    print("=" * 60)
    
    # Информация из чекпоинта (если есть)
    if "val_dice" in checkpoint:
        print(f"\n📈 Метрики из чекпоинта:")
        print(f"  val_dice: {checkpoint['val_dice']:.4f}")
        print(f"  epoch:    {checkpoint['epoch']}")


if __name__ == "__main__":
    main()