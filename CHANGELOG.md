# CHANGELOG

## [v1.6] - 2023.10.17

### Fixed

* Handle exceptions caused by server responding anomalies.

## [v1.5] - 2023.10.14

### Fixed

* Fix crashes by changing a specific "post" into "get".

## [v1.4] - 2023.10.10

### Fixed

* Fix a dumb typo which crashes the whole session when retriving captcha.

## [v1.3] - 2023.09.19

### Fixed

* Fix login issues caused by SEU's next-era SSO.

## [v1.2] - 2023.02.28

### Fixed

* Fix issues caused by providing empty username and password in `config.json`.

## [v1.1] - 2023.02.28

### Features

* Add ban-lifting logic when the script send requests too rapidly.
* Add more log output.

### Fixed

* Fix exception-handling issue: The script can now exit properly.
