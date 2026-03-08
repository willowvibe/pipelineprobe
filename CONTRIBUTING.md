# Contributing to PipelineProbe

Welcome! We are excited that you want to contribute to PipelineProbe. Before you get started, please take a moment to review this guidelines.

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/willowvibe/PipelineProbe.git
   cd PipelineProbe
   ```

2. We recommend using `hatch` or just a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -e ".[dev]"
   # Assuming you also install pytest, ruff, etc.
   ```

## Running Tests

Run the test suite via pytest:
```bash
pytest
```

## Linting

We use `ruff` to ensure code quality:
```bash
ruff check .
ruff format .
```

## Pull Request Process

1. Fork the repo and create your branch from `main`.
2. Ensure you have added tests that cover your modifications.
3. Ensure CI passes.
4. Issue a Pull Request with a clear description of the problem and your solution.
