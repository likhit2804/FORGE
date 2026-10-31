import json
from pathlib import Path

import numpy as np
import pytest

from scripts.convert_imd_gridded_to_district_csv import convert


def test_imd_netcdf_converter_handles_official_dimension_order(tmp_path):
    xr = pytest.importorskip("xarray")
    root = Path(__file__).parents[1]
    boundary_path = root / "data" / "boundaries" / "tamil_nadu_districts.geojson"
    if not boundary_path.is_file():
        pytest.skip("download district boundaries before converter integration test")

    dataset = xr.Dataset(
        {"RAINFALL": (("LONGITUDE", "LATITUDE", "TIME"),
                      np.full((4, 4, 2), 12.5, dtype=float))},
        coords={
            "LONGITUDE": [76.0, 77.0, 78.0, 79.0],
            "LATITUDE": [8.0, 9.0, 10.0, 11.0],
            "TIME": np.array(["2023-12-17", "2023-12-18"], dtype="datetime64[D]"),
        },
    )
    dataset["RAINFALL"].attrs = {"units": "mm", "_FillValue": -999.0, "missing_value": -999.0}
    input_path = tmp_path / "imd_sample.nc"
    output_path = tmp_path / "district_rainfall.csv"
    dataset.to_netcdf(input_path)

    metadata = convert(input_path, boundary_path, output_path)

    assert metadata["district_count"] == 38
    assert metadata["row_count"] == 76
    assert metadata["unit"] == "mm"
    assert len(metadata["input_sha256"]) == 64
    with output_path.open(encoding="utf-8") as handle:
        first_data_row = handle.readlines()[1].strip().split(",")
    assert first_data_row[0] == "2023-12-17"
    assert float(first_data_row[2]) == pytest.approx(12.5)
    sidecar = json.loads(output_path.with_suffix(".csv.metadata.json").read_text(encoding="utf-8"))
    assert sidecar["aggregation"].startswith("unweighted mean")
