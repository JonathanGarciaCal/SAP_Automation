' Simple SAP Transaction Navigation
session.FindById("wnd[0]/tbar[0]/okcd").Text = "/nVA01"
session.FindById("wnd[0]").SendVKey(0)
result = "Navigation successful"
