from __future__ import annotations

from pathlib import Path

from PIL import Image

import image_utils


def _make_image(path: Path, size: tuple[int, int], fmt: str = "PNG") -> None:
    Image.new("RGB", size, color=(120, 30, 200)).save(path, format=fmt)


class TestCropCenter:
    def test_crops_to_requested_size(self) -> None:
        img = Image.new("RGB", (100, 60))
        cropped = image_utils.crop_center(img, 40, 20)
        assert cropped.size == (40, 20)


class TestCropMaxSquare:
    def test_landscape_becomes_square(self) -> None:
        img = Image.new("RGB", (100, 60))
        square = image_utils.crop_max_square(img)
        assert square.size == (60, 60)

    def test_portrait_becomes_square(self) -> None:
        img = Image.new("RGB", (40, 90))
        square = image_utils.crop_max_square(img)
        assert square.size == (40, 40)


class TestConvertImageToFormat:
    def test_produces_file_with_new_suffix(self, tmp_path: Path) -> None:
        src = tmp_path / "pic.png"
        _make_image(src, (50, 50))
        out = image_utils.convert_image_to_format(src, "jpg")
        assert out == src.with_suffix(".jpg")
        assert out.exists()
        assert Image.open(out).format == "JPEG"


class TestCropImageToSquare:
    def test_resizes_in_place_to_thumbnail_width(self, tmp_path: Path) -> None:
        src = tmp_path / "pic.jpg"
        _make_image(src, (200, 100), fmt="JPEG")
        image_utils.crop_image_to_square(src)
        with Image.open(src) as im:
            assert im.size == (
                image_utils.THUMBNAIL_WIDTH,
                image_utils.THUMBNAIL_WIDTH,
            )


class TestConvertRawPictureToThumbnail:
    def test_returns_square_jpg(self, tmp_path: Path) -> None:
        src = tmp_path / "raw.png"
        _make_image(src, (300, 150))
        out = image_utils.convert_raw_picture_to_thumbnail_format_and_shape(src)
        assert out.suffix == ".jpg"
        with Image.open(out) as im:
            assert im.size == (
                image_utils.THUMBNAIL_WIDTH,
                image_utils.THUMBNAIL_WIDTH,
            )
