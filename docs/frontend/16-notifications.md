# 7K -- Notifications

## Route Structure

No dedicated route. Notifications surface in two places:

- **NotificationCenter** -- a `Sheet` overlay triggered by the bell icon in the application header.
  Badge shows unread count. Opens a slide-over panel listing notifications with mark-read / mark-all-read
  actions. This is the primary interaction surface.
- **NotificationPreferencesPanel** -- lives under Settings > Notifications tab. A 22-category x 4-channel
  checkbox grid with quiet-hours and frequency controls.

## Components

```
components/notifications/
  notification-center.tsx              Bell trigger button + Sheet slide-over. Owns the single
                                       WebSocket connection for this user. Displays badge count,
                                       notification list, mark-all-read action.
  notification-row.tsx                 Individual notification: icon by category, message, timestamp,
                                       read/unread state. Click marks as read.
  notification-preferences-panel.tsx   22-category checkbox grid (rows) x 4 channel columns
                                       (in_app, email, sms, push). Quiet hours time range input.
                                       Frequency selector (instant, hourly_digest, daily_digest).
                                       Save button wired to PUT /notifications/preferences.

lib/notifications/queries.ts           notificationKeys factory + useNotificationsQuery /
                                      useUnreadCountQuery / useNotificationPreferencesQuery
lib/notifications/mutations.ts        markNotificationRead, markAllRead, updatePreferences
```

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | /notifications | Paginated notification list for current user |
| GET | /notifications/unread-count | Badge count integer |
| PATCH | /notifications/{id}/read | Mark single notification as read |
| POST | /notifications/mark-all-read | Mark all as read (returns 204) |
| GET | /notifications/preferences | Current user's preference grid |
| PUT | /notifications/preferences | Update full preference grid |
| WS | /notifications/ws?token={accessToken} | Real-time push of new notifications |

## Query Keys & Mutations

Query key factory (`notificationKeys`):

- `notificationKeys.list` -- paginated notification list
- `notificationKeys.unreadCount` -- badge count, with a 60-second `refetchInterval` as a safety net
  on top of the WebSocket (ensures the badge stays accurate even if the WS drops briefly)
- `notificationKeys.preferences` -- the 22 x 4 preference grid

Mutations:

- **markNotificationRead** -- optimistic update on the list query (flips `is_read` locally), then
  invalidates `unreadCount`. Rollback on error restores the previous state.
- **markAllRead** -- optimistic update sets all visible notifications to read, decrements `unreadCount`
  to 0. Invalidates `notificationKeys.all` on success.
- **updatePreferences** -- standard mutation with `onSuccess` invalidation of `notificationKeys.preferences`.

All three mutations use optimistic store updates with query invalidation on success, matching the
project-wide pattern established in 7E.

## Validation

`notificationPreferencesSchema` (Zod):

- Quiet hours: regex-validated time strings (`HH:MM` format)
- Frequency: enum of `instant`, `hourly_digest`, `daily_digest`
- Channel toggles: per-category boolean flags (no custom validation beyond the schema shape)

## Permission Gates

- **Preferences panel**: `notifications:manage_preferences` -- controls visibility of the entire
  NotificationPreferencesPanel inside Settings. Without this permission, the Notifications tab does
  not render.
- **NotificationCenter** (bell icon): no permission gate -- every authenticated user sees the bell
  and receives notifications. The bell is part of the application shell, not gated.

## WebSocket

Single connection managed inside `NotificationCenter`:

- **Auth**: `?token={accessToken}` query parameter on the WS URL. No separate WS auth handshake.
- **Reconnection**: exponential backoff on disconnect. Does not re-register handlers on reconnect
  -- the component lifecycle manages connection teardown and setup.
- **Data flow**: the Zustand notification store is seeded from the REST `GET /notifications` response
  on mount, then the WebSocket becomes the source of truth for incoming notifications. New WS messages
  prepend to the store and increment the unread count. REST is only re-hit on explicit refresh or
  the 60-second safety-net refetch on `unreadCount`.

## Notification Categories and Channels

22 notification categories covering operational events (plant health alerts, inventory thresholds,
sales milestones, AI prediction updates, scheduling, employee actions, etc.). 4 delivery channels:

- **in_app** -- defaults ON
- **email** -- defaults ON
- **sms** -- defaults OFF
- **push** -- defaults OFF

Default state: in_app + email enabled, sms + push disabled, for all 22 categories. Users can
override per-category per-channel.

## Patterns

- **Single WS instance**: one WebSocket per user session, owned by `NotificationCenter`. Not shared
  across components.
- **Store-seeds-from-query**: REST fetch provides initial state; WS provides incremental updates.
  The two sources never conflict because REST is read-once-on-mount and WS is append-only.
- **Optimistic updates**: `markNotificationRead` and `markAllRead` update the store before the
  server confirms, with rollback on failure.
- **Shared UI state**: panel open/close is managed through `useUiStore` (Zustand), not URL state.
  The bell button and the Sheet share this state so the panel can be toggled from either side.

## Known Limitations

- **No conversation thread / list view**: notifications are flat rows, not grouped into conversations
  or threads. There is no notification detail view -- clicking a row marks it read, it does not
  navigate to a detail page.
- **No infinite scroll**: the notification list loads a fixed page. No scroll-to-load-more behavior.
- **No per-row quiet hours in the UI**: quiet hours are global, not per-category. The backend may
  support per-category overrides but the UI does not expose this.
- **Narrow E2E coverage**: WebSocket integration is hard to test in E2E without a real WS server
  running. The 8 unit tests cover store logic and component rendering, not live WS message handling.

## Test Coverage

- **E2E** (1 test): preference save and reload -- verifies that updating notification preferences
  persists across a page reload. Written and reviewed against real components; not execution-verified
  in this sandbox (no Postgres/Docker, same disclosed constraint as all other `e2e/*.spec.ts` files).
- **Vitest/RTL** (8 tests): WebSocket reconnection logic, notification list rendering, mark-read
  optimistic updates, unread count badge, preference grid save, category/channel toggle behavior,
  empty state, error state. All passing against MSW-mocked network responses.
