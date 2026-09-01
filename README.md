# GPUFlow

GPUFlow is a Distributed GPU-Aware Workload Scheduling and Resource Management Platform.

## Architecture
GPUFlow consists of a React frontend and a FastAPI/Python backend. 
It uses a custom scheduler algorithm for workload distribution to worker nodes via gRPC communication. 

## FA1 Scope (Current)
This repository currently covers the FA1 scope which includes:
- Basic project architecture
- Custom scheduling design placeholders
- gRPC communication base
- Logging and Health checks

## Usage
Start the backend via Docker Compose or manually using Uvicorn.
