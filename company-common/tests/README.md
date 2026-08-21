# Tests for Company Data Models

This directory contains comprehensive test coverage for the Pydantic models in `models/company_data.py`.

## Running Tests Locally

### Prerequisites
Install test dependencies:
```bash
pip install -r requirements-dev.txt
```

### Run All Tests
```bash
pytest tests/
```

### Run with Verbose Output
```bash
pytest tests/ -v
```

### Run Specific Test File
```bash
pytest tests/test_company_data.py -v
```

### Run Specific Test Class
```bash
pytest tests/test_company_data.py::TestCompanyData -v
```

### Run Specific Test
```bash
pytest tests/test_company_data.py::TestCompanyData::test_minimal_valid_company -v
```

### Generate Coverage Report
```bash
pip install pytest-cov
pytest tests/ --cov=models --cov-report=html
```

## Test Structure

The test suite includes 26 tests organized into the following categories:

### Unit Tests
- **TestCompanyFundingInfo**: Tests for funding round information validation
- **TestCompanyFinancials**: Tests for financial data validation
- **TestCompanyOperatingMetrics**: Tests for operating metrics validation
- **TestCompanyStatus**: Tests for company status enum
- **TestCurrentCompanyStatus**: Tests for current status tracking
- **TestCompanyEmployeeCount**: Tests for employee count data
- **TestCompanyLocation**: Tests for company location validation
- **TestCompanyData**: Tests for main company data model

### Integration Tests
- **TestIntegration**: Complex scenarios with multiple related objects, serialization, and deserialization

## What's Tested

✅ Required field validation
✅ Optional field defaults
✅ Type validation and coercion
✅ Enum validation
✅ List field defaults
✅ Nested object validation
✅ Model serialization (dict and JSON)
✅ Complex multi-object scenarios

## CI/CD Integration

The GitHub Actions workflow (`.github/workflows/tests.yml`) runs tests automatically on:
- Push to main and develop branches
- Pull requests to main and develop branches

The workflow:
1. Runs on Python 3.9, 3.10, 3.11, and 3.12
2. Checks type annotations with mypy
3. Runs all tests with pytest
4. Generates coverage reports
