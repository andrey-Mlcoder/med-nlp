"""Утилиты для анализа датасетов """
import numpy as np
import pandas as pd
import cv2
from pathlib import Path
from tqdm import tqdm
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split

def compute_dataset_stats(base_path: str, split: str = "train"):
    """Сбор статистик по датасету FuSeg."""
    img_dir = Path(base_path) / split / "images"
    mask_dir = Path(base_path) / split / "labels"

    stats = []
    for img_path in tqdm(list(img_dir.glob("*.png"))):
        mask_path = mask_dir / img_path.name
        if not mask_path.exists(): continue

        img = cv2.imread(str(img_path), cv2.IMREAD_COLOR) # загрузка в BGR
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        mask_bin = (mask > 127).astype(np.uint8)

        # Статистики для раны
        wound_px = np.sum(mask_bin)
        wound_ratio = wound_px / (512 * 512)

        # Цветовые статистики (только в области раны)
        wound_region = img[mask_bin > 0] if wound_px > 0 else np.array([])

        stats.append({
            "filename": img_path.name,
            "wound_px": wound_px,
            "wound_ratio": wound_ratio,
            "brightness": cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).mean(),
            "contrast": cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).std(),
            "wound_mean_R": wound_region[:, 0].mean() if len(wound_region) > 0 else 0,
            "wound_mean_G": wound_region[:, 1].mean() if len(wound_region) > 0 else 0,
            "wound_mean_B": wound_region[:, 2].mean() if len(wound_region) > 0 else 0,
        })

    stats_df = pd.DataFrame(stats)
    plt.hist(stats_df["wound_ratio"] * 100, bins=30)
    plt.xlabel("Площадь раны, %")
    plt.title("Распределение размеров ран")
    plt.show()
    small_wounds = stats_df[stats_df["wound_ratio"] < 0.003]
    big_wounds = stats_df[stats_df["wound_ratio"] > 0.016]
    
    print(f"Медиана площади: {stats_df['wound_ratio'].median() * 100:.2f}%")
    print(f"Диапазон: {stats_df['wound_ratio'].min() * 100:.2f}% – {stats_df['wound_ratio'].max() * 100:.2f}%")
    print(f"Маленьких ран (<0.3%): {len(small_wounds)} из {len(stats_df)}")
    print(f"Больших ран (>1.6%): {len(big_wounds)} из {len(stats_df)}")

    return stats_df


def compute_dataset_stats_dfuc(base_path: str):
    """Сбор статистик по датасету DFUC"""
    img_dir = Path(base_path) / 'DFUC2022_train_images' 
    mask_dir = Path(base_path) / 'DFUC2022_train_masks' 

    stats = []
    for img_path in tqdm(list(img_dir.glob("*.jpg"))):
        mask_path = mask_dir / img_path.name.replace('.jpg','.png')
        if not mask_path.exists(): continue

        img = cv2.imread(str(img_path), cv2.IMREAD_COLOR) # загрузка в BGR
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        mask_bin = (mask > 127).astype(np.uint8)

        # Статистики для раны
        wound_px = np.sum(mask_bin)
        wound_ratio = wound_px / (640 * 480)

        stats.append({
            "filename": img_path.name,
            "wound_px": wound_px,
            "wound_ratio": wound_ratio,
            "brightness": cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).mean(),
            "contrast": cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).std(),
        })
        
    stats_df = pd.DataFrame(stats)
    plt.hist(stats_df["wound_ratio"] * 100, bins=30)
    plt.xlabel("Площадь раны, %")
    plt.title("Распределение размеров ран")
    plt.show()
    small_wounds = stats_df[stats_df["wound_ratio"] < 0.004]
    big_wounds = stats_df[stats_df["wound_ratio"] > 0.028]
    
    print(f"Медиана площади: {stats_df['wound_ratio'].median() * 100:.2f}%")
    print(f"Диапазон: {stats_df['wound_ratio'].min() * 100:.2f}% – {stats_df['wound_ratio'].max() * 100:.2f}%")
    print(f"Маленьких ран (<0.4%): {len(small_wounds)} из {len(stats_df)}")
    print(f"Больших ран (>2.8%): {len(big_wounds)} из {len(stats_df)}")
    
    return stats_df
