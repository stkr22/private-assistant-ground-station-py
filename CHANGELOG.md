# Changelog

## [0.6.0](https://github.com/stkr22/private-assistant-ground-station-py/compare/v0.5.0...v0.6.0) (2026-01-01)


### Features

* :recycle: refactor config to use commons 5.4.0 [AI] ([87dfc4c](https://github.com/stkr22/private-assistant-ground-station-py/commit/87dfc4c422a049ce2d8ab452dfa5690ac6ce0ea1))
* :recycle: refactor config to use commons 5.4.0 [AI] ([c45a304](https://github.com/stkr22/private-assistant-ground-station-py/commit/c45a304903eab9b813ecd748b66c92bba6142c62))
* :sparkles: update MQTT config initialization for improved flexibility ([f5708c4](https://github.com/stkr22/private-assistant-ground-station-py/commit/f5708c4e06024edf8a50c8f65928cd7aa87d9c90))

## [0.5.0](https://github.com/stkr22/private-assistant-ground-station-py/compare/v0.4.0...v0.5.0) (2025-11-23)


### Features

* update Python version to 3.13.9 in Containerfile ([edebb17](https://github.com/stkr22/private-assistant-ground-station-py/commit/edebb17575ce410422fedd046beb8a1797ebf3d3))
* update Python version to 3.13.9 in Containerfile ([2f28147](https://github.com/stkr22/private-assistant-ground-station-py/commit/2f28147151e9c8a85b11700061cd4a2367e3163c))

## [0.4.0](https://github.com/stkr22/private-assistant-ground-station-py/compare/v0.3.2...v0.4.0) (2025-11-15)


### Features

* add remote_broadcast_topic for external notification ([080e104](https://github.com/stkr22/private-assistant-ground-station-py/commit/080e104c16e4174ade90178dfa13f7a7aa6167c8))


### Bug Fixes

* rename put_endpoint_token to text_endpoint_auth_token for clarity ([b96421b](https://github.com/stkr22/private-assistant-ground-station-py/commit/b96421b30fdb5ed6ba7d1307fdeecdd4d3042c7d))

## [0.3.2](https://github.com/stkr22/private-assistant-ground-station-py/compare/v0.3.1...v0.3.2) (2025-11-15)


### Bug Fixes

* :recycle: simplify WebSocket disconnect handling [AI] ([e51f3e4](https://github.com/stkr22/private-assistant-ground-station-py/commit/e51f3e445bf5eb517d4830aa5f13e5d1dff6ff40))

## [0.3.1](https://github.com/stkr22/private-assistant-ground-station-py/compare/v0.3.0...v0.3.1) (2025-11-13)


### Bug Fixes

* 🐛 handle broadcast messages in listen() without dedicated queue ([485a1f9](https://github.com/stkr22/private-assistant-ground-station-py/commit/485a1f9aad2776cdf70541d81e978a9106e19ac6))
* 🐛 handle broadcast messages in listen() without dedicated queue ([3b3e756](https://github.com/stkr22/private-assistant-ground-station-py/commit/3b3e756157dcb540be46b3b331144267bf831ba7))

## [0.3.0](https://github.com/stkr22/private-assistant-ground-station-py/compare/v0.2.1...v0.3.0) (2025-11-13)


### Features

* ✨ add PUT /text endpoint for non-satellite devices ([78a837c](https://github.com/stkr22/private-assistant-ground-station-py/commit/78a837c62ee380f4062815fb75f9f5979f587c82))


### Bug Fixes

* 🔧 update SPDX license identifier to GPL-3.0-only ([3537c80](https://github.com/stkr22/private-assistant-ground-station-py/commit/3537c80a421fb9ae1212422ffb206ea99338f982))

## [0.2.1](https://github.com/stkr22/private-assistant-ground-station-py/compare/v0.2.0...v0.2.1) (2025-10-23)


### Miscellaneous Chores

* update container image and deps ([084bd90](https://github.com/stkr22/private-assistant-ground-station-py/commit/084bd90bd33db46cbbc6d7c66eb986c7c932131b))

## [0.2.0](https://github.com/stkr22/private-assistant-ground-station-py/compare/v0.1.1...v0.2.0) (2025-10-22)


### Features

* :sparkles: close WebSockets when MQTT disconnects [AI] ([99956a8](https://github.com/stkr22/private-assistant-ground-station-py/commit/99956a896199326c1e6f2f885132ec1ad51f18b3))
* :sparkles: close WebSockets when MQTT disconnects [AI] ([747ce47](https://github.com/stkr22/private-assistant-ground-station-py/commit/747ce47b80f2b843886fd331b89b7827bb095f6e))

## [0.1.1](https://github.com/stkr22/private-assistant-ground-station-py/compare/v0.1.0...v0.1.1) (2025-10-21)


### Bug Fixes

* :bug: implement automatic MQTT reconnection [AI] ([0352101](https://github.com/stkr22/private-assistant-ground-station-py/commit/0352101a19e341d9d48cbad9ec86a1bac5fa2c5a)), closes [#5](https://github.com/stkr22/private-assistant-ground-station-py/issues/5)
* implement automatic MQTT reconnection ([0e0372d](https://github.com/stkr22/private-assistant-ground-station-py/commit/0e0372d6e97f5c634aedb1415a4e67b3b156ffa8))

## 0.1.0 (2025-08-20)


### Features

* :sparkles: initial ground station implementation [AI] ([6240ed6](https://github.com/stkr22/private-assistant-ground-station-py/commit/6240ed681c7f300399507620466cef3506d6a5b6))


### Bug Fixes

* :art: resolve linting errors in test files [AI] ([b713956](https://github.com/stkr22/private-assistant-ground-station-py/commit/b7139565ad8665180374ca176917f26bc512d358))
* fixing containerfile asset nonexist ([5a14b3f](https://github.com/stkr22/private-assistant-ground-station-py/commit/5a14b3f7a02971390828ad9670ffa0e68e6eb5fc))
