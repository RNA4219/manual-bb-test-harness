---
feature_id: ORD-CANCEL-02
title: Order Cancellation with Partial Refund
summary: Allow users to cancel orders and receive partial refunds when coupons were applied.
actors: buyer, system, payment_gateway
---

## Summary

This feature enables order cancellation with automatic partial refund calculation
when coupons or discounts were applied to the original order.

## Acceptance Criteria

- AC-1: User can cancel order within 30 minutes of placement
- AC-2: System calculates refund amount minus coupon value
- AC-3: Refund is processed within 24 hours
- AC-4: User receives confirmation email with refund details

## Business Rules

- BR-1: Cancellation not allowed after order is shipped
- BR-2: Coupon value is not refunded (absorbed by platform)
- BR-3: Minimum refund amount is 0 (no negative refunds)

## Actors

- Buyer initiates cancellation
- System validates and processes
- Payment Gateway handles refund

## Devices

- Web
- Mobile App
- API

## Changed Areas

- order_service
- payment_service
- notification_service
- refund_calculator