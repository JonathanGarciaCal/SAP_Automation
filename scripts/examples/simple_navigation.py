"""Simple SAP Transaction Navigation.

This script navigates to transaction VA01 (Create Sales Order).
Converted from VBScript - demonstrates basic property and method usage.
"""

# PARAM: transaction_code:string:true:SAP transaction code to navigate to (e.g., VA01)

# Navigate to SAP transaction
session.find_by_id("wnd[0]/tbar[0]/okcd").value = transaction_code
session.find_by_id("wnd[0]").send_vkey(0)

# Wait for screen to load (in real execution, this would be handled by COM timeout)
result = "Navigation successful"
