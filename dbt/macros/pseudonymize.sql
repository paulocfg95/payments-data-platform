{#
    Pseudonymize a personal data value (LGPD): SHA-256 of salt + value, in hex.

    The salt is read from the PostgreSQL session setting
    app.pseudonymization_salt, set by run_dbt.sh from an environment variable.
    It is never written in the SQL code. If the setting is missing, the query
    fails, so we never write unsalted hashes.
#}
{% macro pseudonymize(expression) -%}
    encode(
        sha256(convert_to(current_setting('app.pseudonymization_salt') || ({{ expression }}), 'UTF8')),
        'hex'
    )
{%- endmacro %}
