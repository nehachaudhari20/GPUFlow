#!/usr/bin/env bash
# Run on EC2 (Amazon Linux) after project is copied to /opt/gpuflow
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/gpuflow}"
WORKER_ENV="${WORKER_ENV:-$INSTALL_DIR/worker.env}"

echo "==> Installing GPUFlow worker in $INSTALL_DIR"

sudo mkdir -p "$INSTALL_DIR"
sudo chown -R "$USER:$USER" "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Amazon Linux dependencies
if command -v dnf >/dev/null 2>&1; then
  sudo dnf install -y python3 python3-pip gcc python3-devel
elif command -v yum >/dev/null 2>&1; then
  sudo yum install -y python3 python3-pip gcc python3-devel
fi

python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r backend/requirements.txt
python -m grpc_tools.protoc -I protobufs \
  --python_out=protobufs --grpc_python_out=protobufs protobufs/gpuflow.proto

if [[ ! -f "$WORKER_ENV" ]]; then
  echo "ERROR: missing $WORKER_ENV"
  exit 1
fi

# systemd unit uses ec2-user on Amazon Linux
sudo cp deploy/systemd/gpuflow-worker.service /etc/systemd/system/
sudo sed -i "s/^User=.*/User=$USER/" /etc/systemd/system/gpuflow-worker.service
sudo systemctl daemon-reload
sudo systemctl enable gpuflow-worker
sudo systemctl restart gpuflow-worker

sleep 2
sudo systemctl status gpuflow-worker --no-pager || true
echo "==> Worker install complete. Logs: sudo journalctl -u gpuflow-worker -f"
