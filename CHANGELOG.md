# Changelog

## 1.0.3

- Adds an opt-in Automatic restart switch for recovering a stalled CC Tools add-on.
- Detects two consecutive missed schedule slots while respecting replanning and later successful executions.
- Recovers scheduler operations that remain stale for 30 minutes.
- Adds restart cooldown, daily limit and stabilization protections without creating Home Assistant notifications.

## 1.0.2

- Moves print sensors and the scheduled-prints switch to each printer device.
- Renames the printer switch to Scheduled prints.
- Removes the manual Send next print button.

## 1.0.1

- Adds a latest order sensor with the current status and useful order attributes.
- Removes redundant automation, browser, scheduler and per-task entities.
- Keeps the available boosts sensor and the print-related controls and entities.

## 1.0.0

- Initial HACS release.
- Adds account, points, rewards, task and order entities.
- Adds one Home Assistant device per configured printer.
- Adds task switches, manual action buttons and Home Assistant events.
- Includes English and Spanish translations.
