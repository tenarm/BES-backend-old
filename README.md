# BES Factory Backend

This is the modular monorepo for the **BES (Business Execution System)** backend, built using [FastAPI](https://fastapi.tiangolo.com/), [SQLModel](https://sqlmodel.tiangolo.com/), and [PDM](https://pdm-project.org/).

## 🏗️ Architecture

The backend follows a **Kernel-and-Plugin** structure within a PDM workspace.

- **`core/`**: The BES Kernel. Contains the foundation: Auth, DB Session management, RBAC logic, Event Bus, and Base Models (`BESBase`).
- **`extensions/`**: Domain-specific modules (Finance, HR, Sales, etc.). These depend on `core` but are isolated from each other.
- **`instances/`**: Deployment entry points. An instance "fuses" the Core with a set of licensed Extensions for a specific client.
- **`onboarded/`**: JSON configuration files for each client instance.

---

## 🚀 Getting Started

### 1. Requirements
- Python 3.10+
- [PDM](https://pdm-project.org/)

### 2. Installation
```bash
pdm install
```

### 3. Running an Instance
To run the server for a specific client (e.g., Acme Corp):
```bash
pdm run uvicorn instances.acme_corp.acme_corp.main:app --reload
```

### 4. API Documentation
Once running, visit:
- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Bootstrap Info**: [http://127.0.0.1:8000/api/v1/bootstrap](http://127.0.0.1:8000/api/v1/bootstrap)

---

## 🛠️ Development Workflow

### Adding a New Extension
Use the AI assistant with the **`create-extension`** skill to scaffold a new module. This ensures all layers (models, schemas, services, routers, events) are correctly created.

### Database Migrations
For Day 1, the backend performs a "Self-Healing" boot:
```python
SQLModel.metadata.create_all(engine)
```
This automatically creates missing tables in the client's dedicated database based on the active extensions.

---

## 📜 Coding Rules
All backend code MUST comply with the **[Backend Coding Rules](../.gemini/rules/backend.md)**.
Specifically, remember the **Money Rule**: Never use `float` for financial values; always use `Decimal`.
