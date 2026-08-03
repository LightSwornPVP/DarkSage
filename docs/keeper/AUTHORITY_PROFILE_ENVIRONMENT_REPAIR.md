# KeeperAuthority 1.7.5 authenticated profile-environment repair

KeeperAuthority 1.7.5 repairs the production Windows profile-environment lookup
used by Provider Host enrollment and Codex registration. Protocol 7 and schema 6
are unchanged.

The service already retains two authenticated handles for one named-pipe peer:
the exact pipe-client impersonation token and a separately retained client
process token. Windows documents that `CreateEnvironmentBlock` accepts an
impersonation token with `TOKEN_QUERY`, while a primary token additionally
requires `TOKEN_DUPLICATE`. The earlier implementation converted the retained
process token to a primary token for this read-only lookup. That path returned
`ERROR_ACCESS_DENIED` in the production LocalSystem service even though the
same-user test process succeeded.

The corrected path passes the exact authenticated pipe-client impersonation
token directly to `CreateEnvironmentBlock`. It first verifies Security
Impersonation level, does not impersonate the service thread, does not widen the
token handle, and keeps the process-token primary duplicate solely for deriving
the restricted provider execution token. SID, process, session, profile,
Authority identity, executable, Host, and active-session validations remain
unchanged and fail closed.

Provider Host 1.7.5 remains exact-version locked to KeeperAuthority 1.7.5,
protocol 7, and schema 6. Installing or updating the per-user Host does not
modify KeeperAuthority. Updating the Windows service remains a separate
Founder-authorized lifecycle operation.

An enrollment proposal is package-hash bound. Proposal creation now rejects an
unresolved local checkpoint instead of overwriting it. When an older Host
package has a Founder-authorized `PROPOSED` checkpoint but Authority's supported
status proves that no enrollment record exists, the 1.7.5 client first archives
the complete checkpoint as a durable `SUPERSEDED` record. The archive binds the
old proposal/checkpoint digest, Host/package identity, exact Authority status,
and replacement package manifest. It is written and read back before the active
checkpoint name is removed; interruption is idempotently recoverable. Pending,
proved, active, uncertain, same-package, mismatched, or ambiguous Authority
states remain blocked.

If the process stops after persisting a proposal but before Founder
authentication returns, the exact current-package checkpoint contains no
Founder capability, grant, or proof. Authority must again prove that no
enrollment exists before Keeper durably archives that inert checkpoint as an
interrupted unauthorized proposal and retries. Founder-authorized proposals
remain subject to the stricter package-change rule.

All supported enrollment, resume, reconciliation, and revocation flows hold one
crash-releasing operating-system checkpoint lock across both their local state
transitions and Authority calls. Supersession also reloads and digest-compares
the exact `PROPOSED` generation immediately before deletion. A concurrent
transition to Founder-authorized, `PROVED`, or `COMMITTED` state therefore
cannot be deleted by an older supersession snapshot.
