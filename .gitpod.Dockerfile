FROM gitpod/workspace-full

ENV JASPER_LIBDIR="/usr/lib/x86_64-linux-gnu"
ENV JASPER_INCDIR="/usr/include"
ENV PNG_LIBDIR="/usr/lib/x86_64-linux-gnu"
ENV PNG_INCDIR="/usr/include"
ENV ZLIB_LIBDIR="/usr/lib/x86_64-linux-gnu"
ENV ZLIB_INCDIR="/usr/include"

RUN wget http://security.ubuntu.com/ubuntu/pool/main/j/jasper/libjasper-dev_1.900.1-debian1-2.4ubuntu1.3_amd64.deb \
      && wget http://security.ubuntu.com/ubuntu/pool/main/j/jasper/libjasper1_1.900.1-debian1-2.4ubuntu1.3_amd64.deb \
      && sudo dpkg --install libjasper1_1.900.1-debian1-2.4ubuntu1.3_amd64.deb \
      && sudo dpkg --install libjasper-dev_1.900.1-debian1-2.4ubuntu1.3_amd64.deb \
      && rm libjasper1_1.900.1-debian1-2.4ubuntu1.3_amd64.deb \
      && rm libjasper-dev_1.900.1-debian1-2.4ubuntu1.3_amd64.deb