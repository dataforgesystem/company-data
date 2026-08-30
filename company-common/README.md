# Company Common

Shared Pydantic models used by the company services.

## Local development

From a service directory, install the shared package in editable mode:

```bash
python -m pip install -e ../company-common
```

reinstall
python -m pip install --force-reinstall -e ../company-common


Then import the models without copying their definitions:

```python
from models.company_data import CompanyData, CompanyStatus
```

For a deployed service, install the package as a regular dependency during
the image/build step instead of using editable mode. Keep the version in
`pyproject.toml` aligned with the service's dependency or package registry.
