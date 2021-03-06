import datetime

from django.core.exceptions import FieldDoesNotExist
from django.db.models import Field, BooleanField, ForeignKey
from django.utils.formats import localize
from django.utils.html import format_html
from django.utils.http import urlencode

from smart_lists.exceptions import SmartListException
from django.utils.translation import gettext_lazy as _

from smart_lists.filters import SmartListFilter


class TitleFromModelFieldMixin(object):
    def get_title(self):
        if self.model_field:
            return self.model_field.verbose_name.title()
        elif self.field_name == '__str__':
            return self.model._meta.verbose_name.title()
        try:
            field = getattr(self.model, self.field_name)
        except AttributeError as e:
            return self.field_name.title()
        if callable(field) and getattr(field, 'short_description', False):
            return field.short_description
        return self.field_name.replace("_", " ").title()


class QueryParamsMixin(object):
    def get_url_with_query_params(self, new_query_dict):
        query = dict(self.query_params).copy()
        for key, value in query.items():
            if type(value) == list:
                query[key] = value[0]
        query.update(new_query_dict)
        for key, value in query.copy().items():
            if value is None:
                del query[key]
        return '?{}'.format(urlencode(query))


class SmartListField(object):
    def __init__(self, smart_list_item, column, object):
        self.smart_list_item = smart_list_item
        self.column = column
        self.object = object

    def get_value(self):
        if type(self.object) == dict:
            return self.object.get(self.column.field_name)
        field = getattr(self.object, self.column.field_name)
        if callable(field):
            if getattr(field, 'do_not_call_in_templates', False):
                return field
            else:
                return field()
        else:
            display_function = getattr(self.object, 'get_%s_display' % self.column.field_name, False)
            if display_function:
                return display_function()
            return field

    def format(self, value):
        if isinstance(value, datetime.datetime) or isinstance(value, datetime.date):
            return localize(value)
        return value

    def render(self):
        return format_html(
            '<td>{}</td>', self.format(self.get_value())
        )

    def render_link(self):
        if not hasattr(self.object, 'get_absolute_url'):
            raise SmartListException("Please make sure your model {} implements get_absolute_url()".format(type(self.object)))
        return format_html(
            '<td><a href="{}">{}</a></td>', self.object.get_absolute_url(), self.format(self.get_value())
        )


class SmartListItem(object):
    def __init__(self, smart_list, object):
        self.smart_list = smart_list
        self.object = object

    def fields(self):
        return [
            SmartListField(self, column, self.object) for column in self.smart_list.columns
        ]


class SmartOrder(QueryParamsMixin, object):
    def __init__(self, query_params, column_id, ordering_query_param):
        self.query_params = query_params
        self.column_id = column_id
        self.ordering_query_param = ordering_query_param
        self.query_order = query_params.get(ordering_query_param)
        self.current_columns = [int(col) for col in self.query_order.replace("-", "").split(".")] if self.query_order else []
        self.current_columns_length = len(self.current_columns)

    @property
    def priority(self):
        if self.is_ordered():
            return self.current_columns.index(self.column_id) + 1

    def is_ordered(self):
        return self.column_id in self.current_columns

    def is_reverse(self):
        for column in self.query_order.split('.'):
            c = column.replace("-", "")
            if int(c) == self.column_id:
                if column.startswith("-"):
                    return True
        return False

    def get_add_sort_by(self):
        if not self.is_ordered():
            if self.query_order:
                return self.get_url_with_query_params({
                    self.ordering_query_param: '{}.{}'.format(self.column_id, self.query_order)
                })
            else:
                return self.get_url_with_query_params({
                    self.ordering_query_param: self.column_id
                })
        elif self.current_columns_length > 1:
            new_query = []
            for column in self.query_order.split('.'):
                c = column.replace("-", "")
                if not int(c) == self.column_id:
                    new_query.append(column)
            if not self.is_reverse() and self.current_columns[0] == self.column_id:
                return self.get_url_with_query_params({
                    self.ordering_query_param: '-{}.{}'.format(self.column_id, ".".join(new_query))
                })
            else:
                return self.get_url_with_query_params({
                    self.ordering_query_param: '{}.{}'.format(self.column_id, ".".join(new_query))
                })

        else:
            return self.get_reverse_sort_by()

    def get_remove_sort_by(self):
        new_query = []
        for column in self.query_order.split('.'):
            c = column.replace("-", "")
            if not int(c) == self.column_id:
                new_query.append(column)
        return self.get_url_with_query_params({
            self.ordering_query_param: ".".join(new_query)
        })

    def get_reverse_sort_by(self):
        new_query = []
        for column in self.query_order.split('.'):
            c = column.replace("-", "")
            if int(c) == self.column_id:
                if column.startswith("-"):
                    new_query.append(c)
                else:
                    new_query.append('-{}'.format(c))
            else:
                new_query.append(column)

        return self.get_url_with_query_params({
            self.ordering_query_param: ".".join(new_query)
        })


