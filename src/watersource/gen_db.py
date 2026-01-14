# -*- coding: utf-8 -*-
# Copyright © 2021-2025 Geospatial Research Institute Toi Hangarau
# LICENSE: https://github.com/GeospatialResearch/Digital-Twins/blob/master/LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
This script provides functions to set up the watersource table in the database
"""
import os
import re
import gzip
import sqlalchemy
from natsort import natsorted
from itertools import groupby
import rasterio as rio
import geopandas as gpd
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Union, List, Dict, Any, Tuple
import time
from tqdm import tqdm
from shapely.geometry import Point
from sqlalchemy import text  # TIMESTAMP, Float, Integer, String
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from src.digitaltwin.setup_environment import get_engine, get_connection_from_profile
from src.config import EnvVariable


class Watersource:

    VARIABLE_CONFIG = {
        "velocity": {
            "filename_pattern": "*_velocity_*.tif",
            "crs": "EPSG:2193",
            "unit": "m",
        },
        "waterdepth": {
            "filename_pattern": "*_waterdepth_*.tif",
            "crs": "EPSG:2193",
            "unit": "m",
        },
        "hydro": {
            "filename_pattern": "*_hydro_*.tif",
            "crs": "EPSG:2193",
            "unit": "m",
        },
        "rain": {
            "filename_pattern": "*_rain_*.tif",
            "crs": "EPSG:2193",
            "unit": "m",
        },
        "stage": {
            "filename_pattern": "*_stage_*.tif",
            "crs": "EPSG:2193",
            "unit": "m",
        },
    }

    @staticmethod
    def combine_all_hydros(
        hydro_files: list[Path], export_dir: Path
    ) -> Tuple[list[Path], Path]:
        """Combine all hydro rasters for each time slice."""
        assert len(hydro_files) > 0, "No hydro files to combine."
        # Group by time slice
        groups = {}
        for k, g in groupby(hydro_files, lambda f: f.stem.split("hydro")[0]):
            time_slice = int(
                k[len("watersource") : -1]
            )  # Extract just the time number component
            if k not in groups.keys():
                groups[time_slice] = []
            groups[time_slice].extend(list(g))
        groups_list = sorted(groups.items(), key=lambda x: x[0])

        all_hydros = []
        all_hydros_dir = export_dir / "allhydros"
        all_hydros_dir.mkdir(exist_ok=True, parents=True)

        for time_slice, asc_files in tqdm(groups_list, desc="Combining all hydros"):
            with rio.open(asc_files[0]) as base:
                base_raster = base.read(1)
                base_raster[base_raster == -9999] = np.nan
                base_meta = base.meta.copy()
            for asc_file in asc_files[1:]:
                with rio.open(asc_file) as asc:
                    asc_raster = asc.read(1)
                    asc_raster[asc_raster == -9999] = np.nan
                    mask_both_nan = np.isnan(base_raster) & np.isnan(asc_raster)
                    base_raster = np.nansum(
                        np.dstack((base_raster, asc_raster)), 2
                    )  # add rasters while keeping nan+nan = nan
                    base_raster[mask_both_nan] = np.nan

            output_file = all_hydros_dir / f"watersource{time_slice}_allhydros.asc"
            with rio.open(output_file, "w", **base_meta) as dest:
                dest.write(base_raster, 1)
            all_hydros.append(output_file)

        return all_hydros, all_hydros_dir

    @staticmethod
    def modify_asc_line(file: Path, output_dir: Path, initial_serial: int) -> None:
        """
        Reads an .asc file, modifies: 1. round the 3rd line xllcornner, 2. negative value 4th line yllcornner.
        """
        round_line_number = 2  # zero-based. Round the xllcorner value

        try:
            with gzip.open(file, "rt") as f:
                lines = f.readlines()

            if len(lines) < round_line_number:
                print(f"File {file} does not have enough lines to modify.")
                return

            # Round the target line
            line = lines[round_line_number].strip()
            match = re.search(r"[-+]?\d*\.\d+|\d+", line)
            if match:
                original_number_str = match.group(0)
                original_number = float(original_number_str)
                # Round the number to integer
                rounded_number = round(original_number)
                # Replace the original number string with the new rounded value
                # Note: This simple replacement assumes only one number on the line
                new_line = line.replace(original_number_str, str(rounded_number))
                lines[round_line_number] = new_line + "\n"  # Re-add newline character

            if "watersource" in file.stem.lower():
                serial_number = str(
                    int((file.stem).split("_")[0].replace("watersource", ""))
                    - initial_serial
                )
                _rest = file.stem.split("_")[1].lower()
                output_path = Path(output_dir) / (
                    "watersource" + serial_number + "_" + _rest
                )
            else:
                file_name = Path(file.stem).stem.lower()
                file_extension = Path(file.stem).suffix
                variable_name = "".join([x for x in file_name if x.isalpha()])
                serial_number = str(
                    int("".join([x for x in file_name if x.isdigit()])) - initial_serial
                )
                output_path = Path(output_dir) / (
                    "watersource" + serial_number + "_" + variable_name + file_extension
                )
            with open(output_path, "w") as f:
                f.writelines(lines)
            # print(f"Successfully processed: {file}")
        except Exception as e:
            print(f"Error processing {file}: {e}")

    @staticmethod
    def modify_asc_line_parallel(path: Path, output_dir: Path) -> None:
        """
        Processes multiple .asc files in a directory in parallel.
        """
        files = natsorted([f for f in Path(path).glob("*.gz")])
        print(f"Found {len(files)} .gz files in directory: {path}", flush=True)
        assert len(files) > 0, f"No .gz files found in directory: {path}"

        initial_serial = int("".join([x for x in files[0].stem if x.isdigit()]))
        assert (
            initial_serial == 2806560
        ), f"First file time serial number {initial_serial} is not correct."

        if not files:
            print(f"No .gz files found in directory: {path}")
            return

        print(f"Modify coordinates for {len(files)} .gz files in parallel...")
        # Use ThreadPoolExecutor for parallel execution
        with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
            futures = [
                executor.submit(
                    Watersource.modify_asc_line, file, output_dir, initial_serial
                )
                for file in files
            ]
            # optionally iterate through futures to check for exceptions or results
            for future in futures:
                future.result()  # This will re-raise any exceptions that occurred in the threads

    @staticmethod
    def asc_to_geotiff(
        input_dir: Path,
        export_dir: Path,
        start_time: datetime,
        time_string: str = "%Y%m%d%H%M",
        nodata: int = -9999,
        clean_tmp: bool = True,
    ) -> None:
        all_hydros, tmp_dir = Watersource.combine_all_hydros(
            natsorted([f for f in input_dir.glob("watersource*_hydro*")]),
            export_dir,
        )
        water_source_files = {
            "velocity": sorted([f for f in input_dir.glob("watersource*_velocity*")]),
            "waterdepth": sorted(
                [f for f in input_dir.glob("watersource*_waterdepth*")]
            ),
            "hydro": all_hydros,
            "rain": sorted([f for f in input_dir.glob("watersource*_rain*")]),
            "stage": sorted([f for f in input_dir.glob("watersource*_stage*")]),
        }
        for variable, files in water_source_files.items():
            print(f"Collating {variable}")
            # get metadata
            with rio.open(files[0]) as first_file:
                meta = first_file.meta.copy()
            meta.update(
                {
                    "driver": "GTiff",
                    "count": 1,
                    "nodata": nodata,
                    "crs": Watersource.VARIABLE_CONFIG[variable]["crs"],
                }
            )

            export_dir.mkdir(exist_ok=True, parents=True)
            for file in files:
                minute = int(file.stem.split("_")[0].replace("watersource", ""))
                timestamp = (start_time + timedelta(minutes=minute)).strftime(
                    time_string
                )
                output_file = export_dir / "watersource_{}_{}.tif".format(
                    variable, timestamp
                )

                with rio.open(output_file, "w", **meta) as dst:
                    with rio.open(file) as src:
                        band = src.read(1, masked=True)
                        dst.write(band, 1)
        print(f"Finished collating temporal raster output to: {export_dir}.")
        if clean_tmp:
            import shutil

            print("Cleaning temporary files...")
            shutil.rmtree(tmp_dir)

    @staticmethod
    def load_variable_data(
        data_directory: str, variable: str
    ) -> Tuple[np.ndarray, List[datetime], Dict]:
        """
        load all three water source data

        Args:
            data_directory:
            variable:

        Returns:
            tuple: (data, timestamp, metadata)
        """
        if variable not in Watersource.VARIABLE_CONFIG:
            raise ValueError(f"Do not support: {variable}")

        config = Watersource.VARIABLE_CONFIG[variable]
        pattern = config["filename_pattern"]
        tif_files = natsorted([f for f in Path(data_directory).glob(pattern)])

        if not tif_files:
            raise ValueError(f"No geotiff file in {data_directory}.")

        print(f"{len(tif_files)} {variable} files found in {data_directory}.")

        # parse timestamp by file name
        timestamps = []
        for file_path in tif_files:
            filename = file_path.stem
            # assuming format: watersource_variable_YYYYMMDDHH
            assert (
                variable == filename.split("_")[1]
            ), f"variable {variable} does not match {filename}"
            timestamp = filename.split("_")[2]
            # generate UTC timestamp
            timestamp = datetime.strptime(timestamp, "%Y%m%d%H%M").replace(
                tzinfo=timezone.utc
            )
            timestamps.append(timestamp)

        # get metadata from the first file
        with rio.open(tif_files[0]) as src:
            transform = src.transform
            crs = src.crs
            rows, cols = src.shape
            nodata = src.nodata

        print(f"{variable}: {rows} × {cols}, timestamps: {len(timestamps)}")

        # allocate memory: shape in (timestamp, row, col)
        all_data = np.empty((len(tif_files), rows, cols), dtype=np.float32)

        # for parallel reading
        def load_single_file(i, file_path):
            with rio.open(file_path) as src:
                data = src.read(1).astype(np.float32)
                if nodata is not None:
                    data[data == nodata] = np.nan
                return i, data

        print(f"Loading {variable} data into memory...")
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=32) as executor:
            futures = [
                executor.submit(load_single_file, i, file_path)
                for i, file_path in enumerate(tif_files)
            ]

            for future in futures:
                i, data = future.result()
                all_data[i] = data

        load_time = time.time() - start_time
        print(f"Loading {variable} done in: {load_time:.2f} seconds.")

        metadata = {
            "variable": variable,
            "unit": config["unit"],
            "transform": transform,
            "crs": crs,
            "rows": rows,
            "cols": cols,
            "nodata": nodata,
        }

        return all_data, timestamps, metadata

    @staticmethod
    def create_geodataframe_for_variable(
        all_data: np.ndarray, timestamps: List[datetime], metadata: Dict
    ) -> gpd.GeoDataFrame:
        """
        Create dataframe for a variable

        Args:
            all_data: 3D array (timestamp, row, col)
            timestamps:
            metadata:

        Returns:
            gpd.GeoDataFrame:
        """
        variable = metadata["variable"]
        transform = metadata["transform"]
        rows, cols = metadata["rows"], metadata["cols"]
        crs = metadata["crs"]

        print(f"Vectorising {variable} data...")
        start_time = time.time()

        # create coords mesh
        col_grid, row_grid = np.meshgrid(np.arange(cols), np.arange(rows))

        # vectorise coords
        x_coords = col_grid.ravel() + 0.5
        y_coords = row_grid.ravel() + 0.5
        coordinates = np.array([transform * (x, y) for x, y in zip(x_coords, y_coords)])
        longitudes = coordinates[:, 0]
        latitudes = coordinates[:, 1]

        # reshape back
        pixel_data = all_data.reshape(all_data.shape[0], -1).T

        # filter out invalid data
        valid_mask = ~np.all(np.isnan(pixel_data), axis=1)
        valid_indices = np.where(valid_mask)[0]

        print(
            f"{variable} valid pixels / total pixels: {len(valid_indices)}/{len(valid_mask)}"
        )

        if len(valid_indices) == 0:
            return gpd.GeoDataFrame()

        valid_longitudes = longitudes[valid_indices]
        valid_latitudes = latitudes[valid_indices]
        valid_pixel_data = pixel_data[valid_indices]
        valid_rows = row_grid.ravel()[valid_indices]
        valid_cols = col_grid.ravel()[valid_indices]

        # convert datetime object to PostgreSQL acceptable format
        # timestamps = [ts.isoformat() for ts in timestamps]
        timestamps = [
            pd.to_datetime(ts).strftime("%Y-%m-%d %H:%M:%S%z") for ts in timestamps
        ]

        # to DataFrame
        data_dict = {
            "geometry": [
                Point(lon, lat) for lon, lat in zip(valid_longitudes, valid_latitudes)
            ],
            "variable": [variable] * len(valid_indices),
            "row": valid_rows.astype(int),
            "col": valid_cols.astype(int),
            "timestamps": [timestamps] * len(valid_indices),
            "values": [list(data) for data in valid_pixel_data],
        }

        gdf = gpd.GeoDataFrame(data_dict, crs=crs, geometry="geometry")

        process_time = time.time() - start_time
        print(
            f"{variable} vectorising done: valid pixel: {len(gdf)}, using: {process_time:.2f} seconds."
        )

        return gdf

    @staticmethod
    def import_all_variables(
        engine: sqlalchemy.engine.base.Engine,
        data_directory: str | Path,
        crs: int | str = 3857,
        table_name: str = "watersource",
        variables: List[str] = None,
    ) -> Dict[str, int]:
        """
        Import all variables from a geotiff file to database

        Args:
            data_directory:
            crs:
            table_name:
            variables:

        Returns:
            dict:
        """
        if variables is None:
            variables = list(Watersource.VARIABLE_CONFIG.keys())

        print(f"\n\n=== Start importing: {variables} ===", flush=True)

        import_stats = {}
        start = time.time()

        for variable in variables:
            try:
                print(f"\n--- Processing: {variable} ---", flush=True)

                # load to array
                all_data, timestamps, metadata = Watersource.load_variable_data(
                    data_directory, variable
                )

                # array to dataframe
                gdf = Watersource.create_geodataframe_for_variable(
                    all_data, timestamps, metadata
                )

                if len(gdf) == 0:
                    print(f"Warning: Variable {variable} has no valid data, skip.")
                    continue

                if gdf.crs != crs:
                    gdf = gdf.to_crs(epsg=crs)

                start_i = time.time()
                # Native SQL insert, keep data types correct.
                insert_count = Watersource.insert_with_proper_types(
                    engine, gdf, table_name, variable, crs
                )

                import_stats[variable] = insert_count
                print(
                    f"Importing {variable} finished: {insert_count} records in {time.time() - start_i:.2f} seconds."
                )

            except Exception as e:
                print(f"Importing {variable} failed: {e}")
                import_stats[variable] = 0

        print(
            f"\n=== Import finished: {len(import_stats)} records in {time.time() - start:.2f} seconds. ===",
            flush=True,
        )
        for var, count in import_stats.items():
            print(f"\t\t{var}: {count} records", flush=True)

        return import_stats

    @staticmethod
    def insert_with_proper_types(
        engine: sqlalchemy.engine.base.Engine,
        gdf: gpd.GeoDataFrame,
        table_name: str,
        variable: str,
        crs: int,
    ) -> int:
        """
        Insert data with proper types using native SQL
        """
        inserted_count = 0

        # SQL insert statement
        insert_sql = text(
            f"""
            INSERT INTO {table_name}
            (geometry, variable, timestamps, values, row, col)
            VALUES 
            (ST_SetSRID(ST_GeomFromText(:geom_wkt), :crs), :variable, :timestamps, :values, :row, :col)
            """
        )

        batch_size = 1000
        total_records = len(gdf)

        for i in range(0, total_records, batch_size):
            batch_params = []
            batch_gdf = gdf.iloc[i : min(i + batch_size, total_records)]

            for _, row in batch_gdf.iterrows():
                # should be list of datetime objects not strings
                timestamps_array = row["timestamps"]
                if timestamps_array and isinstance(timestamps_array[0], str):
                    timestamps_array = [
                        datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        for ts in timestamps_array
                    ]
                value_array = row["values"]
                if value_array and isinstance(value_array[0], np.float32):
                    value_array = [
                        float(v) if not np.isnan(v) else None for v in value_array
                    ]

                param = {
                    "geom_wkt": row["geometry"].wkt,
                    "variable": variable,
                    "timestamps": timestamps_array,
                    "values": value_array,
                    "row": int(row["row"]),
                    "col": int(row["col"]),
                    "crs": crs,
                }
                batch_params.append(param)

            if batch_params:
                with engine.connect() as conn:
                    conn.execute(insert_sql, batch_params)
                    conn.commit()
                    inserted_count += len(batch_params)

                print(
                    f"\t import progress: {min(i + batch_size, total_records)}/{total_records}",
                    flush=True,
                )

        return inserted_count

    @staticmethod
    def init_table(
        engine: sqlalchemy.engine.base.Engine, tablename: str, crs: int
    ) -> None:
        """
        Initialize the table
        Parameters
        ----------
        engine
        tablename
        crs

        Returns
        -------

        """
        print("Start initializing table...", flush=True)

        try:
            with engine.connect() as conn:

                # Drop exist table. TODO: Comment out in production. It is not recommended to drop the table in production.
                conn.execute(text(f"""DROP TABLE IF EXISTS {tablename}"""))
                conn.commit()

                # enable extension
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gin"))
                # conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))

                # create table
                print(f"Creating {tablename} table...")
                create_table_sql = f"""
                    CREATE TABLE IF NOT EXISTS {tablename} (
                        id BIGSERIAL PRIMARY KEY,
                        geometry GEOMETRY(POINT, {crs}
                        ) NOT NULL,
                        variable VARCHAR(10) NOT NULL,
                        timestamps TIMESTAMPTZ[] NOT NULL,
                        values FLOAT[] NOT NULL,
                        row INTEGER,
                        col INTEGER,
                        created_at TIMESTAMP DEFAULT NOW()
                        )
                """

                conn.execute(text(create_table_sql))

                # Create indexx
                print(f"Creating {tablename} table indexes...")
                indexes = [
                    f"CREATE INDEX IF NOT EXISTS idx_{tablename}_geom ON {tablename} USING GIST(geometry)",
                    f"CREATE INDEX IF NOT EXISTS idx_{tablename}_variable ON {tablename} (variable)",
                    f"CREATE INDEX IF NOT EXISTS idx_{tablename}_timestamps ON {tablename} USING GIN(timestamps)",
                    f"CREATE INDEX IF NOT EXISTS idx_{tablename}_row_col ON {tablename} (row, col)",
                    f"CREATE INDEX IF NOT EXISTS idx_{tablename}_variable_geom ON {tablename} (variable, geometry)",
                    # f"CREATE INDEX IF NOT EXISTS idx_{tablename}_variable_row_col ON {tablename} (variable, row, col)",
                ]

                for index_sql in indexes:
                    try:
                        conn.execute(text(index_sql))
                    except Exception as e:
                        print(f"Creating table error: {e}")

                conn.commit()

                print("Table initialization finished.", flush=True)

                # Validate
                table_exists = conn.execute(
                    text(
                        f"""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables
                            WHERE table_schema = 'public'
                            AND table_name = '{tablename}'
                        )
                        """
                    )
                ).scalar()

                if table_exists:
                    print(f"✓ Table {tablename} create successfully.", flush=True)
                else:
                    print(f"✗ Table {tablename} create failed.", flush=True)

                # Check extension
                extensions = conn.execute(
                    text(
                        """
                        SELECT extname FROM pg_extension
                        """
                    )
                    # WHERE extname IN ('postgis', 'uuid-ossp')
                ).fetchall()

                print(
                    f"✓ Enabled extensions: {[ext[0] for ext in extensions]}",
                    flush=True,
                )

                # Check index
                indexes = conn.execute(
                    text(
                        """
                            SELECT 
                                schemaname,
                                tablename,
                                indexname,
                                indexdef
                            FROM pg_indexes 
                            WHERE tablename = :tablename
                            AND schemaname = 'public'
                            ORDER BY indexname
                        """
                    ),
                    {"tablename": tablename},
                ).fetchall()

                print(f"✓ Exist indexes: {[ind[2] for ind in indexes]}", flush=True)

        except Exception as e:
            print(f"Fail to init table: {e}")
            raise


def gen_db(
    input_dir: Path = Path("./model_output"),
    start_time: datetime = datetime(2024, 6, 1, 0, 0, 0),
    crs: int | str = 3857,
    clean_tmp: bool = False,
) -> None:
    """
    Generate watersource database from asc/text files
    ------------
    input_dir: Path
        directory containing asc/text files
    start_time:  datetime
        start time of the watersource model output
    crs: int or str
        coordinate reference system, e.g. 3857 or "EPSG:3857"
    ------------
    Returns:
        None
    """
    # Check Engine connection immediately
    engine = get_connection_from_profile()
    data_dir = input_dir.parent / "watersource"
    data_dir.mkdir(exist_ok=True, parents=True)

    modified_dir = input_dir.parent / "modified"
    modified_dir.mkdir(exist_ok=True, parents=True)

    # round source coordinates to integer
    Watersource.modify_asc_line_parallel(input_dir, modified_dir)

    # asc to geotiff
    Watersource.asc_to_geotiff(modified_dir, data_dir, start_time)

    # get crs as int
    if isinstance(crs, str):
        crs = int(crs.split(":")[1])

    # init table
    Watersource.init_table(engine, "watersource", crs)

    # load file and import to table in db
    Watersource.import_all_variables(engine, data_dir, crs)

    # clean temp dirs
    if clean_tmp:
        import shutil

        print("Cleaning temporary files...")
        shutil.rmtree(modified_dir)


if __name__ == "__main__":
    in_dir = Path(EnvVariable.DATA_DIR_MODEL_OUTPUT)
    gen_db(in_dir)
