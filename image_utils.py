from pathlib import Path

from PIL import Image
from PIL.Image import Image as PILImage

DESIRED_THUMBNAIL_FORMAT = "jpg"
THUMBNAIL_WIDTH = 300


def convert_image_to_format(image_filepath: Path, desired_format: str) -> Path:
    desired_filepath = image_filepath.with_suffix(f".{desired_format}")

    im = Image.open(image_filepath).convert("RGB")
    im.save(desired_filepath)

    return desired_filepath


def crop_center(pil_img: PILImage, crop_width: int, crop_height: int) -> PILImage:
    img_width, img_height = pil_img.size
    return pil_img.crop(
        (
            (img_width - crop_width) // 2,
            (img_height - crop_height) // 2,
            (img_width + crop_width) // 2,
            (img_height + crop_height) // 2,
        )
    )


def crop_max_square(pil_img: PILImage) -> PILImage:
    return crop_center(pil_img, min(pil_img.size), min(pil_img.size))


def crop_image_to_square(path_to_image: Path) -> None:
    im = Image.open(path_to_image).convert("RGB")
    im_thumb = crop_max_square(im).resize(
        (THUMBNAIL_WIDTH, THUMBNAIL_WIDTH), Image.Resampling.LANCZOS
    )
    im_thumb.save(path_to_image, quality=95)


def convert_raw_picture_to_thumbnail_format_and_shape(picture_filename: Path) -> Path:
    thumbnail = convert_image_to_format(picture_filename, DESIRED_THUMBNAIL_FORMAT)
    crop_image_to_square(thumbnail)
    return thumbnail
