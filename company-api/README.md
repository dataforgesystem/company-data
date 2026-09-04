# Company Data Service

This is the core backend service for the Data-Forge System.

## Prerequisites

- Python 3.10+
- `pip` and `venv`

## Local Development Setup

1. **Navigate to the service directory**:
   ```bash
   cd company-data/company-api

## Create and activate virtual environment

```bash
python -m venv venv
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

## Install Dependencies

```bash
pip install -r requirements.txt
```
## Run the development server

```bash
uvicorn main:app --reload
```

## Verify it's working:
- Open your browser to ```http://localhost:8000``` → Should return ```{"status": "ok"}```
- Interactive API docs are available at http://localhost:8000/docs

## Running the tests
```bash
# From the company-api directory
python -m pytest
```
