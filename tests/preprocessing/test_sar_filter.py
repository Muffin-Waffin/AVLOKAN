import numpy as np
import rasterio
from rasterio.transform import from_origin

from pipeline.preprocessing.sar_filter import lee_filter


def test_lee_filter_uses_windows_and_preserves_georeferencing(tmp_path):
    source, output = tmp_path / "sar.tif", tmp_path / "filtered.tif"
    rng = np.random.default_rng(7)
    values = rng.uniform(0.1, 1.0, size=(530, 540)).astype(np.float32)
    values[:4, :4] = 0
    transform = from_origin(500000, 2500000, 10, 10)
    with rasterio.open(source, "w", driver="GTiff", width=540, height=530,
                       count=1, dtype="float32", crs="EPSG:32643",
                       transform=transform, nodata=0) as dst:
        dst.write(values, 1)

    lee_filter(source, output, window_size=7)
    with rasterio.open(output) as result:
        assert (result.width, result.height) == (540, 530)
        assert result.crs.to_string() == "EPSG:32643"
        assert result.transform == transform
        assert result.nodata == 0
        sample = result.read(1, window=((0, 64), (0, 64)))
        assert np.isfinite(sample).all()
        assert (sample[4:, 4:] > 0).all()
