# Contributing to Secure Biometric Attendance System

First off, thank you for considering contributing to the Secure Biometric Attendance System! It's people like you that make the open-source community such a great place to learn, inspire, and create.

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## How Can I Contribute?

### Reporting Bugs
* **Check the Issue Tracker**: Before creating a new issue, please check if the bug has already been reported.
* **Be Specific**: Include details about your environment (OS, Python version), steps to reproduce, and expected vs. actual behavior.

### Suggesting Enhancements
* **Explain the Value**: Why is this feature necessary? Who would benefit from it?
* **Draft a Plan**: If possible, suggest an implementation approach.

### Pull Requests
1. **Fork the repo** and create your branch from `main`.
2. **If you've added code**, add tests that cover your changes.
3. **Ensure the test suite passes** by running `python manage.py test`.
4. **Follow PEP 8** for Python code style.
5. **Update documentation** (like README.md) if you're changing the API or setup process.
6. **Detailed commit messages** are appreciated!

## Development Setup

1. Clone your fork: `git clone https://github.com/your-username/secure-biometric-attendance-system.git`
2. Create a virtual environment: `python -m venv venv`
3. Activate it:
   - macOS/Linux: `source venv/bin/activate`
   - Windows: `venv\Scripts\activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Set up your `.env`: `cp .env.example .env`
6. Run migrations: `python manage.py migrate`
7. Start the dev server: `python manage.py runserver`

## Style Guide
- **Python**: Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/).
- **Commits**: Use imperative mood (e.g., "Add encryption" instead of "Added encryption").

Thank you for your contributions!
