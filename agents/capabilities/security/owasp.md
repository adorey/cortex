# OWASP — Application Security Best Practices

<!-- CAPABILITY REFERENCE
Application security best practices card based on the OWASP Top 10.
To combine with a role (e.g. roles/security-compliance/security-engineer.md) and a language/framework capability.
-->

> **Reference:** OWASP Top 10 (2021) | **Last updated:** 2026-02
> **Official docs:** [owasp.org/Top10](https://owasp.org/www-project-top-ten/) | [Cheat Sheet Series](https://cheatsheetseries.owasp.org/)

---

## 🏛️ OWASP Top 10 (2021)

### A01 — Broken Access Control

Broken access control is the #1 vulnerability. A user can access resources that do not belong to them.

```
Prevention:
- Deny by default: everything is forbidden unless explicitly authorised
- Check permissions server-side on EVERY request
- Never trust the client for access control
- IDOR: validate that the user has access to the requested resource
- Rate limiting on sensitive endpoints
- Disable web server directory listing
- Log access failures and alert on suspicious patterns
```

### A02 — Cryptographic Failures

Sensitive data exposed by absent or defective encryption.

```
Prevention:
- Classify data (sensitive vs non-sensitive)
- HTTPS everywhere (HSTS, TLS 1.2+)
- Passwords: bcrypt or argon2id (never MD5/SHA1/SHA256 alone)
- AES-256-GCM encryption for sensitive data at rest
- No secrets in source code or logs
- Rotate encryption keys
```

### A03 — Injection

SQL injection, NoSQL injection, OS command injection, LDAP injection...

```
Prevention:
- Prepared statements / parameterised queries (MANDATORY)
- ORM with query builder (never concatenation)
- Input validation and sanitisation (whitelist)
- Escape outputs (context-aware: HTML, JS, SQL, URL)
- Principle of least privilege for the DB (no DROP, no GRANT)
```

```php
// ✅ Prepared statement
$stmt = $pdo->prepare('SELECT * FROM user WHERE email = :email');
$stmt->execute(['email' => $userInput]);

// ❌ Concatenation (SQL injection)
$query = "SELECT * FROM user WHERE email = '" . $userInput . "'";
```

### A04 — Insecure Design

Weaknesses in the application's own design.

```
Prevention:
- Threat modelling during the design phase
- Security user stories / abuse cases
- Separate layers (presentation, business, data)
- Limit resource consumption (rate limiting, quotas)
- Automated security tests in CI
```

### A05 — Security Misconfiguration

Default configurations, unnecessary services, missing headers.

```
Prevention:
- Remove default configurations and accounts
- HTTP security headers:
  Content-Security-Policy
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Strict-Transport-Security
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy
- Disable unused features and services
- Automated configuration review (CIS Benchmarks)
- No stack traces / debug in production
```

### A06 — Vulnerable and Outdated Components

Third-party components (libraries, frameworks) with known CVEs.

```
Prevention:
- Regular dependency audits (composer audit, npm audit, pip audit)
- Automate with Dependabot / Renovate / Snyk
- Monitor CVEs (NVD, GitHub Security Advisories)
- Remove unused dependencies
- Update policy: patches within the week, minors within the month
```

### A07 — Identification and Authentication Failures

Broken authentication, poorly managed sessions.

```
Prevention:
- MFA for privileged accounts
- No default credentials
- Rate limiting + lockout on login attempts
- Sessions: expiration, ID rotation after login, invalidation on logout
- Passwords: length > complexity (min 12 chars, no absurd rules)
- JWT: verify signature + expiration + issuer + audience
```

### A08 — Software and Data Integrity Failures

Compromised CI/CD pipelines, unverified updates.

```
Prevention:
- Verify dependency signatures and checksums
- Secure CI/CD (restricted access to pipelines, protected secrets)
- Signed commits (GPG)
- Mandatory review before merge
- SBOM (Software Bill of Materials)
```

### A09 — Security Logging and Monitoring Failures

No logs, no monitoring, no detection.

```
Prevention:
- Log all authentication events (successes + failures)
- Log all access control failures
- Structured format (JSON) with context (user, IP, action, timestamp)
- NEVER log: passwords, tokens, personal data
- Centralise logs (ELK, Loki, Datadog)
- Alerts on suspicious patterns (brute force, mass enumeration)
- Incident response plan
```

### A10 — Server-Side Request Forgery (SSRF)

The application fetches a URL provided by the user without validation.

```
Prevention:
- Validate and sanitise user-provided URLs
- Whitelist authorised domains/IPs
- Block requests to internal networks (169.254.x.x, 10.x.x.x, etc.)
- No open redirects
- Network segmentation
```

---

## 🔧 CI integration

```yaml
# Example: security pipeline
security:
  stages:
    - name: SAST
      tool: semgrep / phpstan-security / eslint-security
      when: On every commit

    - name: Dependency Check
      tool: composer audit / npm audit / trivy
      when: On every commit

    - name: DAST
      tool: OWASP ZAP / Nuclei
      when: On staging, before each release

    - name: Secret Detection
      tool: gitleaks / trufflehog
      when: Pre-commit hook + CI
```

---

## ✅ Quick checklist

```
- [ ] Prepared statements everywhere (zero SQL concatenation)
- [ ] HTTPS + HSTS (no HTTP)
- [ ] Security headers configured
- [ ] Robust authentication (rate limit, MFA, session management)
- [ ] Authorisation verified server-side on every request
- [ ] Passwords hashed (bcrypt/argon2id)
- [ ] Secrets outside the code (env vars, vault)
- [ ] Dependencies audited and up to date
- [ ] Structured logging (without sensitive data)
- [ ] SAST + Dependency check in CI
- [ ] No debug/stack traces in production
```
