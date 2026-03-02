#!/bin/bash
set -e

# ==== параметры ====
NGINX_VERSION=1.29.1
INSTALL_DIR=/usr/local/nginx
HLS_DIR=/var/www/hls

# ==== зависимости ====
apt update
apt install -y build-essential libpcre3 libpcre3-dev \
  libssl-dev zlib1g-dev wget git

# ==== загрузка исходников ====
cd /usr/local/src
wget http://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz
tar -xzf nginx-${NGINX_VERSION}.tar.gz
cd nginx-${NGINX_VERSION}

# ==== загрузка rtmp-модуля ====
git clone https://github.com/arut/nginx-rtmp-module.git

# ==== сборка ====
./configure --prefix=${INSTALL_DIR} \
  --with-http_ssl_module \
  --with-http_stub_status_module \
  --add-module=./nginx-rtmp-module
make
make install

# ==== конфиг ====
cat > ${INSTALL_DIR}/conf/nginx.conf <<'EOF'
worker_processes auto;

events {
    worker_connections 1024;
}

rtmp {
    server {
        listen 1935;
        chunk_size 4096;

        application live {
            live on;
            record off;

            hls on;
            hls_path /var/www/hls;
            hls_fragment 3;
            hls_playlist_length 60;
        }
    }
}

http {
    include       mime.types;
    default_type  application/octet-stream;

    server {
        listen 8080;

        location /hls {
            root /var/www;
            types {
                application/vnd.apple.mpegurl m3u8;
                video/mp2t ts;
            }
            add_header Cache-Control no-cache;
            add_header 'Access-Control-Allow-Origin' '*';
        }
    }
}
EOF

# ==== директории HLS ====
mkdir -p ${HLS_DIR}
chmod -R 777 ${HLS_DIR}

# ==== запуск nginx ====
${INSTALL_DIR}/sbin/nginx

echo "✅ Установка завершена!"
echo "RTMP слушает: rtmp://<SERVER_IP>/live/stream"
echo "HLS доступно: http://<SERVER_IP>:8080/hls/stream.m3u8"
