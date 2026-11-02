FROM python:3.12-slim@sha256:1148dbb014615300fa7e713b2f94f550c0d1c69780c0805f84f093ceee34dd0b

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    AWS_DEFAULT_REGION=us-east-2 \
    AWS_EC2_METADATA_DISABLED=true

WORKDIR /app
COPY containers/probe/requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir --require-hashes --only-binary=:all: -r requirements.txt
COPY src/airline_warehouse/connectivity_probe.py /app/src/airline_warehouse/connectivity_probe.py
COPY tests/test_connectivity_probe.py /app/tests/test_connectivity_probe.py
USER 65532:65532
ENTRYPOINT ["python", "-m", "airline_warehouse.connectivity_probe"]
