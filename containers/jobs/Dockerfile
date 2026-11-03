FROM python:3.12-slim@sha256:1148dbb014615300fa7e713b2f94f550c0d1c69780c0805f84f093ceee34dd0b
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src \
    AWS_DEFAULT_REGION=us-east-2 AWS_EC2_METADATA_DISABLED=true \
    DBT_SEND_ANONYMOUS_USAGE_STATS=false HOME=/work/home TMPDIR=/work
WORKDIR /app
RUN apt-get update && apt-get upgrade -y && apt-get clean && find /var/lib/apt/lists -type f -delete
COPY containers/jobs/requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir --require-hashes --only-binary=:all: -r requirements.txt
COPY src /app/src
COPY dbt /app/dbt
COPY sql /app/sql
COPY references /app/references
COPY .streamlit /app/.streamlit
COPY infra/jobs/refresh.asl.json.tftpl /app/infra/jobs/refresh.asl.json.tftpl
COPY uv.lock /app/uv.lock
COPY tests /app/tests
RUN mkdir -p /work && chown 65532:65532 /work
USER 65532:65532
VOLUME ["/work"]
ENTRYPOINT ["python", "-m", "airline_warehouse.cloud_stage"]
