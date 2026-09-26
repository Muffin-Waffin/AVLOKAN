from pathlib import Path

import numpy as np
import rasterio


SCL_PATH = Path(
    "data/raw/sentinel2/"
    "S2C_MSIL2A_20250329T052841_N0511_R105_"
    "T43QEF_20250329T105014/"
    "SCL_20m.jp2"
)


def main() -> None:
    with rasterio.open(SCL_PATH) as src:
        print("SCL raster")
        print("=" * 50)

        print(f"Driver:      {src.driver}")
        print(f"Dimensions:  {src.width} x {src.height}")
        print(f"Bands:       {src.count}")
        print(f"CRS:         {src.crs}")
        print(f"Resolution:  {src.res}")
        print(f"Transform:   {src.transform}")
        print(f"Bounds:      {src.bounds}")
        print(f"Dtype:       {src.dtypes[0]}")
        print(f"NoData:      {src.nodata}")

        data = src.read(1)

        values, counts = np.unique(
            data,
            return_counts=True,
        )

        print("\nSCL classes found")
        print("=" * 50)

        total = data.size

        for value, count in zip(values, counts):
            percentage = (count / total) * 100

            print(
                f"Class {int(value):2d}: "
                f"{count:10d} pixels "
                f"({percentage:6.2f}%)"
            )


if __name__ == "__main__":
    main()
