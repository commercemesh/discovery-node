# Contributing to Discovery Node

We love your input! We want to make contributing to Discovery Node as easy and transparent as possible, whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features
- Becoming a maintainer

## Development Process

We use GitHub to host code, to track issues and feature requests, as well as accept pull requests.

1. Fork the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests.
3. If you've changed APIs, update the documentation.
4. Ensure the test suite passes.
5. Make sure your code follows the existing style.
6. Issue that pull request!

## Pull Request Process

1. Update the README.md with details of changes to the interface, this includes new environment variables, exposed ports, useful file locations and container parameters.
2. Increase the version numbers in any examples files and the README.md to the new version that this Pull Request would represent.
3. The PR will be merged once you have the sign-off of at least one other developer.

## Any contributions you make will be under the MIT Software License

In short, when you submit code changes, your submissions are understood to be under the same [MIT License](LICENSE) that covers the project. Feel free to contact the maintainers if that's a concern.

## Report bugs using GitHub's [issues](https://github.com/yourusername/discovery-node/issues)

We use GitHub issues to track public bugs. Report a bug by [opening a new issue](https://github.com/yourusername/discovery-node/issues/new); it's that easy!

## Write bug reports with detail, background, and sample code

**Great Bug Reports** tend to have:

- A quick summary and/or background
- Steps to reproduce
  - Be specific!
  - Give sample code if you can
- What you expected would happen
- What actually happens
- Notes (possibly including why you think this might be happening, or stuff you tried that didn't work)

## Development Setup

1. **Clone your fork**
   ```bash
   git clone https://github.com/yourusername/discovery-node.git
   cd discovery-node
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # Development dependencies
   ```

4. **Set up pre-commit hooks**
   ```bash
   pre-commit install
   ```

5. **Run tests**
   ```bash
   pytest
   ```

## Code Style

- We use [Black](https://github.com/psf/black) for Python code formatting
- We use [isort](https://github.com/PyCQA/isort) for import sorting
- We use [flake8](https://flake8.pycqa.org/) for linting
- Type hints are encouraged where appropriate
- Docstrings should follow Google style

Run formatting:
```bash
black .
isort .
flake8 .
```

## Testing

- Write tests for any new functionality
- Ensure all tests pass before submitting PR
- Aim for high test coverage
- Use pytest for testing

Run tests:
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_specific.py
```

## Commit Messages

- Use the present tense ("Add feature" not "Added feature")
- Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit the first line to 72 characters or less
- Reference issues and pull requests liberally after the first line

## Documentation

- Update documentation for any changed functionality
- Add docstrings to new functions and classes
- Update README.md if adding new features or changing setup

## License

By contributing, you agree that your contributions will be licensed under its MIT License.

## References

This document was adapted from the open-source contribution guidelines for [Facebook's Draft](https://github.com/facebook/draft-js/blob/master/CONTRIBUTING.md)