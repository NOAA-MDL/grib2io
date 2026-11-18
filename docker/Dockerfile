FROM condaforge/miniforge3:latest

ENV CMAKE_PREFIX_PATH=/opt/conda \
    G2C_DIR=/opt/conda

RUN mamba install -y -c conda-forge \
        c-compiler \
        cmake \
        ninja \
        nceplibs-g2c \
        scikit-build-core \
        cython \
        numpy \
        pyproj \
        pip && \
    conda clean -afy

COPY . /grib2io

WORKDIR /grib2io

RUN pip install --no-build-isolation --no-deps .
