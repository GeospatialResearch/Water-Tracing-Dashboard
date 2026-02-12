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

"""The main web application that serves the Digital Twin to the web through a Rest API."""

import logging
from urllib.parse import urlparse, parse_qs, unquote
from http.client import OK

from flask import Flask, jsonify, make_response, Response, request
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint
import requests

from src.config import EnvVariable
from src.check_celery_alive import check_celery_alive
from src.geoserver import get_terria_catalog
from src.watersource.query_db import query_watersource_data

# Initialise flask server object
app = Flask(__name__)
CORS(app)

# Serve API documentation
SWAGGER_URL = "/swagger"
API_URL = "/static/api_documentation.yml"
swagger_ui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL, API_URL, config={"app_name": "Porirua Explorer"}
)
app.register_blueprint(swagger_ui_blueprint, url_prefix=SWAGGER_URL)

# Default response format for data queries
F_RESPONSE = "csv"


@app.route("/")
def index() -> Response:
    """
    Ping this endpoint to check that the flask app is running.
    Supported methods: GET

    Returns
    -------
    Response
        The HTTP Response. Expect OK if health check is successful
    """
    return Response(
        """
    Backend is receiving requests.
    GET /health-check to check if celery workers active.
    GET /swagger to get API documentation.
    """,
        OK,
    )


@app.route("/health-check")
@check_celery_alive
def health_check() -> Response:
    """
    Ping this endpoint to check that the server is up and running.
    Supported methods: GET

    Returns
    -------
    Response
        The HTTP Response. Expect OK if health check is successful
    """
    return Response("Healthy", OK)


@app.route("/terria-catalog.json")
def terria_catalog() -> Response:
    """
    Return a terria catalog that includes entries for static files and input layers from geoserver.
    Supported methods: GET

    Returns
    -------
    Response
        The HTTP Response. Expect OK if health check is successful
    """
    catalog = get_terria_catalog()
    return make_response(jsonify(catalog), OK)


@app.route("/api/normalise/", methods=["GET"])
def normalise_layer() -> Response:
    """Pass the request to geoserver but normalise it"""

    # Find what year we are looking at
    query_parameters = request.args.to_dict()
    layer = query_parameters["layers"]
    year = layer[:5]

    # Request the raw RGB values (not depth scaled) from geoserver
    rgb_raw_layer = f"{year}_watersourceRGB_10m_raw"
    query_parameters["query_layer"] = rgb_raw_layer
    geoserver_resp = requests.request(
        method=request.method,
        url=f"{EnvVariable.GEOSERVER_INTERNAL_HOST}:{EnvVariable.GEOSERVER_INTERNAL_PORT}/geoserver/static_files/wms",
        params=query_parameters
    )
    geoserver_resp.raise_for_status()
    json = geoserver_resp.json()
    props = json["features"][0]["properties"]

    # Normalise into the range 0-100% instead of 0-255
    rgb = ["Streams", "Rain", "Tide"]
    new_props = {}
    for i, (k, v) in enumerate(props.items()):
        normalised = min(v / 2.55, 100)
        new_props[rgb[i]] = f"{round(normalised)} %"
    json["features"][0]["properties"] = new_props

    return make_response(json, 200)


@app.route("/api/query", methods=["GET"])
def query_watersource():
    """retrieve watersource data for a given lat/lon coordinate."""
    try:
        if request.is_json:
            data = request.get_json()
        else:
            # parse query parameters from URL
            parsed_url = urlparse(request.url)
            query_params = parse_qs(parsed_url.query)
            data = {}
            for key, value in query_params.items():
                # Decode URL-encoded values and convert single-item lists to values
                decoded_value = (
                    unquote(value[0])
                    if len(value) == 1
                    else [unquote(v) for v in value]
                )
                try:
                    # Try to evaluate as Python literal (e.g., list, number)
                    data[key] = eval(decoded_value)
                except:
                    # Fallback to string if eval fails
                    data[key] = decoded_value

        print(f"Received {request.method} request to /api/query: {data}.", flush=True)

        if not data:
            return jsonify({"error": "No valid query request found."}), 400

        if (
            "bbox" not in data
            or "width" not in data
            or "height" not in data
            or "i" not in data
            or "j" not in data
        ):
            return jsonify({"error": "missing required parameters."}), 400

        variable = data.get("variable", "hydro").lower()
        if variable in ("", "all", "none", "null"):
            variable = None

        epoch = data.get("epoch", "2020s").lower()
        # below conditions should not happen but for safety.
        if epoch in {"current", "present", "now"}:
            epoch = "2020s"
        if epoch not in ("2020s", "2050s", "2080s"):
            return (
                jsonify(
                    {"error": "invalid epoch. Must be one of 2020s, 2050s, 2080s."}
                ),
                400,
            )

        try:
            crs = data["crs"]
            assert crs == "EPSG:3857", "only EPSG:3857 supported."
            crs = int(crs.split(":")[1])
            bbox = data["bbox"]
            width = data["width"]
            height = data["height"]
            i = data["i"]  # column index
            j = data["j"]  # row index

            # note: bbox is lowest-left, upper-right, but i and j are from upper-left, so we need to flip j
            latitude = float(
                bbox[1] + (bbox[3] - bbox[1]) * (height - j + 0.5) / height
            )
            longitude = float(bbox[0] + (bbox[2] - bbox[0]) * (i + 0.5) / width)

        except (ValueError, TypeError):
            return jsonify({"error": "latitude or longitude is not valid."}), 400

        # run task TODO: make it async with celery
        print(
            f"Start retrieve {variable}: coordinate: ({longitude}, {latitude})",
            flush=True,
        )
        result = query_watersource_data(
            longitude, latitude, epoch, variable, crs, f_response=F_RESPONSE
        )

        if isinstance(result, str):  # csv
            response = make_response(result, OK)
            response.content_type = "text/csv"
            return response
        elif isinstance(result, dict):  # json
            return (
                jsonify(
                    {
                        "status": "finished",
                        "message": "Retrieving watersource data.",
                        "coordinates": {"longitude": longitude, "latitude": latitude},
                        "variable": variable,
                        "data": result,
                    }
                ),
                202,
            )

    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({f"Error: internal error {str(e)}"}), 500


@app.route("/a-time-series-mockup")
def a_timeseries() -> Response:
    csv = """
Time (UTC),Proportion of water from streams (%) 
2023-11-22T00:00:00.000Z,0.4559512734413147
2023-11-23T00:00:00.000Z,0.43369847536087036
2023-11-24T00:00:00.000Z,0.4384692907333374
2023-11-25T00:00:00.000Z,0.4204336702823639
"""
    response = make_response(csv, OK)
    response.content_type = "text/csv"
    return response


def test_query_watersource():
    """Test function for query_watersource endpoint."""
    with app.test_client() as client:
        response = client.get(
            "/api/query",
            json={
                "bbox": (
                    19467593.859894972,
                    -5026498.980033189,
                    19468816.852347534,
                    -5025275.987580627,
                ),
                "i": 0,
                "j": 176,
                "width": 256,
                "height": 256,
                "variable": "hydro",
                "crs": "EPSG:3857",
            },
        )
        print("Test /api/query response status code:", response.status_code)
        if F_RESPONSE == "json":
            print("Test /api/query response data:\n", response.get_json())
        else:
            print("Test /api/query response data:\n", response.data.decode("utf-8"))


# Development server
if __name__ == "__main__":
    # app.run(debug=True, host="0.0.0.0")
    test_query_watersource()

# Production server
if __name__ != "__main__":
    # Set gunicorn loggers to work with flask
    gunicorn_logger = logging.getLogger("gunicorn.error")
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
