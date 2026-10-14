#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/gpuflow}"
WORKER_ENV="${WORKER_ENV:-$INSTALL_DIR/worker.env}"

echo "==> Slim GPUFlow worker install in $INSTALL_DIR"
cd "$INSTALL_DIR"

if [[ ! -f "$WORKER_ENV" ]]; then
  echo "ERROR: missing $WORKER_ENV"
  exit 1
fi

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
if [[ -d deploy/wheels ]] && ls deploy/wheels/*.whl >/dev/null 2>&1; then
  pip install -q --no-index --find-links deploy/wheels -r backend/requirements-worker.txt
else
  pip install -q -U pip
  pip install -q -r backend/requirements-worker.txt
fi

if [[ ! -f protobufs/gpuflow_pb2.py ]]; then
  python -m grpc_tools.protoc -I protobufs \
    --python_out=protobufs --grpc_python_out=protobufs protobufs/gpuflow.proto
fi

sudo cp deploy/systemd/gpuflow-worker.service /etc/systemd/system/
sudo sed -i "s/^User=.*/User=$USER/" /etc/systemd/system/gpuflow-worker.service
sudo systemctl daemon-reload
sudo systemctl enable gpuflow-worker
sudo systemctl restart gpuflow-worker
sleep 1
sudo systemctl is-active gpuflow-worker
echo "==> Worker running. Logs: sudo journalctl -u gpuflow-worker -n 20 --no-pager"
