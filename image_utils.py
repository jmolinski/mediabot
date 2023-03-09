from PIL import Image

DESIRED_THUMBNAIL_FORMAT = "jpg"
THUMBNAIL_WIDTH = 300


def convert_image_to_format(image_filepath: str, desired_format: str) -> str:
    desired_filepath = image_filepath.rsplit(".", 1)[0] + "." + desired_format

    im = Image.open(image_filepath).convert("RGB")
    im.save(desired_filepath)

    return desired_filepath


def crop_center(pil_img: Image, crop_width: int, crop_height: int) -> Image:
    img_width, img_height = pil_img.size
    return pil_img.crop(
        (
            (img_width - crop_width) // 2,
            (img_height - crop_height) // 2,
            (img_width + crop_width) // 2,
            (img_height + crop_height) // 2,
        )
    )


def crop_max_square(pil_img: Image) -> Image:
    return crop_center(pil_img, min(pil_img.size), min(pil_img.size))


def crop_image_to_square(image_filepath: str) -> None:
    im = Image.open(image_filepath).convert("RGB")
    im_thumb = crop_max_square(im).resize(
        (THUMBNAIL_WIDTH, THUMBNAIL_WIDTH), Image.LANCZOS
    )
    im_thumb.save(image_filepath, quality=95)
