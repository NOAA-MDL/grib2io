FROM continuumio/anaconda3:latest

ENV DEPENDS="numpy pyproj"
ENV JASPER_LIBDIR="/lib"
ENV JASPER_INCDIR="/usr/include"
ENV PNG_LIBDIR="/usr/lib/aarch64-linux-gnu"
ENV PNG_INCDIR="/usr/include"
ENV ZLIB_LIBDIR="/usr/lib/aarch64-linux-gnu"
ENV ZLIB_INCDIR="/usr/include"

RUN apt update -y && apt install -y libeccodes-dev libpng-dev cmake \
    && git clone https://github.com/jasper-software/jasper.git \
    && cd jasper \
    && mkdir jasper-build \
    && cmake -B jasper-build -DCMAKE_INSTALL_PREFIX=/usr \
    && cp -r src/libjasper/include/jasper /usr/include/ \
    && cmake --build jasper-build --target install \
    && pip install $DEPENDS

COPY . /grib2io

WORKDIR /grib2io

RUN python setup.py build \
    && python setup.py install