Change Testplan exported JSON report structure to reduce report size.

* Remove unused report entry fields.
    * ``fix_spec_path`` and ``host``.
    * ``status_override`` and ``status_reason`` in case they are empty.
    * ``line_no``, ``code_context`` and ``file_path`` if ``--code`` is not enabled.
    * ``env_status``, ``part`` and ``strict_order`` depending on report category.
* Remove unused assertion entry fields ``category`` and ``flag`` if they are ``DEFAULT``.
* Merge assertion entry fields ``utc_time`` and ``machine_time`` into a unix timestamp field ``timestamp``, and store timezone info in parent Test-level report under key ``timezone``.
* Replace ISO 8601 time string with unix timestamp in all ``timer`` fields, and add a ``timezone`` field to Testplan-level report as well.
* Update data structure of several serialized assertion entries.
    * Delta encode level info of ``flattened_dict`` fields of ``DictLog`` and ``FixLog`` entries.
    * Delta encode level info of ``comparison`` fields of ``DictMatch`` and ``FixMatch`` entries.
    * Delta encode level info of nested ``comparison`` fields of ``DictMatchAll`` and ``FixMatchAll`` entries, remove extra nesting of ``matches`` as well.
    * Preserve abbreviations of match status of ``DictMatch``, ``FixMatch``, ``DictMatchAll`` and ``FixMatchAll`` entries, i.e. ``p`` instead of ``Passed``, ``f`` instead of ``Failed``, ``i`` instead of ``Ignored``.
    * Remove ``indices`` field of ``TableLog`` entries.
