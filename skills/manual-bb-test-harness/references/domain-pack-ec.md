# Domain Pack: EC / Order Flow

Read this when testing e-commerce, order, payment, shipment, inventory, coupon, return, refund, or cancellation features.

## Common State Dimensions

- cart
- order pending
- payment authorized
- payment failed
- paid
- allocated
- shipped
- delivered
- cancelled
- returned
- refunded

## Common Rule Dimensions

- stock availability
- payment status
- shipment status
- coupon use and restoration
- point use and restoration
- partial cancellation
- duplicate operation
- timeout or external service failure
- buyer vs support operation

## Common Risk Hotspots

- order state and payment state diverge
- inventory is restored twice or not restored
- coupon or points are restored incorrectly
- shipped or delivered order can be cancelled
- refund is issued without matching cancellation
- duplicate submit creates multiple side effects
- external payment or inventory service returns delayed/partial failure

## Suggested Observations

- Valid and invalid lifecycle transitions.
- Decision table for order_state x payment_status x shipment_status x coupon_used.
- Idempotency for cancel, refund, and retry.
- Recovery from network loss or service timeout.
- Evidence consistency across UI, email, inventory, coupon, and audit/log views.
