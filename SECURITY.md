# Security Policy

## Reporting a Vulnerability

If you find a security vulnerability, please **DO NOT** create a public issue. Instead, please report it privately:

- **Email**: [vemalivardhan@gmail.com](mailto:vemlivardhan@gmail.com)
- **GitHub Security Advisory**: You can also use the "Report a vulnerability" button on our GitHub repository.

We aim to respond to all reports within 48 hours.

## Security Features

This project implements professional-grade security:
- **AES-256-CBC Encryption**: All biometric logs are encrypted at the Edge before sync.
- **NIST PBKDF2 Key Derivation**: Session keys are derived using 600,000 iterations for defense against brute force.
- **Anti-Replay Protection**: Each sync event uses a one-time nonce and timestamp verification.
- **Hardware Attestation**: Gateways must prove their identity using MAC Address and CPU Serial.

## Best Practices

- **Never** commit your `.env` file. A `.env.example` is provided for reference.
- **Rotate** your `GATEWAY_API_KEY` regularly.
- **Use HTTPS** in production environments.