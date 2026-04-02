# Secure Biometric Attendance System

### A Hybrid Cloud-Edge IoT Framework with AES-256 Encryption and AI-Powered Analytics

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Security: AES-256](https://img.shields.io/badge/Encryption-AES--256--CBC-brightgreen.svg)](SECURITY.md)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)]()
[![Framework: Django 5](https://img.shields.io/badge/Framework-Django%205-092E20.svg)]()
[![Edge: Raspberry Pi](https://img.shields.io/badge/Edge-Raspberry%20Pi-C51A4A.svg)]()
[![Key Derivation: PBKDF2](https://img.shields.io/badge/KDF-PBKDF2%20600K-orange.svg)]()


## Table of Contents

- [Overview](#overview)
- [Problem Statement](#problem-statement)
- [Proposed Solution](#proposed-solution)
- [System Architecture](#system-architecture)
- [Security Framework (Zero-Trust)](#security-framework-zero-trust)
- [AI-Powered Analytics Engine](#ai-powered-analytics-engine)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Cloud Backend Setup](#1-cloud-backend-django-server)
  - [Edge Gateway Setup](#2-edge-gateway-raspberry-pi-client)
- [Testing and Simulations](#testing-and-simulations)
- [Environment Variables](#environment-variables)
- [Development Phases](#development-phases)
- [Future Work](#future-work)
- [Contributing](#contributing)
- [Security Policy](#security-policy)
- [License](#license)
- [References](#references)


## Overview

This project addresses critical security vulnerabilities in conventional biometric attendance systems by introducing a **Hybrid Cloud-Edge Architecture** powered by a Raspberry Pi secure gateway. The system ensures that sensitive biometric attendance data is encrypted at the edge, buffered locally during network outages, and synchronized securely to a Django cloud backend -- achieving **zero data loss** and **end-to-end confidentiality**.

The platform also integrates a local AI engine (Ollama / Llama 3.2) to perform automated attendance risk assessments, converting raw punch logs into actionable intelligence with risk scoring and automated stakeholder alerts via AWS SES.


## Problem Statement

Existing biometric attendance systems suffer from fundamental architectural weaknesses:

| Vulnerability | Description |
|---|---|
| **Unencrypted Transmission** | Attendance data is sent as plaintext JSON over HTTP, exposing it to interception and Man-in-the-Middle (MitM) attacks. |
| **No Device Authentication** | Any device on the network can impersonate a biometric machine and inject false records. |
| **Internet Dependency** | Direct-to-cloud models fail completely during network outages, resulting in permanent data loss. |
| **Replay Attacks** | Without nonce or timestamp validation, captured packets can be re-sent to duplicate attendance entries. |
| **Irreversible Breach Impact** | Biometric identifiers (fingerprints, facial data) cannot be changed once compromised, unlike passwords. |

These vulnerabilities make traditional systems unsafe for handling sensitive biometric data in production environments.


## Proposed Solution

This system introduces a **Local Secure Gateway** (Raspberry Pi) between the biometric device and the cloud server:

```
Biometric Device --> [LAN] --> Raspberry Pi Gateway --> [Encrypted/Internet] --> Django Cloud Server
                                    |                                                |
                              Local SQLite Buffer                           AI Analytics + Dashboard
                              AES-256 Encryption                           Decryption + Verification
                              Device Validation                            Alert Notifications (SES)
```

**Key innovations:**
- Data never leaves the local network unencrypted.
- Network outages cause zero data loss (local SQLite buffering).
- Every sync requires a fresh cryptographic handshake.
- AI engine performs automated attendance risk analysis.


## System Architecture

The system operates across three layers:

### Layer 1: Edge (Biometric Device)
Standard eSSL/ZKTeco biometric machines push raw attendance logs via the ADMS protocol over HTTP Port 80. Supported verification modes include fingerprint (mode 1), facial recognition (mode 15), and password fallback (mode 0).

### Layer 2: Gateway (Raspberry Pi)
The Python-based gateway intercepts HTTP traffic and performs:
1. **Device Validation** -- Verifies the biometric machine is registered and authorized.
2. **Local Buffering** -- Stores all punch records in a local SQLite database.
3. **AES-256-CBC Encryption** -- Encrypts the payload using a dynamically derived session key.
4. **Secure Sync** -- Transmits the encrypted payload to the Django server with nonce and timestamp.

### Layer 3: Cloud (Django Backend)
The Django REST API receives encrypted payloads and performs:
1. **Gateway Authentication** -- Validates MAC address and API key under a Zero-Trust model.
2. **Nonce Verification** -- Confirms the one-time nonce has not been used before.
3. **Timestamp Validation** -- Rejects requests outside a configurable time window (anti-replay).
4. **AES-256 Decryption** -- Derives the same session key and decrypts the payload.
5. **Deduplication** -- Prevents duplicate log entries using composite unique constraints.
6. **AI Analysis** -- Forwards validated records to the analytics engine for risk scoring.
7. **Automated Alerts** -- Triggers email notifications via AWS SES when risk thresholds are exceeded.

## Security Framework (Zero-Trust)

The system implements a multi-layered Zero-Trust security model where every request is verified before access is granted.

### Challenge-Response Handshake
A three-factor authentication mechanism validates devices before any data sync:

| Factor | Purpose |
|---|---|
| **MAC Address** | Unique network identifier of the gateway device |
| **Hardware Serial** | CPU serial number ensures physical device authenticity and prevents spoofing |
| **One-Time Nonce** | 64-character cryptographic token prevents replay attacks |

### Dynamic Key Derivation (PBKDF2)
Session encryption keys are never stored -- they are derived dynamically for each sync:

```
Session Key = PBKDF2-HMAC-SHA256(
    password = API_KEY (stripped of hyphens),
    salt     = One-Time Nonce,
    iterations = 600,000,
    key_length = 32 bytes
)
```

The 600,000-iteration count follows NIST recommendations for high-security key stretching, making brute-force attacks computationally infeasible.

### AES-256-CBC Encryption
All attendance data is encrypted at the gateway level before transmission:
- **Algorithm**: AES-256 in CBC (Cipher Block Chaining) mode
- **Key Length**: 256 bits (2^256 possible combinations)
- **IV**: Randomly generated 16-byte initialization vector per payload
- **Padding**: PKCS7 block padding

### Anti-Replay Protection
Each sync request includes:
- A **one-time nonce** that is invalidated after use
- A **server-verified timestamp** that must fall within a configurable window
- Composite unique constraints on (user_id, machine, timestamp) to prevent duplicate entries


## AI-Powered Analytics Engine

The system integrates with a local LLM (Ollama running Llama 3.2) to perform automated attendance analysis:

### Performance Scoring (0-100)
Each employee receives a weighted performance score:
- **Punctuality (40% weight)**: Percentage of check-ins before 09:05 AM
- **Consistency (60% weight)**: Attendance frequency over the last 30 working days

### Risk Classification
| Score Range | Risk Level | Action |
|---|---|---|
| 70-100 | LOW | No action required |
| 40-69 | MEDIUM | Monitoring advisory generated |
| 0-39 | HIGH | Automated alerts sent to parents/faculty via AWS SES |

### Graceful Fallback
If the Ollama service is offline, the system falls back to statistical heuristics without interrupting attendance processing.


## Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| **Backend Framework** | Django 5.x + Django REST Framework | REST API, admin dashboard, ORM |
| **Admin Interface** | django-unfold | Modern, responsive admin UI |
| **Task Queue** | Celery + Redis | Asynchronous log processing and scheduled alerts |
| **Scheduled Tasks** | django-celery-beat | Crontab-based daily safety checks |
| **Encryption** | PyCryptodome (AES-256-CBC) | Payload encryption/decryption |
| **Key Derivation** | hashlib (PBKDF2-HMAC-SHA256) | Dynamic session key generation |
| **Email Alerts** | AWS SES via django-ses | Automated absence notifications |
| **AI Analytics** | Ollama (Llama 3.2:1b) | Local LLM for risk assessment |
| **Edge Database** | SQLite | Offline buffering on Raspberry Pi |
| **Edge Hardware** | Raspberry Pi 4/5 | Local secure gateway |
| **Biometric Devices** | eSSL / ZKTeco (ADMS protocol) | Fingerprint, face, password verification |


## Project Structure

```
.
|-- attendance_dashboard/       # Core Django application
|   |-- models.py               # Data models (Gateway, Employee, Logs, Analytics)
|   |-- views.py                # Handshake and Sync API endpoints
|   |-- api_views.py            # Additional REST API views
|   |-- tasks.py                # Celery tasks (safety checks, scheduling)
|   |-- analytics_engine.py     # AI performance scoring (Ollama integration)
|   |-- admin.py                # Django Unfold admin configuration
|   |-- tests.py                # Unit tests (crypto, handshake, sync)
|   `-- templates/              # HTML templates (simulation report)
|
|-- backend/                    # Django project configuration
|   |-- settings.py             # Settings (env-based, no hardcoded secrets)
|   |-- celery.py               # Celery application setup
|   `-- urls.py                 # URL routing
|
|-- gateway_client/             # Raspberry Pi Edge Client
|   |-- main.py                 # Gateway entry point and ADMS listener
|   |-- sync_client.py          # Handshake, encryption, and cloud sync
|   |-- buffer_manager.py       # Local SQLite offline buffer
|   |-- biometric_gateway.service  # systemd service file for auto-start
|   `-- .env.example            # Gateway environment template
|
|-- tests_and_simulations/      # Testing and validation suite
|   |-- security_audit.py       # Replay attack and MFA failure tests
|   |-- run_simulation.py       # Network outage resilience simulation
|   |-- seed_demo_data.py       # Demo data generator (30 days + AI scores)
|   |-- test_sync_flow.py       # End-to-end sync flow test
|   `-- get_gateway_creds.py    # Gateway credential provisioning utility
|
|-- scripts/                    # Operational utilities
|-- .env.example                # Root environment template
|-- requirements.txt            # Python dependencies
|-- manage.py                   # Django management entry point
|-- LICENSE                     # MIT License
|-- CONTRIBUTING.md             # Contribution guidelines
|-- SECURITY.md                 # Security policy and vulnerability reporting
`-- CODE_OF_CONDUCT.md          # Contributor Covenant
```

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Redis server (for Celery task queue)
- Ollama with Llama 3.2 model (optional, for AI analytics)
- A Raspberry Pi 4/5 (for production edge deployment)

### 1. Cloud Backend (Django Server)

```bash
# Clone the repository
git clone https://github.com/your-username/secure-biometric-attendance.git
cd secure-biometric-attendance

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your SECRET_KEY, AWS credentials, and Redis URL

# Initialize the database
python manage.py migrate

# Create an admin superuser
python manage.py createsuperuser

# Start the development server
python manage.py runserver

# In separate terminals, start Celery workers:
celery -A backend worker -l info        # Log processing worker
celery -A backend beat -l info          # Scheduled task scheduler
```

Access the admin dashboard at `http://127.0.0.1:8000/admin/`.

### 2. Edge Gateway (Raspberry Pi Client)

```bash
cd gateway_client

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your DJANGO_SERVER_URL, GATEWAY_MAC, and GATEWAY_API_KEY

# Start the gateway
python main.py
```

**For production deployment on Raspberry Pi**, install as a systemd service for auto-start:

```bash
sudo cp biometric_gateway.service /etc/systemd/system/
sudo systemctl enable biometric_gateway
sudo systemctl start biometric_gateway
```

## Testing and Simulations

A comprehensive suite is provided in `tests_and_simulations/` to validate security, resilience, and correctness:

| Script | Purpose | Command |
|---|---|---|
| **Unit Tests** | Validates cryptographic handshake, key derivation, encryption/decryption, and API authentication | `python manage.py test` |
| **Security Audit** | Tests 6 attack scenarios: valid sync, missing nonce, invalid nonce, replay attack, expired timestamp, hardware attestation failure | `python tests_and_simulations/security_audit.py` |
| **Outage Simulation** | Simulates a 4-hour network outage to verify zero-data-loss buffering and automatic recovery sync | `python tests_and_simulations/run_simulation.py` |
| **Demo Data Seed** | Populates 30 days of attendance data for 5 employee profiles with AI-generated performance scores | `python tests_and_simulations/seed_demo_data.py` |
| **Sync Flow Test** | End-to-end test of the buffer-encrypt-sync pipeline | `python tests_and_simulations/test_sync_flow.py` |

## Environment Variables

All sensitive configuration is managed through environment variables. Copy `.env.example` to `.env` and configure:

### Cloud Backend (.env)

| Variable | Description | Default |
|---|---|---|
| `SECRET_KEY` | Django secret key | *(required)* |
| `DEBUG` | Debug mode toggle | `True` |
| `CELERY_BROKER_URL` | Redis broker URL for Celery | `redis://localhost:6379/0` |
| `PBKDF2_ITERATIONS` | Key derivation iteration count | `600000` |
| `AWS_ACCESS_KEY_ID` | AWS access key for SES | *(required for alerts)* |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key for SES | *(required for alerts)* |
| `AWS_SES_FROM_EMAIL` | Verified SES sender email | *(required for alerts)* |
| `OLLAMA_BASE_URL` | Ollama API endpoint | `http://localhost:11434` |
| `OLLAMA_MODEL` | LLM model for risk analysis | `llama3.2` |

### Edge Gateway (gateway_client/.env)

| Variable | Description | Default |
|---|---|---|
| `DJANGO_SERVER_URL` | Cloud backend sync endpoint | *(required)* |
| `GATEWAY_MAC` | MAC address of this gateway | *(required)* |
| `GATEWAY_API_KEY` | API key issued by the cloud backend | *(required)* |

## Development Phases

The project was developed using a structured phase-wise approach:

**Phase 1 -- Planning and Architecture**
Designed the system architecture (Biometric Device to Raspberry Pi to Django Dashboard), defined secure network flow and security boundaries, and analyzed biometric device communication protocols.

**Phase 2 -- Raspberry Pi Secure Gateway (Edge Layer)**
Developed the Python-based gateway system with local SQLite buffering, AES-256-CBC encryption, secure cloud synchronization, and systemd auto-start configuration.

**Phase 3 -- Django Server and Dashboard (Cloud Layer)**
Built the backend using Django 5 with a secure REST API, implemented server-side decryption and verification logic, and created a responsive admin dashboard using django-unfold with real-time monitoring and analytics.

**Phase 4 -- Testing and Security Validation**
Tested device-to-gateway communication, validated offline buffering during network failures, performed security testing against MitM and replay attacks, and conducted end-to-end system testing from biometric scan to dashboard output.


## Contributing

We welcome contributions. Please read our [Contributing Guidelines](CONTRIBUTING.md) before submitting a Pull Request.


## Security Policy

For vulnerability reports, please refer to our [Security Policy](SECURITY.md). Do not create public issues for security vulnerabilities.


## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.


## References

1. J. Galbally, J. Fierrez, and J. Ortega-Garcia, "On the Resilience of Biometric Authentication Systems against Random Inputs," *IEEE Transactions on Information Forensics and Security*, vol. 7, no. 3, pp. 1124-1136, 2012.
2. A. Alrawais, A. Alhothaily, C. Hu, and X. Cheng, "A Secure, Hybrid, Cloud-Enabled Architecture for Internet of Things," *IEEE Access*, vol. 5, pp. 258-273, 2017.
3. M. Abomhara and G. M. Koien, "Security and Privacy in the Internet of Things: Current Status and Open Issues," *PRISMS*, 2014.
4. A. K. Jain, K. Nandakumar, and A. Nagar, "Biometric Template Security," *EURASIP Journal on Advances in Signal Processing*, 2008.
5. NIST, "Recommendation for Block Cipher Modes of Operation," *NIST Special Publication 800-38A*, 2001.
6. S. Freeman et al., "Active Learning Increases Student Performance in Science, Engineering, and Mathematics," *PNAS*, vol. 111, no. 23, pp. 8410-8415, 2014.


*Developed as a Major Project focusing on IoT Security, Edge-Cloud Hybrid Systems, and AI-Powered Attendance Analytics.*
