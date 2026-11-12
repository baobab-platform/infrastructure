# N02 private profile custody audit — 12 November 2026

Infrastructure #69 at `4417e24adefce0e214281830f5093c56fea8b0fb` and #72
share the same N02 first-party profile sealing implementation. This audit
found a second filesystem read after profile validation: the origin and source
checks used one private inode, but its persisted digest could describe replaced
bytes. Sealing now uses the existing bounded, owner-only, no-symlink original
reader and hashes exactly the bytes parsed for validation. Later profile
replacement therefore disagrees with the sealed digest instead of inheriting
the earlier origin validation. A regression replaces the file during origin
validation and verifies that its replacement is not the sealed original.

Kratos redirect query validation now preserves blank values and rejects extra
empty keys, duplicate empty flow values and bare query fields. Malformed URLs
produce the fixed refusal code. Legitimate same-origin login/recovery redirects
remain passing. These unit tests do not qualify a live browser or provider.

Validation: the full #72 development suite passes 254 tests; the #69 suite passes 159 tests. Both PRs retain
original same-run browser, live IAM/CP/native-owner, independent evidence
custody and teardown requirements. These source corrections do not close
N02/N07 acceptance or authorize protected execution.
