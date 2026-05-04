# Domain Pack: Finance / Payment Flow

Read this when testing payment, transaction, account, authentication, compliance, audit, settlement, refund, fraud detection, or banking features.

## Common State Dimensions

- transaction initiated
- payment pending
- payment authorized
- payment captured
- payment failed
- payment refunded
- payment partially_refunded
- settlement pending
- settlement completed
- settlement failed
- account active
- account suspended
- account closed
- account frozen
- authentication pending
- authentication succeeded
- authentication failed
- authentication expired
- session active
- session expired
- session revoked

## Common Rule Dimensions

- transaction amount limits (min, max, daily, monthly)
- currency support and conversion
- payment method availability (card, bank, wallet, crypto)
- authentication method requirements (password, OTP, biometric, 2FA)
- compliance checks (KYC, AML, sanctions, PII)
- retry and timeout policies
- duplicate transaction prevention
- partial vs full refund rules
- fee calculation and distribution
- fraud detection thresholds
- audit log requirements
- data retention policies
- regulatory reporting triggers
- cross-border transaction rules
- merchant vs consumer operation
- batch vs real-time processing

## Common Risk Hotspots

- payment state and settlement state diverge
- double capture or double refund
- partial refund exceeds original amount
- authentication bypass or session hijacking
- sensitive data exposure in logs or responses
- compliance check skipped or bypassed
- fraud detection false positive/negative imbalance
- timeout causes duplicate transaction
- currency conversion rounding errors
- fee calculation mismatch between systems
- audit log gaps during high-volume periods
- cross-border transaction without proper sanctions check
- batch processing failure leaves partial state
- account frozen but transactions still processed
- regulatory reporting deadline missed

## Suggested Observations

- Valid and invalid lifecycle transitions for payment, settlement, account, authentication.
- Decision table for payment_state x refund_state x amount x method.
- Idempotency for capture, refund, retry, and batch operations.
- Recovery from timeout, network loss, partial external failure.
- Authentication state and session consistency.
- Compliance check completeness and ordering.
- Fraud detection threshold boundary testing.
- Audit log completeness and traceability.
- Currency conversion and rounding edge cases.
- Cross-border transaction with sanctions and compliance.
- Evidence consistency across payment gateway, bank, ledger, audit, and compliance views.

## Test Data Strategies

| layer | use |
|---|---|
| `canonical_valid` | Standard successful payment within limits |
| `invalid_single_fault` | Amount over limit, invalid currency, expired card |
| `boundary3` | Min-1, min, min+1 / max-1, max, max+1 for amount limits |
| `rule_combo` | Currency + method + authentication + compliance combination |
| `state_seed` | Payment at each lifecycle state for transition testing |
| `history_seed` | Partially refunded, multiple refunds, refunded-then-captured |
| `compliance_seed` | KYC pending, AML flagged, sanctions hit, PII restricted |

## Compliance Testing Checklist

- KYC (Know Your Customer): identity verification completeness
- AML (Anti-Money Laundering): transaction monitoring thresholds
- Sanctions: blocked entity screening and rejection
- PII (Personal Identifiable Information): data handling and retention
- PCI-DSS: card data security requirements
- GDPR/Privacy: consent, data access, deletion rights
- Regulatory reporting: transaction volume, suspicious activity reports

## Fraud Detection Testing

- Threshold boundaries: amount, velocity, geographic anomaly
- False positive cases: legitimate high-value, frequent transactions
- False negative cases: structured transactions, gradual escalation
- Recovery paths: flagged transaction review, manual override
- Audit trail: fraud decision and override traceability