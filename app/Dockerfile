FROM python:3.13-slim AS builder
WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --require-hashes -r requirements.txt
COPY . .
RUN pip install --no-deps .
# pip is a build tool; the app never needs it at runtime.
RUN pip uninstall -y pip

FROM python:3.13-slim AS release
WORKDIR /app
# Install Debian security fixes published after the base image was built.
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
# The base image's own pip is not needed either.
RUN /usr/local/bin/python -m pip uninstall -y pip
USER 10001
ARG APP_VERSION=dev
ENV APP_VERSION=$APP_VERSION
CMD ["frontdesk" , "serve"]
