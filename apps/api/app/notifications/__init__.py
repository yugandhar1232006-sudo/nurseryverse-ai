"""
Phase 6 Module 11 -- Notifications & Communication.

Enterprise-grade communication services for NurseryVerse AI, built
event-driven: no business module ever sends a notification directly (the
two narrow, disclosed exceptions -- password-reset/email-verification
token emails -- are documented on `EmailSender`/`AuthService` and never
route through this package). Business services publish domain events
(`app/domain_events`); `NotificationEventHandler` (notification_handler.py)
is the single subscriber that decides whether to notify, who to notify,
which channel(s), and how retries/dead-lettering work.

Package layout:
  - `providers.py` -- Protocol-based Email/SMS/Push provider interfaces,
    each with a real (not mock) default implementation.
  - `templates.py` -- versioned, multi-channel/format template rendering
    (Jinja2), org-override-over-global-default resolution.
  - `hub.py` -- in-process WebSocket connection manager (live delivery +
    unread-count push), mirroring the `InMemoryCache`/`InMemoryRateLimiter`
    in-memory-first, disclosed-Redis-upgrade-path pattern from Module 3.
  - `notification_handler.py` -- `NotificationEventHandler`, the
    `EventDispatcher`-registered subscriber that is the *only* code path
    that ever creates a `Notification` row.

See docs/architecture/27-module11-notifications.md for the full design.
"""
