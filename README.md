# Creality Cloud for Home Assistant

Custom Home Assistant integration that exposes the account, rewards and printers managed by the [CC Tools add-on](https://github.com/TitoTB/CC-Tools-HA).

This integration does not connect directly to Creality Cloud and does not replace CC Tools. Scheduling, favorite profiles, G-code selection and other advanced settings remain in CC Tools.

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
- Latest shop order status and details.
- Printer status, daily count, last/next print and last G-code.
- A scheduled-prints switch on each printer device.

## Support

Questions, suggestions and support are available in the [Aguacatec Telegram community](https://t.me/aguacatec_es/13374).

## Disclaimer

**Creality Cloud for Home Assistant and CC Tools are not official applications** and are not affiliated with Creality or Creality Cloud. They are community projects developed by Aguacatec to improve the 3D-printing experience and its integration with home automation.

The goal is not to violate or circumvent Creality Cloud rules. Use these tools at your own risk and always comply with the platform rules.

## License

[MIT](LICENSE)
