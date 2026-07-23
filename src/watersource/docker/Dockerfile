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

# Main Dockerfile for setting up services defined in docker-compose.yml.

FROM mambaorg/micromamba:git-37bfa82-jammy AS build
# Build stage for creating the python environment with micromamba

USER root
COPY ./src/watersource/docker/environment.yml .
RUN micromamba create -vv -y -p /env -f environment.yml && \
    micromamba clean --all --yes && \
    micromamba env export -p /env --explicit

ARG MAMBA_DOCKERFILE_ACTIVATE=1

FROM ubuntu:jammy-20251013

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y git vim tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

ARG user=nonroot
ARG uid=101
ARG gid=100
RUN useradd -l -m -s /bin/bash -N -g $gid -u $uid $user

# Copy python virtual environment from build layer
COPY --chown=$uid:$gid --from=build /env /env

ENV HOME=/home/$user

ENV TZ=Pacific/Auckland \
    SHELL=bash \
    PROJ_LIB=/env/share/proj \
    PATH=/env/bin:$PATH \
    PYTHONPATH=$HOME/:$PYTHONPATH

COPY --chown=$uid:$gid src $HOME/src

WORKDIR $HOME

USER $user

CMD ["tail", "-f", "/dev/null"]