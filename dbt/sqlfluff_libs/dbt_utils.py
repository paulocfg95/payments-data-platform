"""Lint-only stand-ins for dbt_utils macros.

sqlfluff renders the dbt SQL with plain Jinja, without dbt. These functions
return simple valid SQL so the models can be linted. They are never used
by dbt itself.
"""


def generate_surrogate_key(field_list):
    return "md5(" + " || ".join(field_list) + ")"


def date_spine(datepart, start_date, end_date):
    return f"select generate_series({start_date}, {end_date}, interval '1 day') as date_day"
