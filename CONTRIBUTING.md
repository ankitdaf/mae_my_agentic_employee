# Contributing to MAE (My Agentic Employee)

Thank you for your interest in contributing to MAE! We welcome contributions from the community to help make this project even better.

## Getting Started

1.  **Fork the repository**: Click the "Fork" button at the top right of this page.
2.  **Clone your fork**:
    ```bash
    git clone https://github.com/your-username/mae-my-agentic-employee.git
    cd mae-my-agentic-employee
    ```
3.  **Set up the environment**:
    ```bash
    # Create a virtual environment (recommended)
    python3 -m venv venv
    source venv/bin/activate

    # Install dependencies
    pip install -r requirements.txt
    ```

## Development Workflow

1.  **Create a branch**: Always work on a new branch for your changes.
    ```bash
    git checkout -b feature/your-feature-name
    ```
2.  **Make your changes**: Write clean, readable code.
3.  **Run tests**: Ensure your changes don't break existing functionality.
    ```bash
    # Run all tests
    pytest
    ```
4.  **Lint your code**: We use `flake8` for linting.
    ```bash
    flake8 src/
    ```

## Reporting Issues

If you find a bug or have a feature request, please open an issue on GitHub. Provide as much detail as possible, including:
- Steps to reproduce the issue
- Expected behavior
- Actual behavior
- Logs or error messages

## Pull Requests

1.  Push your changes to your fork.
2.  Open a Pull Request (PR) against the `main` branch of the original repository.
3.  Describe your changes clearly in the PR description.
4.  Wait for review and address any feedback.

## Code Style

- Follow PEP 8 guidelines for Python code.
- Use meaningful variable and function names.
- Add docstrings to functions and classes.

## License

By contributing to this project, you agree that your contributions will be licensed under the MIT License.
