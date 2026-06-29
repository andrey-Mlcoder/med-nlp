"""
Скрипт обучения модели.
Режим выбирается переменной MODE в начале файла
"""
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import random
import numpy as np
import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import ReduceLROnPlateau

from torch.utils.data import DataLoader, Subset, ConcatDataset
from tqdm import tqdm
from sklearn.model_selection import train_test_split
from clearml import Task

from src.data.make_dataset import FUSegBaseline, DFUC
from src.data.transforms import train_tf, val_tf
from src.models.loss import DiceFocalLoss
from src.models.config import get_model

# ==================== НАСТРОЙКИ (менять здесь) ====================
MODE = "baseline"           # "baseline" (только FuSeg) или "extended" (FuSeg + DFUC)
MODEL_NAME = "unet_efficientnet"  # "unet_efficientnet", "unet_mit", "deeplabv3_efficientnet"
MAX_EPOCHS = 40
BATCH_SIZE = 8
LR = 2e-4
WEIGHT_DECAY = 5e-4
PATIENCE = 4
SEED = 42

# Пути
FUSEG_ROOT = Path("../../data/raw/Foot Ulcer Segmentation Challenge")
DFUC_ROOT = Path("../../data/raw/DFUC2022_train_release")


# Имя задачи в ClearML
TASK_NAME = f"train_{MODE}_{MODEL_NAME}"
# ===================================================================


def set_seed(seed):
    # Фиксация случайности
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
        task_type=Task.TaskTypes.training,
    )
    # Логируем параметры в ClearML
    task.connect({
        "mode": MODE,
        "model": MODEL_NAME,
        "epochs": MAX_EPOCHS,
        "batch_size": BATCH_SIZE,
        "lr": LR,
        "weight_decay": WEIGHT_DECAY,
        "patience": PATIENCE,
        "seed": SEED,
    })
    logger = task.get_logger()
    
    # Данные
    if MODE == "extended":
        # Объединяем FuSeg + DFUC
        fuseg_train = FUSegBaseline(str(FUSEG_ROOT), "train", transform=train_tf())
        dfuc_full = DFUC(DFUC_ROOT, transform=None)
        
        # 10% DFUC оставляем как тест
        indices = list(range(len(dfuc_full)))
        train_idx, _ = train_test_split(indices, test_size=0.10, random_state=SEED)
        dfuc_train = Subset(DFUC(str(DFUC_ROOT), transform=train_tf()),train_idx)
        
        train_ds = ConcatDataset([fuseg_train, dfuc_train])
    else:
        # Только FuSeg
        train_ds = FUSegBaseline(str(FUSEG_ROOT), "train", transform=train_tf())
    
    val_ds = FUSegBaseline(str(FUSEG_ROOT), "validation", transform=val_tf())
    
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True,
                              num_workers=0, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False,
                            num_workers=0, pin_memory=True)
    
    # Модель
    model = get_model(MODEL_NAME).to(device)
    
    # Loss, Optimizer, Scheduler
    criterion = DiceFocalLoss(dice_weight=1.0, focal_weight=0.5,
                              focal_gamma=2.0, focal_alpha=0.25)
    optimizer = AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    scheduler = ReduceLROnPlateau(
        optimizer, mode="max", patience=3, factor=0.5
    )
    
    # Цикл обучения
    best_dice = 0.0
    patience_counter = 0
    WEIGHTS_DIR = PROJECT_ROOT / 'src' / 'weights'
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)  # создаём папку, если её нет

    best_model_path = WEIGHTS_DIR / f"{MODE}_{MODEL_NAME}_best.pth"
    
    for epoch in range(1, MAX_EPOCHS + 1):
        # train
        model.train()
        train_loss = 0.0
        with tqdm(train_loader, desc=f"Epoch {epoch:02d}/{MAX_EPOCHS} [Train]", leave=False) as pbar:
            for batch in pbar:
                x, y = batch['image'].to(device), batch['mask'].float().unsqueeze(1).to(device)            
                optimizer.zero_grad()
                logits = model(x)
                loss = criterion(logits, y)
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
                train_loss += loss.item()
        
        train_loss /= len(train_loader)
        
        # validation
        model.eval()
        val_loss = 0.0
        tp, fp, fn, tn = 0, 0, 0, 0
        
        with torch.no_grad():
            with tqdm(val_loader, desc=f"Epoch {epoch:02d}/{MAX_EPOCHS} [Val]  ", leave=False) as pbar:
                for batch in pbar:
                    x, y = batch["image"].to(device), batch["mask"].float().unsqueeze(1).to(device)
                    logits = model(x)
                    val_loss += criterion(logits, y).item()
                
                    pred = (torch.sigmoid(logits) > 0.5).to(device).float()
                    tp += (pred * y).sum().item()
                    fp += (pred * (1 - y)).sum().item()
                    fn += ((1 - pred) * y).sum().item()
                    tn += ((1 - pred) * (1 - y)).sum().item()
        
        val_loss /= len(val_loader)
        dice = 2 * tp / (2 * tp + fp + fn + 1e-6)
        iou = tp / (tp + fp + fn + 1e-6)
        precision = tp / (tp + fp + 1e-6)
        recall = tp / (tp + fn + 1e-6)
        
        scheduler.step(dice)
        
        # Логирование в ClearML
        logger.report_scalar("Loss", "train", train_loss, epoch)
        logger.report_scalar("Loss", "val", val_loss, epoch)
        logger.report_scalar("Metrics", "Dice", dice, epoch)
        logger.report_scalar("Metrics", "IoU", iou, epoch)
        logger.report_scalar("Metrics", "Precision", precision, epoch)
        logger.report_scalar("Metrics", "Recall", recall, epoch)
        
        # Вывод 
        lr = optimizer.param_groups[0]["lr"]
        print(f"Epoch {epoch:02d} | "
              f"Train: {train_loss:.4f} | Val: {val_loss:.4f} | "
              f"Dice: {dice:.4f} | IoU: {iou:.4f} | "
              f"P: {precision:.4f} | R: {recall:.4f} | LR: {lr:.1e}")
        
        # Сохранение лучшей модели
        if dice > best_dice:
            best_dice = dice
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_dice": dice,
                "val_loss": val_loss,
                "IoU": iou,
                "precision": precision,
                "recall": recall,
            }, best_model_path)
            print(f"Сохранена лучшая модель | Dice: {dice:.4f}")
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= PATIENCE:
                print("Early stopping triggered")
                break
    
    # === Финал ===
    logger.report_single_value("Best Dice", best_dice)
    task.upload_artifact("best_model", str(best_model_path))
    print(f"Обучение завершено. Лучший Dice: {best_dice:.4f}")
    print(f"ClearML task: {task.get_output_link()}")


if __name__ == "__main__":
    main()
