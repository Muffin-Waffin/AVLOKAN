from pathlib import Path

import rasterio

from pipeline.preprocessing.geotiff import (
    build_multiband_geotiff,
)


SCENE_DIR = Path(
    "data/raw/sentinel2/"
    "S2C_MSIL2A_20250329T052841_N0511_R105_T43QEF_20250329T105014"
)


def test_build_multiband_geotiff(tmp_path):
    output = tmp_path / "sentinel2_4band.tif"

    result = build_multiband_geotiff(
        SCENE_DIR,
        output,
    )

    assert result.exists()

    with rasterio.open(result) as src:
        assert src.driver == "GTiff"
        assert src.count == 4
        assert src.width == 10980
        assert src.height == 10980
        assert src.crs.to_string() == "EPSG:32643"
        assert src.res == (10.0, 10.0)
        assert src.dtypes == (
            "uint16",
            "uint16",
            "uint16",
            "uint16",
        )

        assert src.descriptions == (
            "B02",
            "B03",
            "B04",
            "B08",
        )