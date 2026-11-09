FROM nginxinc/nginx-unprivileged:1.30.6-alpine3.24
# Install Alpine security fixes published after the base image was built.
# The base image runs as user 101; switch to root only for the upgrade.
USER root
RUN apk upgrade --no-cache
USER 101
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html favicon.svg /usr/share/nginx/html/
COPY css /usr/share/nginx/html/css
COPY js /usr/share/nginx/html/js
