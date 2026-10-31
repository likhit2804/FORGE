"""Aggregate an IMD daily gridded rainfall NetCDF file to district-day CSV.

Rainfall is the unweighted mean of valid 0.25-degree grid-cell-centre values
inside each district polygon. This is a grid-derived district mean, not a
station maximum or an official district-mean product.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from tempfile import TemporaryDirectory
from datetime import datetime, timezone
from pathlib import Path


def _find_coordinate(dataset, explicit: str | None, candidates: tuple[str, ...], label: str) -> str:
    if explicit:
        if explicit not in dataset.variables:
            raise ValueError(f"{label} coordinate {explicit!r} not found in NetCDF")
        return explicit
    for candidate in candidates:
        if candidate in dataset.variables:
            return candidate
    raise ValueError(f"could not identify {label} coordinate; pass its name explicitly")


def _find_rain_variable(dataset, explicit: str | None, time_name: str,
                        latitude_name: str, longitude_name: str) -> str:
    if explicit:
        if explicit not in dataset.data_vars:
            raise ValueError(f"rainfall variable {explicit!r} not found in NetCDF data variables")
        return explicit
    required_dims = {dataset[time_name].dims[0], dataset[latitude_name].dims[0],
                     dataset[longitude_name].dims[0]}
    candidates = [name for name, variable in dataset.data_vars.items()
                  if required_dims.issubset(set(variable.dims))]
    if len(candidates) != 1:
        raise ValueError(f"found {len(candidates)} possible rainfall variables {candidates}; pass --variable")
    return candidates[0]


def convert(input_path: Path, boundaries_path: Path, output_path: Path,
            variable_name: str | None = None, time_name: str | None = None,
            latitude_name: str | None = None, longitude_name: str | None = None) -> dict:
    try:
        import numpy as np
        import xarray as xr
        from shapely import contains_xy
        from shapely.geometry import shape
    except ImportError as exc:
        raise RuntimeError('install conversion dependencies with: pip install -e ".[geo,rainfall]"') from exc

    geojson = json.loads(boundaries_path.read_text(encoding="utf-8"))
    manifest_path = boundaries_path.parent / "manifest.json"
    boundary_manifest = (json.loads(manifest_path.read_text(encoding="utf-8"))
                         if manifest_path.is_file() else {})
    district_polygons = []
    for feature in geojson.get("features", []):
        name = feature.get("properties", {}).get("shapeName")
        geometry = feature.get("geometry")
        if name and geometry:
            district_polygons.append((name, shape(geometry)))
    if not district_polygons:
        raise ValueError(f"no named district polygons in {boundaries_path}")

    with xr.open_dataset(input_path, decode_times=True) as dataset:
        t_name = _find_coordinate(dataset, time_name, ("time", "TIME", "date", "Date"), "time")
        lat_name = _find_coordinate(dataset, latitude_name, ("lat", "latitude", "LAT", "LATITUDE", "Latitude"), "latitude")
        lon_name = _find_coordinate(dataset, longitude_name, ("lon", "longitude", "LON", "LONGITUDE", "Longitude"), "longitude")
        rain_name = _find_rain_variable(dataset, variable_name, t_name, lat_name, lon_name)
        time_values = dataset[t_name].values
        latitudes = np.asarray(dataset[lat_name].values, dtype=float).reshape(-1)
        longitudes = np.asarray(dataset[lon_name].values, dtype=float).reshape(-1)
        rainfall = dataset[rain_name]
        time_dim = dataset[t_name].dims[0]
        lat_dim = dataset[lat_name].dims[0]
        lon_dim = dataset[lon_name].dims[0]
        extras = [dim for dim in rainfall.dims if dim not in {time_dim, lat_dim, lon_dim}]
        if extras:
            raise ValueError(f"rainfall variable has unsupported extra dimensions: {extras}")
        rainfall = rainfall.transpose(time_dim, lat_dim, lon_dim)
        lat_grid, lon_grid = np.meshgrid(latitudes, longitudes, indexing="ij")
        valid_counts = rainfall.where(rainfall >= 0).count(dim=time_dim).transpose(lat_dim, lon_dim).values
        district_cells: dict[str, list[tuple[int, int]]] = {}
        for name, polygon in district_polygons:
            cells = list(zip(*np.where(contains_xy(polygon, lon_grid, lat_grid))))
            if not cells or not any(valid_counts[row, col] > 0 for row, col in cells):
                representative = polygon.representative_point()
                order = np.argsort((lat_grid - representative.y) ** 2
                                   + (lon_grid - representative.x) ** 2, axis=None)
                nearest_rows, nearest_columns = np.unravel_index(order, lat_grid.shape)
                nearest = [(int(row), int(col)) for row, col in zip(nearest_rows, nearest_columns)
                           if valid_counts[row, col] > 0]
                cells = nearest[:8] or list(zip(nearest_rows[:8].tolist(), nearest_columns[:8].tolist()))
            district_cells[name] = cells

        output_path.parent.mkdir(parents=True, exist_ok=True)
        row_count = 0
        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=("date", "district", "rainfall_mm"))
            writer.writeheader()
            for time_index, time_value in enumerate(time_values):
                day = str(np.datetime_as_string(time_value, unit="D"))[:10]
                daily_grid = np.asarray(rainfall.isel({time_dim: time_index}).values, dtype=float)
                fill_values = [rainfall.attrs.get("_FillValue"), rainfall.attrs.get("missing_value")]
                for district, cells in district_cells.items():
                    values = np.asarray([daily_grid[row, col] for row, col in cells], dtype=float)
                    valid = np.isfinite(values) & (values >= 0)
                    for fill in fill_values:
                        if fill is not None:
                            valid &= values != float(fill)
                    if not valid.any():
                        continue
                    writer.writerow({"date": day, "district": district,
                                     "rainfall_mm": f"{float(values[valid].mean()):.4f}"})
                    row_count += 1

    digest_builder = hashlib.sha256()
    with input_path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest_builder.update(chunk)
    digest = digest_builder.hexdigest()
    metadata = {
        "source": "India Meteorological Department gridded daily rainfall (0.25 degree)",
        "source_url": "https://www.imdpune.gov.in/cmpg/Griddata/Rainfall_25_NetCDF.html",
        "source_citation": "Pai et al. (2014), MAUSAM 65(1), pp. 1-18",
        "input_file": str(input_path), "input_sha256": digest,
        "boundaries_file": str(boundaries_path),
        "boundary_source": boundary_manifest.get("source"),
        "boundary_year": boundary_manifest.get("district_layer", {}).get("boundaryYearRepresented"),
        "boundary_license": boundary_manifest.get("district_layer", {}).get("boundaryLicense"),
        "boundary_sha256": boundary_manifest.get("geojson_sha256"),
        "variable": rain_name, "time_coordinate": t_name,
        "latitude_coordinate": lat_name, "longitude_coordinate": lon_name,
        "district_count": len(district_cells), "row_count": row_count,
        "aggregation": "unweighted mean of valid grid-cell-centre values covered by district polygon; if the covered cells contain no valid data in the file, average valid values among the eight nearest grid centres to its representative point",
        "unit": rainfall.attrs.get("units", "mm (verify against source file metadata)"),
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "limitations": ["0.25-degree grid smooths local extremes", "coastal districts have partial grid-cell coverage", "aggregation is a district mean and cannot substitute for station maxima"],
    }
    metadata_path = output_path.with_suffix(output_path.suffix + ".metadata.json")
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metadata


def convert_many(input_paths: list[Path], boundaries_path: Path, output_path: Path,
                 variable_name: str | None = None, time_name: str | None = None,
                 latitude_name: str | None = None, longitude_name: str | None = None) -> dict:
    if not input_paths:
        raise ValueError("no NetCDF input files supplied")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    inputs = []
    total_rows = 0
    with TemporaryDirectory(prefix="imd-district-rain-") as temporary_directory:
        temp_root = Path(temporary_directory)
        converted = []
        for index, input_path in enumerate(input_paths):
            if not input_path.is_file():
                raise ValueError(f"NetCDF input does not exist: {input_path}")
            csv_path = temp_root / f"{index:04d}.csv"
            metadata = convert(input_path, boundaries_path, csv_path, variable_name,
                               time_name, latitude_name, longitude_name)
            converted.append(csv_path)
            total_rows += metadata["row_count"]
            inputs.append({"path": str(input_path), "sha256": metadata["input_sha256"],
                           "rows": metadata["row_count"]})
        with output_path.open("w", newline="", encoding="utf-8") as output_handle:
            writer = csv.writer(output_handle)
            writer.writerow(("date", "district", "rainfall_mm"))
            for csv_path in converted:
                with csv_path.open(newline="", encoding="utf-8") as input_handle:
                    reader = csv.reader(input_handle)
                    next(reader, None)
                    writer.writerows(reader)

    manifest_path = boundaries_path.parent / "manifest.json"
    boundary_manifest = (json.loads(manifest_path.read_text(encoding="utf-8"))
                         if manifest_path.is_file() else {})
    metadata = {
        "source": "India Meteorological Department gridded daily rainfall (0.25 degree)",
        "source_url": "https://www.imdpune.gov.in/cmpg/Griddata/Rainfall_25_NetCDF.html",
        "source_citation": "Pai et al. (2014), MAUSAM 65(1), pp. 1-18",
        "input_files": inputs, "boundaries_file": str(boundaries_path),
        "boundary_source": boundary_manifest.get("source"),
        "boundary_year": boundary_manifest.get("district_layer", {}).get("boundaryYearRepresented"),
        "boundary_license": boundary_manifest.get("district_layer", {}).get("boundaryLicense"),
        "boundary_sha256": boundary_manifest.get("geojson_sha256"),
        "district_count": len(json.loads(boundaries_path.read_text(encoding="utf-8")).get("features", [])),
        "row_count": total_rows,
        "aggregation": "unweighted mean of valid grid-cell-centre values inside each district polygon; if covered cells contain no valid data in a file, average valid values among the eight nearest grid centres to its representative point",
        "unit": "mm (variable units read from each NetCDF file)",
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "limitations": ["0.25-degree grid smooths local extremes", "coastal districts have partial grid-cell coverage", "aggregation is a district mean and cannot substitute for station maxima"],
    }
    output_path.with_suffix(output_path.suffix + ".metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, nargs="+", help="One or more IMD annual NetCDF files")
    parser.add_argument("--input-dir", type=Path,
                        help="Convert all RF25_ind*_rfp25.nc files in a directory")
    parser.add_argument("--boundaries", type=Path, default=Path("data/boundaries/tamil_nadu_districts.geojson"))
    parser.add_argument("--output", type=Path, default=Path("data/input/imd_district_daily_rainfall.csv"))
    parser.add_argument("--variable", help="Rainfall variable name if it cannot be inferred")
    parser.add_argument("--time-coordinate")
    parser.add_argument("--latitude-coordinate")
    parser.add_argument("--longitude-coordinate")
    args = parser.parse_args()
    if bool(args.input) == bool(args.input_dir):
        parser.error("provide exactly one of --input (one or more files) or --input-dir")
    if not args.boundaries.is_file():
        parser.error(f"district boundary file does not exist: {args.boundaries}")
    inputs = args.input if args.input else sorted(args.input_dir.glob("RF25_ind*_rfp25.nc"))
    if not inputs:
        parser.error("no RF25_ind*_rfp25.nc files found")
    try:
        metadata = convert_many(inputs, args.boundaries, args.output, args.variable,
                                args.time_coordinate, args.latitude_coordinate,
                                args.longitude_coordinate)
    except (ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print(f"Wrote {metadata['row_count']} district-day rows for {metadata['district_count']} districts")
    print(f"Input files hashed: {len(metadata['input_files'])}")
    print(f"Metadata: {args.output}.metadata.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
