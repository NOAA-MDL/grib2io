FROM continuumio/anaconda3:latest

ENV DEPENDS="cython numpy pyproj"

RUN apt update -y && \
    apt install libopenjp2-7 libopenjp2-7-dev libpng16-16 libpng-dev libaec0 libaec-dev && \
    conda install -c conda-forge nceplibs-g2c && \
    pip install $DEPENDS

COPY . /grib2io

WORKDIR /grib2io

RUN pip install .
