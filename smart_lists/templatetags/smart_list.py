from django import template
from django.utils.safestring import mark_safe

from smart_lists.helpers import SmartList

register = template.Library()


@register.inclusion_tag("smart_lists/smart_list.html", takes_context=True)
def smart_list(context, object_list=None, page_obj=None, is_paginated=None, paginator=None, query_params=None,
               list_display=None, list_filter=None, list_search=None, search_query_param=None,
               ordering_query_param=None):
    """
    Display the headers and data list together.

    TODO: Do pagination inside here??
    """
    if not object_list:
        object_list = context['object_list']
    if not page_obj:
        page_obj = context.get('page_obj', None)
    if not is_paginated:
        is_paginated = context.get('is_paginated')
    if not paginator:
        paginator = context.get('paginator')

    if query_params is None:  # required
        query_params = context['smart_list_settings']['query_params']
    if list_display is None:  # required
        list_display = context['smart_list_settings']['list_display']
    if list_filter is None:  # optional
        list_filter = context.get('smart_list_settings', {}).get('list_filter', [])
    if list_search is None:
        list_search = context.get('smart_list_settings', {}).get('list_search', [])
    if search_query_param is None:
        search_query_param = context.get('smart_list_settings', {}).get('search_query_param', 'q')
    if ordering_query_param is None:
        ordering_query_param = context.get('smart_list_settings', {}).get('ordering_query_param', 'o')

    smart_list_instance = SmartList(
        object_list,
        query_params=query_params,
        list_display=list_display,
        list_filter=list_filter,
        list_search=list_search,
        search_query_param=search_query_param,
        ordering_query_param=ordering_query_param
    )
    return {'smart_list': smart_list_instance, 'page_obj': page_obj, 'is_paginated': is_paginated, 'paginator': paginator}


@register.filter(name='split')
def split(value, arg):
    return value.split(arg)