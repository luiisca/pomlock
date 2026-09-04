# Changelog

## [4.0.0](https://github.com/luiisca/pomlock/compare/v3.0.0...v4.0.0) (2026-09-04)


### ⚠ BREAKING CHANGES

* complete configuration parsing rehaul

### Features

* add activity goals section in main page + replace history.csv with local sqlite db ([dd18a57](https://github.com/luiisca/pomlock/commit/dd18a577e796aa5f61aa74e82e857681074b3f73))
* add gap-aware streak counting and tests ([c9fa2f9](https://github.com/luiisca/pomlock/commit/c9fa2f921275f253bee0d805adcd5c9063122262))
* add settings page ([9f62a74](https://github.com/luiisca/pomlock/commit/9f62a7424648c31dc0a6263794296f963d9c964f))
* add streak indicator style setting and configurable streak UI ([4385d7f](https://github.com/luiisca/pomlock/commit/4385d7fa424bee38d0cf83b09d06ee63ba0eace0))
* add streak widget enhancements, new tests, and changelog ([1e8f92a](https://github.com/luiisca/pomlock/commit/1e8f92a03b9ac2f77aee0ba5b7ec4903f9faeb0f))
* implement settings page improvements including activity deletion, color customization, olive garden palette, and manual goal entry ([c702acc](https://github.com/luiisca/pomlock/commit/c702accde6089b9e9406372c6873e0ceabe6d7ba))


### Code Refactoring

* complete configuration parsing rehaul ([a070af1](https://github.com/luiisca/pomlock/commit/a070af10854bea0cde70396959f39eccd2eafdfa))

## [3.0.0](https://github.com/luiisca/pomlock/compare/v2.1.0...v3.0.0) (2026-08-29)


### ⚠ BREAKING CHANGES

* migrate from rich library to textual framework + improve tk window rendering
* add prettier, more functional logging with rich library

### Features

* add activity flag + update log formatting to include activity name ([2d1f362](https://github.com/luiisca/pomlock/commit/2d1f362704c8de1f76c685a5ea9a9501ee3c6351))
* Add callback and polling support for external scripts ([4cb8ac0](https://github.com/luiisca/pomlock/commit/4cb8ac096e9440d4cd13275b57cf5bb59d04132e))
* add linux device grabbing and compositor fallbacks ([#19](https://github.com/luiisca/pomlock/issues/19)) ([ab9fdda](https://github.com/luiisca/pomlock/commit/ab9fddae7c4880e8a73715977e13b28ba4ca85d7))
* add prettier, more functional logging with rich library ([e169f12](https://github.com/luiisca/pomlock/commit/e169f12ea2f74b139023a49e120d06f424d1a5c7))
* add show-activites flag ([a6d297c](https://github.com/luiisca/pomlock/commit/a6d297c0424969c2d23b3e8e4ca2e638a2107599))
* add wayland support for unpriviliged input blocking ([7339645](https://github.com/luiisca/pomlock/commit/73396457295aa941967b5bedc9151192793045fa))
* Core Pomlock system ([eaea7c0](https://github.com/luiisca/pomlock/commit/eaea7c0190597959772c1201ca546566c1ce789a))
* use minutes instead of seconds ([4521ee9](https://github.com/luiisca/pomlock/commit/4521ee9c1f8339901f6557968279669244169594))


### Bug Fixes

* executable failing with moduel not found errors ([4f7ed72](https://github.com/luiisca/pomlock/commit/4f7ed72fceee8a58375a8ae3514c97fa3650251a))
* formatting, better comments ([3fd5adf](https://github.com/luiisca/pomlock/commit/3fd5adf0d80e40296b72307c1709266aa8bb74fd))
* move some logs to debug level ([c571e7f](https://github.com/luiisca/pomlock/commit/c571e7f0d06db458a818432880bc9890d96e84f7))
* older incompatible python version causes xcb error ([37f2264](https://github.com/luiisca/pomlock/commit/37f226405df2cc889ee88497267b4c5f2b4001f4))
* overlay does not go fullscreen on wayland ([550c477](https://github.com/luiisca/pomlock/commit/550c477673f03809b229df7a83aae330bf8aebc2))
* remove debug print calls ([dae6860](https://github.com/luiisca/pomlock/commit/dae6860d62112c37fa3f1bfe1aff21bced5374b5))
* session progress bar resets after every cycle ([93bf413](https://github.com/luiisca/pomlock/commit/93bf413a34ddab5fbcc507262e8d365928494cb6))
* **xinput:** improve device detection and error handling ([7897b53](https://github.com/luiisca/pomlock/commit/7897b537a1ed554b5b877010fca529d34eaf42ad))


### Documentation

* update readme ([4bf4dda](https://github.com/luiisca/pomlock/commit/4bf4dda43e9a56c75536aea29119de568fd8ddfa))
* update readme ([631615f](https://github.com/luiisca/pomlock/commit/631615f622355c0f3b3d8bed2cd38f9d3f649cb4))
* update README to reflect Python-only implementation ([db3c27c](https://github.com/luiisca/pomlock/commit/db3c27c3103917b1445868a4e3c61a7c6577f39d))


### Code Refactoring

* migrate from rich library to textual framework + improve tk window rendering ([45f863c](https://github.com/luiisca/pomlock/commit/45f863c121492cfe42728ab4126b1d3376fd4105))

## [2.1.0](https://github.com/luiisca/pomlock/compare/v2.0.0...v2.1.0) (2026-08-26)


### Features

* add activity flag + update log formatting to include activity name ([2d1f362](https://github.com/luiisca/pomlock/commit/2d1f362704c8de1f76c685a5ea9a9501ee3c6351))
* add show-activites flag ([a6d297c](https://github.com/luiisca/pomlock/commit/a6d297c0424969c2d23b3e8e4ca2e638a2107599))


### Bug Fixes

* older incompatible python version causes xcb error ([37f2264](https://github.com/luiisca/pomlock/commit/37f226405df2cc889ee88497267b4c5f2b4001f4))

## [2.0.0](https://github.com/luiisca/pomlock/compare/v1.2.2...v2.0.0) (2025-09-01)


### ⚠ BREAKING CHANGES

* add prettier, more functional logging with rich library

### Features

* Add callback and polling support for external scripts ([4cb8ac0](https://github.com/luiisca/pomlock/commit/4cb8ac096e9440d4cd13275b57cf5bb59d04132e))
* add prettier, more functional logging with rich library ([e169f12](https://github.com/luiisca/pomlock/commit/e169f12ea2f74b139023a49e120d06f424d1a5c7))
* add wayland support for unpriviliged input blocking ([7339645](https://github.com/luiisca/pomlock/commit/73396457295aa941967b5bedc9151192793045fa))


### Bug Fixes

* executable failing with moduel not found errors ([4f7ed72](https://github.com/luiisca/pomlock/commit/4f7ed72fceee8a58375a8ae3514c97fa3650251a))
* overlay does not go fullscreen on wayland ([550c477](https://github.com/luiisca/pomlock/commit/550c477673f03809b229df7a83aae330bf8aebc2))
* session progress bar resets after every cycle ([93bf413](https://github.com/luiisca/pomlock/commit/93bf413a34ddab5fbcc507262e8d365928494cb6))

## [1.2.2](https://github.com/luiisca/pomlock/compare/v1.2.1...v1.2.2) (2025-08-10)


### Bug Fixes

* remove debug print calls ([dae6860](https://github.com/luiisca/pomlock/commit/dae6860d62112c37fa3f1bfe1aff21bced5374b5))

## [1.2.1](https://github.com/luiisca/pomlock/compare/v1.2.0...v1.2.1) (2025-08-10)


### Bug Fixes

* formatting, better comments ([3fd5adf](https://github.com/luiisca/pomlock/commit/3fd5adf0d80e40296b72307c1709266aa8bb74fd))
* **xinput:** improve device detection and error handling ([7897b53](https://github.com/luiisca/pomlock/commit/7897b537a1ed554b5b877010fca529d34eaf42ad))

## [1.2.0](https://github.com/luiisca/pomlock/compare/v1.1.0...v1.2.0) (2025-06-28)


### Features

* use minutes instead of seconds ([4521ee9](https://github.com/luiisca/pomlock/commit/4521ee9c1f8339901f6557968279669244169594))


### Bug Fixes

* move some logs to debug level ([c571e7f](https://github.com/luiisca/pomlock/commit/c571e7f0d06db458a818432880bc9890d96e84f7))

## [1.1.0](https://github.com/luiisca/pomlock/compare/v1.0.0...v1.1.0) (2025-03-10)


### Features

* Core Pomlock system ([eaea7c0](https://github.com/luiisca/pomlock/commit/eaea7c0190597959772c1201ca546566c1ce789a))
