# KeeperAuthority 1.7.3 CNG recovery repair

KeeperAuthority 1.7.3 repairs the Windows security-descriptor binding used by
the elevated Provider Host Authority-identity provisioning step. The repair is
bounded to protocol 7 and schema 6; it does not change provider execution,
enrollment, registration, qualification, or pricing authority.

The lifecycle now:

- resolves `GetSecurityDescriptorLength` from `advapi32.dll` with an explicit
  Windows signature;
- opens only the Microsoft Software Key Storage Provider and the exact durable
  machine-key name;
- rejects an existing object unless its name, unique name, RSA algorithm,
  3072-bit length, non-exportable policy, and security-descriptor support agree;
- assigns the exact Administrators owner plus the protected DACL granting only
  SYSTEM, Administrators, and the KeeperAuthority service SID while denying the
  Restricted Code SID first;
- reads the owner and DACL back through CNG and compares their canonical SDDL
  before exposing the public identity or persisting its lifecycle record; and
- closes every opened handle and fails closed on unavailable APIs, inaccessible
  properties, ambiguous identity, policy mismatch, interruption, or read-back
  failure.

A finalized same-name key left by an interruption before ACL persistence is
reconciled without exporting, deleting, replacing, or recreating private key
material. The exact public identity is persisted only after the repaired policy
has been applied and verified. A later retry is idempotent and revalidates the
same durable identity and policy.

No service lifecycle or live CNG mutation is performed by the offline repair
and verification process. Installation remains a separately authorized,
exact-artifact recovery operation.
