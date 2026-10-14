#!/usr/bin/env bash
# Run on each EC2 worker (gpuflow-1, gpuflow-2, gpuflow-3) as ubuntu user.
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/gpuflow}"
REPO_URL="${REPO_URL:-}"  # set to your git URL or scp project manually

sudo mkdir -p "$INSTALL_DIR"
sudo chown "$USER:$USER" "$INSTALL_DIR"

if [[ -n "$REPO_URL" ]]; then
  git clone "$REPO_URL" "$INSTALL_DIR"
else
  echo "Copy CPUFlow project to $INSTALL_DIR (git clone or scp), then re-run."
  exit 1
fi

cd "$INSTALL_DIR"
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r backend/requirements.txt
python -m grpc_tools.protoc -I protobufs \
  --python_out=protobufs --grpc_python_out=protobufs protobufs/gpuflow.proto

cp deploy/aws-worker.env.example "$INSTALL_DIR/worker.env"
echo "Edit $INSTALL_DIR/worker.env with SCHEDULER_ADDRESS and WORKER_HOSTNAME (private IP)"

sudo cp deploy/systemd/gpuflow-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable gpuflow-worker
echo "After editing worker.env: sudo systemctl start gpuflow-worker"
