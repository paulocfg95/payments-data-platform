{#
    Generic test: fails for every row where the column is zero or negative.
    Null values are ignored (use not_null for them).
#}
{% test positive_value(model, column_name) %}

select {{ column_name }}
from {{ model }}
where {{ column_name }} <= 0

{% endtest %}
