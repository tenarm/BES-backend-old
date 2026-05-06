# ERP Factory Backend

This is the "Repo-Ready" Modular Monolith backend for the ERP Factory. It uses a PDM-based monorepo structure to maintain strict boundaries between the Core Kernel, Product Extensions, and Client Instances.

## Directory Structure

- `core/`: The ERP Kernel (Auth, DB Foundation, Event Bus, Base Models).
- `extensions/`: Shared Product Modules (e.g., Sales, Finance).
- `instances/`: Client-specific deployment entry points.

## Getting Started

### 1. Requirements
- Python 3.10+
- [PDM](https://pdm-project.org/)

### 2. Installation
Install all dependencies for the workspace:
```bash
pdm install
```

### 3. Activating the Environment
To activate the virtual environment manually:
```bash
source .venv/bin/activate
```

## Running the Server

In this architecture, you run a specific **Instance** rather than individual modules.
navigate to their location

### Run Acme Corp Instance
```bash
pdm run uvicorn acme_corp.main:app --reload
```
Once running, you can access:
- **API Documentation**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Bootstrap Endpoint**: [http://127.0.0.1:8000/api/v1/bootstrap](http://127.0.0.1:8000/api/v1/bootstrap)

## Architectural Rules

1. **Strict Dependency Direction**: Extensions can import from `core`, but `core` must NEVER import from extensions.
2. **Module Isolation**: Modules (e.g., Sales and Finance) must not import from each other directly. Use the **Event Bus** for cross-module communication.
3. **No Cross-Module Joins**: Avoid SQL joins across different domain tables. Perform separate queries and link by ID to maintain future repository independence.
4. **Master Data**: Follow the Hybrid Strategy (Base Table in Core + Detail Table in Extension).
