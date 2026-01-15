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
This script provides functions to retrieve the watersource table in the database
"""
import numpy as np
from typing import Union, List, Dict, Any, Tuple
from pyproj import Transformer
from sqlalchemy import text  # TIMESTAMP, Float, Integer, String
import csv
from io import StringIO
from src.digitaltwin.setup_environment import get_connection_from_profile
from src.config import EnvVariable


def query_simple(
    longitude: float,
    latitude: float,
    variable: str,
    tolerance: float = 31,
    crs: int = 3857,
    f_response: str = "csv",
) -> None | str | dict[str, Any]:
    """
    simple retrieve：by coordinates return all time points values for a variable

    Args:
        longitude:
        latitude:
        variable:
        tolerance:
        crs:
        format: "csv" or "json"

    Returns:
        dict:
    """
    engine = get_connection_from_profile()
    if not isinstance(variable, str):
        raise ValueError("variable must be a string.")

    query_sql = text(
        """
        SELECT
            id,
            ST_X(geometry) as actual_lon,
            ST_Y(geometry) as actual_lat,
            variable,
            timestamps,
            values,
            row,
            col,
            ST_Distance(geometry, ST_SetSRID(ST_MakePoint(:lon, :lat), :crs)) as distance
        FROM watersource
        WHERE variable = :variable
        AND ST_DWithin(geometry, ST_SetSRID(ST_MakePoint(:lon, :lat), :crs), :tolerance)
        ORDER BY distance
        LIMIT 1
        """
    )

    # convert coordinates from EPSG:4326 to EPSG:3857 if needed
    if crs == 4326:
        transformer = Transformer.from_crs(crs, 3857, always_xy=True)
        longitude_t, latitude_t = transformer.transform(longitude, latitude)
        tolerance_t = tolerance * 111320  # approx. degree to meter
    elif crs == 3857:
        longitude_t, latitude_t = longitude, latitude
        tolerance_t = tolerance
    else:
        raise ValueError(f"Do not support CRS: {crs}")

    print(f"Querying: ({longitude_t}, {latitude_t}), variable: {variable}", flush=True)
    try:
        with engine.connect() as conn:
            result = (
                conn.execute(
                    query_sql,
                    {
                        "lon": longitude_t,
                        "lat": latitude_t,
                        "variable": variable,
                        "tolerance": tolerance_t,
                        "crs": 3857,
                    },
                )
                .fetchone()
                ._asdict()
            )

            if not result:
                return None

            result["values_nonan"] = [
                v for v in result["values"] if isinstance(v, (int, float))
            ]

            # construct response
            if f_response == "json":
                response = {
                    "query": {
                        "location": {"longitude": longitude, "latitude": latitude},
                        "variables": variable,
                        "tolerance": tolerance,
                        "crs": f"EPSG:{crs}",
                    },
                    "variables_data": {
                        variable: {
                            "nearest_point": {
                                "longitude": result["actual_lon"],
                                "latitude": result["actual_lat"],
                                "distance": float(result["distance"]),
                                "pixel_position": {
                                    "row": result["row"],
                                    "col": result["col"],
                                },
                            },
                            "variable_info": {"name": result["variable"]},
                            "variable_data": {
                                "timestamps": [
                                    ts.isoformat() for ts in result["timestamps"]
                                ],
                                "values": result["values"],
                            },
                            "statistics": {
                                "count": len(result["values_nonan"]),
                                "min": float(min(result["values_nonan"])),
                                "max": float(max(result["values_nonan"])),
                                "mean": float(
                                    sum(result["values_nonan"])
                                    / len(result["values_nonan"])
                                ),
                                "std": (
                                    float(np.std(result["values_nonan"]))
                                    if len(result["values_nonan"]) > 1
                                    else 0.0
                                ),
                            },
                        }
                    },
                }
            else:  # csv
                output = StringIO()
                csv_writer = csv.writer(output)
                csv_writer.writerow(["timestamp", "value"])  # header row

                for ts, val in zip(result["timestamps"], result["values"]):
                    # to UTC ISO format
                    csv_writer.writerow([ts.isoformat().replace("+00:00", "Z"), val])

                response = output.getvalue()
        return response

    except Exception as e:
        print(f"Error: {str(e)}")
        return None


def query_multiple_variables_simple(
    longitude: float,
    latitude: float,
    variables: List[str] = None,
    tolerance: float = 31,
    crs: int = 3857,
) -> Dict[str, Any]:
    """
    retrieve a coordinate and return time serial values for all variable

    Args:
        longitude:
        latitude:
        variables:
        tolerance:
        crs:

    Returns:
        dict:
    """
    engine = get_connection_from_profile()

    if variables is None or variables == "":
        # Check existing variables in the table
        with engine.connect() as conn:
            existing_vars = conn.execute(
                text(
                    """
                    SELECT DISTINCT variable FROM watersource
                    """
                )
            ).fetchall()
            variables = [row[0] for row in existing_vars]
            print(f"Existing variables in the table: {variables}")

    if not variables:
        return None

    query_sql = text(
        """
        SELECT DISTINCT ON (variable)
            variable,
            ST_X(geometry) as actual_lon,
            ST_Y(geometry) as actual_lat,
            timestamps,
            values,
            row,
            col,
            ST_Distance(geometry, ST_SetSRID(ST_MakePoint(:lon, :lat), :crs)) as distance
        FROM watersource
        WHERE variable = ANY(:variables)
        AND ST_DWithin(geometry, ST_SetSRID(ST_MakePoint(:lon, :lat), :crs), :tolerance)
        ORDER BY variable, distance
        """
    )

    # convert coordinates from EPSG:4326 to EPSG:3857 if needed
    if crs == 4326:
        transformer = Transformer.from_crs(crs, 3857, always_xy=True)
        longitude_t, latitude_t = transformer.transform(longitude, latitude)
        tolerance_t = tolerance * 111320  # approx. degree to meter
    elif crs == 3857:
        longitude_t, latitude_t = longitude, latitude
        tolerance_t = tolerance
    else:
        raise ValueError(f"Do not support CRS: {crs}")

    with engine.connect() as conn:
        results = conn.execute(
            query_sql,
            {
                "lon": longitude_t,
                "lat": latitude_t,
                "variables": variables,
                "tolerance": tolerance_t,
                "crs": 3857,
            },
        ).fetchall()

        if not results:
            return None

        results = [row._asdict() for row in results]

        # construct response
        response = {
            "query": {
                "location": {"longitude": longitude, "latitude": latitude},
                "variables": variables,
                "tolerance": tolerance,
                "crs": f"EPSG:{crs}",
            },
            "variables_data": {},
        }

        for result in results:
            # clean null values for statistics
            result["values_nonan"] = [
                v for v in result["values"] if isinstance(v, (int, float))
            ]

            variable = result["variable"] if result["variable"] else "unknown"

            variable_data = {
                "nearest_point": {
                    "longitude": result["actual_lon"],
                    "latitude": result["actual_lat"],
                    "distance": float(result["distance"]),
                    "pixel_position": {"row": result["row"], "col": result["col"]},
                },
                "variable_data": {
                    "timestamps": [ts.isoformat() for ts in result["timestamps"]],
                    "values": result["values"],
                },
                "statistics": {
                    "count": len(result["values_nonan"]),
                    "min": float(min(result["values_nonan"])),
                    "max": float(max(result["values_nonan"])),
                    "mean": float(
                        sum(result["values_nonan"]) / len(result["values_nonan"])
                    ),
                    "std": (
                        float(
                            np.std(result["values_nonan"])
                            if len(result["values_nonan"]) > 1
                            else 0.0
                        )
                    ),
                },
            }

            response["variables_data"][variable] = variable_data

        return response


def query_watersource_data(
    longitude: float,
    latitude: float,
    variable: Union[str, list],
    crs: int,
    f_response: str = "csv",
) -> Dict[str, Any]:
    """Celery task：retrieve watersource data from the database based on geographic coordinates."""
    try:
        if isinstance(variable, str) and variable != "":
            results = query_simple(
                longitude, latitude, variable, crs=crs, f_response=f_response
            )
        elif isinstance(variable, list):
            if len(variable) == 1:
                results = query_simple(
                    longitude, latitude, variable[0], crs=crs, f_response=f_response
                )
            elif len(variable) == 2 or len(variable) == 3:
                results = query_multiple_variables_simple(
                    longitude, latitude, variable, crs=crs
                )
            else:
                raise Exception(f"Unknown variable list length: {len(variable)}")
        elif variable is None:
            results = query_multiple_variables_simple(longitude, latitude, crs=crs)
        else:
            raise Exception(f"Unknown variable: {variable}")

        # post-process results
        if not results:
            return {
                "status": "completed",
                "message": f"No data found.",
                "data": [],
                "count": 0,
                "coordinates": {"longitude": longitude, "latitude": latitude},
            }

        if f_response == "json":
            print(
                f'Retrieve finished: found {len(results["variables_data"])} variables at {longitude}, {latitude}.'
            )
            return {
                "status": "completed",
                "data": results,
                "count": len(results["variables_data"]),
                "coordinates": {"longitude": longitude, "latitude": latitude},
            }
        else:
            # for csv format
            print(f"Retrieve finished at {longitude}, {latitude}.")
            return results

    except Exception as e:
        print(f"Error: retrieve failed: {str(e)}")


def test_query():
    # test simple query
    from pprint import pprint

    # result = query_simple(174.85107, -41.11647, "hydro")
    # pprint(result)

    # result = query_multiple_variables_simple(174.85107, -41.11647)
    # pprint(result)

    result = query_watersource_data(19465616, -5028020, crs=3857, variable="rain")
    pprint(result)


if __name__ == "__main__":
    test_query()
