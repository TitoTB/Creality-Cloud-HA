# Creality Cloud for Home Assistant

Custom Home Assistant integration that exposes the account, rewards, scheduled tasks and printers managed by the **CC Tools** add-on.

## Requirements

- Home Assistant 2026.3 or newer.
- The [CC Tools add-on](https://github.com/TitoTB/CC-Tools-HA) version 1.0.9 or newer, configured and signed in to Creality Cloud.
- Home Assistant must be able to reach the add-on HTTP endpoint.

This integration does not connect directly to Creality Cloud and does not replace CC Tools. Scheduling, favorite profiles, comments, G-code selection and other advanced settings remain in CC Tools.

## Installation with HACS

1. Open HACS in Home Assistant.
2. Go to **Integrations** and open the custom repositories menu.
3. Add `https://github.com/TitoTB/Creality-Cloud-HA` as an **Integration** repository.
4. Install **Creality Cloud**.
5. Restart Home Assistant.
6. Open **Settings > Devices & services > Add integration** and search for **Creality Cloud**.

The setup flow first tries to detect the CC Tools add-on automatically. If it cannot be reached using its internal add-on address, enter the URL shown by CC Tools, for example `http://192.168.1.44:8080`.

## Devices and entities

The main device uses the name of the signed-in Creality Cloud profile. Each printer configured in CC Tools is represented as a separate device.

The integration provides:

- Total points and points earned today.
- Lottery tickets and available boosts.
- Daily print counter and last/next print execution.
- A switch for enabling or disabling scheduled prints.
- A collection run button, a scheduling switch, and sensors for credited collections today, last run and next run.
- Printer status, daily count, last/next print, last G-code and a button to send the next configured print.

## Collections

Collection entities require CC Tools 1.0.11 or newer with the `collections` API ([companion pull request](https://github.com/TitoTB/CC-Tools-HA/pull/1)). They remain unavailable on older add-ons and become available after the add-on is updated and the next successful refresh completes.

The collection switch controls scheduling; enabling it requires **Discover designs** to be enabled in CC Tools. The button requests one manual run. CC Tools selects the model, saves it to Default Collections and verifies the daily reward. Scheduling windows remain configured in CC Tools.

Collection results use the existing `creality_cloud_task_completed` and `creality_cloud_task_failed` events with `task: collections`. A skipped run does not emit a completion event.

## Events

The integration fires these events on the Home Assistant event bus:

- `creality_cloud_task_completed` when a task completes.
- `creality_cloud_task_failed` when a task fails.
- `creality_cloud_order_shipped` when an order changes to shipped.
- `creality_cloud_shop_goal_redeemed` when a scheduled points redemption completes.

The event payload includes `type`, `task`, `status`, `source`, `message`, `occurredAt` and information about the related design, order, product or G-code when available.

## Support

Questions, suggestions and support are available in the [Aguacatec Telegram community](https://t.me/aguacatec_es/13374).

## Disclaimer

**Creality Cloud for Home Assistant and CC Tools are not official applications** and are not affiliated with Creality or Creality Cloud. They are community projects developed by Aguacatec to improve the 3D-printing experience and its integration with home automation.

The goal is not to violate or circumvent Creality Cloud rules. Use these tools at your own risk and always comply with the platform rules.

## License

[MIT](LICENSE)
