FROM nwtgck/llvm-clang:3.6.2

# Dependencies
RUN apt update && apt upgrade -y
RUN apt install build-essential checkinstall zlib1g-dev -y
RUN apt install -y ca-certificates && update-ca-certificates --fresh

# Build openssl
WORKDIR /usr/local/src/
RUN sudo wget https://github.com/openssl/openssl/archive/refs/tags/OpenSSL_1_1_1c.tar.gz -O openssl-1.1.1c.tar.gz
RUN tar -xf openssl-1.1.1c.tar.gz && mv openssl-OpenSSL_1_1_1c openssl-1.1.1c
WORKDIR /usr/local/src/openssl-1.1.1c
RUN ./config --prefix=/usr/local/ssl --openssldir=/usr/local/ssl shared zlib
RUN make -j8
RUN make install
WORKDIR /etc/ld.so.conf.d/
RUN echo '/usr/local/ssl/lib' > openssl-1.1.1c.conf
RUN ldconfig -v
RUN mv /usr/bin/c_rehash /usr/bin/c_rehash.backup
RUN mv /usr/bin/openssl /usr/bin/openssl.backup
ENV PATH="/usr/local/llvm/llvm-3.6.2/bin:${PATH}:/usr/local/ssl/bin"

# Build python 3.9
RUN apt update
RUN apt install -y software-properties-common libncurses5-dev libgdbm-dev libnss3-dev \
                libssl-dev libreadline-dev libffi-dev wget curl libbz2-dev
WORKDIR /usr/local/src
RUN wget https://www.python.org/ftp/python/3.9.1/Python-3.9.1.tgz
RUN tar -xvzf Python-3.9.1.tgz
WORKDIR /usr/local/src/Python-3.9.1
RUN ./configure --with-openssl=/usr/local/ssl
RUN make altinstall

# Install pip3
RUN curl https://bootstrap.pypa.io/pip/get-pip.py --output get-pip.py
RUN /usr/local/bin/python3.9 get-pip.py 
RUN pip install --upgrade pip

# Dependencies
RUN apt install -y autoconf libtool libexplain-dev curl libtinfo-dev \
                lib32z1 bison flex subversion git unzip python texinfo autopoint gettext

# Get Prophet source code
RUN mkdir -p /home/workspace
WORKDIR /home/workspace
RUN git clone https://github.com/epicosy/prophet.git

# Build Prophet
WORKDIR /home/workspace/prophet
RUN chmod +x tools/*.py
RUN autoreconf -i
RUN ./configure
RUN make CXXFLAGS='-w -fno-rtti' -j8
RUN make install

# Download synapser

WORKDIR /opt/
RUN git clone https://github.com/epicosy/synapser

# Install synapser dependencies

WORKDIR /opt/synapser
RUN add-apt-repository ppa:deadsnakes/ppa -y && \ 
    apt install -y python3.8 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.8 2 && \
    apt-get install -y python3-distutils python3.8-dev && \
    curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py && \
    python3 get-pip.py 2>&1

# Install synapser

RUN DEBIAN_FRONTEND=noninteractive apt-get install -y tzdata && \
    apt-get install -y postgresql libpq-dev && pip3 install -r requirements.txt && \
    pip3 install . && \
    su -l postgres -c "/etc/init.d/postgresql start && psql --command \"CREATE USER synapser WITH SUPERUSER PASSWORD 'synapser123';\" && \
    createdb synapser" && \ 
    mkdir -p ~/.synapser/config/plugins.d && mkdir -p ~/.synapser/plugins/tool && \
    cp config/synapser.yml ~/.synapser/config/ && \
    cp -a config/plugins/.  ~/.synapser/config/plugins.d && \
    cp -a synapser/plugins/.  ~/.synapser/plugins/tool

WORKDIR /tmp/plugin
ADD genprog.syn.py
ADD genprog.syn.yml

# Install genprog plugin for synapser
RUN synapser plugin install -d /tmp/plugin
