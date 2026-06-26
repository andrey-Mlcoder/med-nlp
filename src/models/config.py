"""Фабрика моделей."""
import segmentation_models_pytorch as smp

def get_model(model_name: str):
    if model_name == "unet_efficientnet":
        return smp.Unet(
            encoder_name="timm-efficientnet-b0",
            encoder_weights="imagenet",
            in_channels=3,
            classes=1,
            activation=None,
            decoder_dropout=0.2,
        )
    elif model_name == "unet_mit":
        return smp.Unet(
            encoder_name="mit_b1",
            encoder_weights="imagenet",
            in_channels=3,
            classes=1,
            activation=None,
            decoder_dropout=0.2,
        )
    elif model_name == "deeplabv3_efficientnet":
        return smp.DeepLabV3(
            encoder_name="timm-efficientnet-b0",
            encoder_weights="imagenet",
            in_channels=3,
            classes=1,
            activation=None,
            decoder_dropout=0.2,
        )
    else:
        raise ValueError(f"Неизвестная модель: {model_name}")
