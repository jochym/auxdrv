# Changelog

All notable changes to this project will be documented in this file.

## [1.1.0] - 2026-01-07

### Added
- **Hardware Interaction Test (HIT)**: Interactive safety routine for physical mount testing (`scripts/hit_validation.py`).
- **Photography & Pointing Test (PPT)**: Automated accuracy measurement using INDI and ASTAP (`scripts/ppt_accuracy.py`).
- **Emergency Abort**: Support for `TELESCOPE_ABORT_MOTION` in the driver.
- **Residual-Aware Grid Thinning**: Improved alignment point management using consistency-weighted grid sectors.

### Changed
- Updated `AlignmentModel` to use 15° grid sectors for better sky coverage.
- Optimized functional tests for robustness against encoder jitter.

## [1.0.0] - 2026-01-07

### Added
- **Phase 11: Advanced Calibration** implemented.
- **6-Parameter Geometric Model**: Compenses for Rotation, Cone Error ($CH$), Non-Perpendicularity ($NP$), and Altitude Index error ($ID$).
- **Spatial Point Thinning**: Alignment points within 5 degrees are automatically replaced, ensuring even sky coverage and preventing local "clouds" of data from skewing the global model.
- **Refraction Correction**: Switchable atmospheric refraction correction in the driver logic.
- **Calibration Tab**: New INDI tab displaying measured mechanical errors and residuals.
- **Graceful Fallback**: The alignment system automatically switches between Identity, Axis-Angle, SVD, and Full Geometric models depending on the number of available stars.
- New test suite `tests/test_alignment_advanced.py`.

### Changed
- Refactored `AlignmentModel` to use `scipy.optimize.least_squares` for non-linear fitting.
- Updated `celestron_indi_driver.py` to support new calibration properties.
- Formalized dependencies in `requirements.txt` (`scipy`).

## [0.9.0] - 2026-01-07

### Added
- **Phase 9: Comprehensive Test Documentation**: Added detailed Google-style docstrings to all 23+ tests, documenting methodology and expected results.
- **Phase 10: Simulator Realism**: Added tunable imperfections to the NSE Simulator:
  - **Mechanical Backlash**: Simulates gear play when reversing.
  - **Periodic Error (PE)**: Sinusoidal tracking error in RA/Azimuth.
  - **Cone Error**: Mechanical offset in Altitude axis.
  - **Encoder Jitter**: Random Gaussian noise in position reporting.
- **Simulator Core Test Suite**: Added `tests/test_simulator_core.py` to verify simulator physics and protocol compliance.
- New TUI Panel: Displays active imperfections in the simulator interface.

### Changed
- Improved `config.yaml` to support simulator-specific settings.
- Refactored `NexStarScope` to support simulation of mechanical errors.

## [0.8.0] - 2026-01-07

### Added
- **Phase 8: Multi-Point SVD Alignment** implemented.
- Replaced 3-point matrix inversion with a robust **Singular Value Decomposition (SVD)** solver.
- Support for an **unlimited number of alignment stars** with automatic fit optimization.
- **RMS Error** reporting in INDI (arcseconds residual).
- **Proximity Weighting (Local Bias)**: Heavy weighting of points near the target for high-precision local models.
- **Automatic Pruning**: Configurable circular buffer for alignment points (useful for long AP sessions).
- Comprehensive documentation in `docs/` and `simulator/`.
- New test suite `tests/test_alignment_svd.py`.

### Changed
- Refactored `alignment.py` to use `numpy` for linear algebra.
- Updated `celestron_indi_driver.py` to use the new alignment properties and logic.
- Optimized alignment point management (Clear Last, Clear All).

## [0.7.0] - 2026-01-07

### Added
- **Phase 7: Moving Objects Support** implemented.
- Support for tracking **Sun, Moon, and Planets** using `ephem` library.
- Support for **Satellite tracking** using **TLE** data (`TLE_DATA` property).
- New INDI properties: `TARGET_TYPE`, `PLANET_SELECT`, `TLE_DATA`.
- Implemented `_get_target_equatorial` for dynamic coordinate resolution.
- New test suite `tests/test_moving_objects.py` verifying non-sidereal tracking.

### Changed
- **Simulator Calibration**: Adjusted slew speeds to match **Celestron Evolution** ($4^\circ/s$ Fast, $1^\circ/s$ Slow).
- **Test Optimization**: Updated functional tests to use realistic speeds and longer timeouts.

## [0.6.1] - 2026-01-06

### Fixed
- Fixed **Altitude wrap-around bug** in simulator where negative altitudes were reported as large positive values (e.g., 337.5° instead of -22.5°).
- Treated Altitude as a **linear axis** instead of a full circle to avoid incorrect movement directions in GoTo.
- Added support for **signed angle representation** in simulator TUI for Altitude.
- Normalized incoming motor controller coordinates to handle signed values correctly in driver logic.
- All 17 automated tests (Functional, Safety, Math) verified passing.

## [0.6.0] - 2026-01-06

### Added
- **Phase 6: Safety & Accessories** implemented.
- New INDI properties: `TELESCOPE_LIMITS`, `TELESCOPE_CORDWRAP`, `TELESCOPE_CORDWRAP_POS`.
- Support for **Focuser** accessory (`ABS_FOCUS_POSITION`).
- Support for **GPS** module (`GPS_REFRESH`, automatic location sync).
- New test suite `tests/test_safety.py` for safety features.
- Enforced software slew limits in `goto_position` and background monitoring.

### Changed
- **Internationalization**: All documentation, comments, and UI strings translated to **English**.
- Increased simulator slew rates: `GOTO_FAST` at 15 deg/s, `GOTO_SLOW` at 0.5 deg/s.
- Improved AUX command logging in simulator TUI.
- Fixed latitude/longitude parsing from GPS module.

