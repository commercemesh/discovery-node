# Security Policy

## Supported Versions

We release patches for security vulnerabilities. Which versions are eligible for receiving such patches depends on the CVSS v3.0 Rating:

| Version | Supported          |
| ------- | ------------------ |
| latest  | :white_check_mark: |

## Reporting a Vulnerability

Please report (suspected) security vulnerabilities to **[INSERT SECURITY EMAIL]**. You will receive a response from us within 48 hours. If the issue is confirmed, we will release a patch as soon as possible depending on complexity but historically within a few days.

Please include the following information in your report:

- Type of issue (e.g. buffer overflow, SQL injection, cross-site scripting, etc.)
- Full paths of source file(s) related to the manifestation of the issue
- The location of the affected source code (tag/branch/commit or direct URL)
- Any special configuration required to reproduce the issue
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit the issue

## Preferred Languages

We prefer all communications to be in English.

## Security Best Practices for Users

### API Keys and Credentials

1. **Never commit API keys or credentials to the repository**
   - Use environment variables for all sensitive configuration
   - Reference `.env.sample` for required environment variables

2. **Rotate credentials regularly**
   - Change API keys and passwords periodically
   - Update credentials immediately if exposed

3. **Use secure credential storage**
   - Use a secrets management system in production
   - Never store credentials in plain text

### Database Security

1. **Use strong passwords** for database accounts
2. **Limit database user permissions** to only what's necessary
3. **Enable SSL/TLS** for database connections in production
4. **Regular backups** and test restore procedures

### Network Security

1. **Use HTTPS** for all API endpoints in production
2. **Configure CORS** appropriately for your use case
3. **Implement rate limiting** to prevent abuse
4. **Use a firewall** to restrict access to services

### Dependency Management

1. **Keep dependencies updated**
   ```bash
   pip list --outdated
   pip install --upgrade [package]
   ```

2. **Audit dependencies for vulnerabilities**
   ```bash
   pip install safety
   safety check
   ```

3. **Use exact version pinning** in production

## Security Features

Discovery Node includes several security features:

- Environment-based configuration (no hardcoded secrets)
- SQL injection protection via SQLAlchemy ORM
- Input validation using Pydantic schemas
- CORS configuration for API endpoints
- Authentication ready (implement as needed)

## Disclosure Policy

When we receive a security report, our team will:

1. Confirm the problem and determine affected versions
2. Audit code to find similar problems
3. Prepare fixes for all supported releases
4. Release new security fix versions

## Comments on this Policy

If you have suggestions on how this process could be improved please submit a pull request.