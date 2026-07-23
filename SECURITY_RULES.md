# DarkSage Security Rules

## Purpose

These rules apply to the desktop application, mobile application, backend services, market-data integrations, broker integrations, AI systems, databases, deployment, development agents, and future live trading.

Security-sensitive behavior must fail closed whenever system state is uncertain.

## Secrets

Never commit:

- API keys
- Broker credentials
- Access tokens
- Refresh tokens
- Passwords
- Private keys
- Database passwords
- Cloud credentials
- Signing secrets

Secrets must never appear in source code, Git history, README files, issues, test fixtures, screenshots, or logs.

During development use:

- Environment variables
- `.env` files excluded by `.gitignore`
- OS credential storage where appropriate

Production should use secure secret storage.

## Environment Separation

Maintain separate environments for:

- Development
- Testing
- Paper trading
- Production/live trading

Paper and live credentials must always be separate.

## Least Privilege

Broker access should permit only what is necessary.

DarkSage must never require:

- Withdrawal permission
- External money transfers
- Account ownership changes

## Live Trading

Live trading is disabled by default.

Enabling live trading requires:

- Explicit user action
- Valid live credentials
- Security checks
- Risk configuration
- Broker connection verification
- Audit logging
- Strong authentication

No AI agent or background process may enable live trading automatically.

## Strong Authentication

High-risk actions should require strong authentication.

Examples:

- Enabling live trading
- Changing live broker credentials
- Increasing major risk limits
- Emergency Flatten
- Re-enabling trading after security events

## Backend Enforcement

Security decisions must be enforced on the backend.

UI controls alone are never sufficient security controls.

## Secure Communication

Production remote communication must use encrypted transport:

- HTTPS
- TLS
- Secure WebSockets where used

Localhost HTTP is acceptable for local development.

## Authentication and Authorization

All non-public backend endpoints must require authentication.

Authorization must be enforced separately from authentication.

Possible permission groups:

- Read-only
- Trade approval
- Auto-Trader control
- Administrative settings
- Live-trading management

## Session Management

Sessions should support:

- Expiration
- Logout
- Revocation
- Secure refresh
- Device/session visibility

## Input Validation

All external input must be validated.

Sources include:

- User input
- Market-data APIs
- Broker APIs
- AI output
- Imported files
- Strategy definitions
- Mobile clients
- Desktop clients

## AI Output Is Untrusted Input

AI output must never directly:

- Execute shell commands
- Modify security settings
- Submit broker orders
- Change live credentials
- Override risk controls

Structured output produced by AI must be validated.

## Common Application Security

Use parameterized database queries and safe frontend rendering.

Protect against:

- SQL injection
- Command injection
- Cross-site scripting
- CSRF where applicable
- Unsafe deserialization
- Unvalidated external data

## Dependency Security

Dependencies must be:

- Necessary
- Maintained where possible
- Version controlled
- Reviewed before adoption

Avoid unnecessary dependencies and uncontrolled automatic upgrades in critical areas.

## Automated Tooling Security

Agents must follow:

- PROJECT_SPEC.md
- ARCHITECTURE.md
- ROADMAP.md
- AGENTS.md
- SECURITY_RULES.md
- TRADING_RULES.md

Agents must not:

- Commit secrets
- Disable security checks
- Enable live trading without explicit approval
- Expose services publicly by default
- Install unnecessary dependencies
- Make destructive system changes without approval

## Independent Review

No single AI agent should both implement and solely approve critical live-trading safety code.

Independent review is required for:

- Risk engine
- Broker execution
- Kill switch
- Duplicate-order protection
- Broker reconciliation
- Authentication
- Authorization
- Secret handling

## Logging

Logs must never contain full secrets.

Sensitive values should be redacted.

Security-sensitive actions should be audited, including:

- Login
- Failed login
- Credential change
- Live-trading enable
- Auto-Trader enable/disable
- Risk-limit changes
- Emergency Stop
- Emergency Flatten
- Trade override
- Permission changes