## [0.5.3] - 2026-01-06

### Added
- New functional test `test_6b_robustness_pole` checking driver stability near the celestial pole.

### Fixed
- Increased GoTo speeds in simulator (Fast: 5°/s, Slow: 1°/s) and extended timeouts in the driver, eliminating timeout errors in tests.
- Improved physical motion model in simulator (smoother braking and no oscillations at target).
- Secured mathematical functions against precision errors near singularities (poles, zenith).

## [0.5.2] - 2026-01-06

### Added
- Debug mode (`-d` / `--debug`) in simulator, reporting operation parameters to `stderr`.
- Implementation of a sliding window for sky velocity calculations (vRA, vDec) to eliminate numerical noise.

### Fixed
- Fixed oscillations of displayed vRA/vDec speeds in the TUI interface.
- Improved velocity calculation stability in headless mode.

## [0.5.1] - 2026-01-06

### Added
- Extension of the simulator TUI interface with motor rotation speed display (vAlt, vAzm) in °/s.
- Display of celestial sphere movement speeds (vRA, vDec) in "/s (arcsec/s).
- Improved styling of the Textual interface.

## [0.5.0] - 2026-01-05

### Added
- Modern simulator TUI interface based on the **Textual** library (replacing curses).
- Advanced **Alignment system** based on 3x3 matrix transformations.
- Support for `TELESCOPE_ON_COORD_SET` property (SLEW, TRACK, SYNC modes).
- Ability to add alignment points (max 3 stars) to correct mount alignment errors.
- New test suite: `test_10_alignment_3star` and alignment math tests (`tests/test_alignment_math.py`).
- Support for `EXTERNAL_SIM` environment variable in functional tests.

### Changed
- Full code documentation (Google Style Docstrings) for all modules.
- Removed deprecated function call warnings (`utcnow`, `get_event_loop`).
- Improved `Park` logic – handling step counter wrap-around.
- Changed configuration format to YAML (`config.yaml`).

## [0.4.0] - 2026-01-05

### Added
- Implementation of **Anti-backlash GoTo** approach logic (Phase 4).
- New INDI properties: `GOTO_APPROACH_MODE` (DISABLED, FIXED_OFFSET, TRACKING_DIRECTION) and `GOTO_APPROACH_OFFSET`.
- Advanced tracking loop based on **2nd order prediction** (Phase 5).
- Angular velocity ($\omega$) determination algorithm using symmetric differential expression.
- New INDI properties: `TELESCOPE_TRACK_MODE` (Sidereal, Solar, Lunar).
- Communication locking mechanism (`asyncio.Lock`) in `AUXCommunicator` to ensure safe concurrent access to the AUX bus.
- New functional tests: `test_7_approach_logic`, `test_8_approach_tracking_direction`, `test_9_predictive_tracking`.

### Changed
- Refactored GoTo method to support multi-stage movement (Stage 1: Fast Approach, Stage 2: Slow Final).
- `equatorial_to_steps` method now supports `time_offset` parameter.

## [0.3.0] - 2026-01-05

### Added
- Integration with `ephem` library for astronomical coordinate transformations.
- Support for INDI property `GEOGRAPHIC_COORD` (Latitude, Longitude, Elevation).
- Support for INDI property `EQUATORIAL_EOD_COORD` (RA/Dec).
- Implementation of GoTo logic for equatorial coordinates (RA/Dec -> Alt/Az -> Encoders).
- Automatic calculation and reporting of current RA/Dec based on encoder position.
- New functional test `test_6_equatorial_goto` verifying transformation correctness.
- Configuration file `config.yaml` support with default location in Bębło.
- Stellarium integration instructions for visual verification.

### Changed
- Improved `handle_equatorial_goto` robustness against missing event data.

## [0.2.1] - 2026-01-05

### Added
- Complete set of functional tests in `tests/` directory based on `unittest`.
- Tests cover: Firmware Info, GoTo Precision, Tracking Logic, Park/Unpark, Connection Robustness.
- Automatic capture of simulator logs during tests (`test_sim.log`).

### Changed
- Improved robustness of `handle_sync`, `handle_park`, `handle_unpark`, `handle_guide_rate` methods against missing event data (facilitates testing).
- Synchronized project state and roadmap.

## [0.2.0] - 2026-01-05

### Added
- TCP connection support in `AUXCommunicator` (URL `socket://host:port`).
- "Echo Skipping" mechanism in the AUX protocol, enabling operation on single-wire buses.
- Headless mode (`-t` / `--text`) in the telescope simulator.
- `ephem` library support in the simulator.
- Implementation of `TELESCOPE_GUIDE_RATE` property in the INDI driver.
- Verified control loop operation (Slew/Read/Tracking) with an extended automated test.

### Changed
- Full refactoring of `celestron_indi_driver.py` to adapt to `indipydriver 3.0.4` API.
- Fixed `NumberMember` constructor errors (argument order).
- Improved AUX frame reading stability (using `readexactly`).
- Removed erroneous null bytes from source files.

## [0.1.0] - 2026-01-05

### Added
- Initial implementation of the Celestron AUX driver in Python.
- Basic INDI properties: `CONNECTION`, `PORT`, `FIRMWARE_INFO`, `MOUNT_POSITION`.
- Motion control: `SLEW_RATE`, `TELESCOPE_MOTION_NS/WE`, `TELESCOPE_ABSOLUTE_COORD`.
- Mount synchronization and parking.
- Telescope simulator with TUI (curses) interface.
- Implementation of binary AUX protocol (packet packing/unpacking, checksums).