class SmartColumn(TitleFromModelFieldMixin, object):
    def __init__(self, model, field, column_id, query_params, ordering_query_param):
        self.model = model
        self.field_name = field

        self.order_field = None
        if self.field_name.startswith("_") and self.field_name != "__str__":
            raise SmartListException("Cannot use underscore(_) variables/functions in smart lists")
        try:
            self.model_field = self.model._meta.get_field(self.field_name)
            self.order_field = self.field_name
        except FieldDoesNotExist:
            self.model_field = None
            try:
                field = getattr(self.model, self.field_name)
                if callable(field) and getattr(field, 'admin_order_field', False):
                    self.order_field = getattr(field, 'admin_order_field')
                if callable(field) and getattr(field, 'alters_data', False):
                    raise SmartListException("Cannot use a function that alters data in smart list")
            except AttributeError:
                self.order_field = self.field_name
                pass  # This is most likely a .values() query set

        if self.order_field:
            self.order = SmartOrder(query_params=query_params, column_id=column_id, ordering_query_param=ordering_query_param)
        else:
            self.order = None


class SmartFilterValue(QueryParamsMixin, object):
    def __init__(self, field_name, label, value, query_params):
        self.field_name = field_name
        self.label = label
        self.value = value
        self.query_params = query_params

    def get_title(self):
        return self.label

    def get_url(self):
        return self.get_url_with_query_params({
            self.field_name: self.value
        })

    def is_active(self):
        if self.field_name in self.query_params:
            selected_value = self.query_params[self.field_name]
            if type(selected_value) == list:
                selected_value = selected_value[0]
            if selected_value == self.value:
                return True
        elif self.value is None:
            return True
        return False


class SmartFilter(TitleFromModelFieldMixin, object):
    def __init__(self, model, field, query_params, object_list):
        self.model = model

        # self.model_field = None
        if isinstance(field, SmartListFilter):
            self.field_name = field.parameter_name
            self.model_field = field
        else:
            self.field_name = field
            self.model_field = self.model._meta.get_field(self.field_name)
        self.query_params = query_params
        self.object_list = object_list

    def get_title(self):
        if isinstance(self.model_field, SmartListFilter):
            return self.model_field.title
        return super(SmartFilter, self).get_title()

    def get_values(self):
        values = []
        if isinstance(self.model_field, SmartListFilter):
            values = [
                SmartFilterValue(self.model_field.parameter_name, choice[1], choice[0], self.query_params) for choice in self.model_field.lookups()
            ]
        elif self.model_field.choices:
            values = [
                SmartFilterValue(self.field_name, choice[1], choice[0], self.query_params) for choice in self.model_field.choices
            ]
        elif type(self.model_field) == BooleanField:
            values = [
                SmartFilterValue(self.field_name, choice[1], choice[0], self.query_params) for choice in (
                    (1, _('Yes')),
                    (0, _('No'))
                )
            ]
        elif issubclass(type(self.model_field), ForeignKey):
            pks = self.object_list.order_by().distinct().values_list('%s__pk' % self.field_name, flat=True)
            qs = self.model_field.rel.model.objects.filter(pk__in=pks)
            values = [
                SmartFilterValue(self.field_name, obj, str(obj.pk), self.query_params) for obj in qs
            ]

        return [SmartFilterValue(self.field_name, _("All"), None, self.query_params)] + values



class SmartList(object):
    def __init__(self, object_list, query_params=None, list_display=None, list_filter=None,
                 list_search=None, search_query_param=None, ordering_query_param=None):
        self.object_list = object_list
        self.model = object_list.model
        self.query_params = query_params or {}
        self.list_display = list_display or []
        self.list_filter = list_filter or []
        self.list_search = list_search or []
        self.search_query_value = self.query_params.get(search_query_param, '')
        self.search_query_param = search_query_param
        self.ordering_query_value = self.query_params.get(ordering_query_param, '')
        self.ordering_query_param = ordering_query_param
        self.columns = [
            SmartColumn(self.model, field, i, self.query_params, self.ordering_query_param) for i, field in enumerate(self.list_display, start=1)
        ] or [SmartColumn(self.model, '__str__', 1, self.ordering_query_value, self.ordering_query_param)]
        self.filters = [
            SmartFilter(self.model, field, self.query_params, self.object_list) for i, field in enumerate(self.list_filter, start=1)
        ] if self.list_filter else []


    @property
    def items(self):
        return [
            SmartListItem(self, obj) for obj in self.object_list
        ]
