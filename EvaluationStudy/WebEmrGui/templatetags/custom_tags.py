from django import template
# Py3 fix: cgi.escape() was deprecated in Py3.2 and removed in Py3.8.
# html.escape() is the modern equivalent and exists in every Py3 version
# on the VM (3.6 / 3.8 / 3.11).
import html

register = template.Library()

@register.filter(name='get_json_arr')
def get_json_arr(lab_info, lab):
    # Defensive: return an empty JSON list if the lab is missing so the
    # template can render a placeholder chart instead of 500-ing.
    return lab_info.get(lab, '[[],[],[0,0],[0,0],"",""]')

@register.filter(name='get_fixed_name')
def get_fixed_name(lab_names, lab):
    v = lab_names.get(lab)
    return html.escape(v[0].rstrip()) if v else lab

@register.filter(name='get_fixed_name2')
def get_fixed_name2(lab_names, lab):
    v = lab_names.get(lab)
    return (v[0] + ' - ' + v[1]) if v and len(v) >= 2 else str(lab)

@register.filter(name='get_labnames')
def get_group_members(group_info, group_name):
     # Defensive: unknown group returns an empty list so the template's
     # {% for %} loop simply renders nothing instead of raising KeyError.
     return group_info.get(group_name, [])

@register.filter(name='shorten_name')
def shorten_name(group_name):
    return group_name.replace('istry', '')

@register.filter(name="get_recent_value")
def get_recent_value(recent, lab):
    if lab in recent.keys():
        return recent[lab]
    else:
        return "Never"

@register.filter(name="next_lab")
def next_lab(value, arg):
    try:
        return value[int(arg)+1]
    except:
        return None

@register.filter(name="date_only")
def date_only(full_date):
    try:
        return full_date[0:10]
    except:
        return full_date

@register.filter(name="full_gender")
def full_gender(gender_char):
    if gender_char == 'F':
        return 'female'
    elif gender_char == 'M':
        return 'male'
    else:
        return ''

@register.filter(name='get_meds')
def get_meds(route_mapping, route):
    return route_mapping.get(route, [])

@ register.filter(name='date_line')
def date_line(global_time):
    import datetime
    admit = datetime.datetime.fromtimestamp(global_time['min_t']/1000.0)
    current = datetime.datetime.fromtimestamp(global_time['max_t']/1000.0)
    delta =  current - admit
    return 'Admitted to the ICU on: ' + admit.strftime("%m/%d") + ' | Current date: ' + current.strftime("%m/%d") + ' | Current ICU day: ' + str(delta.days+1)


@ register.filter(name='short_id')
def short_id(long_id):
    return str(long_id)[-3:]