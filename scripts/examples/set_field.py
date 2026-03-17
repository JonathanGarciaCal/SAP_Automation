"""Set Field Value in SAP UI.

Generic script to set a value in a SAP field by UI ID.
Demonstrates parameter binding and dynamic field access.
"""

# PARAM: field_id:string:true:SAP UI element ID (e.g., wnd[0]/usr/ctxtVBELN)
# PARAM: field_value:string:true:Value to set in the field

# Set the field value
element = session.find_by_id(field_id)
element.value = field_value

result = f"Set {field_id} = {field_value}"
