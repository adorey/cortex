# OWASP — Application Security Best Practices

<!-- CAPABILITY REFERENCE
Fiche de best practices sécurité applicative basée sur l'OWASP Top 10.
À combiner avec un rôle (ex: roles/security-engineer.md) et une capacité langage/framework.
-->

> **Référence :** OWASP Top 10 (2021) | **Dernière mise à jour :** 2026-02
> **Docs officielles :** [owasp.org/Top10](https://owasp.org/www-project-top-ten/) | [Cheat Sheet Series](https://cheatsheetseries.owasp.org/)

---

## 🏛️ OWASP Top 10 (2021)

### A01 — Broken Access Control

Le contrôle d'accès cassé est la vulnérabilité #1. Un utilisateur peut accéder à des ressources qui ne lui appartiennent pas.

```
Prévention :
- Deny by default : tout est interdit sauf autorisation explicite
- Vérifier les permissions côté serveur à CHAQUE requête
- Ne jamais se fier au client pour le contrôle d'accès
- IDOR : valider que l'utilisateur a accès à la ressource demandée
- Rate limiting sur les endpoints sensibles
- Désactiver le directory listing du serveur web
- Logger les échecs d'accès et alerter sur les patterns suspects
```

### A02 — Cryptographic Failures

Données sensibles exposées par un chiffrement absent ou défaillant.

```
Prévention :
- Classifier les données (sensibles vs non-sensibles)
- HTTPS partout (HSTS, TLS 1.2+)
- Mots de passe : bcrypt ou argon2id (jamais MD5/SHA1/SHA256 seul)
- Chiffrement AES-256-GCM pour les données sensibles au repos
- Pas de secrets dans le code source ou les logs
- Rotation des clés de chiffrement
```

### A03 — Injection

SQL injection, NoSQL injection, OS command injection, LDAP injection...

```
Prévention :
- Prepared statements / requêtes paramétrées (OBLIGATOIRE)
- ORM avec query builder (jamais de concaténation)
- Validation et sanitization des entrées (whitelist)
- Échapper les sorties (context-aware : HTML, JS, SQL, URL)
- Principle of least privilege BDD (pas de DROP, pas de GRANT)
```

```php
// ✅ Prepared statement
$stmt = $pdo->prepare('SELECT * FROM user WHERE email = :email');
$stmt->execute(['email' => $userInput]);

// ❌ Concaténation (SQL injection)
$query = "SELECT * FROM user WHERE email = '" . $userInput . "'";
```

### A04 — Insecure Design

Faiblesses dans la conception même de l'application.

```
Prévention :
- Threat modeling en phase de design
- Security user stories / abuse cases
- Séparer les couches (présentation, métier, données)
- Limiter la consommation de ressources (rate limit, quotas)
- Tests de sécurité automatisés dans la CI
```

### A05 — Security Misconfiguration

Configurations par défaut, services inutiles, headers manquants.

```
Prévention :
- Supprimer les configurations et comptes par défaut
- Headers de sécurité HTTP :
  Content-Security-Policy
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Strict-Transport-Security
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy
- Désactiver les features et services non utilisés
- Revue de configuration automatisée (CIS Benchmarks)
- Pas de stack traces / debug en production
```

### A06 — Vulnerable and Outdated Components

Composants tiers (bibliothèques, frameworks) avec des CVE connues.

```
Prévention :
- Audit régulier des dépendances (composer audit, npm audit, pip audit)
- Automatiser avec Dependabot / Renovate / Snyk
- Surveiller les CVE (NVD, GitHub Security Advisories)
- Supprimer les dépendances non utilisées
- Politique de mise à jour : patch dans la semaine, minor dans le mois
```

### A07 — Identification and Authentication Failures

Authentification cassée, session mal gérée.

```
Prévention :
- MFA pour les comptes à privilèges
- Pas de credentials par défaut
- Rate limiting + lockout sur les tentatives de login
- Sessions : expiration, rotation d'ID après login, invalidation au logout
- Mots de passe : longueur > complexité (min 12 chars, pas de règles absurdes)
- JWT : vérifier signature + expiration + issuer + audience
```

### A08 — Software and Data Integrity Failures

Pipelines CI/CD compromis, mises à jour non vérifiées.

```
Prévention :
- Vérifier les signatures et checksums des dépendances
- CI/CD sécurisée (accès restreint aux pipelines, secrets protégés)
- Signed commits (GPG)
- Review obligatoire avant merge
- SBOM (Software Bill of Materials)
```

### A09 — Security Logging and Monitoring Failures

Pas de logs, pas de monitoring, pas de détection.

```
Prévention :
- Logger tous les événements d'authentification (succès + échecs)
- Logger tous les échecs de contrôle d'accès
- Format structuré (JSON) avec contexte (user, IP, action, timestamp)
- NE JAMAIS logger : mots de passe, tokens, données personnelles
- Centraliser les logs (ELK, Loki, Datadog)
- Alertes sur les patterns suspects (brute force, mass enumeration)
- Plan de réponse aux incidents
```

### A10 — Server-Side Request Forgery (SSRF)

L'application fetch une URL fournie par l'utilisateur sans validation.

```
Prévention :
- Valider et sanitizer les URLs fournies par l'utilisateur
- Whitelist des domaines/IPs autorisés
- Bloquer les requêtes vers les réseaux internes (169.254.x.x, 10.x.x.x, etc.)
- Pas de redirection ouverte
- Segmentation réseau
```

---

## 🔧 Intégration dans la CI

```yaml
# Exemple : pipeline de sécurité
security:
  stages:
    - name: SAST
      tool: semgrep / phpstan-security / eslint-security
      quand: À chaque commit

    - name: Dependency Check
      tool: composer audit / npm audit / trivy
      quand: À chaque commit

    - name: DAST
      tool: OWASP ZAP / Nuclei
      quand: Sur staging, avant chaque release

    - name: Secret Detection
      tool: gitleaks / trufflehog
      quand: Pre-commit hook + CI
```

---

## ✅ Checklist rapide

```
- [ ] Prepared statements partout (zéro concaténation SQL)
- [ ] HTTPS + HSTS (pas de HTTP)
- [ ] Headers de sécurité configurés
- [ ] Authentification robuste (rate limit, MFA, session management)
- [ ] Autorisation vérifiée côté serveur à chaque requête
- [ ] Mots de passe hashés (bcrypt/argon2id)
- [ ] Secrets hors du code (env vars, vault)
- [ ] Dépendances auditées et à jour
- [ ] Logging structuré (sans données sensibles)
- [ ] SAST + Dependency check dans la CI
- [ ] Pas de debug/stack traces en production
```