## Database and Backups

Databases must not be publicly exposed.

Production databases should use:

- Authentication
- Restricted network access
- Least-privilege accounts
- Encryption where appropriate
- Regular backups

Critical data should have secure backups and recovery procedures.

## Broker Safety

Before live orders are allowed, verify:

- Correct broker environment
- Correct account
- Correct execution mode
- Valid credentials
- Expected account identifier

The system must protect against accidentally connecting live code to the wrong account.

## Order Authorization

Every order must have an internal authorization trail.

Required checks:

- Authenticated user/system action
- Allowed strategy
- Allowed instrument
- Risk approval
- Permissions approval
- Execution approval

No direct client-to-broker bypass.

## Emergency Controls

Emergency Stop should be easy for authorized users to trigger.

Emergency Flatten is more dangerous and requires stronger authentication and explicit confirmation in live mode.

## Fail Closed

When critical uncertainty exists, block new trades.

Examples:

- Authentication unavailable
- Market data stale
- Broker mismatch
- Risk engine failure
- Database inconsistency
- Permissions engine unavailable

Do not guess.

## Broker Reconciliation

Compare internal and broker state regularly:

- Cash
- Buying power
- Positions
- Open orders
- Filled orders
- Average entry price

If reconciliation fails:

- Pause new trading
- Alert the user
- Record an audit event

## Network Exposure

Local development services must not be publicly exposed by default.

Do not automatically:

- Open router ports
- Create public tunnels
- Disable firewalls
- Bind sensitive services to all interfaces

## Desktop and Mobile Security

Desktop and mobile clients should avoid storing broker secrets directly.

Use secure platform storage where sensitive local data is required.

For iOS, use Keychain.

## AI Privacy and Provider Credentials

Local and cloud AI should not receive credentials or unnecessary sensitive account data.

Cloud AI must remain optional. The application must function fully with zero cloud AI provider configured.

DarkSage supports multiple user-configurable AI providers (initially: local, OpenAI, Anthropic, Google Gemini, and custom OpenAI-compatible endpoints) behind a common interface. Provider API keys must be treated as credentials:

- Never committed to source control
- Never logged, including in debug/verbose logs
- Never exposed in frontend/client source or bundled JavaScript
- Never sent to any provider other than the one the user configured for that key
- Not stored as plaintext where an OS/application secure credential store is available
- Production credentials must use OS credential storage (e.g. Windows Credential Manager, macOS Keychain) or an encrypted secrets vault
- Development may use `.env` files excluded by `.gitignore`

A future Settings > AI Providers UI must support adding, testing, editing, disabling, and removing provider credentials, and must never redisplay a stored key in full once saved.

No AI provider, local or cloud, may communicate directly with a broker or bypass the canonical TradeValidationPipeline (full definition: ARCHITECTURE.md §14). No provider may directly access or call the Execution Engine or Broker Adapter. This applies identically regardless of vendor.

## Security Testing

Security testing should include:

- Authentication tests
- Authorization tests
- Secret scanning
- Dependency scanning
- Input validation tests
- API abuse tests
- Rate-limit tests
- Broker safety tests
- Fault injection

Test failures such as:

- Broker disconnect
- Data provider disconnect
- Database failure
- Network timeout
- Duplicate requests
- Partial broker responses
- Backend restart
- Mobile disconnect
- Desktop crash

## Git Security

`.gitignore` must exclude at minimum:

- `.env`
- `.env.*`
- Secret files
- Credentials
- Local databases where appropriate
- Build artifacts
- Dependency directories
- Private keys

## Security Review Before Live Trading

A dedicated security review must occur before live trading.

Review:

- Authentication
- Authorization
- Secrets
- Broker credentials
- Broker permissions
- Risk engine
- Execution engine
- Emergency controls
- Reconciliation
- Logging
- Deployment
- Mobile controls
- Network exposure

## Core Security Rule

When convenience conflicts with protection of user money, credentials, trading authority, or account access, security takes priority.

When uncertain: fail closed.
