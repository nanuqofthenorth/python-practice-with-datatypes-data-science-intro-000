FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x docker-entrypoint.sh

# Actual persistence depends on the host mounting a volume here (see
# render.yaml) -- without one, this directory is container-local and its
# contents are lost on every redeploy or restart, same as any other path
# in the image.
VOLUME ["/app/data"]

EXPOSE 8501

ENTRYPOINT ["./docker-entrypoint.sh"]
