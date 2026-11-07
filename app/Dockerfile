FROM python:3.13-slim AS builder
WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --require-hashes -r requirements.txt
COPY . .
RUN pip install --no-deps . 

FROM python:3.13-slim AS release
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
USER 10001
ARG APP_VERSION=dev
ENV APP_VERSION=$APP_VERSION
CMD ["frontdesk" , "serve"]
